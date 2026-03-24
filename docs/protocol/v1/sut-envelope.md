# CTS SUT Envelope Protocol

**Version:** 1.0  
**Applies to:** AEOS Conformance Test Suite v1  
**Status:** Compatibility-Normative (AEOS lane)

> This document is retained for AEOS adapter compatibility.
> Unified protocol baseline for all lanes is defined in:
> - `cts/protocol/v1/runner-contract.md`
> - `cts/protocol/v1/lane-aeos.md`

---

## Overview

This document defines the protocol contract between the CTS runner and any conforming System Under Test (SUT). It is the normative source of truth for:

- What a SUT must accept as input
- What a SUT must emit as output
- How the runner invokes the SUT
- How implementors use the CTS to validate their own AEON engines

Any AEON engine can be validated against the CTS by wrapping it in a thin CLI adapter that conforms to this protocol.

---

## 1. Invocation Model

The runner executes the SUT as a subprocess:

```
<sut-binary> [validate]
```

- The runner writes the **input envelope** as a single JSON object to the SUT's **stdin**, followed by EOF.
- The runner reads the **result envelope** as a single JSON object from the SUT's **stdout**.
- The runner reads **stderr** for diagnostic logging only; stderr output does not affect test outcome.

### 1.1 Exit Code Semantics (normative)

| Exit code | Meaning |
|-----------|---------|
| `0` | SUT ran to completion and produced a valid result envelope JSON (even if `ok: false`) |
| non-zero | SUT crash, invalid/unparseable result JSON, or protocol violation |

A non-zero exit code MUST be treated by the runner as a **harness failure**, not as a test failure. This distinction prevents "expected failing validation" from being misinterpreted as "tool failure."

The SUT MUST NOT use exit codes to signal validation outcome. Only the `ok` field of the result envelope carries that signal.

---

## 2. Input Envelope

The runner writes exactly one JSON object to stdin:

```typescript
{
  "aes": AssignmentEvent[],   // required; the AES to validate
  "schema": SchemaV1 | null   // required; null if no schema is being applied
}
```

### 2.1 Field rules

- `aes` MUST be a valid JSON array. It MAY be empty.
- `schema` MUST be either a valid `SchemaV1` object or the JSON value `null`. The field MUST always be present.
- The SUT MUST NOT modify the provided AES. Validators are read-only consumers of AES.
- The SUT MUST NOT require any fields beyond `aes` and `schema`. Additional fields MAY be ignored.

---

## 3. Result Envelope

The SUT MUST write exactly one JSON object to stdout before exiting with code `0`:

```typescript
{
  "ok": boolean,
  "errors": Diagnostic[],
  "warnings": Diagnostic[],
  "guarantees": Record<string, string[]>
}
```

### 3.1 Field rules

- `ok` MUST be `true` if and only if `errors` is empty.
- `errors` MUST be present. It MUST be an empty array when `ok` is `true`.
- `warnings` MUST always be present. It MAY be an empty array.
- `guarantees` MUST always be present. It MAY be an empty object (`{}`). When non-empty, keys are canonical paths and values are arrays of guarantee labels. Output MUST be deterministic given the same input.

---

## 4. Diagnostic Shape

Each entry in `errors` and `warnings` MUST conform to:

```typescript
{
  "path": string | null,
  "code": string,
  "phase": number,
  "span": [number, number] | null
}
```

### 4.1 Field rules

- `path` MUST be a canonical AEON path string (e.g., `$.user.name`) or `null` if the diagnostic does not relate to a specific path.
- `code` MUST be a non-empty string identifying the violation. Codes are defined per spec version in the error model appendix.
- `phase` MUST be a positive integer corresponding to the processing phase that produced the diagnostic (e.g., `5` for type constraints, `6` for schema validation, `7` for reference resolution, `8` for finalization).
- `span` MUST be `[start, end]` where `start` and `end` are zero-based character offsets into the original AEON source, or `null` for diagnostics where no source location is available (e.g., a missing required path). The SUT MUST NOT guess span values.

---

## 5. Guarantees

When a SUT produces output guarantees (phase 9), it MUST encode them as:

```json
{
  "$.path.to.value": ["guarantee-label-a", "guarantee-label-b"]
}
```

- Keys MUST be canonical paths.
- Values MUST be arrays of guarantee label strings as defined in the AEOS spec.
- Output MUST be deterministic: the same AES + schema MUST always produce the same guarantees map.
- The SUT MUST NOT emit guarantees for paths not present in the AES.

---

## 6. Conformance Requirements Summary

| Requirement | MUST / MUST NOT |
|-------------|----------------|
| SUT reads input envelope from stdin | MUST |
| SUT writes result envelope to stdout | MUST |
| SUT exits `0` when it produces valid result JSON | MUST |
| SUT uses exit codes to signal `ok: false` | MUST NOT |
| SUT modifies the input AES | MUST NOT |
| `schema` field always present in input | MUST |
| `errors`, `warnings`, `guarantees` always present in output | MUST |
| `ok: true` when `errors` is empty | MUST |
| `ok: false` when `errors` is non-empty | MUST |
| `span` guessed when no location is available | MUST NOT |
| `guarantees` output is deterministic | MUST |
| SUT requires fields beyond `aes` and `schema` | MUST NOT |

---

## 7. Runner Behaviour

The runner MUST:

- Invoke the SUT once per test case.
- Use the same envelope protocol for every suite. Per-suite protocol variations are not supported.
- Treat a non-zero exit code as a harness failure with an error message indicating protocol violation.
- Treat invalid or unparseable stdout JSON as a harness failure, not a test failure.
- Record both `errors` and `warnings` from the result envelope in test output.

The runner MUST NOT:

- Share state between SUT invocations.
- Modify the test case's input envelope before passing it to the SUT.
- Interpret stderr content as structured output.

---

## 8. Implementing a Conforming SUT

To validate your AEON engine against the CTS:

1. Build a thin CLI wrapper around your validator that:
   - Reads one JSON object from stdin
   - Invokes your validator with `input.aes` and `input.schema`
   - Writes the result envelope to stdout
   - Exits `0`
2. Run the CTS runner pointing at your binary:
   ```
   cts-runner --sut ./your-validator --cts path/to/aeos-validator-cts.v1.json
   ```
3. Use the per-suite files in `cts/aeos/v1/suites/` to target a subset. Suites are independent by default; check the `requires` metadata field for any cross-suite dependencies.
4. A passing suite means your engine conforms to the AEOS constraints that suite covers. Consult the `spec` metadata in each suite file for the spec sections each test exercises.

---

## 9. Annotation CTS Lane (orthogonal note)

The annotation CTS lane is intentionally orthogonal to the AEOS envelope protocol defined in this document.

- AEOS CTS (`cts/aeos/v1`) uses the stdin/stdout envelope contract in Sections 2–4.
- Annotation CTS (`cts/annotations/v1`) validates source-to-annotation emission behavior and does not alter AEOS envelope semantics.
- Implementations MAY use a different SUT surface for annotation CTS (for example, CLI inspect output), as long as runner expectations remain deterministic and explicitly documented.

This separation preserves backward compatibility for AEOS validator conformance while allowing independent evolution of annotation-stream conformance.
