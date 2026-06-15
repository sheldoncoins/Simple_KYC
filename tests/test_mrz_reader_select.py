"""Unit tests for the MRZ-reader candidate selection.

These exercise the pure `_choose_mrz` selector -- the logic that makes OCR
preprocessing *additive* -- without needing Tesseract/OpenCV, so they run in CI.
The OCR itself (PassportEyeMrzReader) stays manual.
"""
from __future__ import annotations

from app.providers.mrz_reader import _choose_mrz, _is_valid
from app.services.mrz_demo import make_mrz


def _valid_pair() -> tuple[str, str]:
    l1, l2 = make_mrz(number="AB1234567")
    return l1, l2


def _break(pair: tuple[str, str]) -> tuple[str, str]:
    """Flip the composite check digit so the pair fails validation."""
    l1, l2 = pair
    last = l2[-1]
    return l1, l2[:-1] + ("0" if last != "0" else "1")


def test_valid_pair_is_valid_precondition() -> None:
    assert _is_valid(_valid_pair()) is True
    assert _is_valid(_break(_valid_pair())) is False


def test_choose_prefers_check_digit_valid_even_if_not_first() -> None:
    valid = _valid_pair()
    invalid = _break(valid)
    # raw read (invalid) first, a preprocessed read (valid) later -> pick valid.
    assert _choose_mrz([None, invalid, valid]) == valid


def test_choose_falls_back_to_first_read_when_none_validate() -> None:
    invalid = _break(_valid_pair())
    other = _break((_valid_pair()[0], _valid_pair()[1]))
    # Nothing validates -> return the first thing that read at all (the raw read),
    # so downstream validation reports the failure rather than silently dropping.
    assert _choose_mrz([None, invalid, other]) == invalid


def test_choose_returns_none_when_nothing_read() -> None:
    assert _choose_mrz([None, None]) is None
    assert _choose_mrz([]) is None
