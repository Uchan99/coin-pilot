from __future__ import annotations

from typing import Optional

import pandas as pd


def format_qty(value: float, decimals: int = 6) -> str:
    """Format quantity with trimmed trailing zeros."""
    if pd.isna(value):
        return "N/A"
    text = f"{float(value):,.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_krw(value: float, signed: bool = False) -> str:
    """Format KRW amount with thousand separators."""
    if pd.isna(value):
        return "N/A"
    v = float(value)
    if signed:
        if v > 0:
            return f"+{v:,.0f}"
        if v < 0:
            return f"{v:,.0f}"
        return "0"
    return f"{v:,.0f}"


def format_krw_compact(value: float, signed: bool = False) -> str:
    """
    Compact KRW formatter.
    Example: 8,847,360 -> 884.7만 원
    """
    if pd.isna(value):
        return "N/A"

    v = float(value)
    abs_v = abs(v)
    if abs_v < 10000:
        return format_krw(v, signed=signed)

    compact = abs_v / 10000.0
    text = f"{compact:,.1f}만 원"

    if signed:
        if v > 0:
            return f"+{text}"
        if v < 0:
            return f"-{text}"
        return "0"

    if v < 0:
        return f"-{text}"
    return text


def format_pct(value: float, decimals: int = 2, signed: bool = True) -> str:
    """Format percentage with optional sign and zero without sign."""
    if pd.isna(value):
        return "N/A"
    v = float(value)
    if signed:
        if v > 0:
            return f"+{v:.{decimals}f}%"
        if v < 0:
            return f"{v:.{decimals}f}%"
        return f"{0:.{decimals}f}%"
    return f"{v:.{decimals}f}%"
