# CTS SUT Invocation Examples

Status: informative examples for `cts.protocol.v1`

This document is not the normative runner contract.

Its purpose is to show how a runner may encode the invocation context described in:

- `runner-contract.md`
- `sut-envelope.md`

## Why this exists

Some implementations can be launched with just a command path.

Others require:

- a specific working directory;
- explicit environment variables;
- a workspace-relative binary path rather than a globally installed package.

Those settings belong to runner configuration, not to test-case data.

## Example SUT Profiles

An implementation-aware runner might keep SUT launch profiles shaped like this:

```json
{
  "version": "example.sut-profiles.v1",
  "profiles": {
    "typescript": {
      "cwd": "altopelago/aeon/implementations/typescript",
      "command": ["pnpm", "test:cts:adapter"]
    },
    "rust": {
      "cwd": "altopelago/aeon/implementations/rust",
      "command": ["cargo", "run", "-p", "aeon-cli", "--", "cts-adapter"]
    },
    "python": {
      "cwd": "altopelago/aeon/implementations/python",
      "env": {
        "PYTHONPATH": "src"
      },
      "command": ["python3", "-m", "aeon.cts_adapter"]
    }
  }
}
```

See the repository-owned JSON example in:

- `manifests/examples/sut-profiles.example.json`

## Python Note

Python SUTs should be launched from the Python implementation workspace when that is how local imports resolve.

In the AEON implementation workspace this means:

- working directory: `implementations/python`
- environment override: `PYTHONPATH=src`

Without that, a runner may accidentally execute against an older globally installed package instead of the checked-out implementation under test.

## Runner Guidance

Runners should treat these profiles as harness configuration:

- choose the profile before running CTS;
- apply `cwd` and `env` before launching the SUT subprocess;
- keep the CTS case payload unchanged.

The conformance result must still depend only on the CTS input envelope and the selected implementation under test.
