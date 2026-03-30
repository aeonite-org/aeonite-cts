# CTS Runner Contract (`cts.protocol.v1`)

## 1. Invocation Model
- Runner executes the SUT once per test case.
- Runner writes one JSON input envelope to `stdin`, then EOF.
- SUT writes one JSON output envelope to `stdout`.
- `stderr` is log-only and non-normative.
- Runner MUST support SUT-specific invocation context, including working directory and environment overrides, when an implementation requires them for deterministic dependency resolution.
- Runner MUST treat those invocation-context settings as harness configuration, not as case data.

### 1.1 Invocation Context
- The SUT command alone is not always sufficient to identify the correct execution environment.
- Runners SHOULD allow each SUT definition to specify:
  - command and arguments;
  - working directory;
  - environment overrides.
- This is especially important for Python implementations that resolve local packages via workspace-relative execution or `PYTHONPATH` rather than a globally installed package.

## 2. Exit Code Semantics
- Exit `0`: protocol-complete execution (case can still fail by output content).
- Non-zero exit: harness failure (crash/protocol violation), not case failure.

## 3. Envelope Base Shape
### Input
```json
{
  "lane": "aeos|annotations|core|aes",
  "case_id": "string",
  "fixture": {},
  "policy": {}
}
```

### Output
```json
{
  "ok": true,
  "errors": [],
  "warnings": [],
  "result": {}
}
```

## 4. Required Output Rules
- `ok`, `errors`, `warnings`, and `result` MUST be present.
- `ok` MUST be `true` iff `errors` is empty.
- `errors` and `warnings` MUST be arrays.
- `result` MAY be `null` only if lane contract allows it.

## 5. Diagnostics Shape
All diagnostics in `errors`/`warnings` use:
```json
{
  "code": "STRING_CODE",
  "path": "$.x.y",
  "span": [0, 10],
  "phase": 6,
  "message": "optional text"
}
```

Rules:
- `code`: required, non-empty string.
- `path`: required, string or `null`.
- `span`: required, `[start,end]` or `null`.
- `phase`: required, number or `null`.
- `message`: optional; non-normative by default.

## 6. Matching Policy
- Normative keys: `code`, `path`, `phase`.
- `span` is matched when present in expectations.
- `message` is ignored unless a suite explicitly opts in.
- Runner MUST ignore unknown output fields unless lane contract whitelists them for matching.

## 7. Fail-Closed Rules
- Malformed input envelope: runner/harness failure.
- Malformed output envelope: runner/harness failure.
- Unknown lane in input: runner/harness failure.

## 8. Determinism Rules
- Same input envelope MUST produce equivalent normative output fields.
- Runner comparison MUST use normalized ordering for deterministic structures defined by lane contracts.
