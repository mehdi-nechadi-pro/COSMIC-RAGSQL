import pytest

from graph import build_targets_query, extract_text_from_content, validate_target_filters
from prompts import UNIVERSAL_ASTRONOMER_PROMPT


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


def test_target_filters_accept_sky_region_filters():
    cleaned = validate_target_filters({
        "ra_min": 350,
        "ra_max": 10,
        "dec_min": -20,
        "dec_max": 35,
    })

    assert cleaned["ra_min"] == 350
    assert cleaned["ra_max"] == 10
    assert cleaned["dec_min"] == -20
    assert cleaned["dec_max"] == 35


def test_extract_text_from_content_handles_mixed_block_shapes():
    content = [
        {"type": "text", "text": '```json\n{"chat_reply": "ok", "targets": [], "bool_sun": false, "constellations_IAU": []}\n```'},
        {"type": "tool_call", "name": "search_targets", "args": {"type": "Nebula"}},
    ]

    text = extract_text_from_content(content)

    assert "chat_reply" in text
    assert "targets" in text
    assert "Nebula" not in text or "Nebula" in text


def test_astronomer_prompt_formats_json_examples():
    prompt = UNIVERSAL_ASTRONOMER_PROMPT.format(
        schema="schema",
        city="Paris",
        hour="2026-09-25T20:00:00+00:00",
        mission="Que voir ce soir ?",
        sql_where={"error": "", "sql_where": ""},
        sun_error="",
        solar_system_objects={"observables": []},
    )

    assert '{"type": "Nebula"' in prompt
    assert '{"name": "M8"' in prompt


def test_build_targets_query_applies_visibility_constraint():
    engine = __import__('sqlalchemy').create_engine('sqlite://')
    query = build_targets_query(
        {"type": "Nebula", "limit": 5},
        engine,
        visibility_sql="IS_VISIBLE(ra, dec, 48.8, 12.5, 5) = 1",
    )

    sql = str(query)
    assert 'IS_VISIBLE' in sql
    assert 'WHERE' in sql


def test_build_targets_query_applies_sky_region_filters():
    engine = __import__('sqlalchemy').create_engine('sqlite://')
    query = build_targets_query(
        {"ra_min": 350, "ra_max": 10, "dec_min": -20, "dec_max": 35, "limit": 5},
        engine,
    )

    sql = str(query)
    assert 'ra >= ' in sql
    assert 'ra <= ' in sql
    assert 'dec >= ' in sql
    assert 'dec <= ' in sql
    assert ' OR ' in sql
