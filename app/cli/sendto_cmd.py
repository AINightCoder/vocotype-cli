"""install-send-to / uninstall-send-to 子命令 + daemon 启动时的静默自动安装。

把 vocotype.exe 注册到 Windows 资源管理器的右键 "发送到" 菜单。
安装后：任意音视频文件 → 右键 → 发送到 → Vocotype →
        Explorer 调起 `vocotype.exe transcribe <文件路径>` → 同目录写 .txt。

仅当从 PyInstaller 冻结 exe (sys.frozen=True) 调用时生效；开发模式给清晰错误。

opt-out 机制：uninstall-send-to 在 %APPDATA%\\VocoType\\.no_auto_sendto 写一个
标记文件，下次 daemon 启动看到标记就不会再自动安装；install-send-to 会反过来
删除标记（用户显式重装意味着撤销 opt-out）。
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path


logger = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000


def _sendto_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("环境变量 APPDATA 未设置，无法定位 SendTo 目录")
    return Path(appdata) / "Microsoft" / "Windows" / "SendTo"


def _lnk_path() -> Path:
    return _sendto_dir() / "Vocotype.lnk"


def _marker_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("环境变量 APPDATA 未设置")
    return Path(appdata) / "VocoType" / ".no_auto_sendto"


def _require_frozen() -> str:
    if not getattr(sys, "frozen", False):
        print("错误: 此命令必须从 PyInstaller 冻结的 vocotype.exe 调用。", file=sys.stderr)
        print("开发模式下请先 `pyinstaller vocotype.spec`，再用 `dist\\vocotype.exe install-send-to`。", file=sys.stderr)
        sys.exit(2)
    return sys.executable


def _create_lnk(exe: str, lnk: Path) -> None:
    """通过 PowerShell + WScript.Shell COM 创建 .lnk。失败抛 RuntimeError。"""
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
        raise RuntimeError(f"创建 .lnk 失败: {proc.stderr.strip()}")


def _clear_marker() -> None:
    """删除 opt-out 标记（如存在）；静默失败。"""
    try:
        marker = _marker_path()
        if marker.exists():
            marker.unlink()
    except Exception as exc:
        logger.debug("清除 opt-out 标记失败 (已忽略): %s", exc)


def _write_marker() -> None:
    """写 opt-out 标记，阻止 daemon 再次自动安装；失败仅 warning。"""
    try:
        marker = _marker_path()
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "User opted out of auto Send To install by running `uninstall-send-to`.\n"
            "Delete this file (or run `install-send-to`) to re-enable auto-install.\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"警告: 无法写 opt-out 标记: {exc}", file=sys.stderr)


def install(args: argparse.Namespace) -> int:
    """手动安装：用户显式调 `vocotype install-send-to`。撤销之前的 opt-out。"""
    exe = _require_frozen()
    lnk = _lnk_path()
    try:
        _create_lnk(exe, lnk)
    except RuntimeError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    _clear_marker()
    print(f"已安装到 'Send To' 菜单: {lnk}")
    print("用法：在 Explorer 任意音视频文件上 右键 → 发送到 → Vocotype")
    print(f"      → 自动调用 `{Path(exe).name} transcribe <文件>` → 写同名 .txt")
    return 0


def uninstall(args: argparse.Namespace) -> int:
    """手动卸载：删 .lnk 并写 opt-out 标记，daemon 后续不再自动安装。"""
    lnk = _lnk_path()
    if lnk.exists():
        try:
            lnk.unlink()
        except OSError as exc:
            print(f"删除失败: {exc}", file=sys.stderr)
            return 1
        print(f"已移除: {lnk}")
    else:
        print(f"未安装（找不到 {lnk}）")

    _write_marker()
    print("已写 opt-out 标记，daemon 将不再自动安装。")
    print("如需恢复，运行 `vocotype install-send-to`。")
    return 0


def maybe_auto_install() -> None:
    """daemon 启动时调用：在冻结 exe + 未装 + 未 opt-out 三个条件全成立时静默安装。
    任何失败都吞掉，绝不阻塞 daemon 启动。
    """
    if not getattr(sys, "frozen", False):
        return  # 开发模式不动 SendTo
    try:
        lnk = _lnk_path()
        marker = _marker_path()
        if lnk.exists() or marker.exists():
            return  # 已装 或 用户明确 opt-out
        _create_lnk(sys.executable, lnk)
        # flush=True 关键：daemon 启动 stdout 是块缓冲，不立即刷会导致信息丢失（exit 前缓冲未清空）
        print(f"[首次启动] 已自动注册到 Send To 菜单: {lnk.name}", flush=True)
        print("           不需要的话运行 `vocotype uninstall-send-to` 永久关闭", flush=True)
    except Exception as exc:
        logger.debug("auto-install send-to 失败 (已忽略): %s", exc)
