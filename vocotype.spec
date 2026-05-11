# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VocoType CLI — single-file Windows build.

Usage:
    .venv/Scripts/pyinstaller vocotype.spec

Output: dist/vocotype.exe (一个 ~200-300 MB 的单文件，运行时解压到 %TEMP%)

注意：FunASR 的 ~500 MB ONNX 模型不打进 exe，首次运行会从
modelscope 拉到 %USERPROFILE%\.cache\modelscope\。
"""
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
