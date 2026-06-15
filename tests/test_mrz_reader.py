"""The dev MRZ reader extracts two lines and rejects incomplete input."""
from __future__ import annotations

import pytest
from app.providers.mrz_reader import TextMrzReader


def test_reads_two_mrz_lines() -> None:
    line1, line2 = TextMrzReader().read(b"P<UTOLINE1...\nL898902C36UTO...\n")
    assert line1 == "P<UTOLINE1..." and line2 == "L898902C36UTO..."


def test_rejects_incomplete_mrz() -> None:
    with pytest.raises(ValueError):
        TextMrzReader().read(b"only-one-line")
