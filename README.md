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

## Validation

For a lightweight repository-integrity check of the published CTS assets, run:

```bash
python3 runners/validate_cts_repo.py
```

This validates:

- every JSON file parses
- core/canonical/aeos-style manifests resolve to real suite files
- inline suite manifests such as the annotations lane have valid test IDs
- test IDs are unique within each manifest lane

## Licensing

This repository is released under the MIT License. See `LICENSE`.
