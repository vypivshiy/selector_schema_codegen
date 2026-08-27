# JSON Key Alias Remapping

Accepted: Python and JavaScript JSON responses use the DSL field name as the
canonical result key, while an optional second field argument identifies the
source JSON key (for example, `context str "@context"`). Python and JavaScript
generate one universal `ssc_remap_json_keys` / `sscRemapJsonKeys` runtime
helper and per-`json` mapping data only for schemas that contain an alias in
their recursive JSON subtree; mappings are complete source-key-to-canonical-key
descriptors and nested objects/arrays are remapped recursively. The helper is
inlined normally and moved to the separate runtime module under `-R`; it
omits absent keys, performs no validation or casting, and Go remains unchanged.

Duplicate source keys and duplicate resulting canonical keys are lint errors.
