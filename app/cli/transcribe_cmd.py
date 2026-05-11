"""`python main.py transcribe <FILE> [-o OUT]` 子命令实现。

把单个音视频文件解码 → VAD 切句 → 逐段调用 FunASR/Volcengine 后端 → 写 .txt。
跑完即退出，不启动热键监听。
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from app.config import ensure_logging_dir, load_config
from app.logging_config import setup_logging
from app.media import (
    SUPPORTED_EXTENSIONS,
    UnsupportedFormatError,
    decode_to_pcm16,
    segment_speech,
    SileroVAD,
)
from app.transcribe import TranscriptionWorker


logger = logging.getLogger(__name__)


def run(args: argparse.Namespace) -> int:
    """子命令入口；返回进程退出码。"""
    config = load_config(args.config)
    log_dir = ensure_logging_dir(config)
    setup_logging(level=config["logging"].get("level", "INFO"), log_dir=log_dir)

    input_path = Path(args.input).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_path.with_suffix(".txt")
    )

    # 1) 解码
    print(f"[1/3] 解码 {input_path.name} ...", flush=True)
    t0 = time.time()
    try:
        samples, sr = decode_to_pcm16(input_path)
    except FileNotFoundError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    except UnsupportedFormatError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        print(f"支持的格式: {sorted(SUPPORTED_EXTENSIONS)}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"解码失败: {exc}", file=sys.stderr)
        return 3
    duration_s = len(samples) / sr
    print(f"      解码完成，时长 {duration_s:.1f}s，耗时 {time.time()-t0:.2f}s", flush=True)

    # 2) VAD 切句
    print(f"[2/3] VAD 静音切分 ...", flush=True)
    t0 = time.time()
    vad_model = SileroVAD()
    segments = segment_speech(samples, sr, model=vad_model)
    print(
        f"      切分完成，{len(segments)} 段，耗时 {time.time()-t0:.2f}s",
        flush=True,
    )
    if not segments:
        print("警告: 未检测到任何语音片段（可能是纯静音或无语音内容）", file=sys.stderr)
        output_path.write_text("", encoding="utf-8")
        print(f"已写空文件: {output_path}", flush=True)
        return 0

    # 3) 逐段转写（共用同一个 TranscriptionWorker / 后端实例）
    print(f"[3/3] 转写 {len(segments)} 段 ...", flush=True)
    worker = TranscriptionWorker(config_path=args.config, on_result=None)
    texts: list[str] = []
    asr_t0 = time.time()
    try:
        for i, seg in enumerate(segments, 1):
            seg_t0 = time.time()
            result = worker.transcribe_samples(seg.samples)
            seg_dt = time.time() - seg_t0
            if result.error:
                logger.warning(
                    "段 %d/%d (%.2f-%.2fs) 转写失败: %s",
                    i, len(segments), seg.start_s, seg.end_s, result.error,
                )
                continue
            text = result.text.strip()
            if text:
                texts.append(text)
            print(
                f"\r      [{i}/{len(segments)}] {seg.start_s:6.1f}-{seg.end_s:6.1f}s "
                f"({seg_dt:4.1f}s) -> {len(text):3d} 字",
                end="",
                flush=True,
            )
        print()  # 收尾换行
    finally:
        try:
            worker.cleanup()
        except Exception as exc:
            logger.debug("清理 worker 失败: %s", exc)

    # 4) 写文件
    full_text = "\n".join(texts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")

    total_dt = time.time() - asr_t0
    print(
        f"\n完成: {output_path}",
        f"  字符数: {len(full_text)}",
        f"  音频时长: {duration_s:.1f}s",
        f"  转写耗时: {total_dt:.1f}s ({duration_s/max(total_dt, 1e-6):.1f}x 实时)",
        sep="\n",
        flush=True,
    )
    return 0
