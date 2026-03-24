# CTS

Conformance test suites for AEON.

## Purpose
- Provide implementation-neutral conformance inputs/expectations.
- Keep suite data independent from any single language implementation.

## Current Lanes
- `aeos/v1/` - AEOS validator conformance suites.
- `annotations/v1/` - annotation stream conformance suites.
- `core/v1/` - core parse/addressing conformance suites.
- `aes/v1/` - AES emission conformance suites.
- `canonical/v1/` - canonical formatting conformance suites.

## Planned Expansion
- Expand `core/v1` and `aes/v1` from baseline + coverage suites to full conformance corpus.

## Protocol
- `protocol/v1/` - runner/SUT protocol documents.
- Target freeze for all lanes: `cts.protocol.v1` (see `specs/03-releases/r8/cts-protocol-v1-unification.md`).

## Running CTS (TypeScript reference)
From `implementations/typescript`:

```bash
pnpm test:cts
pnpm test:cts:core
pnpm test:cts:aes
pnpm test:cts:canonical
pnpm test:cts:annotations
pnpm test:cts:all
```
