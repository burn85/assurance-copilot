"""Apple Vision OCR backend — on-device, zero-token text recognition.

Calls Apple's Vision framework directly through pyobjc (VNRecognizeTextRequest),
so sensitive audit evidence never leaves the machine and no vision tokens are
spent. No external binary or compile step — the backend is `pip install
pyobjc-framework-Vision pyobjc-framework-Quartz` on macOS.

Intentionally optional: `is_available()` returns False anywhere the frameworks
or platform are missing, and `select_backend("auto")` then falls back to
Tesseract so the repo stays runnable for any reviewer.
"""

from __future__ import annotations

import platform

from .base import OCRBackend, OCRResult

# Vision text-recognition level: 0 = accurate, 1 = fast.
_LEVEL_ACCURATE = 0
# Prefer Korean then English — ISMS-P evidence is typically Korean.
_LANGUAGES = ["ko-KR", "en-US"]


class AppleVisionOCR(OCRBackend):
    name = "apple_vision"

    def is_available(self) -> bool:
        if platform.system() != "Darwin":
            return False
        try:
            import Quartz  # noqa: F401
            import Vision
        except ImportError:
            return False
        return hasattr(Vision, "VNRecognizeTextRequest")

    def extract(self, image_path: str) -> OCRResult:
        import os

        if not os.path.exists(image_path):
            raise FileNotFoundError(image_path)

        import Quartz
        import Vision
        from Foundation import NSURL

        url = NSURL.fileURLWithPath_(image_path)
        source = Quartz.CGImageSourceCreateWithURL(url, None)
        if source is None:
            raise RuntimeError(f"Could not read image: {image_path}")
        cg_image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
        if cg_image is None:
            raise RuntimeError(f"Could not decode image: {image_path}")

        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(_LEVEL_ACCURATE)
        request.setUsesLanguageCorrection_(True)
        # Only request languages Vision actually supports on this machine, so an
        # older macOS without Korean degrades to English rather than failing.
        supported = _supported_languages(request)
        wanted = [lang for lang in _LANGUAGES if lang in supported] if supported else []
        if wanted:
            request.setRecognitionLanguages_(wanted)

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, {})
        ok, err = handler.performRequests_error_([request], None)
        if not ok:
            raise RuntimeError(f"Vision OCR failed: {err}")

        lines: list[str] = []
        confidences: list[float] = []
        for obs in request.results() or []:
            candidates = obs.topCandidates_(1)
            if not candidates:
                continue
            best = candidates[0]
            lines.append(best.string())
            confidences.append(float(best.confidence()))

        text = "\n".join(lines).strip()
        confidence = round(sum(confidences) / len(confidences), 3) if confidences else 1.0
        return OCRResult(text=text, backend=self.name, confidence=confidence)


def _supported_languages(request) -> list[str]:
    """Recognition languages Vision supports on this machine (may be empty)."""
    import Vision

    try:
        langs, _ = Vision.VNRecognizeTextRequest.\
            supportedRecognitionLanguagesForTextRecognitionLevel_revision_error_(
                _LEVEL_ACCURATE, request.revision(), None
            )
        return list(langs or [])
    except Exception:
        return []
