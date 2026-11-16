# Aeonic unqualified civil date-time snapshot 0.1 and mutable next

The default immutable target is
`cts/aeonic-temporal-civil-datetime/v1/aeonic-temporal-civil-datetime-cts.v1.snapshot-0.1.json`,
aligned with `aeonic-temporal-civil-datetime-specs-v1-snapshot-0.1`. Exact manifest
bytes are recognized by the runner; its source/schema, isolated binding/suite
copies and checker helpers are hash-pinned. The explicitly selected profile is
`aeonic.operations.temporal.civil-datetime.v1`.

The separate `.next.json` target advances to snapshot 0.2 and remains mutable.
Artifact-only checks, test replays, failures and mutable runs never establish a
stable claim. A recognized frozen semantic execution must pass every selected
case to set `stable_conformance_claim: true`. Native capacity and package release
remain separate; there are no semantic case opt-outs.

## Complete capability selections

| Selection | Required operations |
| --- | --- |
| `relations` | `equal`, `compare`, `relate` |
| `arithmetic` | `shift`, `shiftClock`, `step`, `materialize` |
| `all` | Both groups plus arithmetic-to-relation chains. |

Every case required by a selected capability runs; no case filter, semantic
exclusion or empty target is accepted. Unclaimed capability cases are counted
separately. Selection does not assert that a provider's other operations are
unavailable. Relations-only implementations consume derived bundles without
producing them locally. Temporal Arithmetic consumes numeric value/history
bundles without claiming separate numerical arithmetic capabilities.

All operations explicitly select the profile through logical policy/context.
Unqualified Gregorian coordinates in years 0001–9999 have ordinary seconds and
exact finite fractions under selected capacity. Reduced dates and clocks retain
all compatible coordinates, not a containing hull. Clock-coordinate seconds do
not assert elapsed time under UTC, a timezone or WTC authority. Qualified forms,
standalone clocks and date-only bridges are outside this contract.

## Commands and artifact evidence

```sh
python3 -m pip install -r runners/requirements-aeonic-operations.txt
python3 runners/run_aeonic_temporal_civil_datetime.py --specs-root ../aeonite-specs --capability-set relations --check
python3 runners/run_aeonic_temporal_civil_datetime.py --specs-root ../aeonite-specs --capability-set arithmetic --check
python3 runners/run_aeonic_temporal_civil_datetime.py --specs-root ../aeonite-specs --capability-set all --check
```

Semantic execution additionally supplies `--sut 'command arguments'`, with
optional `--cwd`, `--timeout` and `--report`. Invocation is shell-free. Python
3.9+ is supported. Tests may select the exact dependency through
`AEONIC_DATETIME_SPECS_ROOT`; CI checks it out separately so older lanes retain
their own pins. Earlier frozen files and imported shared helpers are not rewritten. The date-time
amount checker is aligned with the already-required finite Number grammar before
its first freeze.

There are 154 operation cases, four live-result chains and one eight-value law
group. Full execution makes 355 SUT calls, including 192 generated relation
calls, plus cached equality/strict-before transitivity assertions. Artifact-only
mode makes zero SUT calls and reports `artifacts-validated` with
`semantic_execution: false`. The new boundary cases enforce existing finite Number grammar reuse (no leading-zero
integer mantissas) and scalar temporal-character admission, including raw JSON and
derived coordinates. Unit-test fixture providers/replay controls check
assertions and transport; they are not an operations implementation or semantic
conformance evidence. Native default capacity needs separate probes.

To select mutable development explicitly, add
`--manifest cts/aeonic-temporal-civil-datetime/v1/aeonic-temporal-civil-datetime-cts.v1.next.json`.

## Binding and admission

`cts.protocol.v1` uses `lane`, `case_id`, exactly one fixture field (`request` or
`requestText`) and trusted `policy.resourceLimits`. Outer transport extensions
remain allowed; fixtures and policy are closed. Logical policy/context do not
contain trusted resource settings. The complete 15-limit map is explicit in the
manifest, and case companions override named dimensions only. Null, scalars,
arrays, unknown fields, Boolean/fractional/unsafe limits are harness errors.

Preserve raw JSON number spelling, including `-0`, unsafe integers and huge/tiny
exponents even in opaque deferred payloads. Logical bytes exclude outer CTS
framing. Text input is not reserialized; structured requests use compact JSON
and original number tokens. Duplicate logical keys remain evidence for stage-2
rejection. Result diagnostics produce no value or metadata and no implicit null.

Point/interval arrays are canonical nonempty exact unions. Flags explicitly
preserve both endpoint memberships. A dedicated excluded upper marker represents
the finite start-of-year-10000 boundary without adding that coordinate as a
member. Missing points and gaps remain missing. Metadata keeps date origin,
clock origin, clamping and approximation independent, and relations retain both
operands' metadata separately.

Source-template work/candidate guards precede step/materialization matching.
Partial-period mismatch with insufficient matching capacity therefore returns
`resource_limit` first. Calendar image and exact numeric workspace guards are
also portable and checked before expansion. Counted work is a logical contract,
not an implementation's iteration count or an assurance about whole-process heap.

## Assertion coverage

| Fixture or observed field | Consumed assertion |
| --- | --- |
| Whole `expected.value`, including coordinate strings, endpoint flags and marker | Closed schema, intrinsic/canonical set checks and recursive exact equality. |
| Origins, sticky histories, current evaluation/clamping, effective policy | Exact comparison; positive fixture checks additionally validate metadata ownership/propagation. |
| Diagnostic reason, stage, pointer/null path | Exact comparison; only optional non-normative message is ignored. |
| Protocol `ok`, warnings, errors | Required consistency with result outcome; no unexpected warnings/errors. |
| Work/intermediate/output/text/number/byte limits | Explicit complete maps, positive fixture admission, boundary expected diagnostics and bounded result checks. |
| Chain links | Replace destination with the actual prior success's `value`, not its expected fixture. Symbols/diagnostics cannot feed temporal chains. |
| Relation laws | All observed pair labels and equality/strict-before transitivity; exact endpoint-aware oracle. |
| Artifact provenance | Source/schema/binding/suite/helper hashes, runner digest and post-run recheck. |

Negative controls deliberately change output values, flags, origins, history,
policy, diagnostics and protocol status. Tests also observe work before failure:
piece counts before array iteration, source-template guards before construction,
text/fraction/exponent guards before conversion, and bounded envelope sizing.
These checks do not implement a calendar/clock shift engine. Expected arithmetic
vectors remain fixed assertions under the owning specification.
