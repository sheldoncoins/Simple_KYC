"""Read the passport MRZ from an uploaded document image.

This is the *extraction* step only -- pulling the two TD3 lines off the image.
The integrity check (ICAO 9303 check digits, ``services/mrz.validate_td3``)
stays deterministic and is applied to whatever these readers return, so a bad or
spoofed read still fails validation.

* ``TextMrzReader`` -- the dev/test reader: treats the upload bytes as UTF-8
  text containing the two MRZ lines. Deterministic and dependency-free, so the
  upload pipeline can be exercised end-to-end without a real OCR stack.
* ``PassportEyeMrzReader`` -- the production seam: real OCR over the image
  (PassportEye + Tesseract). Imported lazily so the dependency is only needed
  when this reader is selected (``KYC_MRZ_READER=ocr``).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod


class MrzReader(ABC):
    @abstractmethod
    def read(self, image: bytes) -> tuple[str, str]:
        """Return the two MRZ lines (TD3) extracted from ``image``."""


class TextMrzReader(MrzReader):
    def read(self, image: bytes) -> tuple[str, str]:
        lines = [ln.strip() for ln in image.decode("utf-8", "ignore").splitlines() if ln.strip()]
        if len(lines) < 2:
            raise ValueError("could not read two MRZ lines from the upload")
        return lines[0], lines[1]


def _image_suffix(image: bytes) -> str:
    """Pick a temp-file extension matching the bytes so the image loader uses the
    right decoder. (A wrong extension, e.g. ``.img``, makes imageio try ITK.)"""
    if image[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return ".jpg"


def _clean(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9<]", "<", (value or "").upper())


def _reconstruct_td3(d: dict) -> tuple[str, str]:
    """Rebuild canonical 44-char TD3 lines from PassportEye's parsed fields.

    PassportEye uses the printed check digits to correct OCR slips, so its parsed
    fields are more reliable than the raw OCR text. We re-encode them into the two
    MRZ lines; ``validate_td3`` then re-verifies the check digits independently."""
    doc = (d.get("type") or "P<")[:2].ljust(2, "<")
    country = _clean(d.get("country"))[:3].ljust(3, "<")
    surname = "<".join(re.sub(r"[^A-Z ]", " ", (d.get("surname") or "").upper()).split())
    given = "<".join(re.sub(r"[^A-Z ]", " ", (d.get("names") or "").upper()).split())
    name = (f"{surname}<<{given}" if given else surname)[:39].ljust(39, "<")
    line1 = (doc + country + name)[:44].ljust(44, "<")

    number = _clean(d.get("number"))[:9].ljust(9, "<")
    nationality = _clean(d.get("nationality"))[:3].ljust(3, "<")
    personal = _clean(d.get("personal_number"))[:14].ljust(14, "<")
    line2 = (
        number + str(d.get("check_number", "<"))
        + nationality + (d.get("date_of_birth") or "")[:6]
        + str(d.get("check_date_of_birth", "<")) + (d.get("sex") or "<")[:1]
        + (d.get("expiration_date") or "")[:6] + str(d.get("check_expiration_date", "<"))
        + personal + str(d.get("check_personal_number", "<"))
        + str(d.get("check_composite", "<"))
    )
    return line1, line2[:44].ljust(44, "<")


class PassportEyeMrzReader(MrzReader):  # pragma: no cover - needs the OCR stack
    """Real OCR via PassportEye + Tesseract. Production seam, not run in CI."""

    def read(self, image: bytes) -> tuple[str, str]:
        try:
            import tempfile

            from passporteye import read_mrz
        except ImportError as exc:  # noqa: TRY003
            raise RuntimeError(
                "PassportEyeMrzReader needs passporteye + tesseract; install them "
                "or use KYC_MRZ_READER=text."
            ) from exc
        with tempfile.NamedTemporaryFile(suffix=_image_suffix(image)) as fh:
            fh.write(image)
            fh.flush()
            mrz = read_mrz(fh.name)
        if mrz is None:
            raise ValueError("OCR could not locate an MRZ in the image")
        return _reconstruct_td3(mrz.to_dict())
