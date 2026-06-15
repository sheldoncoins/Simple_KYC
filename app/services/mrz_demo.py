"""Build a valid TD3 MRZ for tests/demo (so check digits actually pass)."""
from __future__ import annotations

from app.services.mrz import _check_digit


def make_mrz(*, country="UTO", surname="DOE", given="JOHN",
             number="L898902C3", nationality="UTO", dob="740812",
             sex="M", expiry="320101") -> tuple[str, str]:
    number = (number + "<" * 9)[:9]
    line1 = f"P<{country}{surname}<<{given}".ljust(44, "<")[:44]

    num_cd = _check_digit(number)
    dob_cd = _check_digit(dob)
    exp_cd = _check_digit(expiry)
    personal = "<" * 14
    pers_cd = _check_digit(personal)

    body = f"{number}{num_cd}{nationality}{dob}{dob_cd}{sex}{expiry}{exp_cd}{personal}{pers_cd}"
    composite = number + str(num_cd) + dob + str(dob_cd) + expiry + str(exp_cd) + personal + str(pers_cd)
    comp_cd = _check_digit(composite)
    line2 = (body + str(comp_cd)).ljust(44, "<")[:44]
    return line1, line2
