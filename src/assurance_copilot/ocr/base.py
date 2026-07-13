"""Pluggable OCR backend interface.

Audit evidence is frequently submitted as screenshots and scanned documents, so
OCR is a real part of the ingestion path — and it is the part where a design
choice actually matters:

- Confidentiality: audit evidence is sensitive client data. An *on-device* OCR
  backend (Apple Vision) keeps that data off any third-party API.
- Cost: on-device OCR is zero-token, versus sending every screenshot to a
  multimodal model.
- Portability: a reviewer on Linux/Windows must still be able to run the repo,
  so a Tesseract backend is the reproducible fallback.

Rather than hard-wire one of these, we program to an interface and select the
backend at runtime. Choosing *when* to use the local, private, zero-token path
versus a portable fallback is exactly the "when to automate vs. surface / build
vs. buy" judgment the system is meant to embody.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OCRResult:
    text: str
    backend: str
    confidence: float = 1.0


class OCRBackend(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap check for whether this backend can run in the current env."""

    @abstractmethod
    def extract(self, image_path: str) -> OCRResult:
        """Extract text from an image or scanned document at `image_path`."""


def select_backend(prefer: str = "auto") -> OCRBackend:
    """Pick an OCR backend.

    prefer="auto"          -> Apple Vision if available, else Tesseract
    prefer="apple_vision"  -> Apple Vision (raises if unavailable)
    prefer="tesseract"     -> Tesseract
    """
    from .apple_vision import AppleVisionOCR
    from .tesseract import TesseractOCR

    if prefer == "apple_vision":
        b = AppleVisionOCR()
        if not b.is_available():
            raise RuntimeError(
                "Apple Vision backend requested but unavailable (needs macOS + "
                "`pip install pyobjc-framework-Vision pyobjc-framework-Quartz`)."
            )
        return b

    if prefer == "tesseract":
        return TesseractOCR()

    # auto
    apple = AppleVisionOCR()
    if apple.is_available():
        return apple
    return TesseractOCR()
