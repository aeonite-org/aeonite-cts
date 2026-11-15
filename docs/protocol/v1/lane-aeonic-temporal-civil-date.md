# Aeonic civil-date temporal snapshot 0.1

The default target is `aeonic-temporal-civil-date-cts-v1-snapshot-0.1`, aligned
with `aeonic-temporal-civil-date-specs-v1-snapshot-0.1` at specification revision
`279a7679d654dbf135296650e25038ca5bd5b037`. It pins snapshot source/schema under
`resources/aeonic-operations/v1/snapshots/0.1/`, binding/suites under the lane's
`snapshots/0.1/`, and all imported checker helpers. Exact manifest bytes are
recognized by the owning runner. Edits, relabels and semantic exclusions cannot
acquire an immutable claim. No package release or native capacity is implied.

The separate `.next.json` target advances to snapshot 0.2 with mutable source
and schema. Select it explicitly using `--manifest`; it never emits a stable
conformance claim. Earlier numerical/comparison snapshots remain unchanged.

## Two complete capabilities

| Selection | Complete required operations |
| --- | --- |
| `relations` | `equal`, `compare`, `relate` |
| `calendar` | `shift`, `step`, `materialize` |
| `all` | Both capabilities plus actual calendar-to-relation chains. |

The profile `aeonic.operations.temporal.civil-date.v1` must be explicitly
selected through logical policy/context. Both capabilities use the same closed
date bundles, canonical nonempty inclusive range sets, source-granularity and
clamping-history rules. Years remain 0001–9999. No date-set widening, automatic
Boolean predicate, timezone/instant inference, lossy materialization or schema
annotation is introduced.

Every case required by a selected capability runs. There is no per-case filter,
semantic opt-out or empty passing target. Reports count cases outside unclaimed
capabilities separately; those exclusions cannot remove a selected operation.
Selecting one claim does not assert that the provider's other operations are
unavailable. A relation-only claim must consume canonical arithmetic-style date
sets/history, but it does not need a local arithmetic producer. Combined chains
feed actual successful bundles between capabilities.

## Run or validate

```sh
python3 -m pip install -r runners/requirements-aeonic-operations.txt
python3 runners/run_aeonic_temporal_civil_date.py \
  --specs-root ../aeonite-specs --capability-set relations --check
python3 runners/run_aeonic_temporal_civil_date.py \
  --specs-root ../aeonite-specs --capability-set calendar --check
python3 runners/run_aeonic_temporal_civil_date.py \
  --specs-root ../aeonite-specs --capability-set all --check
```

Semantic execution additionally supplies `--sut 'command arguments'`, optional
`--cwd`, `--timeout` and `--report`. Commands use shell-free argument splitting.
Python 3.9+ is supported. The selected map contains all eight logical limits;
case companions override only their named dimensions. Explicit settings are
test admission, not a promise that an implementation's native defaults support
every Cartesian combination or impose total process time/heap bounds.

The runner tests accept `AEONIC_TEMPORAL_SPECS_ROOT` for this dependency. The
full repository job keeps the older semantic lanes' existing specification pin
and checks out this temporal revision separately; a new lane does not require
repinning unrelated mutable comparison inputs. The temporal-only workflow uses
its own matching specification sibling on both Python versions.

The target has 181 operation cases, two chains and one bounded relation-law
group. Full execution adds generated pairwise equal/compare/relate checks and
cached equality/strict-before transitivity checks. Artifact-only mode executes
zero SUT calls and reports `artifacts-validated`, `semantic_execution: false`,
`stable_conformance_claim: false`. Only a successful semantic run of the
recognized immutable target emits a stable claim for the selected complete
capabilities. A failed run, artifact-only check or mutable semantic run cannot.
Replay controls in runner unit tests test the checker, not an implementation.

## Binding and ownership

The `cts.protocol.v1` request has `lane`, `case_id`, exactly one fixture field
(`request` or `requestText`) and trusted `policy.resourceLimits`. Outer transport
extensions remain allowed; fixture and trusted policy shapes are closed.
Null/scalar/array/unknown/malformed resource settings are harness errors.
Reached logical limits are ordinary no-value operation diagnostics.

Adapters must preserve every logical numerical token, including integer `-0`,
unsafe integers, overflow and underflow forms. Those are usually malformed date
configuration or opaque deferred payload, but their original bytes still count
before policy/operand validation. They must not become host floats or shrink
before byte admission. `requestText` is not reserialized. Structured logical
requests use compact JSON with original number tokens and decoded scalar strings.
The artifact decoder preserves numerical tokens only within logical request
subtrees; trusted protocol settings use exact mathematical integer validation.

The owning schema covers closed shapes; semantic checker code additionally
checks intrinsic ISO dates, canonical ranges, selected widths, successful
envelope bytes and current-clamping/history consistency. These checks do not
supply a calendar operation implementation. Expected case results remain exact
conformance assertions rather than agreement between two copies of an engine.

## Assertion coverage

| Fixture/result data | Consumed assertion |
| --- | --- |
| `expected.outcome`, complete `value`, origin/history, all metadata/effective settings | Closed result/schema checks followed by recursive exact equality. |
| Diagnostic reason, stage and pointer/null path | Exact comparison, plus protocol `ok`/errors consistency; no diagnostic value allowed. |
| Optional diagnostic `message` | Validated as scalar text, deliberately excluded from equality on both sides. |
| Chain links | Validated backward temporal-only donors; actual prior `value` bundles injected, each reached result checked. |
| Law values | Complete result checking against a bounded canonical-interval relation oracle, then transitivity over observed symbols. |
| `requires` | Must match operations; fixed complete selection, no silent semantic exclusions. |
| Manifest/source/schema/binding/suites/helpers | Exact hashes before execution and again after execution; changed artifacts fail the run. |

Runner tests retain a passing replay control and deliberately wrong symbol,
operand-history, effective count and diagnostic-pointer responses that cause
nonzero failure through the actual CLI. They do not demonstrate correctness of
a temporal SUT. Law groups contain 3–8 values to keep generated work bounded.

## Work before failure

Malformed diagnostic pointer escapes are rejected by a linear scan before
schema matching. The owning schema separates pointer delimiters from token
characters, avoiding ambiguous slash partitions on invalid input. Relation-only
calendar-work at/below cases accompany the calendar work boundaries.

Result range-count and successful-envelope guards precede complete schema/range
iteration. Envelope measurement walks only through its allowance and checks
string length before escaping. Large positive-fixture counts are compared
lexically to the bounded year domain before conversion. Count/range/byte probes
use two modest sizes and a safe control; passing a final diagnostic alone is not
evidence of early rejection.

The SUT process has a timeout and writes stdout/stderr to temporary files. The
8 MiB protocol-output cap is checked before controller decoding; it is a
post-process harness cap, not a disk-growth limit or sandbox for arbitrary
executables. Repository artifacts and outer framing remain trusted harness
material, outside logical operation budgets. Native getters/proxies, key
enumeration, per-application chain budgets and machine capacity stay separate.

Frozen comparison/finite/rational resources and their owning runners are
unchanged. This lane reuses pinned strict JSON/protocol/chain and bounded process
helpers without changing their globals or immutable-target recognition.
