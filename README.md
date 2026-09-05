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

The released Core snapshot remains `core-cts-v1-snapshot-0.2`. Current
development targets the experimental, consolidated
`cts/core/v1/core-cts.v1.next.json` manifest. It reuses the immutable released
suites, explicitly excludes four superseded limit expectations, and adds their
next-semantics replacements plus the complete Aeonic limit boundary suite.
The smaller `core-limits-cts.v1.next.json` manifest remains available for
limit-only checks.
Finalization and transport limits use the same pattern through
`finalize-limits-cts.v1.next.json` and `transport-limits-cts.v1.next.json`.

Portable AES v0 has two stable, authority-separated targets. The immutable
`aes-events-cts-v0-snapshot-0.1` manifest contains 38 transport-neutral record
and profile-validation vectors. The immutable
`telex-cts-v0-snapshot-0.1` manifest contains 50 Telex syntax,
canonicalization, and format-limit vectors. Each manifest pins the SHA-256
digest of every referenced suite; JavaScript and Rust pass both targets.

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
