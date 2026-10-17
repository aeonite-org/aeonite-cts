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

The SANSA Query and experimental Mutate `.next.json` manifests add development
coverage for reduced-date datetime/WTC composition, malformed field/comment
boundaries, exact fractional scale, reserved Base64URL decodability and lossless
prose/trimtick target representability. They do not change released SANSA
snapshots or assert richer chronology for disjoint date/clock completion sets.

The current released Core target is `core-cts-v1-snapshot-0.5`, exposed by
`cts/core/v1/core-cts.v1.snapshot-0.5.json`. Its 299 vectors retain the 0.4
surface and require reserved `base64` values to be decodable Base64URL with
valid padding and zero unused tail bits, while leaving `encoding`, `inline`,
and `embed` opaque. Every referenced suite is content-hash pinned. The
historical 0.4 and 0.3 targets remain unchanged; the `.next` and smaller
`core-limits-cts.v1.next.json` manifests remain available for ongoing and
limit-only development.
Finalization and transport limits use the same pattern through
`finalize-limits-cts.v1.next.json` and `transport-limits-cts.v1.next.json`.
The experimental `finalize-json-cts.v1.next.json` and
`finalize-map-cts.v1.next.json` targets define the strict-versus-transport
compatibility policy for special values without changing released snapshots.
The mutable Core, AES projection, canonical, and finalize next targets remain
available for ongoing development beyond their promoted snapshots.
Core next also covers the existing binding-side `node<T>` reserved-argument
rule across clarifiers, metadata, anonymous items, and reference values, with
positive controls for custom/domain arguments and node-head content claims.
The Core 0.5, Core 0.4, and AES 0.4 snapshots cover the single-marker trimtick
grammar and exact space-or-tab gutter normalization. Historical released
snapshots retain their width-bearing trimtick cases unchanged.

The current released canonical target is
`canonical-cts-v1-snapshot-0.4`, exposed by
`cts/canonical/v1/canonical-cts.v1.snapshot-0.4.json`. Its 197 selected vectors
freeze reference-safe smallest-eligible-key ordering, authored Core reference
validation, exact numeric clarifiers and type-only generic arguments, alongside
literal-family, symbolic, temporal and trimtick preservation. All ten suites
are SHA-256 pinned. The target records normative specification revision
`ae427af77568518a71aaf86ec0dc620e07658944`, not a new named specification
snapshot. Historical canonical 0.3 retains its 62 vectors; 0.2 and 0.1 also
remain unchanged.

The opt-in `cts/canonical/v1/canonical-reference-ordering-cts.v1.next.json`
manifest remains available for development. Its reviewed 197-case selection
is frozen by canonical 0.4 without changing the moving manifest or suite bytes.
The selection includes 105 reference-ordering vectors for
smallest-eligible-key sorting, nested dependencies, fixed indexed positions,
header/body separation, Unicode scalar key order, original-input rejection,
and canonical fixed points. Canonical 0.4 retains exactly the two reviewed
exclusions: the superseded baseline reference output and the existing trimtick
case whose replacement remains selected. Every selected case is required for a
0.4 claim, including reused fixtures retaining experimental provenance tags.
Promotion does not switch implementation defaults or claims, publish packages,
or migrate integrity/hash contracts; those remain separate implementation gates.

Portable AES v1 has authority-separated targets. The prepared immutable
`aes-events-cts-v1-snapshot-0.2` manifest contains 48 transport-neutral record
and profile-validation vectors. The prepared immutable
`telex-cts-v1-snapshot-0.2` manifest contains 61 Telex syntax,
canonicalization, and format-limit vectors. Each manifest pins the SHA-256
digest of every referenced suite. The historical 38-vector AES events 0.1 and
50-vector Telex 0.1 targets remain unchanged.

The development Core and canonical next targets add type-only generic
arguments and exact numeric clarifiers. The new `aes-events-cts.v1.next.json`,
`telex-cts.v1.next.json`, and `film-cts.v1.next.json` targets apply the same
constraint at the logical AES, text, and binary boundaries. Bare numeric or
string generic arguments are invalid; numeric clarifiers on outer and nested
type descriptors remain valid. Film rejects numeric generics at completed AES
validation while retaining historical tag `02` physical framing for provisional
decoding. The binary grammar, numeric-clarifier tag `02`, and kind codes remain
unchanged; provisional decoding is not acceptance of a valid AES record.

The prepared AES events 0.2, Telex 0.2, and Film 0.3 snapshots promote these
transport corrections with hash-pinned suites and explicit exclusions of
superseded numeric-generic expectations. Replacement cases retain round-trip
and resource-boundary coverage. Historical manifests, suites, and hashes are
unchanged. The new snapshots record normative specification revision
`ae427af77568518a71aaf86ec0dc620e07658944`; they do not claim a new named
specification snapshot. Codec adoption and package publication remain separate.

Film next additionally selects 37 logical generic-depth vectors aligned to
specification revision `242daa4214237cdc70d512b593c126615ab0556b`. Leaf arguments
and clarifiers do not add depth; sibling branches take the maximum. The cases
cover inclusive limits, true one-over levels, encode/decode/transcode symmetry,
independent component/argument/clarifier/byte limits, malformed leaves and early
rejection before further descent. Exactly one additional old expectation is
excluded only in next: its original full optional-field bytes are retained in
a new depth-zero acceptance case, while true depth exhaustion has new negative
cases. Film next selects 128 operations; released Film 0.3 stays at 92, with
its manifests, suite bytes and hashes unchanged. These development expectations
expose the pending codec correction, not a claim that existing readers pass.

`runners/test_film_generic_depth.py` independently checks the small fixture
bytes and logical boundaries without importing an implementation checkout.
Implementation harnesses should run the decode vectors through their one-shot
and every-split incremental paths; the CTS does not introduce a new streaming
wire operation or enable durable writers.

The prepared immutable `film-cts-v1-snapshot-0.4`, at
`cts/film/v1/film-cts.v1.snapshot-0.4.json`, freezes those 128 operations and
every referenced suite's SHA-256 digest. It records the same reviewed
specification revision and retains all 37 depth cases, including the exact
optional-field replacement. Its 103 direct decode operations are the reader
surface; encoder and transcode operations remain separately identified.
Film 0.3 and earlier targets retain their original bytes and expectations.
An implementation adopting corrected logical-depth behavior must explicitly
adopt the new target rather than keep claiming the superseded depth boundary.
Implementation claims, dependency publication and durable-writer enablement
are separate steps; creating the snapshot does not perform them.

The prepared `film-cts-v1-snapshot-0.3` contains 92 vectors, retaining the
existing binary framing and kind assignments while rejecting literal generic
arguments at completed AES validation and preserving exact numeric clarifiers.
Film's pre-existing physical generic-depth accounting is not changed by these
targets; harmonization with logical AES depth requires separate review.

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
