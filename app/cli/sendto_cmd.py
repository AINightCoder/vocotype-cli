"""install-send-to / uninstall-send-to 子命令。

把 vocotype.exe 注册到 Windows 资源管理器的右键 "发送到" 菜单。
安装后：任意音视频文件 → 右键 → 发送到 → Vocotype →
        Explorer 调起 `vocotype.exe transcribe <文件路径>` → 同目录写 .txt。

仅当从 PyInstaller 冻结 exe (sys.frozen=True) 调用时生效；开发模式给清晰错误。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


_CREATE_NO_WINDOW = 0x08000000


def _sendto_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("环境变量 APPDATA 未设置，无法定位 SendTo 目录")
    return Path(appdata) / "Microsoft" / "Windows" / "SendTo"


def _lnk_path() -> Path:
    return _sendto_dir() / "Vocotype.lnk"


def _require_frozen() -> str:
    if not getattr(sys, "frozen", False):
        print("错误: 此命令必须从 PyInstaller 冻结的 vocotype.exe 调用。", file=sys.stderr)
        print("开发模式下请先 `pyinstaller vocotype.spec`，再用 `dist\\vocotype.exe install-send-to`。", file=sys.stderr)
        sys.exit(2)
    return sys.executable


def install(args: argparse.Namespace) -> int:
    """创建 SendTo\\Vocotype.lnk 指向当前 exe。"""
    exe = _require_frozen()
    lnk = _lnk_path()
    lnk.parent.mkdir(parents=True, exist_ok=True)

    ps = f"""
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut('{lnk}')
$lnk.TargetPath = '{exe}'
$lnk.Arguments  = 'transcribe'
$lnk.WorkingDirectory = '{Path(exe).parent}'
$lnk.IconLocation = '{exe},0'
$lnk.Description  = 'Transcribe audio/video to .txt with VocoType'
$lnk.Save()
"""
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        creationflags=_CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        print(f"创建快捷方式失败:\n{proc.stderr}", file=sys.stderr)
        return 1

    print(f"已安装到 'Send To' 菜单: {lnk}")
    print("用法：在 Explorer 任意音视频文件上 右键 → 发送到 → Vocotype")
    print(f"      → 自动调用 `{Path(exe).name} transcribe <文件>` → 写同名 .txt")
    return 0


def uninstall(args: argparse.Namespace) -> int:
    """删除 SendTo\\Vocotype.lnk。"""
    lnk = _lnk_path()
    if not lnk.exists():
        print(f"未安装（找不到 {lnk}）")
        return 0
    try:
        lnk.unlink()
    except OSError as exc:
        print(f"删除失败: {exc}", file=sys.stderr)
        return 1
    print(f"已移除: {lnk}")
    return 0
