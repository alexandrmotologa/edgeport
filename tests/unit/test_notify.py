"""Tests for desktop notification dispatcher."""

from edgeport.client.notify import NotificationManager, send_desktop_notification


def test_send_desktop_notification_non_blocking() -> None:
    # Must run without throwing an exception or blocking
    send_desktop_notification("EdgePort Test", "Notification dispatched successfully")


def test_notification_manager() -> None:
    manager = NotificationManager(enabled=True)
    manager.on_transaction("POST", "/webhooks/stripe", 200, "Stripe")
    manager.on_error("Test failure message")

    manager_disabled = NotificationManager(enabled=False)
    manager_disabled.on_transaction("GET", "/ping", 200)
