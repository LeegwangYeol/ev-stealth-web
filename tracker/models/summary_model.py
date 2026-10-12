"""tracker/models/summary_model.py - Modular summary model definition and re-export.

Provides NationwideSummary with strict NaN/Inf guards and non-negative integer coercion.
"""

from __future__ import annotations

from tracker.subsidy_models import NationwideSummary

__all__ = ["NationwideSummary"]
