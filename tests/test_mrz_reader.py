"""The dev MRZ reader extracts two lines and rejects incomplete input."""
from __future__ import annotations

import pytest
from app.providers.mrz_reader import TextMrzReader, _image_suffix, _reconstruct_td3
from app.services.mrz import validate_td3


def test_reads_two_mrz_lines() -> None:
    line1, line2 = TextMrzReader().read(b"P<UTOLINE1...\nL898902C36UTO...\n")
    assert line1 == "P<UTOLINE1..." and line2 == "L898902C36UTO..."


def test_rejects_incomplete_mrz() -> None:
    with pytest.raises(ValueError):
        TextMrzReader().read(b"only-one-line")


def test_image_suffix_detects_format() -> None:
    assert _image_suffix(b"\xff\xd8\xff\xe0rest") == ".jpg"
    assert _image_suffix(b"\x89PNG\r\n\x1a\nrest") == ".png"


def test_reconstruct_td3_from_parsed_fields_validates() -> None:
    # The shape PassportEye's to_dict() returns (check-digit-corrected).
    fields = {
        "type": "P<", "country": "UTO", "number": "L898902C3", "check_number": "6",
        "nationality": "UTO", "date_of_birth": "740812", "check_date_of_birth": "2",
        "sex": "M", "expiration_date": "320101", "check_expiration_date": "5",
        "personal_number": "<<<<<<<<<<<<<<", "check_personal_number": "0",
        "check_composite": "4", "surname": "DOE", "names": "JOHN",
    }
    line1, line2 = _reconstruct_td3(fields)
    assert len(line1) == 44 and len(line2) == 44
    result = validate_td3(line1, line2)
    assert result.valid, result.failed_checks
    assert result.extracted["surname"] == "DOE"
    assert result.extracted["passport_number"] == "L898902C3"

