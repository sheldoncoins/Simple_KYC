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


class PassportEyeMrzReader(MrzReader):  # pragma: no cover - needs OCR stack
    """Real OCR via PassportEye/Tesseract. Production seam, not run in CI."""

    def read(self, image: bytes) -> tuple[str, str]:
        try:
            import tempfile

            from passporteye import read_mrz
        except ImportError as exc:  # noqa: TRY003
            raise RuntimeError(
                "PassportEyeMrzReader needs passporteye + tesseract; install them "
                "or use KYC_MRZ_READER=text."
            ) from exc
        with tempfile.NamedTemporaryFile(suffix=".img") as fh:
            fh.write(image)
            fh.flush()
            mrz = read_mrz(fh.name)
        if mrz is None:
            raise ValueError("OCR could not locate an MRZ in the image")
        lines = mrz.aux["text"].splitlines()
        if len(lines) < 2:
            raise ValueError("OCR returned an incomplete MRZ")
        return lines[0].strip(), lines[1].strip()
