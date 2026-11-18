# Aeonic standalone civil clock snapshot 0.1 and mutable next

The default immutable target is
`cts/aeonic-temporal-civil-clock/v1/aeonic-temporal-civil-clock-cts.v1.snapshot-0.1.json`,
aligned with `aeonic-temporal-civil-clock-specs-v1-snapshot-0.1`. Exact manifest
bytes are recognized by the runner; isolated source/schema, binding/suites and
checker helpers are hash pinned. Profile selection remains explicitly
`aeonic.operations.temporal.civil-clock.v1`.

The separate `.next.json` target advances to snapshot 0.2 and remains mutable.
Only an actual passing execution against the recognized immutable manifest, with
every case in a complete selected capability and explicit limits, reports
`stable_conformance_claim: true`. Artifact-only checks, failures and mutable runs
never do. Synthetic fixture replays test the harness and are not evidence of a
genuine implementation's semantics. Native capacities and publication remain
separate facts; earlier frozen files/defaults are unchanged.

## Complete capabilities

| Selection | Required operations |
| --- | --- |
| `relations` | `equal`, `compare`, `relate` |
| `arithmetic` | `shiftClock`, `step`, `materialize` |
| `all` | Both complete groups and arithmetic-to-relation chains |

Claims have no semantic opt-outs or arbitrary case filters. An unclaimed group's
cases are counted separately; selection does not disable the provider's other
operations. Relations-only providers consume derived sets. Arithmetic consumes
finite numeric value/history bundles without requiring numerical arithmetic.
Logical policy/context must explicitly select the profile; availability and
trusted resource limits belong to the host, outside the logical request.

## Values and boundary

Authored `HH:`, `HH:MM` and `HH:MM:SS[.digits]` describe unqualified ordinary civil
clocks on reference day zero. Full second forms are points; hours/minutes are
half-open extents. Derived canonical nonempty point/interval unions retain signed
relative days as canonical text and exact finite fractional seconds. Endpoint
inclusion and gaps are preserved, with no modulo wrap or date anchoring. Equality
includes relative day; chronology describes this relative axis, not dated events.
Materialization requires exact selected extent starting on day zero; it cannot
silently discard carry. An excluded next-midnight end is permitted for the final
hour/minute on day zero.

Origin clock form is descriptive metadata. Approximation history is a separate
sticky string marker; a marked zero shift amount propagates it. There is no
clamping marker. Unknown domains are recognized only within this new profile's
vocabulary and rejected after supported operand validation; their payloads stay
opaque. Qualifiers, leap seconds, rational shift amounts, wrapping and external
authorities are deferred.

## Commands

```sh
python3 -m pip install -r runners/requirements-aeonic-operations.txt
python3 runners/run_aeonic_temporal_civil_clock.py --specs-root ../aeonite-specs --capability-set relations --check
python3 runners/run_aeonic_temporal_civil_clock.py --specs-root ../aeonite-specs --capability-set arithmetic --check
python3 runners/run_aeonic_temporal_civil_clock.py --specs-root ../aeonite-specs --capability-set all --check
```

Python 3.9+ is supported. `--check` validates artifacts without executing a SUT
and reports `artifacts-validated` and `semantic_execution: false`. Semantic runs
supply `--sut 'command arguments'`, optionally `--cwd`, `--timeout`, `--report`.
Invocation uses no shell. Tests use `AEONIC_CLOCK_SPECS_ROOT` for the owning pin;
CI checks it out separately from other lanes' dependencies.

There are 180 operation cases, two live-result chains (six steps) and one
eight-value law group. Full execution makes 378 SUT calls, including 192 generated
relation cases, plus observed equality and strict-before transitivity assertions.
Local fixture-provider replays and deliberate wrong responses verify assertion
sensitivity and transport; they are not independent implementations or evidence
of civil-clock semantic conformance. The fixtures preserve the reviewed working values, diagnostics and complete
metadata/resource/precedence/law controls. Frozen-target runs against the merged
independent JavaScript/Python implementations are retained under
`docs/conformance/civil-clock-snapshot-0.1/`; fixture-provider replays remain
separate. These runs do not automatically change consumer defaults or claims.

To select mutable development explicitly, add
`--manifest cts/aeonic-temporal-civil-clock/v1/aeonic-temporal-civil-clock-cts.v1.next.json`.
New semantic cases belong there or in a newer snapshot; do not edit the frozen
copies. The [freeze record](../../conformance/civil-clock-snapshot-0.1.md) records
implementation revisions, fingerprints and verification limits.

## Binding and admission

`cts.protocol.v1` carries lane, case identity, exactly one of `fixture.request`
or `fixture.requestText`, and `policy.resourceLimits`. Transport extensions remain
allowed; logical requests, fixtures and policy/results are closed. Null, arrays,
unknown resource settings, Booleans, fractional/unsafe or negative limits are
harness errors. The complete 16-limit map is explicit, with case-local overrides.

Logical byte accounting preserves raw number tokens, including `-0`, unsafe
integers and huge/tiny exponents in opaque payloads, in both request forms. Text
is not reserialized and duplicate keys remain evidence. Compact logical JSON
bytes exclude outer CTS framing. Native admission must bound shared graphs
without unfolding them exponentially; native proxies/accessors/subclasses,
eager key enumeration, framing, process/heap and whole-chain capacity remain
separate host boundaries, not capacities established by this lane.

Piece/work, relative-day/fraction, numeric workspace, text and successful-envelope
limits are independent. Work is portable accounting rather than implementation
iteration count. Nonzero clock shifts and steps use the source's mandatory compact
workspace formulas before exponent expansion. Matching budgets precede incomplete
form diagnostics; output day capacity includes excluded endpoints. A long interval
is one piece, regardless of its relative-day span. No date/second enumeration is
required. Resource denial produces a diagnostic without a partial or rounded value.

## Assertion coverage

| Contract field | Consumed assertion |
| --- | --- |
| Value, relative days, coordinates, endpoint flags and gaps | Closed schema, canonical/intrinsic checks, exact positive arithmetic fixture checks, full observed result equality |
| History, origin, evaluation and effective policy | Complete result equality and positive fixture ownership/propagation checks |
| Diagnostic reason, stage and pointer/null path | Complete equality, ignoring only optional human-readable message |
| Protocol status, errors and warnings | Consistency with result, no unexpected warnings/errors |
| All 16 resource settings | Complete trusted map; admitted exact thresholds and fixed denial expectations |
| Chain links | Actual preceding success `value` replaces the next operand; no symbols/diagnostics as temporal values |
| Relation laws | Exact endpoint-aware oracle for all ordered pairs; observed equality/strict-before transitivity |
| Provenance | Source/schema/binding/suite/helper hashes, runner digest and post-run integrity recheck |

Checker helpers evaluate bounded successful fixture math and compact admission
formulas. They do not implement the staged failure API and cannot serve as the SUT.
Tests alter returned day/fraction/flags/gaps, metadata, symbols, diagnostics and
protocol status, and include passing controls. Resource tests observe guards before
conversion, construction and traversal at two widths. Artifact-only validation,
fixture replays, CI, stable snapshots, native capacity and releases are distinct.
