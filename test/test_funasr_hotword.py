"""L1+L2 测试：FunASR 后端热词路径。

L1：hotword 触发模型 ID 切换、构造时 strip 处理。
L2：transcribe_audio 根据 _asr_supports_hotword 标志分发到不同调用签名。
"""
from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger("app.funasr_server").setLevel(logging.CRITICAL)

from app.funasr_server import FunASRServer


BASE_ID = "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx"
CTX_ID = "iic/speech_paraformer-large-contextual_asr_nat-zh-cn-16k-common-vocab8404-onnx"


class TestModelIdSelection(unittest.TestCase):
    """FunASRServer.__init__ 根据 hotword 选择不同的 ASR 模型 ID。"""

    def test_empty_hotword_keeps_base_model(self):
        srv = FunASRServer(hotword="")
        self.assertEqual(srv.model_names["asr"], BASE_ID)
        self.assertEqual(srv._hotword, "")

    def test_whitespace_only_falls_back_to_base(self):
        srv = FunASRServer(hotword="   ")
        self.assertEqual(srv.model_names["asr"], BASE_ID)
        self.assertEqual(srv._hotword, "", msg="空白被 strip 后视为无热词")

    def test_none_hotword_falls_back_to_base(self):
        # 实际运行时用户配置缺字段 dict.get 会返回 None；
        # FunASRServer 用 (hotword or "").strip() 兼容，所以这里显式测 None。
        srv = FunASRServer(hotword=None)  # type: ignore[arg-type]
        self.assertEqual(srv.model_names["asr"], BASE_ID)

    def test_non_empty_hotword_switches_to_contextual_model(self):
        srv = FunASRServer(hotword="Vocotype Kubernetes")
        self.assertEqual(srv.model_names["asr"], CTX_ID)
        self.assertEqual(srv._hotword, "Vocotype Kubernetes")

    def test_chinese_hotword_switches_to_contextual_model(self):
        srv = FunASRServer(hotword="英雄 升级")
        self.assertEqual(srv.model_names["asr"], CTX_ID)


class _FakeBaseParaformer:
    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, *args, **kwargs):
        self.calls.append(("base", args, kwargs))
        return [{"preds": ("基础识别", [])}]


class _FakeContextualParaformer:
    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, *args, **kwargs):
        self.calls.append(("contextual", args, kwargs))
        return [{"preds": ("热词识别", [])}]


class TestTranscribeAudioDispatch(unittest.TestCase):
    """transcribe_audio 根据 _asr_supports_hotword 选择不同调用签名。"""

    def test_base_model_uses_list_audio_path(self):
        srv = FunASRServer(hotword="")
        srv.initialized = True
        srv.asr_model = _FakeBaseParaformer()
        srv.vad_model = None
        srv.punc_model = None

        with patch("os.path.exists", return_value=True), \
             patch.object(srv, "_get_audio_duration", return_value=1.0):
            r = srv.transcribe_audio("/fake.wav", options={"use_vad": False, "use_punc": False})

        self.assertEqual(srv.asr_model.calls[-1], ("base", (["/fake.wav"],), {}))
        self.assertTrue(r["success"])
        self.assertEqual(r["raw_text"], "基础识别")

    def test_contextual_model_passes_hotwords_string(self):
        srv = FunASRServer(hotword="Vocotype Kubernetes")
        srv.initialized = True
        srv.asr_model = _FakeContextualParaformer()
        srv._asr_supports_hotword = True
        srv.vad_model = None
        srv.punc_model = None

        with patch("os.path.exists", return_value=True), \
             patch.object(srv, "_get_audio_duration", return_value=1.0):
            r = srv.transcribe_audio(
                "/fake.wav",
                options={"hotword": "Vocotype Kubernetes", "use_vad": False, "use_punc": False},
            )

        self.assertEqual(
            srv.asr_model.calls[-1],
            ("contextual", ("/fake.wav", "Vocotype Kubernetes"), {}),
        )
        self.assertTrue(r["success"])
        self.assertEqual(r["raw_text"], "热词识别")

    def test_contextual_model_with_empty_options_hotword_passes_empty_string(self):
        """即使 options 里 hotword 字段缺失，contextual 路径也要传一个空字符串，
        而不是漏传位置参数（ContextualParaformer.__call__ 必填 hotwords）。"""
        srv = FunASRServer(hotword="x")  # 任意非空触发 contextual 路径
        srv.initialized = True
        srv.asr_model = _FakeContextualParaformer()
        srv._asr_supports_hotword = True
        srv.vad_model = None
        srv.punc_model = None

        with patch("os.path.exists", return_value=True), \
             patch.object(srv, "_get_audio_duration", return_value=1.0):
            srv.transcribe_audio(
                "/fake.wav",
                options={"use_vad": False, "use_punc": False},  # 没有 hotword 字段
            )

        # 应该 fallback 到 default_options["hotword"] = "" 然后传给 ContextualParaformer
        last_call = srv.asr_model.calls[-1]
        self.assertEqual(last_call[0], "contextual")
        self.assertEqual(last_call[1], ("/fake.wav", ""))


if __name__ == "__main__":
    unittest.main()
