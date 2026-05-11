"""ASR 结果后处理：用户自定义替换词典。

解决 ASR 系统性识别错误（"识别死局"）——同一个错误每次都犯，
靠模型本身或 hotword 偏置都治不好的情况。例如：

    "the message" -> "提交的 message"
    "K8S" -> "Kubernetes"
    "我是 sora" -> "我是 Cursor"

配置格式（config.json 中 `replacements` 字段）：

    "replacements": [
        {"from": "the message", "to": "提交的 message"},
        {"from": "k8s", "to": "Kubernetes"},
        {"from": "/\\bAI\\b/i", "to": "人工智能", "regex": true}
    ]

字段说明：
- `from` (必填)：要替换的字符串；当 `regex=true` 时被当作 Python re 模式
- `to`   (必填)：替换为的内容；正则模式下可用 `\\1` 引用捕获组
- `regex` (可选, 默认 false)：是否启用正则匹配
- 正则可用 `/pattern/flags` 形式带 flags（目前支持 `i` 忽略大小写、`m` 多行、`s` dotall）

规则按数组顺序逐条 apply，所以应把更具体的规则写在前面、宽泛的写在后面。
hotword 是识别前的"建议"，本模块是识别后的"必改"——两者互补不冲突。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Pattern


logger = logging.getLogger(__name__)


@dataclass
class CompiledRule:
    """一条编译后的替换规则。"""
    pattern: Pattern[str] | None  # 非 None 表示正则模式
    literal_from: str | None      # 非 None 表示字面替换
    to: str

    def apply(self, text: str) -> str:
        if self.pattern is not None:
            return self.pattern.sub(self.to, text)
        assert self.literal_from is not None  # 构造时已保证 pattern / literal_from 二选一
        return text.replace(self.literal_from, self.to)


_FLAG_MAP = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}


def _parse_regex_field(raw: str) -> tuple[str, int]:
    """支持 `/pattern/flags` 语法；不带斜杠就当裸 pattern、无 flag。"""
    if len(raw) >= 2 and raw.startswith("/"):
        # 找最后一个 /，前面是 pattern、后面是 flags
        end = raw.rfind("/")
        if end > 0:
            pattern = raw[1:end]
            flag_chars = raw[end + 1:].lower()
            flags = 0
            for ch in flag_chars:
                if ch not in _FLAG_MAP:
                    raise ValueError(f"未知的正则 flag: {ch!r}")
                flags |= _FLAG_MAP[ch]
            return pattern, flags
    return raw, 0


def compile_replacements(rules: Iterable[Any] | None) -> List[CompiledRule]:
    """把配置中的规则编译成 CompiledRule 列表。

    - 缺字段、空字符串：跳过 + warning，不抛
    - 正则编译失败：降级为字面替换 + warning（用户体验优先于严格）
    """
    compiled: List[CompiledRule] = []
    if not rules:
        return compiled

    for idx, raw_rule in enumerate(rules):
        if not isinstance(raw_rule, dict):
            logger.warning("replacements[%d] 不是 dict，已跳过: %r", idx, raw_rule)
            continue
        src = raw_rule.get("from")
        dst = raw_rule.get("to")
        if not isinstance(src, str) or not src:
            logger.warning("replacements[%d] 缺少有效的 'from' 字段，已跳过", idx)
            continue
        if not isinstance(dst, str):
            logger.warning("replacements[%d] 'to' 字段非字符串，已跳过", idx)
            continue
        is_regex = bool(raw_rule.get("regex", False))

        if is_regex:
            try:
                pattern_str, flags = _parse_regex_field(src)
                pattern = re.compile(pattern_str, flags)
                compiled.append(CompiledRule(pattern=pattern, literal_from=None, to=dst))
                continue
            except (re.error, ValueError) as exc:
                logger.warning(
                    "replacements[%d] 正则编译失败 (%s)，降级为字面替换: %r -> %r",
                    idx, exc, src, dst,
                )
                # fall through to literal
        compiled.append(CompiledRule(pattern=None, literal_from=src, to=dst))

    if compiled:
        logger.info("已加载 %d 条替换规则", len(compiled))
    return compiled


def apply_replacements(text: str, compiled: List[CompiledRule]) -> str:
    """按序应用所有规则。空文本或空规则列表直接返回原值。"""
    if not text or not compiled:
        return text
    for rule in compiled:
        try:
            text = rule.apply(text)
        except Exception as exc:  # noqa: BLE001 — 单条失败不应连累整段输出
            logger.warning("替换规则执行异常 (已跳过本条): %s", exc)
    return text


__all__ = ["CompiledRule", "compile_replacements", "apply_replacements"]
