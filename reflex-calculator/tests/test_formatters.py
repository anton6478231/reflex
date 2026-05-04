"""Тесты форматирования для KPI и экспорта."""
from utils.formatters import format_currency, format_currency_compact


def test_format_currency_compact_millions():
    assert "млн" in format_currency_compact(3_360_000)
    assert "3,36" in format_currency_compact(3_360_000)


def test_format_currency_compact_thousands():
    s = format_currency_compact(141_000)
    assert "тыс" in s
    assert "141" in s


def test_format_currency_compact_small_uses_full():
    assert format_currency_compact(8_500) == format_currency(8_500)


def test_format_currency_compact_negative():
    s = format_currency_compact(-141_000)
    assert s.startswith("-")
