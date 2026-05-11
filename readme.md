# VocoType - 精准的离线语音输入法

<h2 align="center">您的声音，绝不离开电脑</h2>

**VocoType** 是一款专为注重隐私和效率的专业人士打造的、**完全免费**的桌面端语音输入法。所有识别均在本地完成，无惧断网，不上传任何数据。

这个 GitHub 项目是 VocoType 核心引擎的 **CLI (命令行) 开源版本**，主要面向开发者。

---

### **➡️ 想获得最佳体验？请立即下载免费桌面版！**

开箱即用，功能更完整，无需任何技术背景。

**[立即访问官网，下载免费、完整的 VocoType 桌面版](https://vocotype.com)**

## 功能简介

VocoType 是一款智能语音输入工具，通过快捷键即可将语音实时转换为文字并自动输入到当前应用。支持MCP语音转文字、 AI 优化文本、自定义替换词典等功能，让语音输入更高效、更准确。

### 📹 演示视频

<video controls width="100%">
  <source src="https://s1.bib0.com/leilei/i/2025/11/04/5yba.mp4" type="video/mp4">
  您的浏览器不支持视频播放。
</video>


## 下载

| OS | Download |
|---|---|
| **Windows** | [![Setup](https://img.shields.io/badge/Setup-x64-blue)](https://github.com/233stone/vocotype-cli/releases/download/v1.5.4/VocoType_1.5.4_x64-setup.exe)  | 
| **macOS** | [![DMG](https://img.shields.io/badge/DMG-Apple%20Silicon-black)](https://github.com/233stone/vocotype-cli/releases/download/v1.5.4/VocoType_1.5.4_Universal.dmg) [![DMG](https://img.shields.io/badge/DMG-Intel-black)](https://github.com/233stone/vocotype-cli/releases/download/v1.5.4/VocoType_1.5.4_Universal.dmg)  |
---



## 🤔 VocoType 为何与众不同？

| 特性           |    ✅ **VocoType**     |  传统云端输入法   |  操作系统自带   |
| :------------- | :--------------------: | :---------------: | :-------------: |
| **隐私安全**   | **本地离线，绝不上传** | ❌ 数据需上传云端 | ⚠️ 隐私政策复杂 |
| **网络依赖**   |    **完全无需联网**    |  ❌ 必须联网使用  |  ❌ 强依赖网络  |
| **响应速度**   |      **0.1 秒级**      |  慢，受网速影响   | 慢，受网速影响  |
| **定制化能力** |  **强大的自定义词表**  |      弱或无       |    基本没有     |

## ✅ 核心功能

- **完整的图形用户界面**：开箱即用，所有操作清晰直观。
- **系统级全局输入**：在任何软件、任何文本框内都能直接语音输入。
- **自定义词典**：支持添加 20 个常用术语、人名，提升识别准确率。
- **100% 离线运行**：绝对的隐私和数据安全。
- **旗舰级识别引擎**：精准识别中英混合内容。
- **AI 智能优化**：支持选择多种 AI 模型，通过可定制的 Prompt 模板自动修正语音转录中的错别字、同音字和自我修正，智能识别口语中的修正指令（如"不对"、"改成"等），让输出文本更准确流畅。
- **音视频文件转写**（CLI）：`python main.py transcribe lecture.mp4` 把本地音视频文件一键转成文本；支持 10 种主流格式，长文件自动按句切片，1 小时讲座 < 1 分钟跑完。
- **全局调用入口**（Windows）：单 `.exe` 同时提供 ① 资源管理器右键"发送到 → Vocotype" 一次性转写，以及 ② 常驻 daemon 下按 **F3** 弹文件选择器，模型常驻内存零冷启动；详见下文。

_(对于有更高需求的专业用户，应用内提供了升级到 Pro 版的选项，以解锁无限词典等高级功能。)_

## 🎯 适用各类专业场景

无论是文字工作者、律师、学者、游戏玩家，还是日常办公，VocoType 都能成为您值得信赖的效率伙伴。

| 用户                | 场景                                                                                           |
| :------------------ | :--------------------------------------------------------------------------------------------- |
| **作家与创作者**    | 撰写文章、小说，整理会议纪要，让思绪通过语音即时转化为文字，心无旁骛，专注于创作本身。         |
| **法律 & 医疗人士** | 处理高度敏感的客户信息或病历时，100%离线确保数据安全。自定义词表更能轻松驾驭行业术语。         |
| **学生与学者**      | 快速记录课堂笔记、整理访谈录音、撰写学术论文。告别繁琐的打字，将更多精力投入到思考与研究之中。 |
| **开发者 & 程序员** | 无论是与 AI 结对编程，还是撰写技术文档，都能精准识别 `function`、`Kubernetes pod` 等专业术语。 |
| **游戏玩家**        | 在激烈的游戏对战中，通过语音快速打字与队友交流，无需停下操作，保持游戏节奏，提升团队协作效率。 |

## ✨ VocoType 核心引擎特性

_所有 VocoType 版本共享同一个强大的核心引擎。_

- **🛡️ 100% 离线，隐私无忧**：所有语音识别在您的电脑本地完成。
- **⚡️ 旗舰级识别引擎**：中英混合输入同样精准，告别反复修改。
- **⚙️ 高度可定制**：独创的替换词表功能，让人名、地名、行业术语一次就对。
- **💻 轻量化设计**：仅需 700MB 内存，纯 CPU 推理，无需昂贵显卡。
- **🚀 0.1 秒级响应**：感受所言即所得的畅快，让您的灵感不再因等待而中断。

---

## 🛠️ 【开发者专属】CLI 版安装指南

**请注意：** 此版本面向有一定技术背景的开发者。如果您不熟悉命令行，我们强烈建议您访问官网，下载简单易用的 **VocoType 免费桌面版**。

### 1. 环境依赖

- Python 3.12
- 我们强烈建议使用 `uv` 或 `venv` 创建虚拟环境。

### 2. 克隆与安装

```bash
# 1. 克隆仓库
git clone https://github.com/233stone/vocotype-cli.git
cd vocotype-cli

# 2. (推荐) 创建并激活虚拟环境
pip install uv
uv venv --python 3.12
source .venv/bin/activate  # macOS/Linux
# 或者 .\.venv\Scripts\activate  (Windows)

# 3. 安装依赖
uv pip install -r requirements.txt

# 4. 运行
python main.py

# 保存数据集运行
python main.py --save-dataset
```

> **模型下载**：首次运行时，程序会自动下载约 500MB 的 FunASR 模型文件，请确保网络连接稳定。

### 3. 打包为单文件 `vocotype.exe`（Windows，可选）

不想每次都 `cd` 到项目目录、激活虚拟环境？把整个 CLI 冻结成一个 `.exe` 放到 PATH 上，全局可用：

```bash
# 在已激活的虚拟环境内
uv pip install pyinstaller
pyinstaller vocotype.spec

# 产物：dist/vocotype.exe（约 188 MB，单文件，包含 ffmpeg + 所有 Python 依赖）
```

把 `dist/vocotype.exe` 拷到 `%USERPROFILE%\.local\bin\` 或任意 PATH 上的目录，重启终端：

```powershell
vocotype --help
vocotype transcribe D:\videos\lecture.mp4    # 任意目录直接调用
vocotype                                      # 仍然进热键模式
```

注意：FunASR 模型（~500 MB）不打进 exe，首次运行仍会下载到 `%USERPROFILE%\.cache\modelscope\`；日志写入 `<exe同目录>\logs\`。

### 4. 全局快捷调用（Windows）

不想每次都去 cmd 输命令？两种全局触发方式，按使用习惯任选其一或都用：

#### Mode A —— Send To 右键菜单（无常驻、零内存）

**默认零配置**：首次启动 `vocotype` daemon 时会自动注册 Send To 快捷方式，控制台首行会打印：

```
[首次启动] 已自动注册到 Send To 菜单: Vocotype.lnk
           不需要的话运行 `vocotype uninstall-send-to` 永久关闭
```

之后**资源管理器内任意音视频文件 → 右键 → 发送到 → Vocotype** 即触发转写，输出 `.txt` 落在源文件旁。无后台进程、不占内存；每次重新加载 FunASR 模型 ~4 秒，适合长文件场景。

如果想跳过 daemon 直接装：

```powershell
vocotype install-send-to        # 手动安装（也撤销之前的 opt-out）
vocotype uninstall-send-to      # 移除快捷方式 + 写永久 opt-out 标记
```

opt-out 标记位于 `%APPDATA%\VocoType\.no_auto_sendto`，存在时 daemon 不再自动安装；重跑 `install-send-to` 会删掉它恢复自动行为。

#### Mode B —— 常驻 daemon + F3 文件选择器

```powershell
vocotype                         # 启动 daemon（需管理员，全局热键限制）
# F2: 麦克风录音 → 转写 → type 到当前焦点窗口（原有功能）
# F3: 弹文件选择器 → 选音视频 → 转写 → 写 sidecar .txt
#     + 输出路径自动复制到剪贴板 + Windows toast 通知
```

模型常驻内存（~700 MB），文件转写**即点即转**；适合短到中等文件高频处理。F2 / F3 共享同一 FunASR 实例，并发用 backend lock 串行化避免冲突。

两种模式共存：日常 Send To，需要快速反应时 daemon。

## 📂 音视频文件转写（CLI 子命令）

把本地音视频文件一键转写为同名 `.txt`，复用本地 FunASR 或云端 Volcengine 后端，不启动热键监听：

```bash
python main.py transcribe path/to/audio.mp3                       # 默认生成 audio.txt
python main.py transcribe lecture.mp4 -o /tmp/out.txt              # 自定义输出路径
python main.py transcribe podcast.m4a --config volcengine.json     # 走云端后端
```

**支持的格式**（共 10 种）：
- 音频：`wav` / `mp3` / `flac` / `aac` / `m4a` / `ogg`
- 视频：`mp4` / `mkv` / `webm` / `mov`

**工作原理**：
1. 解码：`wav/flac/ogg` 走 [soundfile](https://github.com/bastibe/python-soundfile)；其余音频与全部视频走 [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) 自带的预编译 ffmpeg 二进制（首次 pip 安装时自动下载 ~80MB，**无需自行配置 PATH**）
2. 切句：[silero-vad](https://github.com/snakers4/silero-vad) ONNX 模型（已随仓库分发，2.27MB）按句子级静音切片，避免长音频 OOM
3. 识别：逐段调用已配置的 ASR 后端，拼接为最终文本

**性能参考**（CPU-only，单线程，FunASR 后端）：

| 输入 | 时长 | VAD 段数 | 转写耗时 | 实时倍率 |
|---|---|---|---|---|
| 中文 mp3 | 3.9s | 1 | 0.1s | 29x |
| 英文 mp4 (1080p) | 144.2s | 19 | 1.7s | **82x** |

## 🌐 Volcengine 火山引擎 BigASR 流式识别后端（可选）

除了默认的本地 FunASR 离线引擎，VocoType CLI 还支持接入[火山引擎豆包大模型流式语音识别](https://www.volcengine.com/docs/6561/1354869)作为云端识别后端。

### 优势

| 特性 | 本地 FunASR | Volcengine BigASR |
|:--|:--:|:--:|
| 网络要求 | 无 | 需要联网 |
| 模型下载 | ~500 MB | 无需下载 |
| 响应延迟 | 本地推理 | 云端极低延迟 |
| 识别质量 | 高 | 旗舰级大模型 |
| 数据隐私 | 完全离线 | 音频发送至火山引擎 |

### 配置步骤

1. 登录[火山引擎控制台](https://console.volcengine.com/speech/app)，创建一个语音应用，获取 **App Key** 和 **Access Key**。

2. 在项目目录创建 `config.json`：

```json
{
  "backend": "volcengine",
  "volcengine": {
    "app_key": "YOUR_APP_KEY",
    "access_key": "YOUR_ACCESS_KEY",
    "resource_id": "volc.bigasr.sauc.duration",
    "enable_punc": true,
    "enable_itn": true
  }
}
```

3. 以 `--config` 参数启动：

```bash
python main.py --config config.json
```

> **注意**：使用 Volcengine 后端时，录音数据会发送到火山引擎服务器进行识别，不再完全离线。如对隐私有严格要求，请继续使用默认的本地 FunASR 后端。

## 常见问题 (FAQ)

**Q: 我的数据安全吗？**

> A: **100%安全**。所有语音识别均在本地离线完成，您的音频数据不会上传到任何服务器。

## 📞 联系我们

- **Bug 与建议**：请优先使用 GitHub Issues。
- **关注我们获取最新动态**：[https://vocotype.com](https://vocotype.com)

## 🙏 致谢

VocoType 的诞生离不开以下优秀的开源项目：

- **[FunASR](https://github.com/modelscope/FunASR)** - 阿里巴巴达摩院开源的语音识别框架，为 VocoType 提供了强大的离线语音识别能力。
- **[silero-vad](https://github.com/snakers4/silero-vad)** (Apache-2.0) - 轻量级开源 VAD 模型，让音视频文件转写功能能按句子级切片，逐段送入 ASR 而不会因长音频导致 OOM。
- **[QuQu](https://github.com/yan5xu/ququ)** - 优秀的开源项目，为 VocoType 提供了重要的技术参考和灵感。

感谢这些开源社区的无私贡献！
