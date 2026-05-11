"""把 ContextualParaformer 的 model_quant.onnx 真正量化为 INT8。

背景：modelscope 上 `iic/speech_paraformer-large-contextual_asr_..._-onnx` repo
发布的 model_quant.onnx 文件名虽然带 "quant"，但权重 100% 是 FP32（共 869MB）。
本脚本用 onnxruntime dynamic INT8 量化把它压到 ~220MB（4x 压缩）。

行为：
- 第一次跑：把原 model_quant.onnx 重命名为 model_quant.fp32.bak（备份），再生成
  真正的 INT8 model_quant.onnx 覆盖。幂等：再次运行检测到 .bak 存在就跳过。
- 仅处理 contextual repo；不动基础 paraformer-large（228MB 已经够小，且结构上
  很可能已经做过部分量化，二次量化风险高于收益）。
- model_eb.onnx (25MB) 含 LSTM 算子，量化容易精度崩，不动。

回滚：`mv model_quant.fp32.bak model_quant.onnx`
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


def _cache_dir() -> Path:
    """ContextualParaformer ONNX repo 在 modelscope cache 里的目录。"""
    base = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic"
    return base / "speech_paraformer-large-contextual_asr_nat-zh-cn-16k-common-vocab8404-onnx"


def main() -> int:
    repo = _cache_dir()
    if not repo.exists():
        print(f"ERROR: contextual 模型目录不存在: {repo}", file=sys.stderr)
        print("提示：先用 hotword 模式跑一次 transcribe 让 funasr_onnx 下载完整 repo，再回来跑此脚本。", file=sys.stderr)
        return 2

    src = repo / "model_quant.onnx"
    backup = repo / "model_quant.fp32.bak"
    out = repo / "model_quant.onnx"  # 覆盖

    if backup.exists() and src.exists() and src.stat().st_size < 500 * 1024 * 1024:
        print(f"已经量化过：{src} ({src.stat().st_size/1e6:.1f} MB)，备份在 {backup}")
        print("（要重新量化请先 rm 备份再跑）")
        return 0

    if not src.exists():
        print(f"ERROR: 找不到 {src}", file=sys.stderr)
        return 2

    original_size = src.stat().st_size
    print(f"原始 model_quant.onnx: {original_size/1e6:.1f} MB")

    # 备份
    if not backup.exists():
        print(f"备份 → {backup.name}")
        src.rename(backup)
    else:
        print(f"备份已存在: {backup.name}，跳过重命名")

    # 量化
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError as exc:
        print(f"ERROR: 缺 onnxruntime quantization 工具: {exc}", file=sys.stderr)
        print("（onnxruntime 默认就带，应该不会缺。检查 .venv 是否激活）", file=sys.stderr)
        # 回滚 rename
        if backup.exists() and not src.exists():
            backup.rename(src)
        return 3

    print("开始 dynamic INT8 量化 (weight_type=QInt8, per_channel=False)...")
    t0 = time.time()
    try:
        quantize_dynamic(
            model_input=str(backup),
            model_output=str(out),
            weight_type=QuantType.QInt8,
            per_channel=False,  # per-tensor 推理更快、精度差不大
        )
    except Exception as exc:
        print(f"量化失败: {exc}", file=sys.stderr)
        # 回滚
        if backup.exists() and not out.exists():
            backup.rename(out)
            print("已回滚到原文件")
        return 4

    elapsed = time.time() - t0
    new_size = out.stat().st_size
    print(f"量化完成，耗时 {elapsed:.1f}s")
    print(f"压缩前: {original_size/1e6:>7.1f} MB")
    print(f"压缩后: {new_size/1e6:>7.1f} MB  ({new_size/original_size*100:.1f}% of original)")
    print(f"节省  : {(original_size-new_size)/1e6:>7.1f} MB")
    print()
    print("验证：跑 `python tools/verify_quantized_model.py` 对比量化前后识别输出")
    print(f"回滚：`mv {backup} {out}`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
