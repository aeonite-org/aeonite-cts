# Empty property keys — development CTS target

Updated: 15 November 2026.
Status: mutable candidate, not immutable snapshot promotion or a released claim.

The merged draft sources in `aeonite-specs` at revision
`e3def93d945611ee950ff7e789b8caf48b5825a3` permit ordinary empty property names in
AEON document/object/attribute-entry bindings, AEON references, SANSA selectors
and creation, and portable AES paths. An empty name is present and distinct from
root, missing names, whitespace names and unnamed structural elements. Ordinary
uniqueness rules remain in force. Node tags, structural identities, datatype
names and local address-space names keep their existing nonempty rules.

## Candidate selections

The following `.next` manifests select the amendment. Other selected suites
remain part of each target; running just the new suite is not a whole-target claim.

| Surface | Mutable manifest | New suite |
| --- | --- | --- |
| AEON Core | [Core next](../../cts/core/v1/core-cts.v1.next.json) | [29-next-empty-keys](../../cts/core/v1/suites/29-next-empty-keys.json) |
| AEON-to-AES projection | [AES next](../../cts/aes/v1/aes-cts.v1.next.json) | [12-next-empty-key-projection](../../cts/aes/v1/suites/12-next-empty-key-projection.json) |
| Logical AES validation | [AES events next](../../cts/aes/v1/aes-events-cts.v1.next.json) | [13-next-empty-key-events](../../cts/aes/v1/suites/13-next-empty-key-events.json) |
| Canonical rendering | [Reference-ordering next](../../cts/canonical/v1/canonical-reference-ordering-cts.v1.next.json) and [canonical next](../../cts/canonical/v1/canonical-cts.v1.next.json) | [11-next-empty-keys](../../cts/canonical/v1/suites/11-next-empty-keys.json) |
| Telex | [Telex next](../../cts/telex/v1/telex-cts.v1.next.json) | [04-next-empty-keys](../../cts/telex/v1/suites/04-next-empty-keys.json) |
| Film | [Film next](../../cts/film/v1/film-cts.v1.next.json) | [07-next-empty-keys](../../cts/film/v1/suites/07-next-empty-keys.json) |
| SANSA Address parser | [Parser next](../../cts/sansa/v1/sansa-address-parser-cts.v1.next.json) | [14-empty-key-address-parser](../../cts/sansa/v1/suites/14-empty-key-address-parser.json) |
| SANSA Resolve | [Resolve next](../../cts/sansa/v1/sansa-resolve-cts.v1.next.json) | [15-empty-key-resolve](../../cts/sansa/v1/suites/15-empty-key-resolve.json) |
| SANSA Mutate | [Mutate next](../../cts/sansa/v1/sansa-mutate-cts.v1.next.json) | [16-empty-key-mutate](../../cts/sansa/v1/suites/16-empty-key-mutate.json) |
| SANSA Instruction | [Instruction next](../../cts/sansa/v1/sansa-instruction-cts.v1.next.json) | [17-empty-key-instruction](../../cts/sansa/v1/suites/17-empty-key-instruction.json) |

The suites cover positive bindings and structural identity, typed/attributed
keys, scalar/container values, nested and consecutive empty members, clone and
pointer targets, missing/forward/self-reference rejection, duplicate decoded
names in each scope, malformed delimiters, canonical fixed points, portable
record paths, text/binary transport and SANSA parse/resolve/lower/plan behavior.
Film golden bytes are assembled from the v1 framing definition, not copied from
an encoder: default context, length-prefixed record, control zero, kind one,
UTF-8 path and value strings. Its transcode case requires the exact original
Telex stream on return.

## Superseded expectations

Keep the original suite files unchanged. Exclude these IDs only in their
evolving selections and require the new positive and retained negative cases:

- Core: `core-addr-001b-empty-quoted-key-reject`,
  `core-addr-001c-empty-quoted-path-segment-reject`,
  `core-snippet-transport-003-empty-quoted-keys-reject`.
- AES projection: `aes-emission-001b-empty-quoted-key-reject`.
- Mutate: `sansa-mutate-0045a1-target-aeon-reports-nested-empty-key-value-path`,
  `sansa-mutate-0045a1a-target-aeon-reports-quoted-nested-key-value-path`.
- Instruction: `sansa-instruction-039-parse-rejects-empty-quoted-create-member`,
  `sansa-instruction-0180j1-target-aeon-rejects-empty-quoted-object-field`.

Runners must honor `exclude_tests`. SANSA source runners were updated to do so;
released selections still run all their original cases. Native and TypeScript
Film checks now recognize the mutable target, with an explicit selected-vector
count; immutable-target digest and count checks remain in place.

## Promotion boundary

All 156 pre-existing non-next CTS JSON files were checked byte-for-byte against
the initial working state and remain unchanged. The repository validator checks
all suite references, exclusions, IDs and existing pinned digests.

This amendment does not assign a new specification revision or snapshot ID to
released consumers. The moving Film manifest no longer presents its older
generic-depth specification revision as the revision for the entire expanded
target. Existing immutable targets retain their revision metadata and hashes.
Draft source review is merged; new immutable CTS promotion, complete runtime
qualification and released claim updates remain release work.
