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
- Canonical snapshot 0.4 and the opt-in reference-ordering target require Core
  reference legality in the authored input order before sorting or adding a
  default header. This does not require schema approval, reference evaluation,
  or materialization.

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
- Canonical snapshot 0.4 and the reference-ordering next manifest use
  smallest-eligible-key ordering with Unicode scalar lexical tie-breaking.
  Lists, tuples and node children retain their positions. Canonical fixed-point inputs assert
  idempotence using the same exact-text comparison.
- Eligibility is local to each sortable scope after dependency projection.
  Already-available enclosing targets are satisfied; an unrelated local entry
  with the same key is not a predecessor. Golden outputs assert the smallest
  eligible key at every step, not merely a legal topological ordering.
- Historical snapshots retain their earlier ordering expectations. All selected
  cases in canonical 0.4 are required, including reused fixtures with
  experimental provenance tags; tags do not override manifest selection.
  Snapshot promotion does not switch implementation defaults or migrate
  historical integrity/hash contracts.
