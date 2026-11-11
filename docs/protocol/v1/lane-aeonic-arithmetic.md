# Aeonic exact arithmetic working lane

The separate `aeonic-arithmetic` lane implements the unpublished working
contract `sources/aes/v1/aeonic-arithmetic-v1.aeon` and
`resources/aeonic-operations/v1/arithmetic-contract.schema.json` in
`aeonite-specs`. Its target is
`cts/aeonic-arithmetic/v1/aeonic-arithmetic-cts.v1.next.json`.
This is mutable development evidence, never a frozen compatibility claim.
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

`--manifest` selects an explicit working manifest; `--timeout` is a per-process
harness limit. Commands are parsed with shlex and run without a shell. A timeout
or crash is a harness failure, never an operation `resource_limit`.

The runner executes every operation, chain, generated capacity boundary and
law group. Chains feed actual successful prior bundles into the next operation.
Generated boundaries exercise the candidate 65,536-character/coefficient
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
failures and `stable_conformance_claim: false`. No invocation freezes or
publishes a snapshot.
