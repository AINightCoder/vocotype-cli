"""Decode audio/video files to 16 kHz mono int16 PCM.

- 原生格式（wav/flac/ogg）走 soundfile，零额外进程开销
- 其余格式（mp3/aac/m4a + 所有视频）走 imageio-ffmpeg 抽音轨
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Tuple

import numpy as np


logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000

_NATIVE_EXTS = frozenset({".wav", ".flac", ".ogg"})
_FFMPEG_EXTS = frozenset({".mp3", ".aac", ".m4a", ".mp4", ".mkv", ".webm", ".mov"})

SUPPORTED_EXTENSIONS = _NATIVE_EXTS | _FFMPEG_EXTS


class UnsupportedFormatError(ValueError):
    """文件扩展名不在 SUPPORTED_EXTENSIONS 中。"""


def decode_to_pcm16(path: str | Path) -> Tuple[np.ndarray, int]:
    """把任意音视频文件解码为 16 kHz 单声道 int16 PCM。

    Returns:
        (samples, sample_rate)，samples 是 1-D int16 ndarray，sample_rate == 16000。

    Raises:
        FileNotFoundError: 文件不存在。
        UnsupportedFormatError: 扩展名不受支持。
        RuntimeError: ffmpeg 调用失败。
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"文件不存在: {p}")

    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"不支持的格式 '{ext}'；支持: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    if ext in _NATIVE_EXTS:
        samples = _decode_native(p)
    else:
        samples = _decode_via_ffmpeg(p)

    return samples, TARGET_SAMPLE_RATE


def _decode_native(p: Path) -> np.ndarray:
    """用 soundfile 解 wav/flac/ogg，按需 soxr 重采样到 16kHz。"""
    import soundfile as sf

    data, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if data.ndim > 1:
        # 多声道 → 单声道（线性混音）
        data = data.mean(axis=1)

    if sr != TARGET_SAMPLE_RATE:
        import soxr

        data = soxr.resample(data, sr, TARGET_SAMPLE_RATE).astype(np.float32)
        logger.debug("soxr 重采样 %d -> %d", sr, TARGET_SAMPLE_RATE)

    return _float_to_int16(data)


def _decode_via_ffmpeg(p: Path) -> np.ndarray:
    """用 imageio-ffmpeg 抽音轨为 16 kHz mono s16le PCM。"""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-nostdin",
        "-loglevel", "error",
        "-i", str(p),
        "-vn",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(TARGET_SAMPLE_RATE),
        "-",
    ]
    logger.debug("ffmpeg 解码: %s", p.name)
    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg 解码失败 ({p.name}): {stderr.strip()}") from exc

    return np.frombuffer(proc.stdout, dtype=np.int16).copy()


def _float_to_int16(data: np.ndarray) -> np.ndarray:
    return (np.clip(data, -1.0, 1.0) * 32767.0).astype(np.int16)
