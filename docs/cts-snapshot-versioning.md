# CTS Snapshot Versioning

CTS growth must not silently redefine what older implementations claim to pass.
Published CTS snapshots are compatibility targets. New cases should be added to
a newer snapshot, draft lane, or experimental lane rather than changing the
meaning of an existing released snapshot.

## Snapshot Identifiers

Use explicit snapshot identifiers:

```text
<surface>-cts-v<spec-version>-snapshot-<snapshot-version>
```

Examples:

```text
core-cts-v1-snapshot-0.1
aes-cts-v1-snapshot-0.1
aeos-validator-cts-v1-snapshot-0.1
address-cts-v1-snapshot-0.1
query-cts-v1-snapshot-0.1
mutate-cts-v1-snapshot-0.1
instruction-cts-v1-snapshot-0.1
```

The `v<spec-version>` segment names the specification surface being tested. The
`snapshot-<snapshot-version>` segment names the CTS compatibility snapshot for
that surface. It is independent of implementation package versions.

## Rules

Released snapshots are immutable. Do not add, remove, or change test
expectations inside a released snapshot.

New tests begin in one of these places:

- a draft or next snapshot;
- an experimental manifest or suite;
- an implementation-owned stress corpus that is not yet conformance authority.

Promotion creates a new explicit snapshot identifier. For example:

```text
mutate-cts-v1-snapshot-0.1
mutate-cts-v1-snapshot-0.2
```

An implementation may truthfully claim the older snapshot until it adopts and
passes the newer one. Failing a newer snapshot is not a conformance regression
unless the implementation has claimed that newer snapshot.

## Manifest Metadata

CTS manifests should expose both a machine snapshot id and a compact version:

```json
{
  "metadata": {
    "version": "0.1.0",
    "snapshot_id": "mutate-cts-v1-snapshot-0.1"
  }
}
```

Existing manifests that only expose `version` should be treated as pre-snapshot
metadata and migrated as part of the next manifest cleanup. Migration should not
change test expectations by itself.

## Implementation Claims

Implementations should pin the snapshot they claim, not a moving branch:

```json
{
  "cts": {
    "core": "core-cts-v1-snapshot-0.1",
    "query": "query-cts-v1-snapshot-0.1",
    "mutate": "mutate-cts-v1-snapshot-0.1"
  }
}
```

CI for an implementation should run required checks against the pinned
snapshot. It may also run draft, next, or experimental snapshots as advisory
checks, but advisory failures must not invalidate the claimed stable snapshot.

## Tags And Releases

Repository tags may group many snapshot ids into one release, but the tag is not
the conformance claim. For example, a CTS repository release may contain:

```text
core-cts-v1-snapshot-0.3
aeos-validator-cts-v1-snapshot-0.2
mutate-cts-v1-snapshot-0.1
```

Implementations should report the individual snapshot ids they pass.
