# SANSA property selectors: preparation protocol 0.1

Status: **experimental, excluded by default, unimplemented**. The owning contract
is `sansa-v1-property-selectors` at specification commit
`87af960eb26d15711369d20c9753efddb8617a48`. This protocol prepares test assets; it
is not a runtime SUT protocol, capability claim or immutable CTS snapshot.
No existing development or released manifest selects these suites.

The explicit target is
`cts/sansa/v1/sansa-property-selectors-cts.v1.next.json`, profile
`sansa-properties-read-only-candidate-0.1`, protocol
`sansa-properties-preparation-v0.1`. It contains 149 expectations: 34 parser,
83 Resolve, 15 Query and 17 denied-consumer cases. Positional selection and
new recursive selectors are outside this target.

## Preparation check

Use Python 3.12 or later and `jsonschema>=4.18,<5` (the existing runner dependency):

```sh
python3 runners/check_sansa_properties.py --check --specs-root ../aeonite-specs
python3 -m unittest discover -s runners -p 'test_sansa_properties_preparation.py'
```

The sibling specification checkout must contain the pinned proposal source,
resource and schema. Their digests, suite/fixture digests, closed expectation
schema, handle/address witnesses, required coverage families, excluded profile
and preparation-only marker are checked. The checker requires a nonzero owning
commit pin. It verifies the specified bytes, not remote Git provenance; a release
job must independently check out the named revision. Tests needing those bytes
use `SANSA_PROPERTY_SPECS_ROOT` if the specs checkout is elsewhere.

Success reports `status: prepared`, `sutExecuted: false`,
`acceptanceQualification: false` and `defaultSelection: exclude`. It must never
be recorded as executed selector conformance. There is no SUT invocation option.
The checker constructs bounded generated input but does not parse or evaluate a
selector or calculate expected results. Review/merge of the proposed contract,
actual provider adapters and a reviewed executable lane protocol are prerequisites
to implementation claims. Unsupported instrumentation must fail rather than
omit an expectation or become an optional-runtime skip.

## Fixture adapter obligations

`fixtures/property-selectors-v1.json` is a deliberately generic SANSA namespace,
not an AEON parser fixture or assertion that every generic topology is legal AEON.
Allocate one opaque handle per binding `id`; never substitute paths for handle
identity. `children` is ordered ordinary navigation; `index` identifies an
anonymous positional edge; `key` identifies an ordinary named edge. `heads` is the
ordered direct-head facet. `attributeSpace` and `localSpaces` give existing space
transitions. Parent edges derive from those explicit relationships, not paths.
`address` is the canonical result witness. Rebasing preserves those witnesses;
it changes authorization, not stored binding identities or paths.

The `properties` flags advertise the optional facet's callable operations.
`nodeKind` is authoritative; `tag` is authoritative **only on NodeHead**. Cached
container/ordinary tags, `cachedTag`, `legacyName` and ordinary `tag` member values
are adversarial metadata for fallback detection. `foreign` and its head are
unreachable from the authorized root. Scope/ownership uses graph reachability
within the current engine frame and direct-head ownership where requested.
Roots can carry misleading key metadata that the engine must not read.

Each operation receives a fresh adapter except the explicitly repeated/reentrant
public-call probes. `rebasedRoot` replaces the namespace root. `contextualRoot`
is supplied using the existing Resolve/Query contextual input, not a new caller
property-authority field. `invalidRoot` supplies an invalid namespace root.
`omit` removes named callbacks, including those whose absence must be found on an
empty branch. No missing operation may be inferred from legacy binding fields.

`faults` replace one callback outcome for the named handle. `return` supplies the
literal `value`; a `nodeHeads` array denotes handles by ID. `absent` returns the
host's supported absence. `throw` raises a checked adapter failure or iterator
failure as appropriate; its message is not public output. `at`, default 1, selects
the one-based invocation of that callback on that handle, including terminal
iterator probes. Scope faults can return `outside`, a false root role or malformed
metadata; they are not permission grants. Iterator faults use the owner handle.
`headNext` means iterator advancement; `headEarlyClose` means cleanup on an early
exit, not a completion probe. Count callback entry even when it throws. Iterators
must be genuinely incremental and expose cleanup, not prebuilt copied arrays.

`wideHeads` replaces only `multi`'s direct heads with 64 or 128 lazily yielded
NodeHead handles in deterministic order. Tags are `left`, except the requested
`first`/`last` match has tag `right`; `none` never matches. All are directly owned
and authorized. No generated head is a result witness. The wrapper counts actual
yields/probes; it must not pre-enumerate them or implement a substitute resolver.

`repeat: 2` invokes the same public Query twice on one adapter, with a fresh
allowance each time. Expected records apply to **each** invocation; call counts
are aggregated. `reenter` invokes its nested public Query once, synchronously
inside the first `key` callback; suppress recursive retriggering. Its supplied
limit is independent. `nestedResultsOk` requires the nested Query to succeed and
select the same authorized document handle. Counts aggregate both invocations.

## AST, generators and result assertions

`source`, `ast` and `generate` are mutually exclusive. Pass text to the real
parser and caller ASTs to the real public normalizer. `astFault: cycle` adds a
self-cycle through `selectors`; `accessor` replaces the first property selector's
`value` data field with a getter that increments `astGetterCalls` and returns its
prior value. Rust/native adapters must demonstrate the equivalent actual accepted
input boundary, or remain unsupported; JSON cannot carry an accessor or cycle.
Do not claim bridge coverage by sanitizing the fault before the real API.

`generate` is the small bounded input-construction vocabulary implemented in
`check_sansa_properties.expand`: payload scalar repetitions, repeated selectors
or an ASCII quoted member sized to the requested canonical length. `form` chooses
text or caller AST; `encoding` selects raw/escaped scalar payloads. Construct an
AST with deliberately untrusted `canonical`/`isExact`; do not trust those fields.
The maximum generated size is 65537. Scalar-count fixtures include astral values
to distinguish scalars from UTF-16 units. This helper is not an address parser.

Every present expected field is mandatory. In particular, compare original
`bindings` handles and structural `addresses` in order, preserving duplicates.
Query `records` retains candidate identity and the explicit `valueBindings` list,
including an empty list; `where` can remove the entire record. Errors return no
partial bindings or records. Assert error, causeCode, phase and resource fields
where specified. A consumer-boundary `mustNotResolve` requires its owning API to
reject before property traversal; a generic Resolve wrapper is insufficient.
Unallocated consumer diagnostics are intentionally not guessed by this candidate.

`calls` is a partial map of **exact** adapter callback counts, not inequalities or
public runtime metrics. Omitted counters are not asserted. Root counts refer to
adapter root acquisition; children counts to ordinary child enumeration. Head
terminal probes and early cleanup are separate counters. `inputUnchanged` compares
caller data before/after; accessor cases additionally require zero getter calls.
`currentPropertyScope` and `currentAddressRoot` inspect the actual parsed Query
current-row expression, not a test-only rewrite. Generated successful parses
without a literal canonical expectation must render/reparse consistently and
retain explicit expected exactness. No fixture implementation may manufacture
success from the expected side of the test.

## Delivery boundary

Scope metadata, key/tag authority, preflight, Query-wide accounting, cleanup and
negative consumers need actual cross-provider execution before advertisement.
AEON literal embedding reuses the shared grammar and has its own lexical/target
integration evidence gate; this target does not add a literal-deny grammar.
AEOS selector and Type Transpiler integration remain separately closed. Existing
reference/target checks and 1.15x latency/1.20x memory ceilings are unchanged.
Official releases, stable promotion and deployment remain held.
