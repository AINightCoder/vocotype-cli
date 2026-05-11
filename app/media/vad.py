"""Silero-VAD 切句器（纯 onnxruntime 路径，零 PyTorch 依赖）。

模型文件：app/media/silero_vad.onnx（v5+，Apache-2.0）
调用约定：每帧 512 样本（16 kHz），需拼接 64 样本滚动 context 才能正确推理。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import onnxruntime as ort


logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).parent / "silero_vad.onnx"

WINDOW_SAMPLES_16K = 512
CONTEXT_SAMPLES_16K = 64
WINDOW_SAMPLES_8K = 256
CONTEXT_SAMPLES_8K = 32


@dataclass
class VADSegment:
    start_s: float
    end_s: float
    samples: np.ndarray  # int16, 16 kHz mono


class SileroVAD:
    """对应 silero-vad 官方 OnnxWrapper 的纯 numpy/onnxruntime 复刻。"""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH, num_threads: int = 1):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = num_threads
        opts.inter_op_num_threads = num_threads
        self.session = ort.InferenceSession(
            str(model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self._output_names = [o.name for o in self.session.get_outputs()]
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 0), dtype=np.float32)
        self._last_sr = 0

    def reset_states(self, sr: int) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        ctx_size = CONTEXT_SAMPLES_16K if sr == 16000 else CONTEXT_SAMPLES_8K
        self._context = np.zeros((1, ctx_size), dtype=np.float32)
        self._last_sr = sr

    def __call__(self, chunk: np.ndarray, sr: int) -> float:
        """单帧推理；chunk 必须为 float32，长度等于该采样率的 window 大小。"""
        expected = WINDOW_SAMPLES_16K if sr == 16000 else WINDOW_SAMPLES_8K
        if chunk.shape[-1] != expected:
            raise ValueError(f"chunk 必须为 {expected} 样本（实际 {chunk.shape[-1]}）")
        if chunk.dtype != np.float32:
            chunk = chunk.astype(np.float32)
        if self._last_sr != sr:
            self.reset_states(sr)

        ctx_size = CONTEXT_SAMPLES_16K if sr == 16000 else CONTEXT_SAMPLES_8K
        x = np.concatenate([self._context, chunk.reshape(1, -1)], axis=1)

        out, new_state = self.session.run(
            self._output_names,
            {
                "input": x,
                "state": self._state,
                "sr": np.array(sr, dtype=np.int64),
            },
        )
        self._state = new_state
        self._context = x[:, -ctx_size:].copy()
        return float(out[0, 0])


def segment_speech(
    samples_int16: np.ndarray,
    sample_rate: int = 16000,
    model: SileroVAD | None = None,
    threshold: float = 0.5,
    min_speech_ms: int = 250,
    min_silence_ms: int = 100,
    pad_ms: int = 30,
) -> List[VADSegment]:
    """对 int16 PCM 做静音切分。

    返回的 VADSegment 列表按时间顺序，samples 字段是切片后的 int16 数组（可直接送 ASR）。
    完全静音或空输入 → 返回空列表。
    """
    if samples_int16.size == 0:
        return []
    if samples_int16.dtype != np.int16:
        raise TypeError(f"samples_int16 必须为 int16，实际 {samples_int16.dtype}")
    if sample_rate not in (8000, 16000):
        raise ValueError(f"sample_rate 必须为 8000 或 16000，实际 {sample_rate}")

    if model is None:
        model = SileroVAD()

    window = WINDOW_SAMPLES_16K if sample_rate == 16000 else WINDOW_SAMPLES_8K
    min_speech = sample_rate * min_speech_ms // 1000
    min_silence = sample_rate * min_silence_ms // 1000
    pad = sample_rate * pad_ms // 1000
    neg_threshold = threshold - 0.15

    audio_f32 = samples_int16.astype(np.float32) / 32768.0

    model.reset_states(sample_rate)
    probs: List[float] = []
    for i in range(0, len(audio_f32), window):
        chunk = audio_f32[i:i + window]
        if len(chunk) < window:
            chunk = np.pad(chunk, (0, window - len(chunk)))
        probs.append(model(chunk, sample_rate))

    # 状态机：拼接 speech / silence 边界
    triggered = False
    raw: List[dict] = []
    current: dict = {}
    temp_end = 0
    for i, p in enumerate(probs):
        if p >= threshold and temp_end:
            temp_end = 0
        if p >= threshold and not triggered:
            triggered = True
            current["start"] = window * i
            continue
        if p < neg_threshold and triggered:
            if not temp_end:
                temp_end = window * i
            if (window * i) - temp_end < min_silence:
                continue
            current["end"] = temp_end
            if current["end"] - current["start"] > min_speech:
                raw.append(current)
            current = {}
            temp_end = 0
            triggered = False
    if current and (len(audio_f32) - current["start"]) > min_speech:
        current["end"] = len(audio_f32)
        raw.append(current)

    if not raw:
        return []

    # 应用对称 padding
    for i, s in enumerate(raw):
        if i == 0:
            s["start"] = max(0, s["start"] - pad)
        if i != len(raw) - 1:
            silence = raw[i + 1]["start"] - s["end"]
            if silence < 2 * pad:
                s["end"] += silence // 2
                raw[i + 1]["start"] = max(0, raw[i + 1]["start"] - silence // 2)
            else:
                s["end"] = min(len(audio_f32), s["end"] + pad)
                raw[i + 1]["start"] = max(0, raw[i + 1]["start"] - pad)
        else:
            s["end"] = min(len(audio_f32), s["end"] + pad)

    return [
        VADSegment(
            start_s=round(s["start"] / sample_rate, 3),
            end_s=round(s["end"] / sample_rate, 3),
            samples=samples_int16[s["start"]:s["end"]],
        )
        for s in raw
    ]
