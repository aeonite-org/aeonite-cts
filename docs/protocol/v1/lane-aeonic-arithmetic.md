# Aeonic exact arithmetic lane

The separate `aeonic-arithmetic` lane implements the unpublished working
contract `sources/aes/v1/aeonic-arithmetic-v1.aeon` and
`resources/aeonic-operations/v1/arithmetic-contract.schema.json` in
`aeonite-specs`. The default target is the immutable
`cts/aeonic-arithmetic/v1/aeonic-arithmetic-cts.v1.snapshot-0.1.json`, aligned
with `aeonic-arithmetic-specs-v1-snapshot-0.1`. Its source/schema, binding,
suites and boundary-recipe reference are copied into snapshot-specific paths.
The separate `.next.json` target now identifies development snapshot 0.2;
passing next remains mutable evidence and cannot establish a 0.1 claim.
Comparison snapshots and their manifests retain their existing meaning.

Use `cts.protocol.v1`: one envelope on stdin and one envelope on stdout.
`lane` is `aeonic-arithmetic`; `fixture` contains exactly one of `request`
(any logical JSON, including negative-test inputs) or `requestText` (exact
Unicode-scalar logical JSON text). `policy` permits only optional trusted
`resourceLimits`. Its object schema rejects null, unknown limits and invalid
values. Transport extensions remain permitted; logical operation/result objects
are closed. Malformed binding is a harness error: nonzero exit and no result.

A valid operation failure exits zero with `ok: false`, one diagnostic in
`errors` (code equal to the result reason, null path/span/phase), empty warnings
and the closed diagnostic result with no value. A success uses `ok: true`, empty
errors/warnings and the complete value/history bundle and effective-policy
metadata. Optional human-readable diagnostic messages are not matched.

Install `runners/requirements-aeonic-operations.txt` in an isolated environment.
Run:

```sh
python runners/run_aeonic_arithmetic.py \
  --specs-root ../aeonite-specs \
  --sut 'node scripts/arithmetic-cts-adapter.mjs' \
  --cwd ../../altopelago/aeonic --report arithmetic-report.json
```

`--manifest` selects an explicit snapshot or working manifest; `--timeout` is a per-process
harness limit. Commands are parsed with shlex and run without a shell. A timeout
or crash is a harness failure, never an operation `resource_limit`.

The runner executes every operation, chain, generated capacity boundary and
law group. Chains feed actual successful prior bundles into the next operation.
Generated boundaries exercise the explicitly selected 65,536-character/coefficient
capacities, exponent magnitude, 131,072-digit workspace, exact UTF-8 request
bytes, depth and materialized output. Adequate companion limits are supplied
where independently testing one capacity requires them. These are explicit
operation admission settings, not promised Cartesian products of all maxima.
The manifest's complete `meta.resource_limits` profile is explicitly supplied
in every SUT invocation; case settings override individual fields. Generated
boundary recipes also pin their targeted allowance. No positive case, negative
boundary or law assertion depends on the SUT's native resource defaults.

Law groups check commutativity, subtraction reversal, identities, distributivity
and history union under adequate limits. They do not convert through floats or
treat diagnostics as numerical values. The result schema and exact expected
metadata are checked as well as mathematical values.

The manifest pins source, schema, binding and suite SHA-256 digests. Changes must
update those pins deliberately; all artifacts, including the manifest, are
rechecked after execution. Reports retain commands, fingerprints, counts,
failures and target status. A successful exact recognized frozen manifest can
report `stable_conformance_claim: true`; failed or mutable runs cannot. Frozen
manifest bytes are anchored in the runner, so editing stable metadata cannot
promote a custom/working target. The boundary recipe reference pins the actual
generator functions and constants; the runner compares its own recipe source
without importing or executing code named by a manifest. Recipe, fixture or
source drift fails integrity checks. No invocation publishes a package.

The portable contract is logical JSON. Cycles, proxies/getters and host-native
graph representation are separate adapter hardening concerns, never a semantic
opt-out or a capacity guarantee inferred from passing this lane. A cyclic native
graph must fail closed; a reached byte/depth guard may preempt cycle detection.
Logical JSON requests retain deterministic staged diagnostics.
