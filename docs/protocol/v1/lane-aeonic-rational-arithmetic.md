# Aeonic rational arithmetic lane

The immutable local target is
`aeonic-rational-arithmetic-cts-v1-snapshot-0.2`, exposed by
`cts/aeonic-rational-arithmetic/v1/aeonic-rational-arithmetic-cts.v1.snapshot-0.2.json`.
It pins the source/schema under
`resources/aeonic-operations/v1/snapshots/0.2/` in `aeonite-specs`, aligned with
`aeonic-rational-arithmetic-specs-v1-snapshot-0.2`. Proposal lifecycle and disabled
publication remain unchanged. Existing finite/comparison targets retain their
own claims and defaults.

The mutable `.next.json` target advances to
`aeonic-rational-arithmetic-cts-v1-snapshot-0.3` and continues to pin the working
source/schema. Its results are development evidence and never establish the
snapshot 0.2 claim. The runner defaults to the frozen manifest; pass `--manifest`
explicitly to select next.

The six-operation capability requires add, subtract, multiply, divide, quantize
and materialize over all supported authored/derived pairings. Exact normalized
decimal results use the existing pair; non-terminating results use the reduced
coefficient/exponent/denominator triple. Derived history is required and actual
returned bundles feed chain steps. Quantization selects an exact positive grid
increment and one of seven explicit modes. It reports current rounding separately
from propagated history. Materialization remains exact and fail-closed.

Use `cts.protocol.v1`, one UTF-8 envelope on stdin and one on stdout. `lane` is
`aeonic-rational-arithmetic`; fixture contains exactly one of `request` or
`requestText`. Trusted binding policy permits only optional `resourceLimits`,
including the new denominator-digit allowance. Explicit null, unknown limits,
Booleans and invalid values are harness failures: nonzero exit and no operation
result. Logical operation failures exit zero with their closed diagnostic result,
`ok: false`, one matching protocol error and empty warnings. Successful envelopes
use `ok: true`, empty errors/warnings and complete value/history/effective-policy
metadata. Optional diagnostic messages and transport extensions are permitted.

The runner reuses fixed strict JSON/chain helpers from the unchanged finite runner.
Their bytes are pinned, along with source, schema, binding and suites. Frozen
manifest recognition also requires its exact hard-coded SHA-256 digest; relabeling
or modifying a mutable or unknown manifest cannot acquire a stable claim. It also
records its own digest and rechecks every recorded artifact after execution.
Manifest-selected code is never imported or executed. Every invocation supplies
the full manifest limit map, overridden by the individual companion case; native
defaults are never conformance evidence. The frozen target selects 16,384 request bytes, depth 32, 1,024 numeric
characters, 512 coefficient digits, 512 denominator digits, exponent magnitude
1,000,000, workspace estimate 4,096 digits and 1,024 output characters. These
settings passed independent JavaScript and Python working executions and separate
capacity probes. Frozen claims require actual frozen-target execution. The map
is not a native-default inference, machine-time/memory promise or guarantee for
every Cartesian combination. Individual companion cases select their own limits.

The target contains 351 explicit operation cases, three actual-result chains and
one law group. Cases include the 28 fixed workspace companions, closed-shape and
canonicality errors, required history, profile overrides, deterministic competing
failures, compact exponent paths and all seven signed rounding modes. A separate
authored-admission suite fixes text/grammar/original-exponent/normalized-value
precedence and covers left, right and unary authored-value diagnostic paths. Law checks
cover arithmetic commutativity/reversal, division round trips, quantization
idempotence/grid membership, monotonicity and history/current-evaluation consistency.

Install `runners/requirements-aeonic-operations.txt` in an isolated environment.
Artifact-only validation requires the matching snapshot specs checkout:

```sh
python runners/run_aeonic_rational_arithmetic.py \
  --specs-root ../aeonite-specs --check --report rational-artifacts.json
```

This reports `artifacts-validated`, `semantic_execution: false`, zero SUT
executions and `stable_conformance_claim: false`. It validates pins, closed shapes,
expected rational coprimality and selected bounds; it does not verify that expected
values or diagnostic precedence agree with a real implementation. Runner unit
tests use controlled doubles and a small process-transport smoke test; those are
tooling checks, not Aeonic implementation conformance.

When an implementation supplies the lane:

```sh
python runners/run_aeonic_rational_arithmetic.py \
  --specs-root ../aeonite-specs \
  --sut 'node scripts/rational-arithmetic-cts-adapter.mjs' \
  --cwd ../aeonic --report rational-snapshot-0.2.json
```

Commands use shlex without a shell. Timeout is a positive per-process harness
limit. Protocol stdout is redirected to a temporary file and checked against an
8 MiB harness cap before controller-memory loading. That post-process cap does
not bound temporary disk growth or arbitrary executable behavior. Allocation
failures, crashes, oversized output and timeouts are harness failures, never
portable operation diagnostics. Passing the logical lane does not establish
native graph/getter/proxy hardening or whole-chain execution budgets.

The profile must be explicitly selected in this capability. Other profiles,
including the finite default when none is supplied, are unsupported here.
Integrating facades dispatch the existing finite profile/default to its owning
contract and retain its separate frozen regression; they must not widen the old
validator, alter error precedence or retry another profile after failure. No
package publication, consumer integration or native-object hardening follows
from the snapshot. A successful semantic run of the recognized, unmodified frozen
target reports `target_status: immutable-local` and `stable_conformance_claim: true`.
A failed run, artifact-only check or mutable run always reports a false claim.
Implementation claim records retain exact authority/runner/SUT fingerprints,
runtimes, selected limits and reports. Native default-capacity probes remain
separate evidence; no per-operation semantic opt-out is introduced.
