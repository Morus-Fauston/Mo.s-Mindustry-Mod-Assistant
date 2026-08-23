"""Core JSON draft parsing, formatting and issue-location behavior."""

from app.core.json_draft import format_json_draft, locate_path_line, parse_json_object


def test_parse_json_object_accepts_a_json_object_only():
    result = parse_json_object('{"type": "Wall", "health": 100}')

    assert result.data == {"type": "Wall", "health": 100}
    assert result.error is None


def test_parse_json_object_keeps_invalid_draft_out_of_data():
    result = parse_json_object('{"type":')

    assert result.data is None
    assert result.error


def test_format_json_draft_preserves_semantics_and_refuses_invalid_source():
    formatted, error = format_json_draft('{"health":100,"type":"Wall"}')

    assert error is None
    assert formatted == '{\n  "health": 100,\n  "type": "Wall"\n}\n'

    unchanged, error = format_json_draft('{"health":')
    assert unchanged == '{"health":'
    assert error


def test_locate_path_line_prefers_a_nested_key_over_the_top_level_key():
    source = """{
  "weapons": [
    {
      "bullet": {
        "damage": 25
      }
    }
  ]
}"""

    location = locate_path_line(source, "weapons[0].bullet.damage")

    assert location.line == 5
    assert location.is_exact


def test_locate_path_line_falls_back_to_the_top_level_key_when_nested_key_is_ambiguous():
    source = """{
  "weapons": [
    {"damage": 10},
    {"damage": 20}
  ]
}"""

    location = locate_path_line(source, "weapons[9].damage")

    assert location.line == 2
    assert not location.is_exact
