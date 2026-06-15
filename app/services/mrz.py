"""Passport MRZ validation -- ICAO 9303 TD3 (two lines x 44 chars).

This replaces document-authenticity ML for our scope. It cannot detect a
high-quality forgery of a *valid* number, but it deterministically rejects
fabricated/typo'd passport numbers, dates, and tampered fields by recomputing
the standard check digits. Free, offline, no vendor.

Line 2 layout (positions are 0-indexed):
   0-8   passport number (9)
   9     passport number check digit
   10-12 nationality (3)
   13-18 date of birth YYMMDD (6)
   19    dob check digit
   20    sex
   21-26 expiry YYMMDD (6)
   27    expiry check digit
   28-41 personal number (14)
   42    personal number check digit
   43    composite check digit
"""
from __future__ import annotations

from dataclasses import dataclass

_VALUES = {**{str(d): d for d in range(10)},
           **{chr(ord("A") + i): 10 + i for i in range(26)},
           "<": 0}
_WEIGHTS = (7, 3, 1)


def _check_digit(field: str) -> int:
    total = 0
    for i, ch in enumerate(field):
        if ch not in _VALUES:
            return -1  # illegal char -> impossible check digit, forces failure
        total += _VALUES[ch] * _WEIGHTS[i % 3]
    return total % 10


@dataclass
class MrzResult:
    valid: bool
    extracted: dict
    failed_checks: list[str]


def validate_td3(line1: str, line2: str) -> MrzResult:
    failed: list[str] = []
    line1 = line1.rstrip("\n")
    line2 = line2.rstrip("\n")

    if len(line1) != 44 or len(line2) != 44:
        return MrzResult(False, {}, ["line_length"])
    if not line1.startswith("P"):
        failed.append("not_passport")

    issuing_country = line1[2:5].replace("<", "")
    names = line1[5:].split("<<", 1)
    surname = names[0].replace("<", " ").strip()
    given = (names[1].replace("<", " ").strip() if len(names) > 1 else "")

    passport_number = line2[0:9]
    nationality = line2[10:13].replace("<", "")
    dob = line2[13:19]
    sex = line2[20]
    expiry = line2[21:27]
    personal_number = line2[28:42]

    checks = {
        "passport_number": (passport_number, line2[9]),
        "dob": (dob, line2[19]),
        "expiry": (expiry, line2[27]),
        "personal_number": (personal_number, line2[42]),
    }
    for name, (field, expected) in checks.items():
        if str(_check_digit(field)) != expected:
            failed.append(f"check_{name}")

    composite = (line2[0:10] + line2[13:20] + line2[21:28] + line2[28:43])
    if str(_check_digit(composite)) != line2[43]:
        failed.append("check_composite")

    extracted = {
        "type": "passport",
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given,
        "passport_number": passport_number.replace("<", ""),
        "nationality": nationality,
        "date_of_birth": dob,
        "sex": sex,
        "expiry": expiry,
    }
    return MrzResult(valid=not failed, extracted=extracted, failed_checks=failed)
