"""Tests for semicolon-delimited target-note metadata helpers."""

import pytest

from indoeuropop.data.target_notes import (
    append_target_note_metadata,
    target_note_metadata,
    target_note_value,
)


def test_target_note_metadata_parses_key_value_segments() -> None:
    """Note parsing should keep only non-empty key-value metadata segments."""
    metadata = target_note_metadata(
        "requested_group_id=Group A; loose text; empty= ; =missing; source=steppe"
    )

    assert metadata == {
        "requested_group_id": "Group A",
        "source": "steppe",
    }


def test_target_note_value_returns_requested_metadata() -> None:
    """A note metadata lookup should trim the requested key before matching."""
    value = target_note_value("requested_group_id=Group A", " requested_group_id ")

    assert value == "Group A"


def test_target_note_value_rejects_empty_or_missing_keys() -> None:
    """Note metadata lookup errors should explain empty and missing keys."""
    with pytest.raises(ValueError, match="target note key"):
        target_note_value("requested_group_id=Group A", " ")
    with pytest.raises(ValueError, match="target note missing key: missing"):
        target_note_value("requested_group_id=Group A", "missing")


def test_append_target_note_metadata_preserves_existing_note_text() -> None:
    """Metadata appending should preserve useful text and skip blank additions."""
    note = append_target_note_metadata(
        "requested_group_id=Group A",
        {"parent_region": "central_europe", "blank": " ", "": "ignored"},
    )

    assert note == "requested_group_id=Group A; parent_region=central_europe"
    assert append_target_note_metadata("", {"parent_region": "central_europe"}) == (
        "parent_region=central_europe"
    )
    assert append_target_note_metadata("existing", {"blank": ""}) == "existing"
