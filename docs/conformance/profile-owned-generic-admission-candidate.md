# Profile-owned generic admission candidate

Status as of 26 November 2026 is experimental. The new suites reference the
[owning proposal](../../../aeonite-specs/sources/aeon/v1/profile-owned-generic-admission.aeon)
and pin its exact revision in suite metadata.

- [Core next](../../cts/core/v1/core-cts.v1.next.json) verifies expanded
  descriptor admission, the outer literal family, type-only arguments and
  generic depth. Its exclusions retire the old reserved-name, node-context and
  custom scalar restrictions in this manifest. Replacement cases have new IDs.
- [AES projection next](../../cts/aes/v1/aes-cts.v1.next.json) checks symbolic
  values with generic and mixed generic/clarifier annotations.
- [Canonical next](../../cts/canonical/v1/canonical-cts.v1.next.json) checks
  descriptor and payload preservation in emitted source. It also selects the
  reference-safe cases and the baseline exclusion already used by canonical
  snapshot 0.5.
- [GP profile next](../../cts/profile/v1/gp-profile-cts.v1.next.json) supplies
  trusted GP selection through its manifest. The runner applies that selection
  to each body and checks rejection codes and paths or accepted bindings.

Run the corresponding AEON TypeScript scripts `test:cts:core:next`,
`test:cts:aes:next`, `test:cts:canonical:next` and `test:cts:gp:next`. The
GP script runs the same vectors in TypeScript and the generated Rust WASM.
The Core, AES and canonical targets retain the other cases selected by their
manifests.

Released snapshot files, suite bytes and implementation claims retain their
original targets. Promotion requires review and a new immutable snapshot.
