# Lane Contract: SANSA (`cts/sansa/v1`)

This lane validates SANSA Addressing, Resolve, and Query behavior over host-neutral fixtures.

SANSA CTS assets currently use manifest and suite JSON files rather than the generic stdin/stdout SUT envelope described in `runner-contract.md`. Implementations may adapt these assets into their own runner shape, but the expectation fields in the suite files are normative for conformance comparison.

## Suite Families

- `01-address-parser.json`: address grammar and canonical rendering.
- `02-aeon-address-literals.json`: AEON-embedded SANSA address literal acceptance boundaries.
- `03-address-resolve.json`: resolution behavior over host-neutral binding fixtures.
- `04-query-parser.json`: Query clause parsing and canonical rendering.
- `05-query-expression-parser.json`: Query expression parsing and AST-shape expectations.
- `06-query-evaluate.json`: Query evaluation behavior over host-neutral binding fixtures.

## Query Evaluation Inputs

Query evaluation cases use:

```json
{
  "namespace": "fixture-id",
  "source": "from $.items.*\nselect .name",
  "options": {}
}
```

Rules:

- `namespace` identifies a fixture in the suite's `fixtures.namespaces` array.
- `source` is the SANSA Query source text.
- `options` is optional and maps to implementation-defined evaluator options when the option is part of a published or proposal-stage CTS surface.
- Query budget options are supplied under `options.budget`.

## Query Evaluation Expectations

Successful Query evaluation cases may assert:

```json
{
  "ok": true,
  "resultAddresses": ["$.items[0]"],
  "selectedAddresses": [["$.items[0].name"]],
  "values": []
}
```

Rules:

- `resultAddresses` compare ResultRecord candidate addresses.
- `selectedAddresses` compare selected binding addresses when the projected value is a Binding Set.
- `values` compare projected value envelopes.

Failed Query evaluation cases may assert:

```json
{
  "ok": false,
  "error": "SANSA_QUERY_BUDGET_EXCEEDED",
  "errorPhase": "from",
  "candidateAddress": "$.items[0]",
  "errorExtension": "sansa.transform.objectFrom",
  "errorBudget": "maxFromBindings",
  "errorLimit": 3,
  "errorObserved": 4
}
```

Rules:

- `error` compares the first diagnostic code.
- `errorPhase` compares the diagnostic phase when expected.
- `candidateAddress` compares candidate-local diagnostic context when expected.
- `errorExtension` compares extension identity for disabled or unsupported extension diagnostics.
- `errorBudget`, `errorLimit`, and `errorObserved` compare budget diagnostics when expected.
- Unknown diagnostic fields are non-normative unless a suite explicitly adds an expectation field for them.

## Budget Diagnostics

Budget exhaustion is an evaluation failure, never implicit truncation. A conforming Query evaluator that accepts a CTS-supplied budget must return no partial result set and should report:

- `SANSA_QUERY_BUDGET_EXCEEDED`
- the pipeline phase where the budget was exceeded;
- the budget name;
- the configured limit;
- the observed count.
