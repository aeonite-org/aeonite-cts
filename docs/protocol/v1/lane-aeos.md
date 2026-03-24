# Lane Contract: AEOS (`cts/aeos/v1`)

This lane validates schema/validator behavior over AES input.

## Input Fixture Shape
```json
{
  "aes": [],
  "schema": {}
}
```

Rules:
- `aes` required (array).
- `schema` required (`object` or `null`).

## Output `result` Shape
```json
{
  "guarantees": {
    "$.path": ["label"]
  }
}
```

Rules:
- `result.guarantees` required (object, may be empty).
- Guarantee keys MUST be canonical paths.
- Guarantee values MUST be arrays of strings.

## Matching Notes
- Normative diagnostics + guarantee map content.
- Guarantee map key order is non-normative; runner normalizes before compare.

## Compatibility
- `sut-envelope.md` remains accepted compatibility wording for AEOS adapters.
- Where this doc conflicts, this lane contract takes precedence for `cts.protocol.v1`.
