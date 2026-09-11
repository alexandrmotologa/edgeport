"""Tests for QR code rendering."""

from edgeport.utils.qrcode_gen import generate_data_uri_qr, generate_svg_qr, generate_terminal_qr


def test_generate_svg_qr() -> None:
    svg = generate_svg_qr("https://edgeport.local/tunnel")
    assert svg.startswith("<?xml") or "<svg" in svg
    assert "</svg>" in svg
    assert "xmlns=" in svg


def test_generate_data_uri_qr() -> None:
    uri = generate_data_uri_qr("https://edgeport.local/tunnel")
    assert uri.startswith("data:image/svg+xml")


def test_generate_terminal_qr() -> None:
    term_qr = generate_terminal_qr("https://edgeport.local/tunnel")
    assert len(term_qr) > 50
    # Should contain either ANSI escape sequences or block characters
    assert "\x1b" in term_qr or "\u2588" in term_qr or " " in term_qr
