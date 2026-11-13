# SANSA child identity candidate

The two `sansa-child-identity-*-cts.v1.next.json` manifests under `cts/sansa/v1/` are mutable experimental targets, excluded from default released claims. They reference the proposal source `aeonite-specs/sources/sansa/v1/child-identity-selectors-v1.aeon`. Existing Addressing and Resolve snapshots are unchanged. Candidate version 0.1.0 identifies preparation work, not an implementation support claim or published snapshot.

The parser suite contains 20 cases. The Resolve suite contains 38 cases using host-neutral binding trees. `supportsIdentity: true` instructs a test adapter to expose the explicit namespace identity accessor; false means the accessor is absent even if fixture bindings carry identity metadata. It must not be inferred from that metadata. Invalid-metadata fixtures intentionally model namespaces outside valid AEON documents.

`expected.identityCalls` is harness instrumentation: count actual identity accessor invocations during one Resolve call. It is not a new public Resolve result field. A candidate rejected before accessor invocation records zero. A candidate beyond the allowed inspection count must not invoke the accessor. Existing expected `addresses`, error codes and result status keep their meanings. Options in test input map to Resolve options; a runner must explicitly support those mappings before claiming this candidate.

Current preparation does not constitute full coverage. Add iterator/cleanup, contextual scope, metadata/local-space transitions, all exposed occurrence kinds, reordered occurrences, branch multiplicity, untrusted AST parity and consumer-denial cases before promoting this candidate. Separately add AEON literal embedding and incremental/chunked host coverage. Parse/Resolve success must not automatically advertise Query, AEOS path, activation, mutation, SO, storage/event paths or AEON references.

Promotion needs a new explicitly selected stable snapshot, complete runtime/adapter evidence for its advertised roster and preserved existing compatibility targets. Parser acceptance alone is not conformance.

Additional candidate vectors live in `fixtures/sansa-child-identity/v1/`: malformed/forged AST parity, AEON lexical embedding and consumer-specific denial. Their presence is not default runner support. The expanded Resolve namespace fixtures expose optional `attributeSpace`, `localSpaces` and `supportsParentTraversal`; adapters must map those explicitly. Node/list/tuple vectors concern exposed child topology and do not independently define a portable node-head mapping.
