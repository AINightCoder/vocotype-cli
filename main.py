"""Command-line entry for the speak-keyboard prototype."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time

import keyboard

from app import HotkeyManager, TranscriptionResult, TranscriptionWorker, load_config, type_text
from app.plugins.dataset_recorder import wrap_result_handler
from app.logging_config import setup_logging


logger = logging.getLogger(__name__)


_TOGGLE_DEBOUNCE_SECONDS = 0.2
_toggle_lock = threading.Lock()
_last_toggle_time = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Speak Keyboard prototype")
    parser.add_argument("--config", help="Path to config JSON")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single transcription cycle for debugging",
    )
    parser.add_argument("--save-dataset", action="store_true", help="Persist audio/text pairs")
    parser.add_argument("--dataset-dir", default="dataset", help="Dataset output directory")

    subparsers = parser.add_subparsers(dest="command")
    sub_tx = subparsers.add_parser(
        "transcribe",
        help="Transcribe an audio/video file to .txt (one-shot, no hotkeys)",
    )
    sub_tx.add_argument("input", help="Path to audio or video file")
    sub_tx.add_argument(
        "-o", "--output",
        default=None,
        help="Output .txt path (default: same name as input, .txt extension)",
    )
    sub_tx.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="Path to config JSON (overrides top-level --config)",
    )

    subparsers.add_parser(
        "install-send-to",
        help="Register this exe to Windows Explorer 'Send To' menu (right-click a file → Send To → Vocotype)",
    )
    subparsers.add_parser(
        "uninstall-send-to",
        help="Remove the 'Send To' shortcut installed by install-send-to",
    )

    return parser.parse_args()


def main() -> None:
    # Windows cp1252/cp936 控制台无法直接打印中文；统一把 stdio 切到 UTF-8，
    # PyInstaller 冻结模式下 PYTHONIOENCODING env var 不被早期 Python 初始化读取，
    # 必须在代码里强制 reconfigure 才能保险。errors="replace" 兜底极端字符。
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, Exception):
            pass

    args = parse_args()
    cmd = getattr(args, "command", None)
    if cmd == "transcribe":
        from app.cli.transcribe_cmd import run
        sys.exit(run(args))
    if cmd == "install-send-to":
        from app.cli.sendto_cmd import install
        sys.exit(install(args))
    if cmd == "uninstall-send-to":
        from app.cli.sendto_cmd import uninstall
        sys.exit(uninstall(args))

    config = load_config(args.config)
    
    # 配置日志系统（统一配置）
    from app.config import ensure_logging_dir
    log_dir_abs = ensure_logging_dir(config)
    setup_logging(
        level=config["logging"].get("level", "INFO"),
        log_dir=log_dir_abs
    )

    output_cfg = config.get("output", {})
    output_method = output_cfg.get("method", "auto")
    append_newline = output_cfg.get("append_newline", False)

    # 先创建worker（没有回调）
    worker = TranscriptionWorker(
        config_path=args.config,
        on_result=None,  # 稍后设置
    )
    
    # 创建result handler（需要worker引用）
    worker.on_result = _make_result_handler(output_method, append_newline, worker)
    if args.save_dataset:
        worker.on_result = wrap_result_handler(worker.on_result, worker, args.dataset_dir)
    
    hotkeys = HotkeyManager()

    toggle_combo = config["hotkeys"].get("toggle", "f2")
    file_combo = config["hotkeys"].get("file", "f3")
    hotkeys.register(toggle_combo, lambda: _toggle(worker))
    hotkeys.register(file_combo, lambda: _file_pick_async(worker))

    try:
        logger.info(
            "Speak Keyboard 启动完成；%s 开/停麦克风录音，%s 文件转写，Ctrl+C 退出",
            toggle_combo, file_combo,
        )
        if args.once:
            _toggle(worker)
            input("按 Enter 停止并退出...")
            _toggle(worker)
        else:
            keyboard.wait()
    except KeyboardInterrupt:
        logger.info("用户中断，正在退出...")
    finally:
        # 清理所有资源
        try:
            worker.stop()
        except Exception as exc:
            logger.debug("停止 worker 时出错: %s", exc)
        
        try:
            worker.cleanup()
        except Exception as exc:
            logger.debug("清理 worker 时出错: %s", exc)
        
        try:
            hotkeys.cleanup()
        except Exception as exc:
            logger.debug("清理热键时出错: %s", exc)
        
        logger.info("所有资源已清理，正常退出")
        sys.exit(0)


def _make_result_handler(output_method: str, append_newline: bool, worker: TranscriptionWorker):
    def _handle_result(result: TranscriptionResult) -> None:
        if result.error:
            logger.error("转写失败: %s", result.error)
            return

        # 获取转录统计信息
        stats = worker.transcription_stats
        
        logger.info(
            "转写成功: %s (推理 %.2fs) [已完成 %d/%d，队列剩余 %d]",
            result.text,
            result.inference_latency,
            stats["completed"],
            stats["submitted"],
            stats["pending"],
        )
        type_text(
            result.text,
            append_newline=append_newline,
            method=output_method,
        )

    return _handle_result


def _file_pick_async(worker: TranscriptionWorker) -> None:
    """F3 入口：起新线程，弹文件选择器并转写选中的文件。"""
    threading.Thread(
        target=_file_pick_and_transcribe,
        args=(worker,),
        daemon=True,
        name="F3FileTranscribe",
    ).start()


def _file_pick_and_transcribe(worker: TranscriptionWorker) -> None:
    """F3 worker：调系统文件选择器 → 解码 → VAD → 逐段 ASR → 写 sidecar .txt。
    最后弹 toast、把输出路径塞剪贴板，进度仍打到 console。
    """
    from pathlib import Path
    from app.cli.desktop import pick_file_dialog, show_toast, copy_to_clipboard
    from app.media import (
        SUPPORTED_EXTENSIONS,
        UnsupportedFormatError,
        decode_to_pcm16,
        segment_speech,
        SileroVAD,
    )

    path_str = pick_file_dialog()
    if not path_str:
        logger.info("F3 文件选择已取消")
        return

    input_path = Path(path_str)
    output_path = input_path.with_suffix(".txt")
    print(f"\n[F3] 转写 {input_path.name} ...", flush=True)

    # 解码
    try:
        samples, sr = decode_to_pcm16(input_path)
    except FileNotFoundError as exc:
        logger.error("F3 文件不存在: %s", exc)
        show_toast("VocoType 转写失败", str(exc))
        return
    except UnsupportedFormatError as exc:
        logger.error("F3 不支持的格式: %s", exc)
        show_toast(
            "VocoType 转写失败",
            f"{input_path.suffix} 不支持；可用格式: {sorted(SUPPORTED_EXTENSIONS)}",
        )
        return
    except Exception as exc:
        logger.exception("F3 解码异常")
        show_toast("VocoType 转写失败", str(exc))
        return

    duration_s = len(samples) / sr
    print(f"      解码 {duration_s:.1f}s 完成，切句中 ...", flush=True)

    # VAD + 逐段转写
    vad_model = SileroVAD()
    segments = segment_speech(samples, sr, model=vad_model)
    if not segments:
        output_path.write_text("", encoding="utf-8")
        show_toast("VocoType", f"{input_path.name} 未检测到语音内容")
        return

    texts: list[str] = []
    for i, seg in enumerate(segments, 1):
        try:
            result = worker.transcribe_samples(seg.samples)
        except Exception as exc:
            logger.warning("F3 第 %d/%d 段失败: %s", i, len(segments), exc)
            continue
        if result.error:
            logger.warning("F3 第 %d/%d 段错误: %s", i, len(segments), result.error)
            continue
        text = result.text.strip()
        if text:
            texts.append(text)
        print(
            f"\r      [F3 {i}/{len(segments)}] {seg.start_s:6.1f}-{seg.end_s:6.1f}s -> {len(text):3d} 字",
            end="",
            flush=True,
        )
    print()

    full_text = "\n".join(texts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")
    copy_to_clipboard(str(output_path))
    show_toast(
        "VocoType 转写完成",
        f"{input_path.name} → {output_path.name}（{len(full_text)} 字符，路径已复制）",
    )
    print(
        f"[F3] 完成: {output_path}\n      字符数 {len(full_text)} | 路径已复制到剪贴板",
        flush=True,
    )


def _toggle(worker: TranscriptionWorker) -> None:
    global _last_toggle_time
    now = time.monotonic()
    with _toggle_lock:
        if now - _last_toggle_time < _TOGGLE_DEBOUNCE_SECONDS:
            logger.debug("忽略快速重复的录音切换请求 (%.3fs)", now - _last_toggle_time)
            return
        _last_toggle_time = now

    if worker.is_running:
        # 停止录音，提交转录任务
        worker.stop()
        stats = worker.transcription_stats
        if stats["pending"] > 0:
            logger.info(
                "录音已停止并提交转录，队列中还有 %d 个任务等待处理",
                stats["pending"]
            )
    else:
        # 开始录音
        stats = worker.transcription_stats
        if stats["pending"] > 0:
            logger.info(
                "开始录音（后台还有 %d 个转录任务正在处理）",
                stats["pending"]
            )
        worker.start()


if __name__ == "__main__":
    main()

