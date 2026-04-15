from __future__ import annotations

from ssc_codegen import parse_ast
from ssc_codegen.converters.go_goquery import GO_GOQUERY_CONVERTER


def test_go_goquery_convert_all_includes_core_file(tmp_path):
    schema = tmp_path / "sample.kdl"
    schema.write_text(
        """
struct Sample {
    title { css \"h1\"; text }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    module = parse_ast(path=str(schema))
    files = GO_GOQUERY_CONVERTER.convert_all(module, package="scraper")

    assert "" in files
    assert "sscgen_core.go" in files

    main_go = files[""]
    core_go = files["sscgen_core.go"]

    assert "package scraper" in main_go
    assert "package scraper" in core_go
    assert "type Sample struct" in main_go
    assert "type SampleType struct {" in main_go
    assert 'Title string `json:"title"`' in main_go
    assert "func NewSample(document string) *Sample" in main_go
    assert "func (sample *Sample) _parseTitle(v any) string {" in main_go
    assert "func (sample *Sample) Parse() SampleType {" in main_go
