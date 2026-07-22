"""Go runtime helper definitions for ssc-gen.

Three exports:

- BASE_RUNTIME      — always-present source lines (stdFallback, sentinel).
- BASE_REST_RUNTIME — REST runtime types (always present in REST modules).
- GO_RUNTIME        — dict {name: (imports, code)} for optional helpers.

Every helper uses the std prefix.  Arr suffixed variants handle
[]string inputs by calling the scalar version in a loop.

The visitor registers helpers via ModuleBuilder.require_std using the
imports list so that emit_runtime can assemble correct Go imports
without scanning generated source text.
"""

from __future__ import annotations

# Lines that are ALWAYS present in sscgen_runtime.go.
BASE_RUNTIME: list[str] = [
    "// stdFallback runs fn with panic recovery, returning fallback on panic.",
    "func stdFallback[T any](fn func() T, fallback T) T {",
    "\tvar result T",
    "\tdefer func() {",
    "\t\tif r := recover(); r != nil {",
    "\t\t\tresult = fallback",
    "\t\t}",
    "\t}()",
    "\tresult = fn()",
    "\treturn result",
    "}",
    "",
]

# ---------------------------------------------------------------------------
# Optional helpers — keyed by name, value is (go_imports, go_source).
# ---------------------------------------------------------------------------

GO_RUNTIME: dict[str, tuple[list[str], str]] = {
    # === ASSERT ===
    "stdAssert": (
        [],
        """\
func stdAssert(cond bool, msg string) {
\tif !cond {
\t\tpanic("ssc-gen: " + msg)
\t}
}""",
    ),
    # === STRING — scalar ===
    "stdTrim": (
        ['"strings"'],
        """\
func stdTrim(s, cutset string) string {
\tif cutset == "" {
\t\treturn strings.TrimSpace(s)
\t}
\treturn strings.Trim(s, cutset)
}""",
    ),
    "stdLTrim": (
        ['"strings"'],
        """\
func stdLTrim(s, cutset string) string {
\tif cutset == "" {
\t\treturn strings.TrimLeft(s, " \\t\\n\\r\\v\\f")
\t}
\treturn strings.TrimLeft(s, cutset)
}""",
    ),
    "stdRTrim": (
        ['"strings"'],
        """\
func stdRTrim(s, cutset string) string {
\tif cutset == "" {
\t\treturn strings.TrimRight(s, " \\t\\n\\r\\v\\f")
\t}
\treturn strings.TrimRight(s, cutset)
}""",
    ),
    "stdRmPrefix": (
        ['"strings"'],
        """\
func stdRmPrefix(s, prefix string) string {
\treturn strings.TrimPrefix(s, prefix)
}""",
    ),
    "stdRmSuffix": (
        ['"strings"'],
        """\
func stdRmSuffix(s, suffix string) string {
\treturn strings.TrimSuffix(s, suffix)
}""",
    ),
    "stdRmPrefixSuffix": (
        ['"strings"'],
        """\
func stdRmPrefixSuffix(s, sub string) string {
\treturn strings.TrimSuffix(strings.TrimPrefix(s, sub), sub)
}""",
    ),
    "stdFmt": (
        ['"strings"'],
        """\
func stdFmt(template, value string) string {
\treturn strings.Replace(template, "{{}}", value, 1)
}""",
    ),
    "stdRepl": (
        ['"strings"'],
        """\
func stdRepl(s, old, new string) string {
\treturn strings.ReplaceAll(s, old, new)
}""",
    ),
    "stdReplMap": (
        ['"strings"'],
        """\
func stdReplMap(s string, m map[string]string) string {
\tfor k, v := range m {
\t\ts = strings.ReplaceAll(s, k, v)
\t}
\treturn s
}""",
    ),
    "stdLower": (
        ['"strings"'],
        """\
func stdLower(s string) string {
\treturn strings.ToLower(s)
}""",
    ),
    "stdUpper": (
        ['"strings"'],
        """\
func stdUpper(s string) string {
\treturn strings.ToUpper(s)
}""",
    ),
    "stdNormSpace": (
        ['"regexp"', '"strings"'],
        """\
var stdSpaceRe = regexp.MustCompile(`\\s+`)

func stdNormSpace(s string) string {
\treturn strings.TrimSpace(stdSpaceRe.ReplaceAllString(s, " "))
}""",
    ),
    "stdUnescape": (
        ['"html"'],
        """\
func stdUnescape(s string) string {
\treturn html.UnescapeString(s)
}""",
    ),
    # === STRING — array variants ===
    "stdTrimArr": (
        [],
        """\
func stdTrimArr(arr []string, cutset string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdTrim(s, cutset)
\t}
\treturn r
}""",
    ),
    "stdLTrimArr": (
        [],
        """\
func stdLTrimArr(arr []string, cutset string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdLTrim(s, cutset)
\t}
\treturn r
}""",
    ),
    "stdRTrimArr": (
        [],
        """\
func stdRTrimArr(arr []string, cutset string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdRTrim(s, cutset)
\t}
\treturn r
}""",
    ),
    "stdRmPrefixArr": (
        [],
        """\
func stdRmPrefixArr(arr []string, prefix string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdRmPrefix(s, prefix)
\t}
\treturn r
}""",
    ),
    "stdRmSuffixArr": (
        [],
        """\
func stdRmSuffixArr(arr []string, suffix string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdRmSuffix(s, suffix)
\t}
\treturn r
}""",
    ),
    "stdRmPrefixSuffixArr": (
        [],
        """\
func stdRmPrefixSuffixArr(arr []string, sub string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdRmPrefixSuffix(s, sub)
\t}
\treturn r
}""",
    ),
    "stdFmtArr": (
        [],
        """\
func stdFmtArr(arr []string, template string) []string {
\tr := make([]string, len(arr))
\tfor i, v := range arr {
\t\tr[i] = stdFmt(template, v)
\t}
\treturn r
}""",
    ),
    "stdReplArr": (
        [],
        """\
func stdReplArr(arr []string, old, new string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdRepl(s, old, new)
\t}
\treturn r
}""",
    ),
    "stdReplMapArr": (
        [],
        """\
func stdReplMapArr(arr []string, m map[string]string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdReplMap(s, m)
\t}
\treturn r
}""",
    ),
    "stdLowerArr": (
        [],
        """\
func stdLowerArr(arr []string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdLower(s)
\t}
\treturn r
}""",
    ),
    "stdUpperArr": (
        [],
        """\
func stdUpperArr(arr []string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdUpper(s)
\t}
\treturn r
}""",
    ),
    "stdNormSpaceArr": (
        [],
        """\
func stdNormSpaceArr(arr []string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdNormSpace(s)
\t}
\treturn r
}""",
    ),
    "stdUnescapeArr": (
        [],
        """\
func stdUnescapeArr(arr []string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdUnescape(s)
\t}
\treturn r
}""",
    ),
    # === REGEX ===
    "stdReSearch": (
        ['"regexp"'],
        """\
func stdReSearch(pattern, value, msg string) string {
\tre := regexp.MustCompile(pattern)
\tm := re.FindStringSubmatch(value)
\tif m == nil {
\t\tpanic("ssc-gen: " + msg)
\t}
\treturn m[1]
}""",
    ),
    "stdReSearchArr": (
        [],
        """\
func stdReSearchArr(arr []string, pattern, msg string) []string {
\tr := make([]string, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdReSearch(pattern, s, msg)
\t}
\treturn r
}""",
    ),
    "stdReMatch": (
        ['"regexp"'],
        """\
func stdReMatch(pattern, value string) bool {
\treturn regexp.MustCompile(pattern).MatchString(value)
}""",
    ),
    "stdReAllMatch": (
        ['"regexp"'],
        """\
func stdReAllMatch(pattern string, arr []string) bool {
\tre := regexp.MustCompile(pattern)
\tfor _, s := range arr {
\t\tif !re.MatchString(s) {
\t\t\treturn false
\t\t}
\t}
\treturn true
}""",
    ),
    "stdReAnyMatch": (
        ['"regexp"'],
        """\
func stdReAnyMatch(pattern string, arr []string) bool {
\tre := regexp.MustCompile(pattern)
\tfor _, s := range arr {
\t\tif re.MatchString(s) {
\t\t\treturn true
\t\t}
\t}
\treturn false
}""",
    ),
    # === ARRAY ===
    "stdLen": (
        ['"github.com/PuerkitoBio/goquery"'],
        """\
// stdLen handles *goquery.Selection | string | []string inputs.
// Sum-type dispatch is the legitimate use of `any` here — accept_type_info
// on Len stays AUTO in the type-checking phase, so the codegen cannot pick
// .Length() vs len() statically.
func stdLen(v any) int64 {
\tswitch t := v.(type) {
\tcase *goquery.Selection:
\t\treturn int64(t.Length())
\tcase string:
\t\treturn int64(len(t))
\tcase []string:
\t\treturn int64(len(t))
\tdefault:
\t\treturn 0
\t}
}""",
    ),
    "stdUnique": (
        [],
        """\
func stdUnique[T comparable](arr []T) []T {
\tseen := make(map[T]bool)
\tr := make([]T, 0, len(arr))
\tfor _, v := range arr {
\t\tif !seen[v] {
\t\t\tseen[v] = true
\t\t\tr = append(r, v)
\t\t}
\t}
\treturn r
}""",
    ),
    # === CAST ===
    "stdToInt": (
        ['"strconv"', '"strings"'],
        """\
func stdToInt(s string) int64 {
\tn, err := strconv.ParseInt(strings.TrimSpace(s), 10, 64)
\tif err != nil {
\t\tpanic("ssc-gen: failed to parse int: " + s)
\t}
\treturn n
}""",
    ),
    "stdToIntArr": (
        [],
        """\
func stdToIntArr(arr []string) []int64 {
\tr := make([]int64, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdToInt(s)
\t}
\treturn r
}""",
    ),
    "stdToFloat": (
        ['"strconv"', '"strings"'],
        """\
func stdToFloat(s string) float64 {
\tf, err := strconv.ParseFloat(strings.TrimSpace(s), 64)
\tif err != nil {
\t\tpanic("ssc-gen: failed to parse float: " + s)
\t}
\treturn f
}""",
    ),
    "stdToFloatArr": (
        [],
        """\
func stdToFloatArr(arr []string) []float64 {
\tr := make([]float64, len(arr))
\tfor i, s := range arr {
\t\tr[i] = stdToFloat(s)
\t}
\treturn r
}""",
    ),
    # === PREDICATE HELPERS ===
    "stdHasAttr": (
        ['"github.com/PuerkitoBio/goquery"'],
        """\
func stdHasAttr(s *goquery.Selection, key string) bool {
\t_, ok := s.Attr(key)
\treturn ok
}""",
    ),
    "stdAttrOr": (
        ['"github.com/PuerkitoBio/goquery"'],
        """\
func stdAttrOr(s *goquery.Selection, key string) string {
\tv, _ := s.Attr(key)
\treturn v
}""",
    ),
    # === JSON ===
    "stdJsonify": (
        ['"encoding/json"', '"github.com/tidwall/gjson"'],
        """\
func stdJsonify[T any](jsonStr, path string, target *T) {
\tvar raw string
\tif path != "" {
\t\traw = gjson.Get(jsonStr, path).Raw
\t} else {
\t\traw = jsonStr
\t}
\tif err := json.Unmarshal([]byte(raw), target); err != nil {
\t\tpanic("ssc-gen: json unmarshal failed: " + err.Error())
\t}
}""",
    ),
    "stdJsonifyValue": (
        ['"github.com/tidwall/gjson"'],
        """\
func stdJsonifyValue(jsonStr, path string) any {
\tif path != "" {
\t\treturn gjson.Get(jsonStr, path).Value()
\t}
\treturn gjson.Parse(jsonStr).Value()
}""",
    ),
}


# ---------------------------------------------------------------------------
# REST runtime — emitted only when module has REST structs.
# ---------------------------------------------------------------------------

BASE_REST_RUNTIME: list[str] = [
    "type sscHeaders = map[string][]string",
    "",
    "type sscReqOpts struct {",
    "\tHeaders sscHeaders",
    "\tBody    string",
    "}",
    "",
    "type sscErrMatcher struct {",
    "\tStatus  int",
    "\tCheck   func([]byte) bool",
    "\tFactory func(int, []byte) error",
    "}",
    "",
    "func sscDispatchErr(matchers []sscErrMatcher, status int, headers sscHeaders, body []byte) error {",
    "\tfor _, m := range matchers {",
    "\t\tif m.Status == status {",
    "\t\t\tif m.Check == nil || m.Check(body) {",
    "\t\t\t\treturn m.Factory(status, body)",
    "\t\t\t}",
    "\t\t}",
    "\t}",
    "\treturn nil",
    "}",
    "",
    "// UnknownErr — unmatched HTTP >= 400 response.",
    "type UnknownErr struct {",
    "\tStatus int",
    "\tBody   string",
    "}",
    "",
    "func (e *UnknownErr) Error() string {",
    '\treturn fmt.Sprintf("ssc-gen: unexpected HTTP %d: %s", e.Status, e.Body)',
    "}",
    "",
    "// TransportErr — network/transport level failure.",
    "type TransportErr struct {",
    "\tCause string",
    "}",
    "",
    "func (e *TransportErr) Error() string {",
    '\treturn "ssc-gen: transport error: " + e.Cause',
    "}",
    "",
]
