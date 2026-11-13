# Aeonic rational arithmetic working lane

This separate lane exercises the explicitly selected profile
`aeonic.operations.arithmetic.rational.v1` from the unpublished working source
`sources/aes/v1/aeonic-rational-arithmetic-v1.aeon` and schema
`resources/aeonic-operations/v1/rational-arithmetic-contract.schema.json` in
`aeonite-specs`. The mutable manifest is
`cts/aeonic-rational-arithmetic/v1/aeonic-rational-arithmetic-cts.v1.next.json`,
identified as `aeonic-rational-arithmetic-cts-v1-snapshot-0.2`. There is no frozen
target or stable claim. The finite arithmetic/comparison lanes remain unchanged.

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
Their bytes are pinned, along with source, schema, binding and suites. It also
records its own digest and rechecks every recorded artifact after execution.
Manifest-selected code is never imported or executed. Every invocation supplies
the full manifest limit map, overridden by the individual companion case; native
defaults are never conformance evidence. Candidate settings are deliberately
modest and uncalibrated: they are not native defaults, advertised support floors,
machine-time/memory promises or guarantees for every Cartesian combination.

The target contains 333 explicit operation cases, three actual-result chains and
one law group. Cases include the 28 fixed workspace companions, closed-shape and
canonicality errors, required history, profile overrides, deterministic competing
failures, compact exponent paths and all seven signed rounding modes. Law checks
cover arithmetic commutativity/reversal, division round trips, quantization
idempotence/grid membership, monotonicity and history/current-evaluation consistency.

Install `runners/requirements-aeonic-operations.txt` in an isolated environment.
Artifact-only validation requires the matching draft specs checkout:

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
  --cwd ../aeonic --report rational-working.json
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
package publication, implementation support or independent runtime capacity is
implied by the working target. Cross-runtime positive execution is required
before any immutable promotion.
