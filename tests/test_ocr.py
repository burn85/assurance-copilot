"""OCR backend checks. Backend tests skip when the backend isn't installed, so
the suite stays green on any machine; where a backend *is* available it is run
for real against a generated image (all-synthetic, no bundled binaries)."""

import pytest

from assurance_copilot.ocr.apple_vision import AppleVisionOCR
from assurance_copilot.ocr.base import select_backend
from assurance_copilot.ocr.tesseract import TesseractOCR

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

# Truetype fonts we can rely on for a legible OCR target (macOS / common Linux).
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size=48):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    pytest.skip("no truetype font available to render a reliable OCR target")


def _text_image(tmp_path, text):
    img = Image.new("RGB", (900, 200), "white")
    ImageDraw.Draw(img).multiline_text((30, 30), text, fill="black", font=_font(), spacing=12)
    p = tmp_path / "evidence.png"
    img.save(p)
    return str(p)


def test_select_backend_explicit_tesseract():
    assert isinstance(select_backend("tesseract"), TesseractOCR)


def test_select_backend_auto_prefers_available():
    from assurance_copilot.ocr.base import OCRBackend

    b = select_backend("auto")
    assert isinstance(b, OCRBackend)  # always returns a backend, never None
    # When any backend is installed, auto must pick a runnable one.
    if AppleVisionOCR().is_available() or TesseractOCR().is_available():
        assert b.is_available()


@pytest.mark.skipif(not AppleVisionOCR().is_available(), reason="Apple Vision not available")
def test_apple_vision_reads_english(tmp_path):
    r = AppleVisionOCR().extract(_text_image(tmp_path, "Access Control Policy APPROVED"))
    assert "APPROVED" in r.text.upper()
    assert r.backend == "apple_vision"


@pytest.mark.skipif(not TesseractOCR().is_available(), reason="Tesseract not available")
def test_tesseract_reads_english(tmp_path):
    r = TesseractOCR().extract(_text_image(tmp_path, "Access Control Policy APPROVED"))
    assert "APPROVED" in r.text.upper()
    assert r.backend == "tesseract"


def test_load_evidence_routes_image_to_ocr(tmp_path):
    if not select_backend("auto").is_available():
        pytest.skip("no OCR backend available")
    from assurance_copilot.cli import _load_evidence

    ev = _load_evidence(_text_image(tmp_path, "APPROVED"), "ISMS-P 2.5.1", "auto")
    assert ev.ocr_backend in ("apple_vision", "tesseract")
    assert ev.text and ev.source == "evidence.png"


def test_load_evidence_reads_text_file_directly(tmp_path):
    from assurance_copilot.cli import _load_evidence

    f = tmp_path / "note.txt"
    f.write_text("plain evidence text", encoding="utf-8")
    ev = _load_evidence(str(f), "ISMS-P 2.5.1", "auto")
    assert ev.text == "plain evidence text"
    assert ev.ocr_backend == ""  # no OCR for text files
