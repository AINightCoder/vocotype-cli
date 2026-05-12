# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VocoType CLI — single-file Windows build.

Usage:
    # （可选）先把 modelscope cache 里的模型同步到项目 models/ 一起打包，
    # 适合分发给无网络的目标机器：
    .venv/Scripts/python.exe tools/sync_models_to_project.py
    .venv/Scripts/pyinstaller vocotype.spec

Output: dist/vocotype.exe (一个 ~200-300 MB 的单文件，运行时解压到 %TEMP%)

模型打包策略：
  - 如果项目内 models/ 目录存在，整目录连同 ONNX 文件一起打进 exe，离线分发零依赖
  - 不存在则仅打包代码，首次运行从 modelscope 拉到 %USERPROFILE%\.cache\modelscope\
  - 运行时优先级：项目 models/ → 用户 cache → 在线下载（见 app/download_models.py）
"""
import os
import glob
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    collect_dynamic_libs,
)

datas: list = []
binaries: list = []
hiddenimports: list = []

# 项目自带数据文件
datas += [
    ("app/media/silero_vad.onnx", "app/media"),
    ("files/DirectML.dll", "files"),
    ("files/DXCore.dll", "files"),
]

# ONNX 模型（可选）：如果开发者跑过 tools/sync_models_to_project.py 把模型复制到
# 项目 models/，这里就把整个目录连同子目录结构一起打包；运行时 _MEIPASS/models/...
# 与 app/download_models.py:_project_models_dir() 约定一致。
# SPECPATH 在 PyInstaller 上下文里就是 spec 所在目录（项目根），不需要再 dirname
_models_root = os.path.abspath(os.path.join(SPECPATH, "models"))
if os.path.isdir(_models_root):
    print(f"[vocotype.spec] 检测到项目 models/，打包模型文件...")
    for src_file in glob.glob(os.path.join(_models_root, "**", "*"), recursive=True):
        if not os.path.isfile(src_file):
            continue
        rel = os.path.relpath(os.path.dirname(src_file), os.path.dirname(_models_root))
        # rel 形如 "models/iic/speech_xxx"，正好作为 datas 的目标相对路径
        datas.append((src_file, rel))
    print(f"[vocotype.spec] 已加入 models/ 下 {sum(1 for _ in datas if _[1].startswith('models'))} 个模型文件")
else:
    print(f"[vocotype.spec] 未检测到 models/ 目录，跳过模型打包（首次运行将从 modelscope 在线下载）")

# 第三方包随包资源（imageio_ffmpeg 含 ffmpeg.exe ~70MB；modelscope/funasr_onnx 含配置/模板）
for pkg in (
    "imageio_ffmpeg",
    "modelscope",
    "funasr_onnx",
    "librosa",
    "onnxruntime",
    "numba",
    "llvmlite",
):
    datas += collect_data_files(pkg)

# 动态加载的子模块（这些包习惯 importlib 按名加载，静态分析抓不到）
for pkg in ("modelscope", "funasr_onnx", "numba"):
    hiddenimports += collect_submodules(pkg)

# llvmlite 的 native DLL
binaries += collect_dynamic_libs("llvmlite")


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="vocotype",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX 易触发杀毒误报，关掉换安全
    upx_exclude=[],
    runtime_tmpdir=None,  # 默认 %TEMP%/_MEIxxxxxx
    console=True,         # 保留控制台窗口，便于看 logs 和错误
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
