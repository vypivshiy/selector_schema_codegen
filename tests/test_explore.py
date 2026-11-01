"""Tests for the redesigned HTML context distillation and reconnaissance engine (`ssc-gen scout`).

Covers all 26 user stories from `docs/specs/scout-redesign-spec.md` across two public seams:
1. Public Python facade (`run_scout`, `run_discover`, `compile_filters`, `ScoutResult`).
2. CLI entrypoint (`ssc-gen scout` via `typer.testing.CliRunner`).

Every CSS selector emitted by `run_scout` is validated against `soup.select()` on the
fixture DOM to prove syntactic validity and target cardinality.
"""

from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup
from typer.testing import CliRunner

from ssc_codegen import (
    AttrFilter,
    DiscoverResult,
    ScoutFilters,
    ScoutResult,
    compile_filters,
    run_discover,
    run_scout,
)
from ssc_codegen.main import app

runner = CliRunner()


def _verify_selector(html: str, selector: str, *, min_matches: int = 1) -> int:
    """Assert that `selector` is valid CSS and matches at least `min_matches` elements in `html`."""
    soup = BeautifulSoup(html, "lxml")
    matched = soup.select(selector)
    assert len(matched) >= min_matches, (
        f"Expected selector {selector!r} to match >= {min_matches} elements, "
        f"got {len(matched)}"
    )
    return len(matched)


# ─────────────────────────── Rich E-Commerce & Catalog Fixture ───────────────

CATALOG_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoParts &amp; Electronics Store</title>
  <style>.hidden { display: none; } body { margin: 0; }</style>
  <noscript><div>Please enable JavaScript</div></noscript>
  <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "ItemList",
      "name": "Featured Electronics",
      "numberOfItems": 2
    }
  </script>
  <script id="__NEXT_DATA__" type="application/json">
    {
      "buildId": "prod-123",
      "props": {
        "pageProps": {
          "items": [
            {"id": 101, "title": "Turbo Charger X1", "price": 499.99, "inStock": true, "discount": 50},
            {"id": 102, "title": "Intake Manifold Pro", "price": 259.50, "inStock": false, "discount": null},
            {"id": 103, "title": "Ceramic Brake Kit", "price": 189.00, "inStock": true, "discount": 15}
          ]
        }
      }
    }
  </script>
  <script>
    var __ENV__ = {"env": "prod"};
    window.APP_CONFIG = {"currency": "USD", "region": "NA", "taxRate": 0.08};
    const CATALOG_META = JSON.parse("{\\"totalPages\\": 12, \\"currentPage\\": 1, \\"category\\": \\"performance\\"}");
    window.DATA_LAYER = [];
    window.DATA_LAYER.push({"event": "view_item_list", "list_id": "perf_parts", "count": 8});
  </script>
</head>
<body>
  <!-- Main Site Header & Navigation -->
  <header class="site-header flex items-center justify-between px-4 py-2 bg-gray-900">
    <svg viewBox="0 0 100 100"><path d="M0 0 L100 100" /></svg>
    <nav class="top-nav">
      <ul class="nav-list flex gap-4">
        <li class="nav-item active"><a href="/home">Home</a></li>
        <li class="nav-item"><a href="/catalog">Catalog</a></li>
        <li class="nav-item"><a href="/deals">Deals</a></li>
        <li class="nav-item"><a href="/brands">Brands</a></li>
        <li class="nav-item"><a href="/support">Support</a></li>
        <li class="nav-item"><a href="/contact">Contact</a></li>
        <li class="nav-item"><a href="/about">About</a></li>
        <li class="nav-item"><a href="/faq">FAQ</a></li>
      </ul>
    </nav>
  </header>

  <main id="catalog-main" class="container mx-auto px-4">
    <h1 class="page-heading text-2xl font-bold">Performance Parts Catalog</h1>

    <!-- Product Grid: 8 cards (> RARE_CLASS_MAX=5) + 1 inline ad-banner outlier -->
    <section id="product-grid" class="catalog-grid grid grid-cols-4 gap-6">
      <article class="product-card featured flex flex-col p-4 border rounded css-1a2b3c sc-bdVaJa" data-sku="SKU-001">
        <div class="layout-wrap"><div class="inner-wrap"><h3 class="product-title"><a class="product-link" href="/p/1">Turbo Charger X1</a></h3></div></div>
        <div class="price-box"><span>1 299</span> <span>₽</span></div>
        <span class="promo-badge">Hot Deal</span>
        <div class="car-specs">
          <span class="spec-item">2022</span>
          <span class="spec-item">2.0L Turbo</span>
          <span class="spec-item">AWD</span>
        </div>
        <div class="tag-cloud">
          <span class="tag-pill">OEM</span>
          <span class="tag-pill">Warranty</span>
        </div>
      </article>

      <article class="product-card odd flex flex-col p-4 border rounded css-1a2b3c sc-bdVaJa" data-sku="SKU-002">
        <div class="layout-wrap"><div class="inner-wrap"><h3 class="product-title"><a class="product-link" href="/p/2">Intake Manifold Pro</a></h3></div></div>
        <div class="price-box"><span>2 450</span> <span>₽</span></div>
        <div class="car-specs">
          <span class="spec-item">2021</span>
          <span class="spec-item">3.0L V6</span>
          <span class="spec-item">RWD</span>
        </div>
        <div class="tag-cloud">
          <span class="tag-pill">Racing</span>
        </div>
      </article>

      <article class="product-card even flex flex-col p-4 border rounded css-1a2b3c sc-bdVaJa" data-sku="SKU-003">
        <div class="layout-wrap"><div class="inner-wrap"><h3 class="product-title"><a class="product-link" href="/p/3">Ceramic Brake Kit</a></h3></div></div>
        <div class="price-box"><span>890</span> <span>₽</span></div>
        <span class="promo-badge">Clearance</span>
        <div class="car-specs">
          <span class="spec-item">2020</span>
          <span class="spec-item">1.8L Hybrid</span>
          <span class="spec-item">FWD</span>
        </div>
        <div class="tag-cloud">
          <span class="tag-pill">Ceramic</span>
          <span class="tag-pill">Low Dust</span>
          <span class="tag-pill">Track</span>
          <span class="tag-pill">TUV</span>
        </div>
      </article>

      <!-- Inline ad banner outlier inside the repeating container -->
      <div class="ad-banner p-4 bg-yellow-100">Sponsored Promo Banner</div>

      <article class="product-card odd flex flex-col p-4 border rounded css-1a2b3c sc-bdVaJa" data-sku="SKU-004">
        <div class="layout-wrap"><div class="inner-wrap"><h3 class="product-title"><a class="product-link" href="/p/4">Coilover Suspension</a></h3></div></div>
        <div class="price-box"><span>3 100</span> <span>₽</span></div>
        <div class="car-specs">
          <span class="spec-item">2023</span>
          <span class="spec-item">2.5L Boxer</span>
          <span class="spec-item">AWD</span>
        </div>
        <div class="tag-cloud">
          <span class="tag-pill">Adjustable</span>
          <span class="tag-pill">Track</span>
          <span class="tag-pill">Street</span>
        </div>
      </article>

      <article class="product-card even flex flex-col p-4 border rounded css-1a2b3c sc-bdVaJa" data-sku="SKU-005">
        <div class="layout-wrap"><div class="inner-wrap"><h3 class="product-title"><a class="product-link" href="/p/5">Forged Piston Set</a></h3></div></div>
        <div class="price-box"><span>4 500</span> <span>₽</span></div>
        <div class="car-specs">
          <span class="spec-item">2019</span>
          <span class="spec-item">4.0L V8</span>
          <span class="spec-item">RWD</span>
        </div>
        <div class="tag-cloud">
          <span class="tag-pill">Forged</span>
        </div>
      </article>

      <article class="product-card odd flex flex-col p-4 border rounded css-1a2b3c sc-bdVaJa" data-sku="SKU-006">
        <div class="layout-wrap"><div class="inner-wrap"><h3 class="product-title"><a class="product-link" href="/p/6">Titanium Exhaust</a></h3></div></div>
        <div class="price-box"><span>5 200</span> <span>₽</span></div>
        <span class="promo-badge">Limited</span>
        <div class="car-specs">
          <span class="spec-item">2024</span>
          <span class="spec-item">3.8L Twin</span>
          <span class="spec-item">AWD</span>
        </div>
        <div class="tag-cloud">
          <span class="tag-pill">Titanium</span>
          <span class="tag-pill">Lightweight</span>
          <span class="tag-pill"> Loud</span>
          <span class="tag-pill">Race</span>
          <span class="tag-pill">Custom</span>
        </div>
      </article>
    </section>

    <!-- Key-Value Representation 1: Vertical KV Table -->
    <table id="tech-specs-table" class="specs-table">
      <tbody>
        <tr><th>Material</th><td>Billet Aluminum</td></tr>
        <tr><th>Weight</th><td>4.2 kg</td></tr>
        <tr><th>Country of Origin</th><td>Germany</td></tr>
        <tr><th>Warranty</th><td>24 Months</td></tr>
      </tbody>
    </table>

    <!-- Key-Value Representation 2: Horizontal Data Table -->
    <table id="compat-table" class="compat-grid">
      <thead>
        <tr><th>Make</th><th>Model</th><th>Year</th></tr>
      </thead>
      <tbody>
        <tr><td>BMW</td><td>M3</td><td>2021</td></tr>
        <tr><td>Audi</td><td>RS4</td><td>2022</td></tr>
        <tr><td>Mercedes</td><td>C63</td><td>2020</td></tr>
      </tbody>
    </table>

    <!-- Key-Value Representation 3: Definition List <dl><dt>/<dd> -->
    <dl id="shipping-details" class="shipping-dl">
      <dt>Carrier</dt><dd>DHL Express</dd>
      <dt>Handling Time</dt><dd>1-2 Business Days</dd>
      <dt>Return Policy</dt><dd>30 Days Free Return</dd>
    </dl>

    <!-- Key-Value Representation 4: Repeating 2-Column Div Rows -->
    <div id="seller-kv" class="seller-specs">
      <div class="spec-row"><span class="spec-label">Seller Name:</span><span class="spec-val">Apex Motorsport</span></div>
      <div class="spec-row"><span class="spec-label">Rating:</span><span class="spec-val">4.9 / 5.0</span></div>
      <div class="spec-row"><span class="spec-label">Location:</span><span class="spec-val">Munich, DE</span></div>
    </div>

    <!-- Attribute JSON element -->
    <div id="widget-config" data-widget='{"widgetType": "calculator", "currencies": ["USD", "EUR", "RUB"], "enabled": true}'></div>
  </main>

  <template id="modal-tpl"><div>Ignored Template Content</div></template>
</body>
</html>
"""


# ─────────────────────────── User Stories 1 & 2: Overview by Default & Alias ─


def test_overview_by_default_and_discover_alias() -> None:
    """US-1 & US-2: `run_scout` runs overview by default; `run_discover` and `--discover` work as aliases."""
    res = run_scout(CATALOG_HTML)
    assert isinstance(res, ScoutResult)
    assert isinstance(res, DiscoverResult)
    assert res.mode == "overview"
    assert res.matched > 0
    assert res.page_summary["title"] == "AutoParts & Electronics Store"
    assert res.page_summary["h1"] == "Performance Parts Catalog"
    assert res.page_summary["has_embedded_json"] is True
    assert res.page_summary["has_kv_blocks"] is True
    assert res.page_summary["repeating_list_count"] >= 1

    # Compatibility alias `run_discover` produces identical overview output
    disc = run_discover(CATALOG_HTML)
    assert disc.to_json() == res.to_json()


# ─────────────────────────── User Story 3: DOM Pruning ───────────────────────


def test_dom_pruning_strips_svg_style_noscript_template_comments() -> None:
    """US-3: `<svg>`, `<style>`, `<noscript>`, `<template>`, and HTML comments are stripped."""
    res = run_scout(CATALOG_HTML)
    text_out = res.to_text()
    json_out = res.to_json()

    for forbidden in (
        "display: none",
        "Please enable JavaScript",
        "Ignored Template Content",
        "Main Site Header & Navigation",
        "viewBox",
    ):
        assert forbidden not in text_out
        assert forbidden not in json_out


# ─────────────────────────── User Stories 4, 5, 6, 7: Selectors & Classes ────


def test_utility_and_hash_classes_filtered_and_repeating_class_kept() -> None:
    """US-4, US-5, US-6, US-7: Utility/state/hash classes are stripped; `.product-card` (N=6) is preserved and DOM-verified."""
    res = run_scout(CATALOG_HTML)
    assert len(res.repeating_lists) >= 1

    product_list = res.repeating_lists[0]
    assert product_list["count"] == 6
    assert "product-card" in product_list["item_classes"]
    # Utility (`flex`, `p-4`), state (`featured`, `odd`, `even`), and hash (`css-1a2b3c`, `sc-bdVaJa`) filtered out
    for noisy in (
        "flex",
        "p-4",
        "border",
        "rounded",
        "featured",
        "odd",
        "even",
        "css-1a2b3c",
        "sc-bdVaJa",
    ):
        assert noisy not in product_list["item_classes"]
        assert noisy not in str(product_list["selector"])

    # Verify container and parent selectors against live DOM
    item_sel = str(product_list["selector"])
    parent_sel = str(product_list["parent_selector"])
    assert "product-card" in item_sel
    assert _verify_selector(CATALOG_HTML, item_sel, min_matches=6) == 6
    assert _verify_selector(CATALOG_HTML, parent_sel, min_matches=1) == 1

    # Verify every relative field selector against the card items in live DOM
    soup = BeautifulSoup(CATALOG_HTML, "lxml")
    cards = soup.select(item_sel)
    assert len(cards) == 6
    fields = product_list["fields"]
    assert isinstance(fields, list)
    for fld in fields:
        assert isinstance(fld, dict)
        rel_css = str(fld["css"])
        matched_in_cards = sum(1 for c in cards if c.select(rel_css))
        assert matched_in_cards == fld["present"]


# ─────────────────────────── User Story 8: Jaccard Classless Clustering ──────


def test_classless_siblings_grouped_by_jaccard_similarity() -> None:
    """US-8: Structurally similar sibling elements without classes are grouped when Jaccard >= 0.5."""
    classless_html = """
    <html><body>
      <section id="reviews">
        <article><h4>Review 1</h4><p>Great product</p><time>2026-01-01</time></article>
        <article><h4>Review 2</h4><p>Fast shipping</p><time>2026-01-02</time><span>Verified</span></article>
        <article><h4>Review 3</h4><p>Solid build</p><time>2026-01-03</time></article>
      </section>
    </body></html>
    """
    res = run_scout(classless_html)
    assert len(res.repeating_lists) == 1
    rev_list = res.repeating_lists[0]
    assert rev_list["count"] == 3
    assert (
        _verify_selector(
            classless_html, str(rev_list["selector"]), min_matches=3
        )
        == 3
    )


# ─────────────────────────── User Story 9: Outlier Isolation ─────────────────


def test_inline_outlier_isolated_without_splitting_list() -> None:
    """US-9: An inline `<div class='ad-banner'>` between product cards is isolated as an outlier."""
    res = run_scout(CATALOG_HTML)
    product_list = res.repeating_lists[0]
    assert product_list["count"] == 6
    outliers = product_list["outliers"]
    assert isinstance(outliers, list)
    assert len(outliers) == 1
    assert outliers[0]["tag"] == "div"
    assert "ad-banner" in outliers[0]["classes"]
    assert outliers[0]["count"] == 1
    assert (
        _verify_selector(
            CATALOG_HTML, str(outliers[0]["selector"]), min_matches=1
        )
        == 1
    )


# ─────────────────────────── User Stories 10 & 11: Ranking & Nav Suppression ─


def test_information_density_ranking_and_navigation_suppression() -> None:
    """US-10 & US-11: Data-rich 6-item product grid outranks 8-item nav list; nav list is collapsed."""
    res = run_scout(CATALOG_HTML)
    # Product grid has 6 items, nav list has 8 items, yet product grid is in repeating_lists
    # and nav list is collapsed into navigation_lists
    assert len(res.repeating_lists) >= 1
    assert res.repeating_lists[0]["count"] == 6
    assert len(res.navigation_lists) >= 1
    nav_entry = res.navigation_lists[0]
    assert nav_entry["count"] == 8
    assert "Home" in nav_entry["samples"]
    assert "<!-- nav-list x8:" in res.to_text()


# ─────────────────────────── User Stories 12, 13, 14, 15, 16: Union Archetype


def test_union_archetype_inline_chains_optional_fields_positional_and_arrays() -> (
    None
):
    """US-12, US-13, US-14, US-15, US-16: Wrapper elision, optional ratio, samples, positional slots, and nested arrays."""
    res = run_scout(CATALOG_HTML)
    product_list = res.repeating_lists[0]
    fields: list[dict[str, object]] = product_list["fields"]  # type: ignore[assignment]

    # US-12: `div.layout-wrap > div.inner-wrap` elided, `h3.product-title > a.product-link` collapsed inline
    title_field = next(
        f
        for f in fields
        if "h3.product-title > a.product-link" in str(f["path"])
    )
    assert title_field["present"] == 6
    assert title_field["total"] == 6
    assert title_field["optional"] is False
    # US-14: text samples and href attr_samples present
    assert "Turbo Charger X1" in title_field["samples"]  # type: ignore[operator]
    assert "/p/1" in title_field["attr_samples"]["href"]  # type: ignore[index]

    # US-13: Optional field `.promo-badge` present in 3/6 cards
    promo_field = next(f for f in fields if "promo-badge" in str(f["path"]))
    assert promo_field["present"] == 3
    assert promo_field["total"] == 6
    assert promo_field["optional"] is True
    assert "[3/6, optional]" in res.to_text()

    # US-15: Fixed 3x `<span class="spec-item">` inside `.car-specs` split into `:nth-of-type(1..3)` positional slots
    pos_fields = [
        f
        for f in fields
        if f["kind"] == "positional" and "car-specs" in str(f["path"])
    ]
    assert len(pos_fields) == 3
    assert "nth-of-type(1)" in str(pos_fields[0]["css"])
    assert "nth-of-type(2)" in str(pos_fields[1]["css"])
    assert "nth-of-type(3)" in str(pos_fields[2]["css"])
    assert "2022" in pos_fields[0]["samples"]  # type: ignore[operator]
    assert "2.0L Turbo" in pos_fields[1]["samples"]  # type: ignore[operator]
    assert "AWD" in pos_fields[2]["samples"]  # type: ignore[operator]

    # US-16: Variable 1..5 `<span class="tag-pill">` per card reported as `kind == "array"` with `array_range == [1, 5]`
    arr_fields = [f for f in fields if f["kind"] == "array"]
    assert len(arr_fields) == 1
    tag_arr = arr_fields[0]
    assert tag_arr["array_range"] == [1, 5]
    assert "[array 1..5 items]" in res.to_text()


# ─────────────────────────── User Stories 17 & 18: Key-Value & Tables ────────


def test_kv_and_table_engine_all_representations() -> None:
    """US-17 & US-18: Detects `table_list`, `kv_table`, `dl`, and `kv_rows` with verified selectors."""
    res = run_scout(CATALOG_HTML)
    kinds = {kv["kind"]: kv for kv in res.kv_blocks}

    assert "kv_table" in kinds
    assert "table_list" in kinds
    assert "dl" in kinds
    assert "kv_rows" in kinds

    # Verify all container & row selectors against the DOM
    for kv in res.kv_blocks:
        csel = str(kv["container_selector"])
        rsel = str(kv["rows_selector"])
        _verify_selector(CATALOG_HTML, csel, min_matches=1)
        _verify_selector(CATALOG_HTML, rsel, min_matches=2)

    # Check kv_table entries
    kv_tbl = kinds["kv_table"]
    assert kv_tbl["key_selector"] == "th"
    assert kv_tbl["value_selector"] == "td"
    tbl_keys = [e["key"] for e in kv_tbl["entries"]]  # type: ignore[index]
    assert "Material" in tbl_keys
    assert "Country of Origin" in tbl_keys

    # Check dl entries
    dl_blk = kinds["dl"]
    assert dl_blk["key_selector"] == "dt"
    assert dl_blk["value_selector"] == "dd"
    dl_keys = [e["key"] for e in dl_blk["entries"]]  # type: ignore[index]
    assert "Carrier" in dl_keys

    # Check kv_rows entries
    kv_rows = kinds["kv_rows"]
    row_keys = [e["key"] for e in kv_rows["entries"]]  # type: ignore[index]
    assert "Seller Name" in row_keys
    assert "Rating" in row_keys


# ─────────────────────────── User Stories 19, 20, 21, 22: Embedded JSON ──────


def test_embedded_json_engine_raw_decode_gjson_paths_and_trivial_filtering() -> (
    None
):
    """US-19, US-20, US-21, US-22: `raw_decode` across scripts, GJSON paths, trivial object filtering, and RFC 8259 validity."""
    res = run_scout(CATALOG_HTML, full=True)
    subtypes = [sig["subtype"] for sig in res.embedded_json]

    assert "json-ld" in subtypes
    assert "json-mime" in subtypes
    assert "js-var" in subtypes
    assert "json-parse" in subtypes
    assert "js-push" in subtypes
    assert "attr-json" in subtypes

    # US-21: Trivial `var __ENV__ = {"env": "prod"}` (1 key, no nested collections) is filtered out
    var_names = [sig.get("var_name") for sig in res.embedded_json]
    assert "__ENV__" not in var_names
    assert "APP_CONFIG" in var_names

    # US-20: Deeply nested array in `__NEXT_DATA__` discovered at `props.pageProps.items`
    next_sig = next(
        sig for sig in res.embedded_json if sig["subtype"] == "json-mime"
    )
    _verify_selector(CATALOG_HTML, str(next_sig["selector"]), min_matches=1)
    cols: list[dict[str, object]] = next_sig["collections"]  # type: ignore[assignment]
    arr_col = next(c for c in cols if c["kind"] == "array")
    assert arr_col["path"] == "props.pageProps.items"
    assert arr_col["count"] == 3
    assert 'path="props.pageProps.items"' in str(next_sig["kdl_hint"])

    field_types = {f["name"]: f["type"] for f in arr_col["fields"]}  # type: ignore[index]
    assert field_types["id"] == "int"
    assert field_types["title"] == "str"
    assert field_types["price"] == "float"
    assert field_types["inStock"] == "bool"
    assert field_types["discount"] == "int?"


# ─────────────────────────── User Stories 23 & 24: Zoom-in & Auto-Expand ─────


def test_zoom_in_normalized_inline_text_and_auto_container_expansion() -> None:
    """US-23 & US-24: `--text '1 299'` matches across `<span>1 299</span> <span>₽</span>` and expands to `.product-card`."""
    res = run_scout(CATALOG_HTML, text="1 299", fixed=True)
    assert res.mode == "zoom"
    assert res.matched == 1
    assert len(res.repeating_lists) == 1

    card_list = res.repeating_lists[0]
    assert card_list.get("matched") is True
    matched_fields = [
        f
        for f in card_list["fields"]
        if isinstance(f, dict) and f.get("matched")  # type: ignore[union-attr]
    ]
    assert len(matched_fields) >= 1
    assert "<-- MATCH" in res.to_text()


def test_zoom_in_standalone_container_and_kv_block() -> None:
    """US-24: Zooming into a KV block or standalone heading climbs to enclosing container with `<-- MATCH`."""
    # Match inside KV block
    kv_res = run_scout(CATALOG_HTML, text="Billet Aluminum", fixed=True)
    assert kv_res.mode == "zoom"
    assert kv_res.matched == 1
    assert len(kv_res.kv_blocks) == 1
    assert kv_res.kv_blocks[0].get("matched") is True
    assert "<-- MATCH" in kv_res.to_text()

    # Match standalone h1 outside repeating lists and KV blocks
    h1_res = run_scout(
        CATALOG_HTML, tag="h1", text="performance parts", ignore_case=True
    )
    assert h1_res.mode == "zoom"
    assert h1_res.matched == 1
    assert len(h1_res.zoom_matches) == 1
    zm = h1_res.zoom_matches[0]
    _verify_selector(CATALOG_HTML, str(zm["match_selector"]), min_matches=1)
    _verify_selector(CATALOG_HTML, str(zm["container_selector"]), min_matches=1)
    assert "<-- MATCH" in h1_res.to_text()


# ─────────────────────────── User Story 25: Default Budgets & `--full` ───────


def test_default_compression_budgets_and_full_mode() -> None:
    """US-25: Default budgets cap lists at 7, KV blocks at 5, JSON signals at 5; `full=True` lifts caps."""
    many_lists_html = (
        "<html><body>"
        + "".join(
            f"<section id='sec-{i}'>"
            + "".join(
                f"<div class='item-{i}'><span class='name'>Item {i}-{j}</span><span class='val'>{j}</span></div>"
                for j in range(4)
            )
            + "</section>"
            for i in range(10)
        )
        + "</body></html>"
    )

    capped = run_scout(many_lists_html, full=False)
    assert len(capped.repeating_lists) == 7
    # Overflow lists are summarized in navigation_lists
    assert len(capped.navigation_lists) == 3

    uncapped = run_scout(many_lists_html, full=True)
    assert len(uncapped.repeating_lists) == 10


def test_field_key_and_json_budget_caps_and_full_lift() -> None:
    """US-25: Verify 25-field cap per list, 80-char sample cap, 25-key KV cap, and 5-signal/20-key JSON cap."""
    long_text = "A" * 120
    # 30 fields inside each repeating card + 30 KV rows + 7 JSON scripts with 25 keys each
    fields_markup = "".join(
        f"<div class='f-{k}'>{long_text}_{k}</div>" for k in range(30)
    )
    cards_markup = "".join(
        f"<article class='rich-card'>{fields_markup}</article>"
        for _ in range(3)
    )
    kv_rows_markup = "".join(
        f"<tr><th>Key_{k}</th><td>Value_{k}</td></tr>" for k in range(30)
    )
    json_scripts = "".join(
        "<script type='application/json'>"
        + json.dumps({f"k_{k}": f"val_{k}" for k in range(25)})
        + "</script>"
        for _ in range(7)
    )
    page_html = f"""
    <html><head>{json_scripts}</head>
    <body>
      <div id="cards">{cards_markup}</div>
      <table id="big-kv">{kv_rows_markup}</table>
    </body></html>
    """

    res_default = run_scout(page_html, full=False)
    assert len(res_default.embedded_json) == 5
    first_col = res_default.embedded_json[0]["collections"][0]  # type: ignore[index]
    assert len(first_col["fields"]) == 20  # type: ignore[arg-type]

    assert len(res_default.kv_blocks) == 1
    assert len(res_default.kv_blocks[0]["entries"]) == 25  # type: ignore[arg-type]

    assert len(res_default.repeating_lists) == 1
    card_fields = res_default.repeating_lists[0]["fields"]
    assert isinstance(card_fields, list)
    assert len(card_fields) == 25
    first_sample = card_fields[0]["samples"][0]  # type: ignore[index]
    assert len(first_sample) == 81 and first_sample.endswith("…")

    # With full=True, all caps are lifted
    res_full = run_scout(page_html, full=True)
    assert len(res_full.embedded_json) == 7
    full_col = res_full.embedded_json[0]["collections"][0]  # type: ignore[index]
    assert len(full_col["fields"]) == 25  # type: ignore[arg-type]
    assert len(res_full.kv_blocks[0]["entries"]) == 30  # type: ignore[arg-type]
    assert len(res_full.repeating_lists[0]["fields"]) == 30  # type: ignore[arg-type]


def test_bare_json_and_wrapped_dl_and_td_only_kv_table() -> None:
    """US-17, US-18, US-19, US-22: Test bare JSON script, `<dl>` with `<div>` wrappers, and `<td>`-only 2-column KV table."""
    html = """
    <html><body>
      <script>[{"sku": "A1", "qty": 10}, {"sku": "B2", "qty": 5}]</script>
      <table id="td-kv">
        <tr><td>Dimensions</td><td>10 x 20 cm</td></tr>
        <tr><td>Color</td><td>Matte Black</td></tr>
        <tr><td>Finish</td><td>Anodized</td></tr>
      </table>
      <dl id="wrapped-dl">
        <div class="dl-pair"><dt>Voltage</dt><dd>12V</dd></div>
        <div class="dl-pair"><dt>Amperage</dt><dd>5A</dd></div>
      </dl>
    </body></html>
    """
    res = run_scout(html)
    assert len(res.embedded_json) == 1
    assert res.embedded_json[0]["subtype"] == "bare-json"
    _verify_selector(html, str(res.embedded_json[0]["selector"]), min_matches=1)

    kv_by_kind = {kv["kind"]: kv for kv in res.kv_blocks}
    assert "kv_table" in kv_by_kind
    assert kv_by_kind["kv_table"]["key_selector"] == "td:nth-of-type(1)"
    assert kv_by_kind["kv_table"]["value_selector"] == "td:nth-of-type(2)"
    _verify_selector(html, str(kv_by_kind["kv_table"]["container_selector"]))

    assert "dl" in kv_by_kind
    assert kv_by_kind["dl"]["row_count"] == 2
    _verify_selector(
        html, str(kv_by_kind["dl"]["rows_selector"]), min_matches=2
    )


# ─────────────────────────── User Story 26 & Seam 2: CLI Entrypoint ──────────


def test_cli_scout_file_stdin_formats_and_exit_codes(tmp_path: Path) -> None:
    """US-26 & Seam 2: Test `ssc-gen scout` CLI with `-i`, `stdin`, `-f text`, `-f json`, `--discover`, and exit codes 0/1/2."""
    html_file = tmp_path / "catalog.html"
    html_file.write_text(CATALOG_HTML, encoding="utf-8")

    # 1. Default overview text output via `-i` (exit code 0)
    res_text = runner.invoke(app, ["scout", "-i", str(html_file)])
    assert res_text.exit_code == 0, res_text.output
    assert "# sample_normalized: true" in res_text.output
    assert "=== PAGE SUMMARY ===" in res_text.output
    assert "=== EMBEDDED JSON ===" in res_text.output
    assert "=== KEY-VALUE & TABLES ===" in res_text.output
    assert "=== REPEATING LISTS & DOM SKELETON ===" in res_text.output

    # 2. JSON output via stdin and `--discover` deprecated flag (exit code 0)
    res_json = runner.invoke(
        app, ["scout", "--discover", "-f", "json"], input=CATALOG_HTML
    )
    assert res_json.exit_code == 0, res_json.output
    payload = json.loads(res_json.stdout)
    assert payload["mode"] == "overview"
    assert payload["sample_normalized"] is True
    assert len(payload["repeating_lists"]) >= 1

    # 3. Zoom-in mode via CLI flags (exit code 0 when matched)
    res_zoom = runner.invoke(
        app,
        ["scout", "-i", str(html_file), "--attr", "data-sku=SKU-001"],
    )
    assert res_zoom.exit_code == 0, res_zoom.output
    assert "<-- MATCH" in res_zoom.output

    # 4. Exit code 1 when Zoom-in filter matches 0 elements
    res_nomatch = runner.invoke(
        app,
        ["scout", "-i", str(html_file), "--text", "NON_EXISTENT_STRING_XYZ"],
    )
    assert res_nomatch.exit_code == 1

    # 5. Exit code 2 on empty HTML input
    res_empty = runner.invoke(app, ["scout"], input="   \n  ")
    assert res_empty.exit_code == 2

    # 6. Exit code 2 on invalid regex or invalid CSS selector
    res_bad_regex = runner.invoke(
        app, ["scout", "-i", str(html_file), "--text", "[unclosed"]
    )
    assert res_bad_regex.exit_code == 2

    res_bad_css = runner.invoke(
        app, ["scout", "-i", str(html_file), "--css", "div[invalid=="]
    )
    assert res_bad_css.exit_code == 2


def test_compile_filters_and_attr_filter_modes() -> None:
    """Test `compile_filters` and `AttrFilter` presence, exact, and regex matching."""
    flt = compile_filters(
        text="Turbo",
        attrs=["data-sku", "data-sku=SKU-001", "data-sku=~^SKU-\\d+$"],
        tag="article",
        css="section#product-grid article",
        ignore_case=True,
        fixed=False,
    )
    assert isinstance(flt, ScoutFilters)
    assert flt.is_active() is True
    assert len(flt.attrs) == 3
    assert isinstance(flt.attrs[0], AttrFilter)

    res = run_scout(CATALOG_HTML, flt)
    assert res.mode == "zoom"
    assert res.matched == 1
