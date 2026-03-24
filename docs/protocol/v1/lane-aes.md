# Lane Contract: AES (`cts/aes/v1`)

This lane validates assignment-event emission semantics.

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
- `mode` and `policy` optional per suite metadata.

## Output `result` Shape
```json
{
  "events": [
    {
      "path": "$.a",
      "datatype": "number",
      "value_kind": "NumberLiteral",
      "reference": null
    }
  ]
}
```

Rules:
- `result.events` required (array).
- Event order is normative and MUST reflect source emission order.
- Event fields are normalized contract fields only.

## Matching Notes
- Assert: cardinality, order, canonical path, datatype signature retention, reference preservation surface.
- Do not assert consumer finalization/output materialization in this lane.
