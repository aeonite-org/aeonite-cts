# Prepared immutable targets for AEON 0.17

These targets freeze reviewed source contracts for the 0.17 release preparation.
Implementation conformance requires running the complete selected target and
claiming its exact identifier; metadata validation alone is not conformance.
The [machine inventory](aeon-0.17-snapshots.json) pins all inputs and suite bytes.

| Target | Cases | Selection |
| --- | --- | --- |
| Core snapshot 0.6 | 657 | Core next at 4bc227f0e042c9c4514a0f2d75492cb6634cab60 |
| AES projection snapshot 0.6 | 87 | AES projection next at that same revision |
| Canonical snapshot 0.5 | 209 | Reference-ordering next at that same revision |

AES projection 0.5 is already allocated to a mutable development manifest.
The new immutable target uses 0.6, retaining that development identifier and its
existing consumers without changing the mutable target.

Specification authority is a6948968e4e2741f2342249024b266ca6adbfeb7 of
aeonite-org/aeonite-specs. No named specification snapshot is implied.
Newly promoted suites are copied to versioned snapshot directories, while
already immutable suite references retain their established bytes and digests.
Every suite is SHA-256 pinned. Future edits to mutable suites do not redefine
these new snapshot copies.

Relative to Core 0.5, the only removed selected cases are the three superseded
empty-key rejections and core-baseline-015-strict-stale-radix-alias-reject.
There are 362 added vectors, including the previously merged authored-reference,
generic, empty-key, block-comment newline and radix16 suites. The 207 physical
block-comment newline vectors concern existing separators, not the deferred
newline convention or canonical-generation warning proposal.

AES projection 0.6 replaces only its old empty-key and stale-radix rejection
selections and adds six vectors. Canonical 0.5 retains all 197 previously selected
vectors unchanged and adds 12 empty-key vectors. Old manifests, exclusions,
expected results, runner assertions, resource limits and mutable targets remain
unchanged. Run the historical targets separately to retain their exact audited
superseded rejection deltas; never relabel those mismatches as old-target passes.

The current Core next manifest contains later development work beyond the pinned
selection. It remains independent and is not silently included in these snapshots.
Property/child-identity experimental targets and remaining AES event/Telex/Film
development targets are not promoted by this change. Existing stable transport
claims require their own complete passing results.

Independent authority/selection QA and actual TS/Rust/Python/WASM target runs
remain required before adopting claims in an implementation release. Snapshot
preparation does not establish a package publication, platform/performance
qualification or production deployment.
