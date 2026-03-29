---
id: aeon-v1-conformance-matrix
title: AEON v1 Conformance Matrix
description: Cross-reference matrix mapping official AEON v1 requirements to the published CTS lane manifests and suite anchors.
group: CTS Documentation
path: cts/conformance/v1/aeon-v1-conformance-matrix
links:
  - aeon-core-v1
  - aeon-core-v1-compliance
  - aeos-v1
---

# AEON v1 Conformance Matrix

Status: CTS-owned conformance mapping document

This matrix maps the canonical AEON v1 specification surface to CTS lanes and suite anchors.

Use this document as the conformance-authoritative mapping bridge between:

- the canonical v1 documents in `aeonite-specs`
- the CTS protocol in `aeonite-cts/docs/protocol/v1`
- the published v1 lane manifests and suite trees in `aeonite-cts/cts/...`

This matrix reflects the current promoted CTS surface. Stress, smoke, and hardening workflows outside the published v1 lane manifests are not conformance anchors unless they are explicitly promoted here.

## CTS Baseline

- Protocol: `cts/protocol/v1`
- Core lane manifest: `cts/core/v1/core-cts.v1.json`
- AES lane manifest: `cts/aes/v1/aes-cts.v1.json`
- Canonical lane manifest: `cts/canonical/v1/canonical-cts.v1.json`
- Annotations lane manifest: `cts/annotations/v1/annotation-stream-cts.v1.json`
- AEOS lane manifest: `cts/aeos/v1/aeos-validator-cts.v1.json`

## Matrix

| Canonical document section    | Conformance topic                             | CTS lane              | Suite anchors                                                 |
| ----------------------------- | --------------------------------------------- | --------------------- | ------------------------------------------------------------- |
| `AEON-spec-v1.md` §4          | core value families baseline                  | `core`, `aes`         | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/aes/v1:suites/01-baseline.json`                          |
|                               | transport-only accepted value forms           | `core`, `aes`         | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
| `AEON-spec-v1.md` §5          | structural syntax surface                     | `core`                | `cts/core/v1:suites/02-addressing-and-syntax.json`            |
|                               | malformed syntax reductions                   | `core`                | `cts/core/v1:suites/07-syntax-invalid.json`                   |
| `AEON-spec-v1.md` §6          | canonical paths and reference legality        | `core`, `aes`         | `cts/core/v1:suites/03-attributes-and-references.json`        |
|                               |                                               |                       | `cts/aes/v1:suites/03-attributes-and-references.json`         |
|                               | transport-mode accepted reference forms       | `core`, `aes`         | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
| `AEON-spec-v1.md` §7          | structured comments and annotation extraction | `annotations`         | `cts/annotations/v1:annotation-stream-cts.v1.json`            |
| `AEON-spec-v1.md` §8          | mode/datatype behavior                        | `core`, `aes`         | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/aes/v1:suites/01-baseline.json`                          |
|                               | strict fail-closed rejections                 | `core`, `aes`         | `cts/core/v1:suites/05-strict-fail-closed.json`               |
|                               |                                               |                       | `cts/aes/v1:suites/04-strict-failure-envelope.json`           |
|                               | custom typed-mode literal acceptance          | `core`                | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/core/v1:suites/11-promoted-custom-literals.json`         |
|                               | custom typed-mode fail-closed rejections      | `core`                | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/core/v1:suites/12-promoted-custom-rejections.json`       |
| `AEON-spec-v1.md` §10         | phase boundaries                              | `core`, `aeos`        | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/aeos/v1:suites/01-baseline.json`                         |
| `AEON-spec-v1.md` §11         | canonical formatting determinism              | `canonical`           | `cts/canonical/v1/suites/01-baseline.json`                    |
|                               | node canonicalization and legacy node reject  | `canonical`           | `cts/canonical/v1/suites/02-node-canonicalization.json`       |
| `aeon-core-compliance-v1.md` §3    | syntax and key requirements                   | `core`                | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/core/v1:suites/02-addressing-and-syntax.json`            |
|                               |                                               |                       | `cts/core/v1:suites/07-syntax-invalid.json`                   |
| `aeon-core-compliance-v1.md` §4    | addressing and reference requirements         | `core`, `aes`         | `cts/core/v1:suites/03-attributes-and-references.json`        |
|                               |                                               |                       | `cts/aes/v1:suites/03-attributes-and-references.json`         |
|                               |                                               |                       | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
| `aeon-core-compliance-v1.md` §5    | depth policy controls                         | `core`, `aeos`        | `cts/core/v1:suites/02-addressing-and-syntax.json`            |
|                               |                                               |                       | `cts/aeos/v1:suites/14-separator-literal-policy.json`         |
| `aeon-core-compliance-v1.md` §6    | comment and annotation requirements           | `annotations`         | `cts/annotations/v1:annotation-stream-cts.v1.json`            |
| `aeon-core-compliance-v1.md` §7-8  | strict/datatype/separator rules               | `core`, `aes`         | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/core/v1:suites/02-addressing-and-syntax.json`            |
|                               |                                               |                       | `cts/core/v1:suites/05-strict-fail-closed.json`               |
|                               |                                               |                       | `cts/aes/v1:suites/04-strict-failure-envelope.json`           |
|                               |                                               |                       | `cts/aes/v1:suites/02-emission-coverage.json`                 |
|                               | custom-mode datatype-policy boundaries        | `core`                | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/core/v1:suites/11-promoted-custom-literals.json`         |
|                               |                                               |                       | `cts/core/v1:suites/12-promoted-custom-rejections.json`       |
| `aeon-core-compliance-v1.md` §9    | node introducer behavior                      | `core`, `aes`         | `cts/core/v1:suites/02-addressing-and-syntax.json`            |
|                               |                                               |                       | `cts/aes/v1:suites/02-emission-coverage.json`                 |
|                               |                                               |                       | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
| `aeon-core-compliance-v1.md` §10   | temporal literal validity                     | `core`, `aes`         | `cts/core/v1:suites/05-strict-fail-closed.json`               |
|                               |                                               |                       | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/core/v1:suites/07-syntax-invalid.json`                   |
|                               |                                               |                       | `cts/aes/v1:suites/04-strict-failure-envelope.json`           |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
| `aeon-core-compliance-v1.md` §11   | canonical node syntax and acceptance          | `core`, `aes`, `canonical` | `cts/core/v1:suites/02-addressing-and-syntax.json`        |
|                               |                                               |                       | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/aes/v1:suites/02-emission-coverage.json`                 |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
|                               |                                               |                       | `cts/canonical/v1/suites/02-node-canonicalization.json`       |
| `aeon-core-compliance-v1.md` §14   | numeric lexical underscore rules              | `core`                | `cts/core/v1:suites/01-baseline.json`                         |
| `AEOS-spec-v1.md` §2          | Core-versus-AEOS authority boundary          | `aeos`                | `cts/aeos/v1:suites/01-baseline.json`                         |
| `AEOS-spec-v1.md` §4-5        | schema model and constraint semantics         | `aeos`                | `cts/aeos/v1:suites/02-schema-rules.json`, `03-presence.json` |
|                               |                                               |                       | `04-type.json`, `05-numeric-form.json`, `06-string-form.json` |
|                               |                                               |                       | `08-datatype-labels.json`, `10-container-kinds.json`          |
|                               |                                               |                       | `11-tuple-arity.json`, `12-tuple-positional.json`             |
|                               |                                               |                       | `13-indexed-path-validation.json`                             |
|                               |                                               |                       | `15-structural-container-items.json`                          |
| `AEOS-spec-v1.md` §6          | diagnostics model                             | `aeos`                | `cts/aeos/v1:suites/00-envelope.json`, `01-baseline.json`     |
| `AEOS-spec-v1.md` §7          | result envelope                               | `aeos`                | `cts/aeos/v1:suites/00-envelope.json`                         |
| `value-types-v1.md`           | literal forms and value kinds                 | `core`, `aes`, `aeos` | `cts/core/v1:suites/01-baseline.json`                         |
|                               |                                               |                       | `cts/aes/v1:suites/01-baseline.json`                          |
|                               |                                               |                       | `cts/aeos/v1:suites/04-type.json`                             |
|                               | transport-only accepted literal forms         | `core`, `aes`         | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
|                               | invalid literal reductions                    | `core`                | `cts/core/v1:suites/07-syntax-invalid.json`                   |
| `structure-syntax-v1.md`      | keys, attributes, separators, newline rules   | `core`, `aes`         | `cts/core/v1:suites/02-addressing-and-syntax.json`            |
|                               |                                               |                       | `cts/core/v1:suites/03-attributes-and-references.json`        |
|                               |                                               |                       | `cts/aes/v1:suites/03-attributes-and-references.json`         |
|                               | malformed syntax reductions                   | `core`                | `cts/core/v1:suites/07-syntax-invalid.json`                   |
| `addressing-references-v1.md` | canonical path rendering and reference forms  | `core`, `aes`, `aeos` | `cts/core/v1:suites/03-attributes-and-references.json`        |
|                               |                                               |                       | `cts/aes/v1:suites/03-attributes-and-references.json`         |
|                               |                                               |                       | `cts/aeos/v1:suites/13-indexed-path-validation.json`          |
|                               | transport reference acceptance                | `core`, `aes`         | `cts/core/v1:suites/06-transport-acceptance.json`             |
|                               |                                               |                       | `cts/aes/v1:suites/05-transport-emission-coverage.json`       |
| `comments-annotations-v1.md`  | annotation channels, attachment, order        | `annotations`         | `cts/annotations/v1:annotation-stream-cts.v1.json`            |

## Notes

- Suite anchors are the current v1 source-of-truth suite files, not generated reports.
- This matrix is intentionally many-to-many: one canonical section may map to several suites, and one suite may support several sections.
- If a canonical rule has no listed CTS anchor, it is not yet fully covered and should be treated as a checklist gap rather than inferred conformance.
- Recent promoted v1 additions include canonical node canonicalization, strict fail-closed suites, transport acceptance/emission suites, and the first reduced syntax-invalid suite.
