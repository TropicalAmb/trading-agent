from __future__ import annotations

from io import BytesIO, TextIOWrapper

from scripts import healthcheck


def test_safe_print_replaces_unicode_unsupported_by_console(monkeypatch) -> None:
    buffer = BytesIO()
    stream = TextIOWrapper(buffer, encoding="ascii", errors="strict")
    monkeypatch.setattr(healthcheck.sys, "stdout", stream)
    healthcheck._safe_print("weekend gap: Fri close → Sun open")
    stream.flush()
    assert b"Fri close ? Sun open" in buffer.getvalue()
