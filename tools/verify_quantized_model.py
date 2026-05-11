"""验证 ContextualParaformer 量化前后的识别输出差异。

使用 res/test/test1.mp3 跑两次：
- 当前 model_quant.onnx（已量化版）
- model_quant.fp32.bak（备份的原 FP32 版）

输出两次识别结果 + 字符级 diff。如果差异不可接受，可以 `mv .bak .onnx` 回滚。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
MAIN_PY = PROJECT_ROOT / "main.py"
AUDIO = PROJECT_ROOT / "res" / "test" / "test1.mp3"
CACHE_REPO = (
    Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic"
    / "speech_paraformer-large-contextual_asr_nat-zh-cn-16k-common-vocab8404-onnx"
)
MODEL_FILE = CACHE_REPO / "model_quant.onnx"
BACKUP_FILE = CACHE_REPO / "model_quant.fp32.bak"


def _run_transcribe(out_path: Path) -> tuple[int, str]:
    """启 main.py transcribe 跑一次。返回 (exit_code, transcribed_text)"""
    work = Path(tempfile.mkdtemp(prefix="vocotype_verify_"))
    cfg = work / "cfg.json"
    cfg.write_text(
        '{"backend":"funasr","asr":{"hotword":"英雄 升级"}}',
        encoding="utf-8",
    )
    cmd = [str(PYTHON), str(MAIN_PY), "transcribe", str(AUDIO), "-o", str(out_path), "--config", str(cfg)]
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    text = out_path.read_text(encoding="utf-8").strip() if out_path.exists() else ""
    shutil.rmtree(work, ignore_errors=True)
    return proc.returncode, text


def main() -> int:
    if not BACKUP_FILE.exists():
        print(f"ERROR: 找不到 FP32 备份: {BACKUP_FILE}", file=sys.stderr)
        print("先跑 tools/quantize_contextual_model.py 生成备份", file=sys.stderr)
        return 2

    if not MODEL_FILE.exists():
        print(f"ERROR: 找不到当前 model_quant.onnx: {MODEL_FILE}", file=sys.stderr)
        return 2

    print(f"模型文件: {MODEL_FILE}")
    print(f"  当前    : {MODEL_FILE.stat().st_size/1e6:.1f} MB")
    print(f"  FP32 备份: {BACKUP_FILE.stat().st_size/1e6:.1f} MB")
    print()

    # 1) 跑当前（量化版）
    print("=" * 60)
    print("[1/2] 跑当前 model_quant.onnx (量化版)")
    print("=" * 60)
    work = Path(tempfile.mkdtemp(prefix="vocotype_q_"))
    rc_q, text_q = _run_transcribe(work / "q.txt")
    print(f"exit: {rc_q}  text: {text_q!r}")
    shutil.rmtree(work, ignore_errors=True)

    # 2) 临时换回 FP32
    print()
    print("=" * 60)
    print("[2/2] 临时换回 FP32 model_quant.fp32.bak")
    print("=" * 60)
    # 移开当前量化版
    tmp_quant = MODEL_FILE.with_suffix(".quant.tmp")
    MODEL_FILE.rename(tmp_quant)
    # 把 .bak 复制成 model_quant.onnx（不动 .bak）
    shutil.copy2(BACKUP_FILE, MODEL_FILE)
    try:
        work2 = Path(tempfile.mkdtemp(prefix="vocotype_fp32_"))
        rc_fp, text_fp = _run_transcribe(work2 / "fp.txt")
        shutil.rmtree(work2, ignore_errors=True)
    finally:
        # 还原量化版
        MODEL_FILE.unlink()
        tmp_quant.rename(MODEL_FILE)
    print(f"exit: {rc_fp}  text: {text_fp!r}")

    # 对比
    print()
    print("=" * 60)
    print("对比")
    print("=" * 60)
    print(f"  FP32 (869MB): {text_fp}")
    print(f"  INT8 (~220MB): {text_q}")
    same = text_fp == text_q
    if same:
        print("\n结果一致 ✓  量化无可见精度损失（基于此样本）")
    else:
        # 字符级差异
        common = sum(1 for a, b in zip(text_fp, text_q) if a == b)
        max_len = max(len(text_fp), len(text_q))
        sim = common / max_len if max_len else 1.0
        print(f"\n结果不同。逐字符相似度: {sim*100:.1f}%")
        print("  ⚠ 注意：单样本不足以评估全面精度，建议跑更多样本再决定")
        print(f"\n回滚命令：mv {BACKUP_FILE} {MODEL_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
