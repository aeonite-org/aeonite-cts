# Aeonic Operations comparison lane

Status: snapshot 0.1 frozen locally on 2026-11-09; mutable follow-up target 0.2.
The default manifest is `aeonic-operations-cts.v1.snapshot-0.1.json`, identifying
`aeonic-operations-cts-v1-snapshot-0.1`. Its suites, binding, specification source
and operation schema are immutable copies. The `.next.json` manifest now names
the separate `aeonic-operations-cts-v1-snapshot-0.2` development target.
No package or GitHub release is implied by the local freeze.

The [Aeonic Semantic Language working contract](../../../../aeonite-specs/sources/aes/v1/aeonic-semantic-language-v1.aeon)
owns operation semantics and the mutable schema at
`aeonite-specs/resources/aeonic-operations/v1/comparison-contract.schema.json`.
Snapshot 0.1 selects frozen resources beneath that directory's `snapshots/0.1/`,
aligned with `aeonic-operations-specs-v1-snapshot-0.1`. The manifest records the
exact specification schema/source and binding paths as well as their digests.
This lane owns fixtures, selection, generation, transport binding and matching.
Legacy `value-semantics` and SANSA targets retain their existing meanings.

Each manifest records exact SHA-256 digests of its suites, operation
schema, binding schema and specification source. A deliberate working-contract
edit requires updating these digests and obtaining new implementation reports.
Released manifests and their referenced artifacts remain immutable.

## Invocation and fixture forms

Use `cts.protocol.v1`: one envelope on stdin, one output envelope on stdout,
then exit zero for either a successful value or an operation diagnostic.
Malformed transport/bindings or a crash are harness failures. Stderr is log-only.

```json
{
  "lane": "aeonic-operations",
  "case_id": "example",
  "fixture": {
    "request": {
      "operation": "compare",
      "input": {
        "left": { "category": "finiteNumber", "value": "1" },
        "right": { "category": "finiteNumber", "value": "2" }
      }
    }
  },
  "policy": {}
}
```

Exactly one fixture member is present: `request` for any structured JSON value,
including intentionally invalid requests, or `requestText` for exact logical
JSON source. Both/neither, non-string text, or unpaired surrogates in the text
binding are fixture errors. Escaped unpaired surrogates *inside* logical JSON
remain operand-validation inputs.

For `requestText`, count the exact decoded string's UTF-8 bytes before parsing:
whitespace and JSON escape spelling count. Exclude the outer CTS envelope.
Do not reserialize before the byte guard. Structural depth counts containers,
root level one, excluding punctuation inside strings. Applicable admission
guards precede strict JSON decoding. Duplicate member names, malformed JSON,
and non-JSON constants produce `invalid_operand`, stage 2, null local path.
Structured fixtures need no particular host serializer spelling; byte-sensitive
vectors use `requestText`. Check depth before invoking a recursive serializer.

Outer `policy.resourceLimits` is trusted harness configuration, separate from
`request.input.policy`. Its portable nonnegative integer limits are
`maxRequestBytes`, `maxRequestDepth`, `maxNumericCharacters`, `maxStringScalars`,
`maxSymbolScalars`, `maxDeclarations`, and `maxDeclaredSymbols`. Positive
capacity vectors run with adequate other budgets. Restricted negative-test
budgets do not establish an implementation's advertised support capacity.

## Results and normative matching

Success: `ok` is true, `errors` and `warnings` are empty, and `result` contains
the closed operation value envelope. Match its symbolic value and the complete
effective-policy metadata, including independently selected string/symbol rules
and the complete selected order plus identifier/version for named declarations.

Failure: `ok` is false, `warnings` is empty, and `errors` contains exactly one
diagnostic with `code` equal to `result.reason`. Its `path`, `span` and `phase`
are null because this logical boundary has no AEON source/document location.
`result` contains `outcome: "diagnostic"`, the reason and exact operation-local
`context.stage` and `context.path`; it has no `value`, including no `value: null`.
The local path is a JSON Pointer or null when unrepresentable, for example an
isolated surrogate in an unknown field name. Optional diagnostic message text
is ignored. Comparison results never become protocol Booleans.

Match objects independently of member order, preserve array order and JSON
types, and perform no string normalization. Unknown operation-result fields
fail the closed schema. Extra transport/error-extension fields remain ignored
under the base protocol. No advisory warnings are defined by this first lane.

## Capability selection

`requiredCapabilities` is suite-selection metadata, never a caller input or
permission to skip an error. The runner supports:

| Set | Operation cases | Ordering-law groups | Generated boundaries |
| --- | ---: | ---: | ---: |
| `baseline` | 124 | 4 | 16 |
| `baseline-with-declared-order` | 135 | 5 | 21 |

Baseline includes request/configuration validation, finite numbers, strings,
Booleans and codepoint symbols. Declared-order execution, membership/resolution,
and its resource capacities are separately selected. Local configuration
validity precedes optional-profile availability: empty/duplicate declarations
and unknown fields remain validation failures, even if a later comparator is
unavailable. A valid overridden comparator is not resolved.

Tests marked `invocationProfile: "without-declared-order"` use a separately
supplied SUT command with that execution capability unavailable. This is trusted
harness invocation context, outside the logical request and outer policy.
The runner requires `--without-declared-order-sut` explicitly; it does not
silently skip these tests. The selected symbols `mode` path identifies an
unavailable effective declared-order comparator at stage 3. Shape failures
precede availability, and unavailable effective profiles precede operand errors.

## Execution

Install `runners/requirements-aeonic-operations.txt` in the chosen Python
environment. Run `runners/run_aeonic_operations.py` with `--sut`,
`--without-declared-order-sut`, and the required `--cwd`. Commands use shlex
splitting with no shell. `--specs-root` can locate a separate specs checkout;
the default is the sibling `aeonite-specs` repository.

Each ordering group executes both primitives over every pair, validates all
result metadata, then checks reflexivity, reversal, strict transitivity,
equivalence substitution, primitive agreement and definiteness. Boundary
generators construct the actual long values, declarations, exact byte counts,
and container depths; they are not counted as passed merely for existing.

All selected groups/cases/boundaries execute. A failure appears in the report
and makes the runner exit nonzero. A timeout is a harness failure, not a portable
`resource_limit`. Reports include target status, artifact digests, invocation
commands, capability set, execution counts and failures. They reject any pinned
artifact changed during execution. Working reports always set
`stable_conformance_claim` to false; a passing immutable-target run can record
the exact local compatibility claim. Running the lane does not create, freeze
or publish a snapshot.
