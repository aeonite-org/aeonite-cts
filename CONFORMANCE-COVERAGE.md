# Conformance Coverage

This document exists to prevent conformance drift.

`aeonite-cts` is intentionally curated, but it must not become a thin sample set that allows implementations to diverge on backbone behavior.

The rule is:

- public CTS suites should stay deliberate and normative
- backbone behavior families must still be covered strongly enough to prevent drift
- broader implementation stress corpora remain feeder surfaces for future CTS promotion

## Backbone rule

The following surfaces are treated as anti-drift backbone behavior families for AEON v1:

- canonical rendering and node normalization
- fail-closed parsing and deterministic rejection behavior
- addressing and reference-path semantics
- quoted-key and traversal disambiguation
- attribute traversal and attribute-depth semantics
- annotation attachment and slash-channel binding
- strict typed literal acceptance boundaries
- strict typed literal rejection boundaries
- separator/path literal handling
- datatype-to-literal validation behavior

These behavior families must not be allowed to drift across implementations.

## Coverage status

The status labels used here are:

- `baseline`: there is already enough CTS surface to make drift visible
- `partial`: some critical behavior is covered, but the family still needs expansion
- `incomplete`: the family is known but not yet covered strongly enough

## Coverage map

| behavior family | status | current CTS owner | current coverage notes | source feeder |
| --- | --- | --- | --- | --- |
| canonical rendering and node normalization | baseline | `cts/canonical/v1/suites/01-baseline.json`, `cts/canonical/v1/suites/02-node-canonicalization.json` | baseline canonical output plus promoted node introducer normalization and legacy rejection cases | `Aeon/cts/canonical`, `Aeon/stress-tests/canonical/*` |
| fail-closed parsing and deterministic rejection behavior | baseline | `cts/core/v1/suites/04-fail-closed-semantics.json`, `cts/core/v1/suites/05-promoted-edge-rejections.json` | baseline fail-closed semantics plus promoted deterministic syntax rejection cases | `Aeon/cts/core`, `Aeon/stress-tests/edge/*` |
| addressing and reference-path semantics | baseline | `cts/core/v1/suites/02-addressing-and-syntax.json`, `cts/core/v1/suites/03-attributes-and-references.json`, `cts/core/v1/suites/06-promoted-domain-fixtures.json`, `cts/core/v1/suites/07-promoted-snippet-transport.json` | baseline addressing plus promoted nested path, quoted-key, and reference rejection cases | `Aeon/cts/core`, `Aeon/stress-tests/domain/addressing/*`, `Aeon/stress-tests/snippets/*` |
| quoted-key and traversal disambiguation | baseline | `cts/core/v1/suites/06-promoted-domain-fixtures.json`, `cts/core/v1/suites/07-promoted-snippet-transport.json` | explicitly covers quoted-key single-segment semantics and quoted traversal behavior | `Aeon/stress-tests/domain/addressing/*`, `Aeon/stress-tests/snippets/*` |
| attribute traversal and attribute-depth semantics | partial | `cts/core/v1/suites/03-attributes-and-references.json`, `cts/core/v1/suites/06-promoted-domain-fixtures.json`, `cts/core/v1/suites/07-promoted-snippet-transport.json` | covers attribute selectors, quoted attribute segments, and max-depth rejection, but could use broader normative coverage | `Aeon/cts/core`, `Aeon/stress-tests/domain/addressing/*`, `Aeon/stress-tests/snippets/*` |
| annotation attachment and slash-channel binding | baseline | `cts/annotations/v1/annotation-stream-cts.v1.json` | baseline annotation stream lane plus promoted slash-channel structured binding case | `Aeon/cts/annotations`, `Aeon/stress-tests/domain/comments/*` |
| strict typed literal acceptance boundaries | baseline | `cts/core/v1/suites/08-promoted-strict-literals.json`, `cts/core/v1/suites/09-promoted-separator-literals.json`, `cts/core/v1/suites/10-promoted-numeric-and-encoding-literals.json` | covers representative accepted strict literals across temporal, separator, numeric, radix, and encoding families | `Aeon/stress-tests/snippets/positive-strict.aeon-cases` |
| strict typed literal rejection boundaries | baseline | `cts/core/v1/suites/08-promoted-strict-literals.json`, `cts/core/v1/suites/09-promoted-separator-literals.json`, `cts/core/v1/suites/10-promoted-numeric-and-encoding-literals.json` | covers representative rejection boundaries across temporal, separator, numeric, encoding, and datatype mismatch classes | `Aeon/stress-tests/snippets/negative-strict.aeon-cases` |
| separator/path literal handling | baseline | `cts/core/v1/suites/09-promoted-separator-literals.json` | includes rooted path, URL-like, nested-list/object, lexical reject, and datatype mismatch behavior | `Aeon/stress-tests/snippets/positive-strict.aeon-cases`, `Aeon/stress-tests/snippets/negative-strict.aeon-cases` |
| datatype-to-literal validation behavior | baseline | `cts/core/v1/suites/08-promoted-strict-literals.json`, `cts/core/v1/suites/09-promoted-separator-literals.json`, `cts/core/v1/suites/10-promoted-numeric-and-encoding-literals.json` | covers datatype/literal mismatch behavior for number, sep, base64, and hex classes | `Aeon/cts/core`, `Aeon/stress-tests/snippets/negative-strict.aeon-cases` |
| custom-mode typed literal acceptance and fail-closed boundaries | baseline | `cts/core/v1/suites/01-baseline.json`, `cts/core/v1/suites/11-promoted-custom-literals.json`, `cts/core/v1/suites/12-promoted-custom-rejections.json` | baseline custom-datatype policy plus promoted custom-mode value-family acceptance, untyped fail-closed behavior, and reserved-datatype mismatch checks | `Aeon/stress-tests/snippets/positive-custom.aeon-cases`, `Aeon/stress-tests/snippets/negative-custom.aeon-cases` |
| AEOS-specific conformance behavior | partial | `cts/aeos/v1/aeos-validator-cts.v1.json`, `cts/aeos/v1/suites/00-envelope.json` through `cts/aeos/v1/suites/16-reference-forms.json` | AEOS already has a meaningful validator-oriented CTS surface covering envelope, schema rules, presence, types, reference-form constraints, guarantees, indexed-path validation, separator policy, and structural container items; what is still missing is the same explicit anti-drift coverage review that core now has | `Aeon/cts/aeos`, future AEOS-specific stress surfaces |

## Promotion rule

Selective promotion is allowed, but not by anecdote.

A behavior family should only be considered safely curated when:

- it maps to a clear spec-owned behavior class
- the CTS surface contains enough cases to detect implementation drift
- the feeder stress surface remains known and documented
- the next missing coverage is explicit rather than accidental

## Working policy

For the next promotion passes:

- do not promote by default from the remaining broad stress corpora
- do promote when a missing backbone behavior family or weak rejection boundary is identified
- keep the feeder source recorded here when a new suite is added
- update this document whenever a new promoted suite materially changes coverage

For AEOS specifically:

- treat the existing `cts/aeos/v1` validator lane as a real baseline, not an empty placeholder
- perform a dedicated AEOS anti-drift review before promoting large new AEOS material
- prefer documenting AEOS behavior families explicitly before expanding the AEOS surface further

## AEOS behavior families

The following surfaces are treated as the current AEOS anti-drift behavior families:

- result-envelope and validator output contract
- schema rule-index integrity
- presence and forbid semantics
- representational type and datatype-label constraints
- numeric lexical-form constraints
- string length and pattern constraints
- guarantee emission
- container-kind and tuple-arity constraints
- indexed-path validation and tuple positional checks
- separator-literal policy enforcement
- structural container item validation
- reference-form constraints and schema-owned reference policy
- Core-versus-AEOS authority boundary preservation

## AEOS coverage map

| AEOS behavior family | status | current CTS owner | current coverage notes |
| --- | --- | --- | --- |
| result-envelope and validator output contract | baseline | `cts/aeos/v1/suites/00-envelope.json` | establishes the validator envelope shape and success-path baseline |
| schema rule-index integrity | baseline | `cts/aeos/v1/suites/02-schema-rules.json` | covers duplicate rule paths and unknown constraint-key rejection |
| presence and forbid semantics | baseline | `cts/aeos/v1/suites/03-presence.json` | covers required presence, successful presence, and forbid-style absence semantics |
| representational type and datatype-label constraints | baseline | `cts/aeos/v1/suites/04-type.json`, `cts/aeos/v1/suites/08-datatype-labels.json` | covers type matching, mismatch behavior, and datatype-label constraint enforcement |
| numeric lexical-form constraints | baseline | `cts/aeos/v1/suites/05-numeric-form.json` | covers sign and digit-form constraint behavior on numeric lexical forms |
| string length and pattern constraints | baseline | `cts/aeos/v1/suites/06-string-form.json`, `cts/aeos/v1/suites/07-pattern.json` | covers min/max length and pattern matching behavior |
| guarantee emission | baseline | `cts/aeos/v1/suites/09-guarantees.json` | covers validator guarantee emission as part of the result surface |
| container-kind and tuple-arity constraints | baseline | `cts/aeos/v1/suites/10-container-kinds.json`, `cts/aeos/v1/suites/11-tuple-arity.json` | covers list-vs-tuple distinction and exact tuple arity enforcement |
| indexed-path validation and tuple positional checks | baseline | `cts/aeos/v1/suites/12-tuple-positional.json`, `cts/aeos/v1/suites/13-indexed-path-validation.json` | covers indexed tuple element validation and malformed indexed path rejection |
| separator-literal policy enforcement | baseline | `cts/aeos/v1/suites/14-separator-literal-policy.json` | covers trailing separator delimiter policy behavior across pass, warn, and fail modes |
| structural container item validation | baseline | `cts/aeos/v1/suites/15-structural-container-items.json` | covers typed indexed paths into structural list/object content |
| reference-form constraints and schema-owned reference policy | baseline | `cts/aeos/v1/suites/16-reference-forms.json` | covers schema-owned reference require/forbid behavior, clone-vs-pointer distinction, invalid schema combinations, and schema-wide reference policy while keeping materialization behavior out of AEOS conformance |
| Core-versus-AEOS authority boundary preservation | baseline | `cts/aeos/v1/suites/01-baseline.json`, `cts/aeos/v1/suites/16-reference-forms.json` | preserves that missing reference targets and related legality checks remain Core-owned even when AEOS constrains reference form |

## AEOS review note

The AEOS validator lane is now strong enough to be treated as a real anti-drift baseline.

What it still lacks is not breadth so much as explicit review framing:

- tighter mapping from AEOS spec sections to AEOS behavior families
- a clearer statement of which diagnostics are validator-contract guarantees
- a short list of AEOS-specific feeder surfaces for future expansion
