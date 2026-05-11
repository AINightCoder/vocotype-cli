"""L3 端到端测试：跑真实 `main.py transcribe` 子命令，对比 hotword= 空 vs 非空 的输出。

需要外部依赖：
- 联网（首次跑 FunASR 热词场景会下载 ~50-70MB 的 ContextualParaformer 模型）
- 测试音频在 res/test/test1.mp3
- Volcengine 场景额外需要 env VOLC_APP_KEY + VOLC_ACCESS_KEY

不在 unittest discover 范围内：手动跑 `python test/test_e2e_real_audio.py [--scenarios <list>]`。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
MAIN_PY = PROJECT_ROOT / "main.py"
AUDIO = PROJECT_ROOT / "res" / "test" / "test1.mp3"


def _write_config(work_dir: Path, name: str, config: dict) -> Path:
    """把 config dict 写到 work_dir/name.json 并返回路径。"""
    p = work_dir / f"{name}.json"
    p.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _run_transcribe(config_path: Optional[Path], out_path: Path) -> tuple[int, str, str]:
    cmd = [str(PYTHON), str(MAIN_PY), "transcribe", str(AUDIO), "-o", str(out_path)]
    if config_path is not None:
        cmd += ["--config", str(config_path)]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    return proc.returncode, proc.stdout, proc.stderr


def _read_output(out_path: Path) -> str:
    if not out_path.exists():
        return "<NO OUTPUT FILE>"
    return out_path.read_text(encoding="utf-8").strip()


# ---------- 场景 ----------


def scenario_replacements(work_dir: Path) -> bool:
    """场景 1：仅替换词典。不下载新模型、最轻量。"""
    print("\n" + "=" * 60)
    print("SCENARIO 1: replacements only (no model download)")
    print("=" * 60)

    cfg = _write_config(work_dir, "replace", {
        "backend": "funasr",
        "replacements": [
            {"from": "英雄", "to": "<HERO>"},
            {"from": "升级", "to": "升 级"},
        ],
    })
    out = work_dir / "replace.txt"
    rc, _stdout, stderr = _run_transcribe(cfg, out)
    text = _read_output(out)
    print(f"exit code   : {rc}")
    print(f"transcribed : {text}")

    ok = rc == 0 and "<HERO>" in text and "升 级" in text
    print(f"verdict     : {'PASS' if ok else 'FAIL'}  (期望含 <HERO> 与 '升 级')")
    if not ok and stderr:
        print(f"stderr (tail):\n{stderr[-500:]}")
    return ok


def scenario_funasr_hotword(work_dir: Path) -> bool:
    """场景 2：FunASR 后端 + 热词。首次跑会下载 ContextualParaformer 模型。"""
    print("\n" + "=" * 60)
    print("SCENARIO 2: FunASR + hotword (will download ContextualParaformer ~50-70MB)")
    print("=" * 60)

    # baseline：默认配置（基础 Paraformer，无热词）
    print("\n[baseline] 默认配置（基础 Paraformer，无热词）...")
    baseline_out = work_dir / "funasr_baseline.txt"
    rc1, _, stderr1 = _run_transcribe(None, baseline_out)
    baseline_text = _read_output(baseline_out)
    print(f"  exit: {rc1} | text: {baseline_text}")

    # with hotword
    print("\n[hotword] 配置 asr.hotword='英雄 升级'（切换 ContextualParaformer）...")
    cfg = _write_config(work_dir, "funasr_hot", {
        "backend": "funasr",
        "asr": {"hotword": "英雄 升级"},
    })
    hot_out = work_dir / "funasr_hot.txt"
    rc2, _stdout2, stderr2 = _run_transcribe(cfg, hot_out)
    hot_text = _read_output(hot_out)
    print(f"  exit: {rc2} | text: {hot_text}")

    print("\n--- diff ---")
    if baseline_text == hot_text:
        print("  (两次输出完全相同——音频中可能没有热词偏置的目标 token)")
    else:
        print(f"  baseline: {baseline_text}")
        print(f"  hotword : {hot_text}")

    # 关键日志校验：stderr 应该包含 contextual 模型加载提示
    log_seen = ("ContextualParaformer" in stderr2) or ("contextual" in stderr2)
    print(f"\n关键日志检测: 'ContextualParaformer' 出现在 stderr = {log_seen}")

    hot_non_empty = bool(hot_text.strip())
    target_words_present = ("英雄" in hot_text) and ("升级" in hot_text)
    print(f"输出非空: {hot_non_empty} | 含目标热词: {target_words_present}")

    ok = rc1 == 0 and rc2 == 0 and log_seen and hot_non_empty and target_words_present
    print(f"verdict     : {'PASS' if ok else 'FAIL'}  (期望两次 exit=0 + ContextualParaformer 日志 + 输出非空且含目标热词)")
    if not ok:
        if stderr1:
            print(f"baseline stderr (tail):\n{stderr1[-500:]}")
        if stderr2:
            print(f"hotword stderr (tail):\n{stderr2[-500:]}")
    return ok


def scenario_volcengine_hotword(work_dir: Path) -> bool:
    """场景 3：Volcengine 后端 + 热词。需 env VOLC_APP_KEY + VOLC_ACCESS_KEY。"""
    print("\n" + "=" * 60)
    print("SCENARIO 3: Volcengine + hotword (cloud, requires env VOLC_APP_KEY/VOLC_ACCESS_KEY)")
    print("=" * 60)

    app_key = os.environ.get("VOLC_APP_KEY")
    access_key = os.environ.get("VOLC_ACCESS_KEY")
    if not app_key or not access_key:
        print("SKIP: env VOLC_APP_KEY / VOLC_ACCESS_KEY 未设置")
        return True  # skip ≠ fail

    cfg = _write_config(work_dir, "volc_hot", {
        "backend": "volcengine",
        "volcengine": {"app_key": app_key, "access_key": access_key},
        "asr": {"hotword": "英雄 升级"},
        "logging": {"level": "DEBUG"},
    })
    out = work_dir / "volc_hot.txt"
    rc, _stdout, stderr = _run_transcribe(cfg, out)
    text = _read_output(out)
    print(f"exit code   : {rc}")
    print(f"transcribed : {text}")

    log_seen = "注入" in stderr and "上下文热词" in stderr
    print(f"关键日志检测: '注入 N 个上下文热词' 出现在 stderr = {log_seen}")

    ok = rc == 0
    print(f"verdict     : {'PASS' if ok else 'FAIL'}  (期望 exit=0；日志检测仅供参考，可能未到 DEBUG 级别)")
    if not ok and stderr:
        print(f"stderr (tail):\n{stderr[-500:]}")
    return ok


# ---------- 主流程 ----------


ALL_SCENARIOS = {
    "replace": scenario_replacements,
    "funasr": scenario_funasr_hotword,
    "volc": scenario_volcengine_hotword,
}


def main():
    parser = argparse.ArgumentParser(description="E2E 真实音频测试")
    parser.add_argument(
        "--scenarios",
        default=",".join(ALL_SCENARIOS.keys()),
        help=f"逗号分隔的场景列表，可选: {','.join(ALL_SCENARIOS.keys())}（默认全跑）",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留临时工作目录（默认跑完删除）",
    )
    args = parser.parse_args()

    if not AUDIO.exists():
        print(f"ERROR: 测试音频不存在: {AUDIO}", file=sys.stderr)
        sys.exit(1)
    if not MAIN_PY.exists():
        print(f"ERROR: main.py 不存在: {MAIN_PY}", file=sys.stderr)
        sys.exit(1)

    requested = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    unknown = [s for s in requested if s not in ALL_SCENARIOS]
    if unknown:
        print(f"ERROR: 未知场景 {unknown}; 可选: {list(ALL_SCENARIOS.keys())}", file=sys.stderr)
        sys.exit(2)

    work_dir = Path(tempfile.mkdtemp(prefix="vocotype_e2e_"))
    print(f"工作目录: {work_dir}")
    print(f"测试音频: {AUDIO}")
    print(f"Python  : {PYTHON}")

    results: dict[str, bool] = {}
    try:
        for name in requested:
            results[name] = ALL_SCENARIOS[name](work_dir)
    finally:
        if not args.keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
        else:
            print(f"\n(已保留工作目录: {work_dir})")

    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    for name, ok in results.items():
        print(f"  {name:10s} : {'PASS' if ok else 'FAIL'}")

    all_ok = all(results.values())
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
