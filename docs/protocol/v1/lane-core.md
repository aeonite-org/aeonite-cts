# Lane Contract: Core (`cts/core/v1`)

This lane validates parse/addressing conformance at the core boundary.

## Input Fixture Shape
```json
{
  "source": "aeon text",
  "mode": "transport|strict|custom",
  "policy": {}
}
```

Rules:
- `source` required (string).
- `mode` optional; defaults per suite metadata.
- `policy` optional lane policy overrides.
- Semantic fail-closed guarantees such as duplicate canonical-path rejection, header conflict rejection, and strict-mode switch enforcement belong in this lane.

## Output `result` Shape
```json
{
  "parse_ok": true,
  "bindings": [
    {
      "path": "$.a",
      "datatype": "number",
      "kind": "binding"
    }
  ]
}
```

Rules:
- `parse_ok` required (boolean).
- `bindings` required when `parse_ok=true`; omitted or empty when parse fails.
- `bindings` are normalized projections, not full AST snapshots.

## Matching Notes
- Parse-fail cases are asserted via diagnostics contract.
- Parse-pass cases assert normalized binding/path projections only.
- Runner MUST NOT compare parser-internal node IDs or engine-specific AST shapes.
- Fail-closed semantic cases should assert `parse_ok=false` with empty bindings, even when a recovery-capable implementation may still be able to retain partial events under non-CTS recovery modes.
