"""L1 单元测试：替换词典 (app/postprocess.py)。

覆盖：字面/正则/词边界/捕获组/级联/空文本/错误降级。
"""
from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger("app.postprocess").setLevel(logging.CRITICAL)

from app.postprocess import apply_replacements, compile_replacements


class TestLiteralReplacement(unittest.TestCase):
    def test_basic_literal(self):
        rules = compile_replacements([{"from": "the message", "to": "提交的 message"}])
        self.assertEqual(
            apply_replacements("send the message please", rules),
            "send 提交的 message please",
        )

    def test_case_sensitive_substring(self):
        rules = compile_replacements([{"from": "k8s", "to": "Kubernetes"}])
        self.assertEqual(
            apply_replacements("deploy to K8s and k8s", rules),
            "deploy to K8s and Kubernetes",
            msg="字面替换大小写敏感：K8s 不应被匹配",
        )

    def test_cascading_rules(self):
        rules = compile_replacements([
            {"from": "a", "to": "X"},
            {"from": "X", "to": "Y"},
        ])
        self.assertEqual(
            apply_replacements("aaa", rules),
            "YYY",
            msg="规则按顺序级联应用",
        )


class TestRegexReplacement(unittest.TestCase):
    def test_word_boundary_with_flags(self):
        rules = compile_replacements([
            {"from": r"/\b(ai|a i)\b/i", "to": "人工智能", "regex": True},
        ])
        self.assertEqual(
            apply_replacements("AI is great, ai also", rules),
            "人工智能 is great, 人工智能 also",
        )

    def test_capture_group_backreference(self):
        rules = compile_replacements([
            {"from": r"/(\d+)\s*个鸡蛋/", "to": r"\1 个鸡蛋", "regex": True},
        ])
        self.assertEqual(apply_replacements("买5个鸡蛋", rules), "买5 个鸡蛋")


class TestEdgeCases(unittest.TestCase):
    def test_empty_rules(self):
        self.assertEqual(apply_replacements("hello", []), "hello")

    def test_empty_text(self):
        rules = compile_replacements([{"from": "x", "to": "Y"}])
        self.assertEqual(apply_replacements("", rules), "")


class TestErrorDegradation(unittest.TestCase):
    """坏规则应被跳过或降级，不应让整个替换链失效。"""

    def test_invalid_rules_filtered_and_degraded(self):
        bad = [
            {"from": "good", "to": "GOOD"},
            {"no_from": True},                                          # 缺 from → 跳过
            None,                                                       # 非 dict → 跳过
            {"from": "/(unclosed/i", "to": "X", "regex": True},         # 正则编译失败 → 降级字面
            {"from": 123, "to": "X"},                                   # from 类型错 → 跳过
            {"from": "world", "to": "WORLD"},
        ]
        compiled = compile_replacements(bad)
        self.assertEqual(len(compiled), 3, msg="期望 2 条正常 + 1 条降级，共 3 条有效")
        self.assertEqual(apply_replacements("good world", compiled), "GOOD WORLD")


if __name__ == "__main__":
    unittest.main()
