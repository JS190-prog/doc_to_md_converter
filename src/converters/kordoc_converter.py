"""kordoc CLI wrapper.

kordoc (https://github.com/chrisryugj/kordoc) is a Node.js based Korean
document parser with strong table reconstruction (merged cells, nested
tables) and deep HWP format coverage (HWP 3.x/5.x, HWPX, distribution HWP).
Installed globally via: npm install -g kordoc pdfjs-dist@5
(pdfjs-dist v6 is incompatible with kordoc 3.x — keep the v5 pin.)
"""

import os
import shutil
import subprocess
import tempfile

_kordoc_cmd = None


def _find_kordoc():
    """Locate the kordoc CLI shim, caching the result."""
    global _kordoc_cmd
    if _kordoc_cmd is not None:
        return _kordoc_cmd

    exe = shutil.which("kordoc") or shutil.which("kordoc.cmd")
    if exe is None:
        candidate = os.path.join(
            os.environ.get("APPDATA", ""), "npm", "kordoc.cmd"
        )
        if os.path.isfile(candidate):
            exe = candidate
    if exe is None:
        raise FileNotFoundError(
            "kordoc CLI not found. Install with: npm install -g kordoc pdfjs-dist@5"
        )
    _kordoc_cmd = exe
    return exe


def convert_with_kordoc(file_path):
    """Convert a document to markdown via the kordoc CLI.

    Returns the markdown string. Raises on CLI failure or empty output
    (e.g. scanned PDFs without a text layer) so router fallbacks engage.
    """
    exe = _find_kordoc()

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "kordoc_out.md")
        result = subprocess.run(
            [exe, os.path.abspath(file_path), "-o", out_path, "--silent"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"kordoc failed (exit {result.returncode}): {stderr[:500]}")
        if not os.path.isfile(out_path):
            raise RuntimeError("kordoc produced no output file")
        with open(out_path, encoding="utf-8") as f:
            md = f.read()

    if not md.strip():
        raise RuntimeError("kordoc produced empty output (image-based document?)")
    return md
