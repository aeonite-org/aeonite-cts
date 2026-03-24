# Lane Contract: Canonical (`cts/canonical/v1`)

This lane validates deterministic canonical formatting at the canonicalizer boundary.

## Input Fixture Shape
```json
{
  "source": "aeon text"
}
```

Rules:
- `source` required (string).
- No mode/policy fields are required; canonicalization is parse-driven.

## Output `result` Shape
```json
{
  "canonical_text": "aeon:header = {\n  mode = \"transport\"\n}\na = 1"
}
```

Rules:
- `canonical_text` required when formatting succeeds.
- Reject cases assert diagnostics contract instead of partial canonical output.

## Matching Notes
- Canonical text comparison is exact after normalizing line endings and trimming trailing file-end whitespace.
- Runner MUST NOT compare implementation-internal AST state.
- Canonical lane is responsible for formatting guarantees such as quoting, indentation, ordering, and multiline preservation.
