"""L2 测试：_dispatch_result 链路把 ASR 原始文本经 replacements 后处理，
但保留 raw_text 给 dataset_recorder 等下游使用。
"""
from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger("app.postprocess").setLevel(logging.CRITICAL)

from app.postprocess import apply_replacements, compile_replacements
from app.transcribe import TranscriptionResult


class TestDispatchPipeline(unittest.TestCase):
    """模拟 _dispatch_result 的处理：text 经过 apply_replacements，raw_text 保留 ASR 原始。

    不实例化真 TranscriptionWorker（避免触发后端加载），只验证替换链路的纯函数逻辑。
    """

    def test_text_post_processed_raw_text_preserved(self):
        rules = compile_replacements([
            {"from": "the message", "to": "提交的 message"},
            {"from": r"/k8s/i", "to": "Kubernetes", "regex": True},
        ])
        asr_result = {
            "success": True,
            "text": "please send the message to k8s and K8s",
            "raw_text": "please send the message to k8s and K8s",
        }
        final_text = apply_replacements(asr_result["text"], rules)

        result = TranscriptionResult(
            text=final_text,
            raw_text=asr_result["raw_text"],
            duration=1.0,
            inference_latency=0.5,
            confidence=0.95,
        )

        self.assertEqual(
            result.text,
            "please send 提交的 message to Kubernetes and Kubernetes",
            msg="text 应该被替换",
        )
        self.assertEqual(
            result.raw_text,
            "please send the message to k8s and K8s",
            msg="raw_text 应该保留 ASR 原始输出（dataset_recorder 落盘用）",
        )


if __name__ == "__main__":
    unittest.main()
