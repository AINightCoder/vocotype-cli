"""把 modelscope cache 里项目用到的 ONNX 模型复制到项目内 models/ 目录。

用途：
- 打包 vocotype.exe 前跑一次，让 PyInstaller 把模型一起塞进 exe
- 迁移到无网络的机器：先在有网机器跑一次让 modelscope 下载，再用本脚本复制到
  项目 models/，把整个项目目录 / dist 目录拷到目标机器即可

不复制：
- contextual repo 的 model_quant.fp32.bak（FP32 备份，体积大且 funasr_onnx 不读它）
- model_eb_quant.onnx 硬链接副本（funasr_server.py 加载前会自动建，不需要分发）
- .mdl / .msc / .mv 等 modelscope 内部记账文件

跑：
    .venv/Scripts/python.exe tools/sync_models_to_project.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models" / "iic"
CACHE_BASE = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic"

# 项目实际用到的 modelscope repo 短名列表
NEEDED_REPOS = [
    "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx",            # 基础 ASR
    "speech_paraformer-large-contextual_asr_nat-zh-cn-16k-common-vocab8404-onnx",  # 热词 ASR (Contextual)
    "speech_fsmn_vad_zh-cn-16k-common-onnx",                                       # VAD
    "punc_ct-transformer_zh-cn-common-vocab272727-onnx",                           # 标点
]

# 不复制的文件名前缀/精确名（modelscope 内部记账 + 不需要分发的备份/硬链接）
SKIP_NAMES = {".mdl", ".msc", ".mv", "model_quant.fp32.bak"}
SKIP_PREFIX = (".",)  # 跳过隐藏文件


def _copy_repo(repo_short: str) -> tuple[int, int]:
    """复制单个 repo；返回 (文件数, 总字节数)。"""
    src_dir = CACHE_BASE / repo_short
    dst_dir = MODELS_DIR / repo_short

    if not src_dir.exists():
        print(f"  ⚠ 源目录不存在: {src_dir}")
        print(f"    （先用 hotword 模式跑一次 transcribe 或 daemon 让 modelscope 下载该模型）")
        return (0, 0)

    dst_dir.mkdir(parents=True, exist_ok=True)
    file_count = 0
    total_bytes = 0

    for src_file in src_dir.iterdir():
        if not src_file.is_file():
            continue
        name = src_file.name
        if name in SKIP_NAMES or name.startswith(SKIP_PREFIX):
            continue

        dst_file = dst_dir / name
        # 大文件跳过已存在且大小相同的
        if dst_file.exists() and dst_file.stat().st_size == src_file.stat().st_size:
            file_count += 1
            total_bytes += dst_file.stat().st_size
            continue

        shutil.copy2(src_file, dst_file)
        file_count += 1
        total_bytes += src_file.stat().st_size
        print(f"  ✓ {name} ({src_file.stat().st_size/1e6:.1f} MB)")

    return (file_count, total_bytes)


def main() -> int:
    print(f"项目目标目录: {MODELS_DIR}")
    print(f"源 cache 目录: {CACHE_BASE}")
    print()

    total_files = 0
    total_bytes = 0
    missing = []
    for repo in NEEDED_REPOS:
        print(f"=== {repo} ===")
        n, b = _copy_repo(repo)
        if n == 0:
            missing.append(repo)
        total_files += n
        total_bytes += b
        print()

    print("=" * 60)
    print(f"复制完成: {total_files} 个文件, {total_bytes/1e6:.1f} MB")
    if missing:
        print(f"\n⚠ 以下 repo 在 cache 里缺失（如已用过对应功能但还报缺失，请检查 cache 路径）:")
        for r in missing:
            print(f"  - {r}")
        print("\n基础识别只需 speech_paraformer-large_..._-onnx + VAD + PUNC；")
        print("contextual 是热词模式才用，如果你不用热词可以忽略它缺失的警告。")
        return 1
    print(f"\n现在可以直接打包: .venv/Scripts/pyinstaller vocotype.spec")
    print(f"运行时优先级: 项目 models/ → 用户 cache → 在线下载")
    return 0


if __name__ == "__main__":
    sys.exit(main())
