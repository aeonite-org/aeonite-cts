# Known-offset coordinate snapshot and mutable CTS

This lane exercises `aeonic.operations.temporal.known-offset.v1` in the ordinary
86,400-second coordinate model. Conversion and Relations are independently complete
capabilities; combined claims additionally execute cross-capability chains. It
preserves original offset claims without verifying physical UTC realization.

The default target is immutable local snapshot 0.1:
`cts/aeonic-temporal-known-offset/v1/aeonic-temporal-known-offset-cts.v1.snapshot-0.1.json`.
It retains 224 cases: 221 operation vectors, two actual-result chains and one
relation-law group. Its exact recognized manifest pins isolated binding/suite and
owning source/schema copies. Mutable `.next.json` advances independently to 0.2.
Only externally qualified, complete genuine passing execution against the
recognized immutable target supports a stable claim. Mutation, failure, missing calls/assertions, filtering,
artifact-only checks and mutable runs cannot establish it. See the
[capture and provider evidence](../../conformance/known-offset-snapshot-0.1.md). Artifact
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
The separately merged provider is verified in the capture record; consumer default
and claim adoption follows owning snapshot merge.

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
execution requires 274 SUT calls. These requirements apply to both frozen and
mutable targets; the exact frozen target is required for external stable-claim qualification.

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


Explicit mutable development uses `--manifest
cts/aeonic-temporal-known-offset/v1/aeonic-temporal-known-offset-cts.v1.next.json`.
All three capability selections are supported on each target. The frozen set's
147 Conversion-only calls and 135 Relations-only calls include shared admission
cases; combined execution uses 274 calls and 334 assertions. Conformance never
waives admitted semantics in response to a provider's implementation capacity.
The retained native default probes establish only their individual dimensions,
not a combined capacity floor, arbitrary native-object or process quota.


## Runner results and external provider qualification

The runner observes requests and replies, not the implementation that produced
them. A stored-answer subprocess can pass the complete protocol suite. Therefore
raw reports always set `stable_conformance_claim`, `semantic_execution` and
`provider_execution_verified` to false. `sut_attempts` counts adapter transport
attempts; `sut_executions` counts calls that returned captured output successfully.
`protocol_execution` is true only when at least one such call returned during the
current run. Failed launches do not count as executions. A returned malformed
reply can count as execution while validation still fails; a launch, timeout or
nonzero-exit failure alone cannot set the flag. Counts are per run, including on
reused runner instances. `complete_passing_execution` records complete successful
protocol checking. Those fields do not authenticate genuine computation, even
for a recognized immutable manifest. There is no CLI flag that upgrades replies
to a semantic claim.

Genuine-provider qualification is separate evidence: reviewed provider revision,
tree and source-file fingerprints; controlled commands actually invoking that
provider; matching input artifacts; and complete passing report fingerprints.
The capture's `verification.json` records this author qualification separately
from raw runner outputs. Its independent review status remains separate. A replay
report alone can never supply the source/execution assessment required for that
record. Future implementation adoption must retain both the protocol reports
and the provider qualification, without treating a bare harness pass as proof.

`--report` may not overlap pinned inputs (including symlink/hard-link aliases),
the specification input tree, or CTS/runner input directories. The replacement
entry and its referent are both checked, including parent-directory aliases and
dangling leaf links. Parent-directory symlinks are resolved before `..`, following
filesystem traversal rather than lexical path normalization. A link inside an
input directory cannot be replaced by a
report even when its referent is outside that directory. It is checked
before SUT execution and again before an atomic report replacement. Use a separate
output directory, such as `docs/conformance/` or an external results directory.
Atomic replacement preserves an existing regular report's permission bits. New
reports and replacements of permitted output symlinks use private temporary-file
permissions; replacing a symlink does not change its referent or copy its mode.

Capture-time schema/binding projections and suite hashes are fixed in the capture
record. CI validates those against frozen artifacts, allowing independently valid
mutable-only cases and schemas to evolve. Checkout attributes preserve all pinned
helpers, the runner and known-offset assets; CRLF checkout conversion must not
change their digests. Capacity qualification remains separate from either claim.
