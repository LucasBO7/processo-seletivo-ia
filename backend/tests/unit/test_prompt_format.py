from app.graph.prompts.json_format import compact_json


def test_prompt_json_uses_utf8_without_optional_whitespace() -> None:
    assert compact_json({"items": ["mínimo", 1]}) == '{"items":["mínimo",1]}'
