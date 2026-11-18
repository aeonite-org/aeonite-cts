# AEOS portable property selectors — development

`aeos-properties-0.1` is an explicitly selected mutable development profile.
It is excluded by default and creates no stable conformance claim. The separate
AES Type Transpiler remains a preliminary proposal with no executable consumer;
it is not a prerequisite for this profile or the0.17.0 release.

The owning unpublished profile is pinned at specifications commit
`e772651a6e2c4ad3c0ce4651d116da7e1bc696d0`. Source, resource, fixture and fixture-schema
digests are checked before any SUT execution. Historical manifests/snapshots and
their assertions remain unchanged.

Use Python3.12+ with `jsonschema`. From a CTS checkout, select that specification
revision in a separate checkout, then run the artifact-only check:

```sh
git -C ../aeonite-specs fetch origin e772651a6e2c4ad3c0ce4651d116da7e1bc696d0
git -C ../aeonite-specs checkout --detach e772651a6e2c4ad3c0ce4651d116da7e1bc696d0
python3 runners/run_aeos_properties.py --specs-root ../aeonite-specs --check
```

The checker validates52 fixture cases without running an implementation. For
semantic execution, pass a built owning SUT explicitly. For example, with
`AEON_ROOT` pointing to the coordinated AEON candidate:

```sh
python3 runners/run_aeos_properties.py --specs-root ../aeonite-specs \
  --sut "node $AEON_ROOT/scripts/cts-aeos-properties-adapter.mjs"
python3 runners/run_aeos_properties.py --specs-root ../aeonite-specs \
  --sut "python3 $AEON_ROOT/implementations/python/tools/run_aeos_properties_cts.py"
```

Rust's `properties_cts` example uses the same protocol. Build it from the owning
AEON Rust workspace with its locked dependencies, then pass the resulting binary
as `--sut`. No parser, namespace or validator substitute is permitted. The runner
does not build/install dependencies or select a registry package on the user's behalf.

The persistent SUT receives one JSON object per input line:

```json
{"entrypoint":"portable","representation":"records","records":[],"schema":{"rules":[]},"options":{}}
```

`entrypoint` is `portable` or the negative `legacy` control. Portable representation
is `records` or `telex`; adapters encode the supplied records through the existing
owning encoder for the latter. `legacy` invokes existing native-event validation
on an empty input, proving that an empty branch cannot bypass its property denial.
The reply is `{"result": RESULT_ENVELOPE, "inputUnchanged": true}`. Do not add logs
to stdout. Output/elapsed guards are runner controls for an explicitly selected
local SUT, not a sandbox for hostile executables.

Each of52 fixtures runs twice; the51 portable fixtures run in both representations,
for206 checked responses. Assert every invocation's boolean `ok`, the complete
error-code/path multiset, empty guarantees on failure and `inputUnchanged` exactly
true. The fixture schema rejects undeclared expected fields. Scope/key/tag/head,
fresh snapshots, repeated/distinct rules, shared identity/property budgets,
attributes, Unicode, native/path denials and two-width head limits are covered.
Unsupported instrumentation or malformed responses fail; nothing silently skips.

Exit0 means the selected development checks passed; exit1 means semantic assertions
failed; exit2 means invalid artifacts/protocol/setup. Reports always retain
`stable_conformance_claim: false`. `--check` executes no SUT. This target does not
qualify broad performance, every platform/provider, native wheels or WASM APIs.
All existing compatibility/target checks and1.15x latency/1.20x memory budgets stay
unchanged. Releases, deployment and stable promotion remain held.
