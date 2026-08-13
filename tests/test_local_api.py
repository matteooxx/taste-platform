from __future__ import annotations

import tempfile
from pathlib import Path

from local_api import TasteStore, validate_item


def test_profile_and_recommendations() -> None:
    errors, item = validate_item(
        {
            "item_name": "Example Mystery",
            "item_type": "show",
            "rating": 5,
            "notes": "Dense and atmospheric",
            "tags": ["mystery", "drama"],
        }
    )
    assert errors == {}

    with tempfile.TemporaryDirectory() as tmp:
        store = TasteStore(Path(tmp) / "taste.db")
        store.upsert("user", item)
        history = store.history("user")
        recommendations = store.recommendations("user", "show")

    assert history[0]["item_name"] == "Example Mystery"
    assert recommendations
    assert "mystery" in recommendations[0]["tags"]


def test_validation_rejects_unknown_type() -> None:
    errors, _ = validate_item(
        {
            "item_name": "Example",
            "item_type": "book",
            "rating": 4,
            "tags": [],
        }
    )
    assert "item_type" in errors
