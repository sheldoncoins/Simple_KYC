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
from collections.abc import Sequence

from app.services.mrz import validate_td3


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


def _is_valid(pair: tuple[str, str]) -> bool:
    """Does this read pass the ICAO 9303 check digits? (The same deterministic
    validation the service applies downstream -- used here only to *choose* among
    candidate reads.)"""
    return validate_td3(pair[0], pair[1]).valid


def _choose_mrz(
    candidates: Sequence[tuple[str, str] | None],
) -> tuple[str, str] | None:
    """Pick the best read from a list of candidates (in priority order).

    Prefers the first candidate whose check digits validate; if none validate,
    returns the first candidate that read anything at all (so downstream
    validation still reports a meaningful failure on the raw read); if nothing
    read, returns None. This is what makes preprocessing strictly additive: the
    raw read is always a candidate, so a preprocessed result can only *win* by
    validating where the raw read did not -- it can never displace a read that
    already works."""
    reads = [c for c in candidates if c is not None]
    for c in reads:
        if _is_valid(c):
            return c
    return reads[0] if reads else None


class PassportEyeMrzReader(MrzReader):  # pragma: no cover - needs the OCR stack
    """Real OCR via PassportEye + Tesseract. Production seam, not run in CI.

    Reads the raw image first; only if that doesn't yield a check-digit-valid MRZ
    does it retry on preprocessed (grayscale/binarized) variants and take the
    first that validates -- which removes colour security tints and lifts text
    contrast without ever regressing an image the raw read already handled."""

    def read(self, image: bytes) -> tuple[str, str]:
        try:
            import passporteye  # noqa: F401
        except ImportError as exc:  # noqa: TRY003
            raise RuntimeError(
                "PassportEyeMrzReader needs passporteye + tesseract; install them "
                "or use KYC_MRZ_READER=text."
            ) from exc

        raw = self._read_one(image)
        if raw is not None and _is_valid(raw):
            return raw  # clean read -- skip preprocessing entirely (the common case)

        # Raw read failed or didn't validate: try preprocessed variants. The raw
        # read stays in the candidate list, so _choose_mrz falls back to it when
        # nothing validates -> behaviour is never worse than today.
        candidates: list[tuple[str, str] | None] = [raw]
        candidates += [self._read_one(v) for v in self._preprocess_variants(image)]
        chosen = _choose_mrz(candidates)
        if chosen is None:
            raise ValueError("OCR could not locate an MRZ in the image")
        return chosen

    def _read_one(self, image: bytes) -> tuple[str, str] | None:
        """Run PassportEye/Tesseract on one image; None if no MRZ is located."""
        import tempfile

        from passporteye import read_mrz

        with tempfile.NamedTemporaryFile(suffix=_image_suffix(image)) as fh:
            fh.write(image)
            fh.flush()
            mrz = read_mrz(fh.name)
        if mrz is None:
            return None
        return _reconstruct_td3(mrz.to_dict())

    def _preprocess_variants(self, image: bytes) -> list[bytes]:
        """Grayscale/binarized renderings that help OCR on tinted or low-contrast
        scans (e.g. the blue security ghost-image over an Indian passport's MRZ).
        Returns PNG bytes (lossless). Empty if OpenCV is unavailable or the image
        can't be decoded -- in which case read() just uses the raw read."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            return []
        frame = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Otsu drops a uniform colour tint; CLAHE first lifts local contrast for
        # uneven lighting/glare. Plain grayscale is the gentlest fallback.
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        _, clahe_otsu = cv2.threshold(
            clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        out: list[bytes] = []
        for img in (gray, otsu, clahe_otsu):
            ok, buf = cv2.imencode(".png", img)
            if ok:
                out.append(buf.tobytes())
        return out
