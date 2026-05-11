"""Windows desktop integration helpers — file picker, toast, clipboard.

为 F3 热键文件转写工作流提供 3 个工具函数：
- pick_file_dialog(): 调系统原生 OpenFileDialog 选音视频文件
- show_toast():       发 Windows 10/11 toast 通知（best-effort，失败静默）
- copy_to_clipboard(): 把字符串塞进系统剪贴板

实现策略：用 PowerShell 子进程调 .NET / WinRT，避免引入 Tk 或额外 GUI 依赖。
所有调用都带 CREATE_NO_WINDOW，防止控制台一闪。
"""
from __future__ import annotations

import html
import logging
import subprocess
from typing import Optional


logger = logging.getLogger(__name__)

# 不弹 PowerShell 窗口
_CREATE_NO_WINDOW = 0x08000000

_FILE_FILTER = (
    "Audio/Video|"
    "*.wav;*.mp3;*.flac;*.aac;*.m4a;*.ogg;"
    "*.mp4;*.mkv;*.webm;*.mov"
)


def pick_file_dialog(initial_dir: Optional[str] = None) -> Optional[str]:
    """弹出 Windows 原生 OpenFileDialog；用户取消或调用失败返回 None。"""
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms | Out-Null
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Filter = '{_FILE_FILTER}'
$d.Title  = '选择要转写的音视频文件'
$d.InitialDirectory = '{initial_dir or ""}'
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{ $d.FileName }}
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        logger.warning("文件选择器等待用户操作超时")
        return None
    except Exception as exc:
        logger.warning("文件选择器调用失败: %s", exc)
        return None

    path = result.stdout.strip()
    return path or None


def show_toast(title: str, message: str, app_id: str = "VocoType") -> None:
    """通过 PowerShell + WinRT 发系统 toast；失败静默（best-effort）。"""
    title_xml = html.escape(title)
    msg_xml = html.escape(message)
    ps = f"""
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] | Out-Null
$xml = @'
<toast><visual><binding template="ToastText02"><text id="1">{title_xml}</text><text id="2">{msg_xml}</text></binding></visual></toast>
'@
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$t = New-Object Windows.UI.Notifications.ToastNotification $doc
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($t)
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            timeout=5,
            capture_output=True,
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception as exc:
        logger.debug("toast 发送失败（已忽略）: %s", exc)


def copy_to_clipboard(text: str) -> None:
    """把字符串复制到 Windows 剪贴板；失败静默。"""
    try:
        import pyperclip

        pyperclip.copy(text)
    except Exception as exc:
        logger.debug("剪贴板复制失败（已忽略）: %s", exc)
