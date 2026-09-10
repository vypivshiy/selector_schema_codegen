"""Rust target backend (dom_query + serde)."""

from ssc_codegen.targets.rust.visitor import RustVisitor

RUST_CONVERTER = RustVisitor()

__all__ = ["RUST_CONVERTER", "RustVisitor"]
