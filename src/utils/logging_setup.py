"""Central logging configuration shared by the GUI, CLI and batch scripts."""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level=logging.INFO):
    """Idempotent root logger setup (stderr)."""
    root = logging.getLogger()
    if not any(getattr(h, "_doc2md", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT, "%H:%M:%S"))
        handler._doc2md = True
        root.addHandler(handler)
    root.setLevel(level)


class CallbackHandler(logging.Handler):
    """Forward log records to a callable (e.g. a GUI log pane)."""

    def __init__(self, callback, level=logging.INFO):
        super().__init__(level)
        self._callback = callback
        self.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    def emit(self, record):
        try:
            self._callback(self.format(record))
        except Exception:
            self.handleError(record)
