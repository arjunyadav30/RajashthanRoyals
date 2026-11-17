"""Accent-insensitive, case-insensitive name normalisation for search."""

from __future__ import annotations

import unicodedata


def normalise_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def compact_name(value: object) -> str:
    return normalise_name(value).replace(" ", "")
