---
id: appendix-validator-conformance-v1
title: Third-Party Validator Conformance
description: CTS-owned conformance expectations for validator implementations and interop verification practices.
group: CTS Documentation
path: cts/validators/v1/third-party-validator-conformance
---

# Third-Party Validator Conformance

Status: CTS-owned validator conformance guidance

**Applies to:** Any non-AEOS validator consuming AEON Assignment Event Streams (AES)

Canonical spec topic owner: `aeonite-specs/aeos/v1/drafts/AEOS-spec-v1.md`

This CTS-owned document captures the operational conformance expectations for third-party validators. If it conflicts with the AEOS spec line, the AEOS spec line wins and this document should be updated.

---

## 0. Purpose and Scope

This appendix defines the **minimum conformance requirements** for any third-party validation engine that consumes the **Assignment Event Stream (AES)** produced by AEON Core.

AEON Core’s **sole semantic output** is AES.
AES preserves source order, binding intent, symbolic structure, and provenance, and MUST remain uninterpreted by validators .

This document exists to ensure that alternative validators can interoperate **without fragmenting AEON semantics** or violating the one-way pipeline guarantees.

---

## 1. Conformance Definition

A third-party validator is **AEON-conformant** if and only if it:

1. Consumes **AES** (not source text, not AST)
2. Treats AES as **read-only**
3. Performs **validation only**, not interpretation
4. Produces diagnostics without mutating semantics
5. Respects AEON’s phase boundaries 

Validation is a **gatekeeper**, not a factory.

---

## 2. Input Requirements

### 2.1 Primary Input

A validator MUST accept:

* An **ordered Assignment Event Stream (AES)**
* Optional external schema or rule definitions

Each Assignment Event MUST be treated as immutable and authoritative.
Validators MUST NOT derive meaning beyond what is symbolically present .

---

### 2.2 AES Metadata (Recovery Awareness)

If AEON Core emitted AES in recovery mode, this MUST be explicit via metadata:

```ts
AES.meta ::= {
  recovery_mode?: "none" | "allow-duplicates" | "best-effort"
}
```

Validators MUST NOT infer recovery intent implicitly.

---

## 3. Output Requirements

### 3.1 Canonical Validator Result Envelope (Normative)

A conformant validator MUST emit a result object with the following minimum structure:

```json
{
  "ok": false,
  "errors": [
    {
      "path": "$.server.port",
      "span": [10, 14],
      "message": "Expected IntegerLiteral, got StringLiteral",
      "phase": "schema_validation",
      "code": "type_mismatch"
    }
  ],
  "warnings": [],
  "guarantees": {
    "$.age": ["integer-representable"]
  }
}
```

### 3.2 Result Semantics

* `ok: true` indicates validation success
* `ok: false` indicates validation failure
* Validators MUST NOT output a modified AES

---

### 3.3 Diagnostic Codes

Validators SHOULD use **AEON Standard Error Codes** where applicable (see Appendix: *Standard Error Codes*).

For implementation-specific diagnostics, error codes MUST be namespaced using a vendor or project prefix, for example:

```
acme:invalid_port_range
```

This ensures interoperability across tooling.

---

## 4. Mandatory Invariants

### 4.1 AES Immutability

Validators MUST NOT:

* mutate Assignment Events
* rewrite `value` nodes
* normalize or coerce literals
* inject defaults or derived values

AES values MUST NOT be coerced, normalized, resolved, or evaluated during validation .

---

### 4.2 Order Preservation

* AES order is authoritative lexical source order
* Validators MUST NOT reorder events
* Validators MUST NOT sort by path

Ordering is deterministic and semantically significant .

---

### 4.3 Uniqueness (Const Semantics)

* Each canonical path MUST appear at most once
* Duplicate bindings MUST be treated as errors
  **unless** `AES.meta.recovery_mode` explicitly permits duplicates

Even in recovery mode:

* Validators MAY observe duplicates
* Validators MUST NOT reconcile or resolve them

Uniqueness is a core AEON invariant .

---

### 4.4 Phase Boundary Enforcement

Validators MUST NOT perform behavior from later AEON phases:

| Forbidden Behavior               | Corresponding Phase |
| -------------------------------- | ------------------- |
| Processor execution              | Phase 5             |
| Schema-driven coercion           | Phase 5+            |
| Reference resolution (`~`, `~>`) | Phase 7             |
| Materialization                  | Phase 8             |

Validators are limited strictly to **schema-level validation** .

---

## 5. What Validators MAY Do

Validators MAY:

* Validate **structure**
* Validate **literal classes**
* Validate **representation eligibility**
* Validate **cross-binding presence constraints**
* Validate **annotation/datatype presence**
* Emit diagnostics with path + span
* Emit **guarantees** (see Section 6)

All validation is performed against the **entire AES**.

---

## 6. Guarantees

Guarantees are **advisory, non-semantic assertions** about representation properties.

They allow downstream interpreters to skip redundant checks without mutating AES.

### 6.1 Tier-1 Standard Guarantee Vocabulary (Normative)

Validators MAY emit the following standardized guarantees:

| Guarantee               | Meaning                                                                                                                                                                                               |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `integer-representable` | The value is either a NumberLiteral with no fractional or exponential component                                                                                                                       |
|                         | **or** a StringLiteral consisting solely of an optional leading sign (`+` or `-`) followed by one or more digits (`0–9`). This guarantee is **syntactic only** and makes no claim about numeric range |
|                         | precision, or storage capacity.                                                                                                                                                                       |
| `float-representable`   | The literal matches a valid floating-point syntax (syntactic only).                                                                                                                                   |
| `boolean-representable` | The literal matches boolean syntax.                                                                                                                                                                   |
| `non-empty-string`      | StringLiteral length > 0.                                                                                                                                                                             |
| `regex:<id>`            | Matches named regular expression.                                                                                                                                                                     |
| `present`               | Binding exists.                                                                                                                                                                                       |

Processors MAY rely on Tier-1 guarantees.

---

### 6.2 Tier-2 Namespaced Guarantees (Non-Normative)

Validators MAY emit namespaced guarantees:

```json
{
  "$.email": ["acme:corporate-email"]
}
```

Rules:

* MUST be namespaced
* MUST NOT be relied upon by generic processors
* MUST NOT affect validator conformance

---

### 6.3 Guarantee Flow (Conceptual)

```
AES
 │
 │  (read-only)
 ▼
Validator (AEOS or third-party)
 │
 │  validates representation
 │  emits guarantees
 ▼
Result Envelope
 │
 │  guarantees observed (optional)
 ▼
Interpreter / Tonic
 │
 │  performs coercion & meaning
 ▼
Materialized Output
```

*Guarantees are advisory signals, not transformed values.*

---

## 7. Prohibited Validator Behavior (Hard Failures)

A validator MUST NOT:

1. Coerce values (`"42"` → `42`)
2. Inject defaults
3. Resolve references
4. Compute derived values
5. Depend on non-normative AES fields
6. Assume downstream correction

Violating any of the above disqualifies conformance.

---

## 8. Consequences of Violating the Order

### 8.1 Semantic Forks

If one validator coerces `"42"` and another does not, AES ceases to be a stable interface.
This fragments the ecosystem and violates deferred semantics .

---

### 8.2 Loss of Auditability

Injecting values not present in source destroys provenance and audit guarantees .

---

### 8.3 Phase Collapse

Resolving references or materializing values during validation collapses AEON’s phase model and eliminates processor isolation .

---

### 8.4 Order-Dependent Meaning

Reordering events changes semantic eligibility and invalidates future constraints.
AES order MUST remain authoritative .

---

## 9. Conformance Checklist

A validator is conformant if all are true:

* [ ] Consumes AES as read-only
* [ ] Preserves event order
* [ ] Respects recovery metadata
* [ ] Does not coerce or normalize values
* [ ] Does not resolve references
* [ ] Does not inject defaults or derived nodes
* [ ] Produces PASS/FAIL + diagnostics only
* [ ] **Output adheres to the Canonical Validator Result Envelope schema**
* [ ] Errors cite path + span + phase

---

## 10. Non-Conformant Modes

Tools MAY offer explicitly named non-conformant modes (e.g. `interpret`, `materialize`, `compile`), but:

* MUST NOT call them “validation”
* MUST NOT claim AEON conformance in those modes

---

## Closing Statement

> **Validation constrains representations.
> Interpretation creates meaning.
> AEON requires these to remain separate.**

---

### Status

✅ **Green-team approved**
✅ **Red-team hardened**
✅ **Ready to lock**
