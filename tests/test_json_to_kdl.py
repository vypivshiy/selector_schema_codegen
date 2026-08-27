import json

from typer.testing import CliRunner

from ssc_codegen.json_to_kdl import json_to_kdl
from ssc_codegen.main import app


def test_json_to_kdl_generates_nested_definitions() -> None:
    source = json_to_kdl(
        {
            "user": {"id": 1, "profile": {"display-name": "Ann"}},
            "tags": ["one", "two"],
        }
    )

    assert source == (
        "json JsonResponseUserProfile {\n"
        '    display_name str "display-name"\n'
        "}\n\n"
        "json JsonResponseUser {\n"
        "    id int\n"
        "    profile JsonResponseUserProfile\n"
        "}\n\n"
        "json JsonResponse {\n"
        "    user JsonResponseUser\n"
        "    tags (array)str\n"
        "}\n"
    )


def test_json_to_kdl_marks_unknown_arrays() -> None:
    source = json_to_kdl({"tags": [1, "x"], "empty": [], "value": None})

    assert "tags (array)null @skip // int, str" in source
    assert "empty (array)null @skip // empty array" in source
    assert "value nil // unknown real type" in source


def test_json_to_kdl_root_array_uses_item_schema() -> None:
    source = json_to_kdl([{"id": 1}])

    assert source == "(array)json JsonResponseItem {\n    id int\n}\n"


def test_json_to_kdl_cli_writes_and_requires_confirmation(tmp_path) -> None:
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.kdl"
    input_file.write_text(json.dumps({"id": 1}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app, ["json-to-kdl", str(input_file), "-o", str(output_file)]
    )
    assert result.exit_code == 0, result.output
    assert "id int" in output_file.read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        ["json-to-kdl", str(input_file), "-o", str(output_file)],
        input="n\n",
    )
    assert result.exit_code == 0
    assert "Output not written." in result.output
