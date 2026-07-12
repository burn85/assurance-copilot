"""Tesseract OCR backend — the portable, reproducible fallback.

Runs anywhere (Linux/Windows/macOS) via the `pytesseract` wrapper and a local
Tesseract install. It is the default when Apple Vision is unavailable, which
guarantees any reviewer can clone the repo and process image evidence without a
Mac. Trade-off vs. Apple Vision: text is processed locally here too, but
accuracy on noisy scans is typically lower.
"""

from __future__ import annotations

from .base import OCRBackend, OCRResult


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

        # `lang="kor+eng"` handles Korean audit evidence alongside English.
        text = pytesseract.image_to_string(Image.open(image_path), lang="kor+eng")
        return OCRResult(text=text.strip(), backend=self.name, confidence=0.9)
