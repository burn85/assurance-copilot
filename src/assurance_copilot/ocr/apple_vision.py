"""Apple Vision OCR backend — on-device, zero-token text recognition.

Wraps the `macvis` binary from mac-local-vision
(https://github.com/junmo-kim/mac-local-vision), which exposes Apple's Vision
framework OCR as a single Swift binary. Runs entirely on-device on Apple
Silicon + macOS 26+, so sensitive audit evidence never leaves the machine and
no vision tokens are spent.

This backend is intentionally optional: `is_available()` returns False anywhere
the binary or platform is missing, and `select_backend("auto")` then falls back
to Tesseract so the repo stays runnable for any reviewer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from .base import OCRBackend, OCRResult

# Override with e.g. MACVIS_BIN=/path/to/macvis if it is not on PATH.
MACVIS_BIN = os.environ.get("MACVIS_BIN", "macvis")


class AppleVisionOCR(OCRBackend):
    name = "apple_vision"

    def is_available(self) -> bool:
        if shutil.which(MACVIS_BIN) is None and not os.path.exists(MACVIS_BIN):
            return False
        try:
            # `macvis doctor` reports whether Vision is usable on this machine.
            out = subprocess.run(
                [MACVIS_BIN, "doctor"],
                capture_output=True, text=True, timeout=15,
            )
            return out.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def extract(self, image_path: str) -> OCRResult:
        if not os.path.exists(image_path):
            raise FileNotFoundError(image_path)
        # `macvis ocr <image> --json` returns recognized text (see repo docs).
        proc = subprocess.run(
            [MACVIS_BIN, "ocr", image_path, "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"macvis ocr failed: {proc.stderr.strip()}")

        text, confidence = _parse_macvis_json(proc.stdout)
        return OCRResult(text=text, backend=self.name, confidence=confidence)


def _parse_macvis_json(stdout: str) -> tuple[str, float]:
    """Parse macvis JSON output defensively.

    The exact schema is pinned when the binary is installed; we read the common
    fields and fall back to raw stdout so a schema tweak never hard-crashes.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout.strip(), 1.0

    if isinstance(data, dict):
        if "text" in data:
            return str(data["text"]).strip(), float(data.get("confidence", 1.0))
        if "lines" in data and isinstance(data["lines"], list):
            lines = [str(l.get("text", l)) if isinstance(l, dict) else str(l)
                     for l in data["lines"]]
            return "\n".join(lines).strip(), 1.0
    if isinstance(data, list):
        return "\n".join(str(x) for x in data).strip(), 1.0
    return str(data).strip(), 1.0
