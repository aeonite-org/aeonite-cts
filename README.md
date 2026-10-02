# aeonite-cts

`aeonite-cts` is the canonical public repository for AEON-family conformance and verification assets.

It is the source of truth for:

- official CTS definitions
- official CTS runners
- public conformance fixtures
- published lane manifests and compatibility support assets
- conformance-pathway stress assets that are part of the official verification surface

## Authority

This repo is conformance-authoritative.

It is intended to own the verification surface used to determine whether an implementation satisfies published conformance requirements.

It is not intended to own:

- implementation source code
- formal specification text
- implementation-only stress or hardening work

## Boundary rule

Use this repo when the material is part of the official public verification pathway.

If a stress or fuzz asset is implementation hardening work but not part of a published conformance pathway, it should remain implementation-owned unless and until it is promoted into the CTS surface.

## Coverage

The current anti-drift coverage map is tracked in `CONFORMANCE-COVERAGE.md`.

CTS compatibility snapshots are versioned explicitly. See
`docs/cts-snapshot-versioning.md` for the naming convention, such as
`mutate-cts-v1-snapshot-0.1`, and for the rule that released snapshots are
immutable compatibility targets. Specification snapshots use the parallel
`*-specs-v1-snapshot-*` convention for documentation alignment.

The current released Core target is `core-cts-v1-snapshot-0.4`, exposed by
`cts/core/v1/core-cts.v1.snapshot-0.4.json`. Its 294 vectors promote symbolic
literals, reduced temporal precision, and the single-marker trimtick grammar
while retaining the unified Aeonic-limit coverage. Every referenced suite is
content-hash pinned. The historical 0.3 target remains unchanged at
`core-cts.v1.snapshot-0.3.json`; the `.next` and smaller
`core-limits-cts.v1.next.json` manifests remain available for ongoing and
limit-only development.
Finalization and transport limits use the same pattern through
`finalize-limits-cts.v1.next.json` and `transport-limits-cts.v1.next.json`.
The experimental `finalize-json-cts.v1.next.json` and
`finalize-map-cts.v1.next.json` targets define the strict-versus-transport
compatibility policy for special values without changing released snapshots.
The mutable Core, AES projection, canonical, and finalize next targets remain
available for ongoing development beyond their promoted snapshots.
The Core and AES 0.4 snapshots cover the single-marker trimtick grammar and
exact space-or-tab gutter normalization. Historical released snapshots retain
their width-bearing trimtick cases unchanged.

The current released canonical target is
`canonical-cts-v1-snapshot-0.2`, exposed by
`cts/canonical/v1/canonical-cts.v1.snapshot-0.2.json`. Its 54 vectors pin
ordinary-string versus trimtick preservation, symbolic-literal escaping and
nesting, reduced temporal precision, second `60`, exact arbitrary fractional
scale, and the four-digit year boundaries across canonical writers.

Portable AES v1 has two stable, authority-separated targets. The immutable
`aes-events-cts-v1-snapshot-0.1` manifest contains 38 transport-neutral record
and profile-validation vectors. The immutable
`telex-cts-v1-snapshot-0.1` manifest contains 50 Telex syntax,
canonicalization, and format-limit vectors. Each manifest pins the SHA-256
digest of every referenced suite; JavaScript and Rust pass both targets.

The immutable `film-cts-v1-snapshot-0.2` manifest contains 73 Film v1 binary
framing, canonicalization, portable-record, Telex-transcoding, and
resource-limit vectors. It is aligned with `film-specs-v1-snapshot-0.2` and
adds the append-only `SymbolicLiteral` kind mapping while retaining explicit
rejection of the next unassigned code. Every referenced suite is pinned by an
exact-byte SHA-256 digest. The historical 0.1 snapshot remains unchanged.
Durable Film writers remain outside this snapshot's implementation claim.

The experimental `aes-path-translation-cts-v1-snapshot-0.1` target adds three
AEON-specific interoperability vectors without modifying either released AES
v0 snapshot. It covers recursive source-to-event node expansion, reverse
materialization of node-content references, and rejection of a direct
synthetic `NodeHead` reference. TypeScript, Rust, Python, and PHP run the same
target through `altopelago/aeon/scripts/aes-path-translation-cts.sh`.

The mutable `value-semantics-cts-v1-snapshot-0.2` development target preserves
the 0.1 minimum-consumer suite and adds the explicit
`aeon.value.radix.numeric.same-base.v1` and
`aeon.value.radix.numeric.cross-base.v1` profiles. Their radix vectors
distinguish default representation identity from opt-in numeric equality and
ordering, exercise the base-range boundaries and full digit alphabet, verify
exact rational comparison across independently resolved bases, and require
fail-closed diagnostics for missing bases, mixed bases under the same-base
profile, and invalid digits.

The value-semantics lane also covers profile-independent `radixScale(...)`
representation metadata, including preserved trailing zeroes and base-aware
validation.

The current released AEON-to-portable-AES projection target is
`aes-cts-v1-snapshot-0.4`, exposed by
`cts/aes/v1/aes-cts.v1.snapshot-0.4.json`. Its 83 vectors retain the complete
portable projection and add symbolic-literal payloads plus single-marker
trimtick normalization. Every referenced suite is content-hash pinned. The
historical 0.3 target remains unchanged at `aes-cts.v1.snapshot-0.3.json`;
`aes-cts.v1.next.json` remains the mutable development target.

## Validation

For a lightweight repository-integrity check of the published CTS assets, run:

```bash
python3 runners/validate_cts_repo.py
bash ./scripts/pre-commit-check.sh
```

This validates:

- every JSON file parses
- CTS manifest snapshot IDs are present, well-formed, and unique
- CTS manifest spec snapshot IDs are well-formed when present
- core/canonical/aeos-style manifests resolve to real suite files
- declared suite content digests match the exact referenced bytes
- inline suite manifests such as the annotations lane have valid test IDs
- test IDs are unique within each manifest lane

The pre-commit check also rejects local filesystem path markers before they can
land in the public CTS repo.

## Licensing

This repository is released under the MIT License. See `LICENSE`.
