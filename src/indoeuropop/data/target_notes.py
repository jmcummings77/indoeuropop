"""Helpers for semicolon-delimited target note metadata."""

from __future__ import annotations


def target_note_metadata(note: str) -> dict[str, str]:
    """Return key-value metadata parsed from a target note string."""
    metadata: dict[str, str] = {}
    for segment in note.split(";"):
        key, separator, value = segment.strip().partition("=")
        if separator and key.strip() and value.strip():
            metadata[key.strip()] = value.strip()
    return metadata


def target_note_value(note: str, key: str) -> str:
    """Return a target-note metadata value or raise a clear error."""
    normalized_key = key.strip()
    if not normalized_key:
        raise ValueError("target note key must be non-empty")
    metadata = target_note_metadata(note)
    try:
        return metadata[normalized_key]
    except KeyError as error:
        raise ValueError(f"target note missing key: {normalized_key}") from error


def append_target_note_metadata(note: str, metadata: dict[str, str]) -> str:
    """Append stable key-value metadata to a target note string."""
    additions = tuple(
        f"{key}={value}"
        for key, value in metadata.items()
        if key.strip() and value.strip()
    )
    if not additions:
        return note
    if not note.strip():
        return "; ".join(additions)
    return f"{note.strip()}; {'; '.join(additions)}"
