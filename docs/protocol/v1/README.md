# CTS Protocol v1

Normative protocol documents for CTS runner/SUT contracts.

## Status
- Version: `cts.protocol.v1`
- Scope: all CTS lanes (`aeos`, `annotations`, `core`, `aes`, `canonical`)

## Documents
- `runner-contract.md` - common invocation, envelope, diagnostics, and matching rules.
- `lane-aeos.md` - AEOS lane payload contract.
- `lane-annotations.md` - annotation lane payload contract.
- `lane-core.md` - core parse/addressing lane payload contract.
- `lane-aes.md` - AES emission lane payload contract.
- `lane-canonical.md` - canonical formatting lane payload contract.
- `sut-envelope.md` - AEOS compatibility contract retained for transition.
- `sut-invocation-examples.md` - non-normative examples for working-directory and environment-aware SUT launches.

## Version Policy
- Protocol-major changes require `cts.protocol.v2`.
- Lane suites MUST declare protocol version in manifest metadata (for example `sut_protocol: cts.protocol.v1`).
