# Lane Contract: Annotations (`cts/annotations/v1`)

This lane validates annotation extraction and deterministic binding.

## Input Fixture Shape
```json
{
  "source": "aeon text",
  "options": {}
}
```

Rules:
- `source` required (string).
- `options` optional object for lane-scoped toggles.

## Output `result` Shape
```json
{
  "annotations": [
    {
      "kind": "doc|annotation|hint|reserved",
      "target_path": "$.path",
      "value": "text"
    }
  ]
}
```

Rules:
- `result.annotations` required (array, may be empty).
- `target_path` MUST be canonical path or `null` for unbound records if suite allows them.

## Matching Notes
- Annotation order is normative when emitted order is part of the suite expectation.
- Whitespace normalization policy must be encoded in suite expectation fields, not inferred by runner.

## Adapter Note
- Lane may be backed by CLI inspect output or envelope-native SUT.
- Runner MUST normalize adapter output to this result shape before compare.
