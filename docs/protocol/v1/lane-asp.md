# Lane Contract: ASP (`cts/asp/v1`)

This lane validates ASP-facing behavior. The first suite family is an
experimental CTS promotion candidate for the conservative SANSA.Mutate lowering
bridge.

ASP lowering CTS assets use manifest and suite JSON files. They do not require
the generic stdin/stdout SUT envelope yet, but implementations may adapt the
case inputs and expectations into their normal runner shape.

## Suite Families

- `01-sansa-mutate-lowering.json`: conservative exact SANSA.Mutate request to
  ASP transaction lowering over a seeded ASP snapshot.

## ASP SANSA Lowering Inputs

Each case starts from `fixtures.seed_transaction`. A runner should apply that
ASP transaction to an empty ASP engine, then invoke its SANSA.Mutate lowering
bridge with the case `input`.

```json
{
  "tx_id": "tx_sansa_mutate_replace_exact",
  "request": {
    "op": "replace",
    "target": "$.inventory.sku",
    "value": "B-200"
  },
  "budget": {},
  "policy": {}
}
```

Rules:

- `request` is either one structured SANSA.Mutate operation or an ordered list
  of operations.
- `tx_id` is the transaction id the lowering bridge should use if it produces
  an ASP transaction.
- `budget` is optional and maps to the conservative lowering budget surface.
- `policy` is trusted runner input for simulating authorization boundaries.
  `requestDenyOperation` denies before SANSA planning, and
  `planDenyTargetPrefix` denies after SANSA planning but before ASP lowering.
- This lane validates lowering only. AEOS validation, storage capability
  enforcement, and commit durability are separate ASP or integration contracts.

## Expectations

Successful cases assert selected ASP transaction fields:

```json
{
  "ok": true,
  "preconditions": [
    { "scope": "$.inventory", "revision": 1 }
  ],
  "operations": [
    {
      "op": "put_assignment",
      "path": "$.inventory.sku",
      "datatype": "string",
      "value": { "type": "StringLiteral", "value": "B-200" }
    }
  ]
}
```

Failed cases assert the first stable diagnostic:

```json
{
  "ok": false,
  "error": {
    "code": "SANSA_MUTATE_OPERATION_UNSUPPORTED_BY_ASP",
    "phase": "asp.lowering",
    "path": "$.items",
    "op_index": 0
  }
}
```

Rules:

- `operations` order is normative.
- Expected operation objects are partial matches; omitted ASP operation fields
  are non-normative for this suite.
- `preconditions` are matched when present and are ordered.
- `error.code` and `error.phase` are normative for failed cases.
- `error.path`, `error.op_index`, `error.budget`, `error.limit`, and
  `error.observed` are normative when present in the expectation.
- Unknown diagnostics and output fields are non-normative unless a later suite
  explicitly adds expectations for them.
