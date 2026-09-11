"""Desktop notification helper for incoming webhook and error events."""

import logging
import os
import platform
import subprocess
import threading

logger = logging.getLogger("edgeport.notify")


def _run_subprocess_safe(cmd: list[str]) -> None:
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        logger.debug("Desktop notification dispatch failed: %s", exc)


def send_desktop_notification(title: str, message: str) -> None:
    """Sends a desktop notification asynchronously without blocking the main event loop."""
    system = platform.system()

    def _notify() -> None:
        safe_title = title.replace('"', '\\"')
        safe_msg = message.replace('"', '\\"')

        if system == "Darwin":
            cmd = [
                "osascript",
                "-e",
                f'display notification "{safe_msg}" with title "{safe_title}"',
            ]
            _run_subprocess_safe(cmd)
        elif system == "Linux":
            cmd = ["notify-send", title, message]
            _run_subprocess_safe(cmd)
        elif system == "Windows":
            # Use PowerShell toast/balloon notification
            ps_script = (
                "[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
                "$obj = New-Object System.Windows.Forms.NotifyIcon; "
                "$obj.Icon = [System.Drawing.SystemIcons]::Information; "
                f"$obj.BalloonTipTitle = '{safe_title}'; "
                f"$obj.BalloonTipText = '{safe_msg}'; "
                "$obj.Visible = $True; "
                "$obj.ShowBalloonTip(2000)"
            )
            cmd = [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ]
            _run_subprocess_safe(cmd)

    thread = threading.Thread(target=_notify, daemon=True, name="edgeport-notifier")
    thread.start()


class NotificationManager:
    """Manages notifications for tunnel events."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled or os.getenv("EDGEPORT_NOTIFY", "").lower() in ("1", "true", "yes")

    def on_transaction(
        self, method: str, path: str, status: int, provider: str | None = None
    ) -> None:
        if not self.enabled:
            return

        title = f"EdgePort [{provider or 'Webhook'}]"
        message = f"{method} {path} -> {status}"
        send_desktop_notification(title=title, message=message)

    def on_error(self, message: str) -> None:
        if not self.enabled:
            return
        send_desktop_notification(title="EdgePort Error", message=message)
