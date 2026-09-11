"""Tests for CLI mock and export commands."""

from typer.testing import CliRunner

from edgeport.cli import app

runner = CliRunner()


def test_cli_mock_list() -> None:
    result = runner.invoke(app, ["mock", "--list"])
    assert result.exit_code == 0
    assert "Available Mock Webhook Templates" in result.stdout
    assert "payment_intent.succeeded" in result.stdout
    assert "push" in result.stdout
    assert "orders/create" in result.stdout


def test_cli_mock_print_only() -> None:
    result = runner.invoke(app, ["mock", "stripe", "payment_intent.succeeded", "--print-only"])
    assert result.exit_code == 0
    assert "Mock Webhook Generated" in result.stdout
    assert "stripe-signature" in result.stdout
    assert "pi_3MtwBwLkdIwHu7ix28a3tqPa" in result.stdout


def test_cli_mock_print_only_signed() -> None:
    result = runner.invoke(app, [
        "mock", "github", "push",
        "--secret", "my_secret_token",
        "--print-only",
    ])
    assert result.exit_code == 0
    assert "x-hub-signature-256" in result.stdout
    assert "Signed: Yes (HMAC)" in result.stdout
