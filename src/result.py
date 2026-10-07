"""Structured result returned by the conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ConversionResult:
    success: bool
    message: str
    output_path: Optional[str] = None
    engine: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def as_tuple(self):
        """Legacy ``(success, message)`` form."""
        return self.success, self.message
