# Authority

`aeonite-cts` is the sole long-term source of truth for official AEON-family conformance assets.

It is authoritative for:

- published CTS suites
- official runner surfaces
- conformance fixtures and manifests
- validator and compatibility assets that belong to the public verification boundary
- stress assets only when they are part of the official conformance pathway

It is not authoritative for:

- implementation code
- formal specification text
- implementation-private hardening work

## Repository boundaries

The repository boundary is:

- `altopelago/aeon`: implementation authority
- `aeonite-org/aeonite-specs`: specification authority
- `aeonite-org/aeonite-cts`: conformance authority
