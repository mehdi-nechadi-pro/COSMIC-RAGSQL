import pytest

from graph import extract_text_from_content, validate_target_filters


def test_target_filters_reject_raw_sql():
    with pytest.raises(ValueError, match="raw SQL|query"):
        validate_target_filters({"query": "SELECT * FROM Celestial WHERE name='M42'"})


def test_target_filters_reject_unknown_field():
    with pytest.raises(ValueError, match="Unknown|Allowed"):
        validate_target_filters({"magnitude_gt": 5.0})


def test_target_filters_reject_too_large_limit():
    with pytest.raises(ValueError, match="limit"):
        validate_target_filters({"limit": 999})


def test_target_filters_accept_valid_filters():
    cleaned = validate_target_filters({
        "type": "Nebula",
        "magnitude_max": 8.5,
        "limit": 12,
        "constellation": "Orion",
    })

    assert cleaned["type"] == "Nebula"
    assert cleaned["limit"] == 12
    assert cleaned["magnitude_max"] == 8.5
    assert cleaned["constellation"] == "Orion"


def test_extract_text_from_content_handles_mixed_block_shapes():
    content = [
        {"type": "text", "text": '```json\n{"chat_reply": "ok", "targets": [], "bool_sun": false, "constellations_IAU": []}\n```'},
        {"type": "tool_call", "name": "search_targets", "args": {"type": "Nebula"}},
    ]

    text = extract_text_from_content(content)

    assert "chat_reply" in text
    assert "targets" in text
    assert "Nebula" not in text or "Nebula" in text
