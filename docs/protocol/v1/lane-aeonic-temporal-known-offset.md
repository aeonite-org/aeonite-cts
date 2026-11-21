# Known-offset coordinate mutable CTS

This lane exercises `aeonic.operations.temporal.known-offset.v1` in the ordinary
86,400-second coordinate model. Conversion and Relations are independently complete
capabilities; combined claims additionally execute cross-capability chains. It
preserves original offset claims without verifying physical UTC realization.

The sole target is mutable
`cts/aeonic-temporal-known-offset/v1/aeonic-temporal-known-offset-cts.v1.next.json`.
It has 224 cases: 221 operation vectors, two actual-result chains and one relation
law group. There is no immutable target or stable conformance claim. Artifact
checking validates pinned sources/schema/helpers, expected positive images and
closed diagnostic expectations; it does not execute a SUT or independently prove
that a diagnostic vector has the right precedence. Harness mutation tests are
separate from product conformance and native capacity evidence.

Use Python 3.9+ and `runners/requirements-aeonic-operations.txt`:

```sh
python3 runners/run_aeonic_temporal_known_offset.py --specs-root ../aeonite-specs --check
python3 runners/run_aeonic_temporal_known_offset.py --specs-root ../aeonite-specs --capability-set conversion --check
python3 runners/run_aeonic_temporal_known_offset.py --specs-root ../aeonite-specs --capability-set relations --check
```

For execution, replace `--check` with `--sut '<adapter command>'`. Use `--cwd` for
the adapter's working directory. A selected capability executes every mandatory
case for that complete capability, plus shared admission cases. Cross-capability
cases are omitted only when a capability is unclaimed, never by semantic case
exclusion. A complete mutable pass still reports `stable_conformance_claim: false`.
No implementation is supplied or claimed by this change.

The protocol envelope has `lane`, `case_id`, `fixture`, `policy` and transport
extensions. Fixture contains exactly one of `request` (logical structured JSON)
or `requestText` (logical raw JSON text). Negative logical requests deliberately
need not satisfy the successful/admission operation schema. Outer policy contains
only trusted `resourceLimits`; malformed/null limits are harness errors. The runner
merges supplied limit overrides with its complete explicit baseline before sending.
Limits are per call. A chain sends each earlier actual `result.value` into the
next designated input; expected bundles never replace observed values.

The adapter returns the existing `cts.protocol.v1` output with `result` holding
the closed operation envelope. `ok` agrees with `result.outcome`; warnings are
empty. A diagnostic has exactly one protocol error with matching `code` and null
`path`, `span`, `phase`; semantic stage/path remain inside `result.context`.
Optional scalar diagnostic messages do not affect equality. Other result fields,
metadata, coordinates, frame spellings, flags and all history/origin markers are
compared completely. The trusted adapter must expose only its claimed capability
surface; logical requests cannot enable operations.

`maxInputPieces` totals both operands, unlike existing civil date-time limits.
Expanded year/month literal pieces count before allocation; conversion work and
candidates count P, relation work counts L + R. No interval interiors are enumerated.
The explicit baseline permits both leap-year operands, but simultaneous maximum
precision/piece combinations can still exceed envelope bytes. Separately verify
native defaults and raised capacities; semantic rejection is not proof of native
capacity. Raw JSON admission preserves token spelling including `-0`, duplicate
keys and opaque payload bytes. This is not elapsed-time or zone resolution.

The generator `runners/generate_temporal_known_offset.py <specs-root>` rewrites
only this mutable target and refreshes its exact content fingerprints. Review all
changed expectations. Commit the owning source/schema first so regeneration pins
an actual retained specification revision, then keep CI's checkout at that pin.
Never use this generator on immutable artifacts. Existing lanes remain unchanged.

Coverage guards require successful linked conversion-to-conversion chains for
Conversion, non-vacuous law groups for Relations, and linked conversion-to-relation
chains for combined claims. The law group retains the cross-frame equality pair
and now has three strictly ordered extents (four input representations), giving
two strict-before transitivity witnesses. Removing required coverage rejects the
target before artifact validity or complete execution can be reported. Combined
execution requires 274 SUT calls; this remains a mutable target.

Positive raw requests are parsed as strict standalone JSON with numerical token
spellings preserved. Their validated operation counts toward coverage exactly
like structured positives. Stage-1 negative requests are shared admission cases
with no capability requirement, classified without recursively decoding raw
bodies. This permits deep depth-limit cases on the minimum Python runtime.
Structured bytes use minimal JSON string escapes and literal UTF-8, with root
container depth one; raw text pays its supplied bytes verbatim. The fixtures cover
non-ASCII literal versus escaped bytes, exact depth boundaries and 1,051 nested
arrays in raw text.

A distinct-input equality witness requires different complete logical operand
values with equal coordinate coverage. Object-key order and position in the law
array do not make otherwise identical values distinct. Exact copies, including
independently allocated deep copies, cannot replace the cross-frame equality
pair when validating or executing a target.
