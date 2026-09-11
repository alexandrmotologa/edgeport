"""Cross-platform QR code generator for terminal and web rendering."""

import io
import sys

import segno


def generate_svg_qr(content: str, scale: int = 6, border: int = 2) -> str:
    """Generates an SVG representation of the QR code."""
    qr = segno.make(content, micro=False)
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=scale, border=border, light="#ffffff", dark="#111827")
    return buf.getvalue().decode("utf-8")


def generate_data_uri_qr(content: str, scale: int = 6) -> str:
    """Generates a data URI SVG representation of the QR code."""
    qr = segno.make(content, micro=False)
    return qr.svg_data_uri(scale=scale, light="#ffffff", dark="#111827")


def generate_terminal_qr(content: str, border: int = 1) -> str:
    """Generates an ANSI terminal representation of the QR code.

    Uses Unicode half-block characters when the output encoding supports it,
    or falls back safely to ANSI inverse video double spaces.
    """
    qr = segno.make(content, micro=False)

    # Check if current encoding can handle unicode half-blocks
    stdout_encoding = (sys.stdout.encoding or "utf-8").lower()
    supports_utf8 = "utf" in stdout_encoding or "65001" in stdout_encoding

    if supports_utf8:
        try:
            out = io.StringIO()
            qr.terminal(out=out, compact=True, border=border)
            return out.getvalue()
        except Exception:
            pass

    # Safe ANSI inverse spaces fallback (works across all Windows/Unix shells)
    matrix = qr.matrix
    # Add border
    width = len(matrix[0]) + (border * 2)
    quiet_row = tuple([0] * width)

    full_matrix = []
    for _ in range(border):
        full_matrix.append(quiet_row)
    for row in matrix:
        full_matrix.append(tuple([0] * border + list(row) + [0] * border))
    for _ in range(border):
        full_matrix.append(quiet_row)

    lines = []
    for row in full_matrix:
        # Val 1 = dark pixel, 0 = light pixel
        # Use white background for light, black background for dark
        line_parts = ["\x1b[40m  \x1b[0m" if val else "\x1b[47m  \x1b[0m" for val in row]
        lines.append("".join(line_parts))

    return "\n".join(lines)
