# Block-comment physical newline amendment

Status: adopted working specification; development CTS coverage.

A physical LF, including the LF in CRLF, inside any completed plain or structured
block comment is available wherever the surrounding grammar permits a newline
separator. The comment need not have another newline outside its closer.
The rule applies to document and header bindings, object members, attribute
entries, list/tuple elements and node children. Between other structural tokens,
that newline remains ordinary layout rather than forcing a binding boundary.

A comment without LF is not a separator. Standalone CR, escaped backslash-n text,
U+2028 and U+2029 do not substitute for LF. Comment-like text and physical newlines
inside literal payloads remain governed by their literal family. Unterminated
comments remain lexer errors and the first matching closer still terminates a
block comment.

Authority is the AEON Structure Syntax and Comments/Annotations References in
`aeonite-specs`. This repository owns the verdicts. The change adopts existing
TypeScript behavior and aligns Python; it does not assert that every other
implementation has adopted the amendment.

## Executable target

`cts/core/v1/core-cts.v1.next.json` selects
`suites/30-next-block-comment-newlines.json`. Its 207 vectors include:

- seven channels, seven contexts, and LF/CRLF positive controls;
- newline-free negative controls in all those contexts;
- standalone CR, escaped text and Unicode line/paragraph separators;
- strict/custom typing, inter-token layout and zero-binding documents;
- literal and compact-token boundaries, first closers and unterminated comments.

The mutable Core next selection now contains 655 cases, with its existing
exclusions retained. The released Core 0.5 target remains at 299 cases. No
released manifest, referenced suite, compatibility snapshot or content hash is
rewritten for this amendment. New snapshot promotion is separate release work.

Python and the available built TypeScript CLI both pass all 655 selected Core
next cases through the implementation source-lane CTS runner. The new 207 cases
also pass scoped direct compilation probes in both implementations. This is
local working-tree evidence, not a published package claim or Rust/PHP result.

## Rust and PHP alignment

Local follow-up checks align the remaining two implementation surfaces:

| Surface | New block-comment CTS | Wider checks |
| --- | --- | --- |
| Rust CLI | 207/207 pass after retaining physical comment newlines | Core next 655/655; Core crate tests pass with Sofia enabled, with two existing ignored tests. |
| PHP CLI | 207/207 pass after fixing the empty-document warning | Core next 590/655; the same 65 other-feature case IDs fail with the original document parser. |

Rust originally passed 105/207 and rejected 102 newline-bearing cases. Its lexer
now buffers physical LF token spans across chunks and publishes them after the
first matching comment closer. Tests cover all seven channels and separator
contexts in both baseline and Sofia parsers, exact byte spans at every Unicode
scalar chunk boundary, and unterminated comments.

PHP already admitted newline-bearing comments through token span line differences.
Its empty-input path read the nonexistent previous token and emitted a warning
that corrupted the CLI JSON envelope. The document span now handles zero consumed
tokens. New PHP tests cover both newline-token modes, all channels and contexts,
and zero-binding inputs: two tests, 710 assertions pass.

The broader PHP Lexer/Parser/Core run passes 195 of 201 tests; six SANSA empty-key
Resolve cases fail and reproduce with the original document-parser trait. The
Core next baseline comparison used that original trait through a temporary
bootstrap, suppressing the known empty-input warning to complete the comparison;
its 65 failed IDs exactly match the changed parser's wider run. These existing
failures cover other language features and are not claimed fixed by this change.
No released CTS targets or ABNF evidence bundles are rewritten.

Implementation base revisions (working-tree changes are present):

- Rust: `805ba506a10c7f0698a4cb98e368478ccf0f65c9`.
- PHP: `23c66b44af17dbeeac914204f670c1e801460cec`.

Exact tested artifact SHA-256 digests:

- CTS suite: `7d665195407e3e6acc7b48caaeab880c0b43c139dd961d7d93295152195faac9`.
- Rust lexer: `7b635332e1ea139d642383db82a91d6006a441b815d87c5c8b9e6aae069355af`.
- PHP document parser: `2dd07fc9d39c02947491502dac4c099632562205a27ed2fd9e81544c0843ef16`.
