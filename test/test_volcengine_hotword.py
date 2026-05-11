"""L2 测试：Volcengine BigASR 热词注入 WebSocket payload。

mock 掉真实 WS 连接，只截获首条 init send 出去的字节序列，解压验证 JSON 结构。
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger("app.volcengine_asr").setLevel(logging.CRITICAL)

from app.volcengine_asr import (
    FULL_SERVER_RESPONSE,
    VolcengineASRClient,
    _build_header,
)


def _extract_first_send_payload(packet: bytes) -> dict:
    """从 _build_full_client_request 打的 packet 里取 gzip(JSON)。"""
    idx = packet.find(b"\x1f\x8b")
    return json.loads(gzip.decompress(packet[idx:]))


class _FakeWS:
    """让 _async_transcribe 走过 send → recv 然后早退；只关心首条 send。"""

    def __init__(self, captured: list):
        self._captured = captured

    async def send(self, data):
        if not self._captured:
            self._captured.append(data)

    async def recv(self):
        # 返回一个会让外层尽早异常退出的不完整 packet（被测试 try/except 吞掉）。
        return bytes(_build_header(FULL_SERVER_RESPONSE, 0b0000)) + (0).to_bytes(4, "big")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


def _run_init_and_capture(options: dict) -> dict:
    """跑一次 _async_transcribe 直到首条 send 完成，返回解出的 init payload。"""
    captured: list = []
    client = VolcengineASRClient({"app_key": "AK", "access_key": "SK"})

    def fake_connect(*args, **kwargs):
        return _FakeWS(captured)

    with patch("websockets.connect", fake_connect):
        try:
            asyncio.run(client._async_transcribe(
                np.zeros(1600, np.int16).tobytes(), 16000, options,
            ))
        except Exception:
            # _parse_server_response 解不完整 packet 会抛，我们已拿到首条 send。
            pass

    assert captured, "首条 send 应在 mock 中被截获"
    return _extract_first_send_payload(captured[0])


class TestVolcengineHotwordInjection(unittest.TestCase):
    def test_empty_options_no_corpus(self):
        payload = _run_init_and_capture({})
        self.assertNotIn("corpus", payload.get("request", {}))

    def test_empty_hotword_string_no_corpus(self):
        payload = _run_init_and_capture({"hotword": ""})
        self.assertNotIn("corpus", payload.get("request", {}))

    def test_whitespace_only_no_corpus(self):
        payload = _run_init_and_capture({"hotword": "   "})
        self.assertNotIn("corpus", payload.get("request", {}))

    def test_none_hotword_no_corpus(self):
        payload = _run_init_and_capture({"hotword": None})
        self.assertNotIn("corpus", payload.get("request", {}))

    def test_non_empty_hotword_injects_corpus_context(self):
        payload = _run_init_and_capture({"hotword": "提交 Vocotype"})
        corpus = payload["request"]["corpus"]
        self.assertEqual(
            corpus["context"]["hotwords"],
            [{"word": "提交"}, {"word": "Vocotype"}],
        )
        self.assertEqual(corpus["context"]["context_type"], "dialog_ctx")

    def test_multiple_whitespace_collapsed(self):
        """  a   b   → 两个词，不会塞入空 word。"""
        payload = _run_init_and_capture({"hotword": "  a   b  "})
        hw = payload["request"]["corpus"]["context"]["hotwords"]
        self.assertEqual(hw, [{"word": "a"}, {"word": "b"}])


if __name__ == "__main__":
    unittest.main()
