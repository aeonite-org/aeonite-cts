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
- The opt-in reference-ordering target also requires Core reference legality
  in the authored input order before sorting or adding a default header. This
  does not require schema approval, reference evaluation, or materialization.

## Output `result` Shape

```json
{
  "canonical_text": "aeon:header = {\n  mode = \"transport\"\n}\na = 1"
}
```

Rules:

- `canonical_text` required when formatting succeeds.
- Reject cases assert diagnostics contract instead of partial canonical output.
- Reference-ordering reject cases explicitly require empty `canonical_text`.
  Adapters must not manufacture an empty value while discarding partial
  formatted output returned by the canonicalizer.

## Matching Notes

- Canonical text comparison is exact after normalizing line endings and trimming trailing file-end whitespace.
- Runner MUST NOT compare implementation-internal AST state.
- Canonical lane is responsible for formatting guarantees such as quoting, indentation, ordering, and multiline preservation.
- The experimental reference-ordering manifest uses smallest-eligible-key
  ordering with Unicode scalar lexical tie-breaking. Lists, tuples and node
  children retain their positions. Canonical fixed-point inputs assert
  idempotence using the same exact-text comparison.
