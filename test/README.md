# 测试

覆盖热词（hotword）+ 替换词典（replacements）两个特性的可用性与正确性。

## 文件

| 文件 | 测试层级 | 是否需要外部依赖 | 跑一次需多久 |
|---|---|---|---|
| `test_postprocess.py` | 单元（L1） | 无 | <1s |
| `test_funasr_hotword.py` | 单元 + 集成（L1+L2） | 无（mock 模型） | <1s |
| `test_volcengine_hotword.py` | 集成（L2） | 无（mock WebSocket） | <1s |
| `test_dispatch_pipeline.py` | 集成（L2） | 无 | <1s |
| `test_e2e_real_audio.py` | 端到端（L3） | 需联网 + 测试音频 | 数十秒 - 几分钟 |

## 快速跑（L1+L2，全部 mock，秒级完成）

在项目根目录：

```bash
.venv/Scripts/python.exe -m unittest discover -s test -v
```

或单独跑一个：

```bash
.venv/Scripts/python.exe -m unittest test.test_postprocess -v
```

## 真实端到端（L3，可选）

跑前确认：

- 测试音频在 `res/test/test1.mp3`（项目已附带）
- 联网，且能访问 modelscope（首次跑 hotword 会下载 ContextualParaformer 模型 ~50MB 量化版）

跑：

```bash
.venv/Scripts/python.exe test/test_e2e_real_audio.py
```

脚本会自动跑三种场景：
1. **替换词典**（必跑，不下载新模型）
2. **FunASR 热词**（首次跑会下载 ~50-70MB 模型）
3. **Volcengine 热词**（仅当 env `VOLC_APP_KEY` + `VOLC_ACCESS_KEY` 设置时才跑）

用 `--scenarios replace,funasr` 限定只跑某几个，避免触发不必要的下载或云端调用：

```bash
.venv/Scripts/python.exe test/test_e2e_real_audio.py --scenarios replace
```

## 测试覆盖范围

**正确性**（输入 → 期望输出严格断言）：
- 替换词典：字面/正则/词边界/捕获组/级联/空文本/错误降级
- FunASR 热词：hotword 触发模型 ID 切换、调用签名分发到 `(audio_path, hotwords_str)` 而非 `([audio_path])`
- Volcengine 热词：WebSocket init payload 注入 `request.corpus.context.hotwords` 数组、空/None/空白时 payload 与改动前 byte-for-byte 一致

**可用性**（端到端跑通）：
- L3 `test_e2e_real_audio.py` 跑真实 `transcribe` 子命令，对比 hotword= 空 vs 非空 的输出
