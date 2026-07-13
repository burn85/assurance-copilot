"""Tesseract OCR backend — the portable, reproducible fallback.

Runs anywhere (Linux/Windows/macOS) via the `pytesseract` wrapper and a local
Tesseract install. It is the default when Apple Vision is unavailable, which
guarantees any reviewer can clone the repo and process image evidence without a
Mac. Trade-off vs. Apple Vision: text is processed locally here too, but
accuracy on noisy scans is typically lower.
"""

from __future__ import annotations

import os

from .base import OCRBackend, OCRResult

# Korean audit evidence alongside English; override with TESSERACT_LANG.
# Falls back to "eng" if the requested language data is not installed.
_DEFAULT_LANG = os.environ.get("TESSERACT_LANG", "kor+eng")


class TesseractOCR(OCRBackend):
    name = "tesseract"

    def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError:
            return False
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract(self, image_path: str) -> OCRResult:
        import pytesseract
        from PIL import Image

        image = Image.open(image_path)
        try:
            text = pytesseract.image_to_string(image, lang=_DEFAULT_LANG)
        except pytesseract.TesseractError:
            # Requested language data missing (e.g. no `kor`): degrade to English
            # rather than crash, so the repo stays runnable on a bare install.
            text = pytesseract.image_to_string(image, lang="eng")
        return OCRResult(text=text.strip(), backend=self.name, confidence=0.9)
