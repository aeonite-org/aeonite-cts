#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - surfaced as CLI output
        errors.append(f"invalid json: {path}: {exc}")
        return None


def validate_suite_tests(
    lane_label: str,
    suite_label: str,
    tests: list[object],
    seen_test_ids: set[str],
    errors: list[str],
) -> None:
    for index, test in enumerate(tests, start=1):
        if not isinstance(test, dict):
            errors.append(f"{lane_label} {suite_label}: test {index} is not an object")
            continue
        test_id = test.get("id")
        if not isinstance(test_id, str) or not test_id:
            errors.append(f"{lane_label} {suite_label}: test {index} is missing a string id")
            continue
        if test_id in seen_test_ids:
            errors.append(f"{lane_label}: duplicate test id `{test_id}`")
            continue
        seen_test_ids.add(test_id)


def validate_external_suite_manifest(manifest_path: Path, data: dict[str, object], errors: list[str]) -> None:
    lane_label = str(manifest_path.relative_to(ROOT))
    seen_test_ids: set[str] = set()
    suites = data.get("suites")
    if not isinstance(suites, list):
        errors.append(f"{lane_label}: manifest suites must be a list")
        return

    for index, suite_ref in enumerate(suites, start=1):
        if not isinstance(suite_ref, dict):
            errors.append(f"{lane_label}: suite entry {index} is not an object")
            continue
        suite_id = suite_ref.get("id")
        suite_file = suite_ref.get("file")
        if not isinstance(suite_id, str) or not suite_id:
            errors.append(f"{lane_label}: suite entry {index} is missing a string id")
        if not isinstance(suite_file, str) or not suite_file:
            errors.append(f"{lane_label}: suite entry {index} is missing a string file")
            continue

        suite_path = (manifest_path.parent / suite_file).resolve()
        if not suite_path.exists():
            errors.append(f"{lane_label}: missing suite file {suite_file}")
            continue

        suite_data = load_json(suite_path, errors)
        if not isinstance(suite_data, dict):
            continue

        file_suite_id = suite_data.get("id")
        if isinstance(suite_id, str) and file_suite_id != suite_id:
            errors.append(
                f"{lane_label}: suite id mismatch for {suite_file}: manifest `{suite_id}` vs file `{file_suite_id}`"
            )

        tests = suite_data.get("tests")
        if not isinstance(tests, list):
            errors.append(f"{suite_path.relative_to(ROOT)}: tests must be a list")
            continue
        validate_suite_tests(lane_label, str(suite_path.relative_to(ROOT)), tests, seen_test_ids, errors)


def validate_inline_suite_manifest(manifest_path: Path, data: dict[str, object], errors: list[str]) -> None:
    lane_label = str(manifest_path.relative_to(ROOT))
    seen_test_ids: set[str] = set()
    suites = data.get("suites")
    if not isinstance(suites, list):
        errors.append(f"{lane_label}: manifest suites must be a list")
        return

    for index, suite in enumerate(suites, start=1):
        if not isinstance(suite, dict):
            errors.append(f"{lane_label}: inline suite {index} is not an object")
            continue
        suite_id = suite.get("id")
        if not isinstance(suite_id, str) or not suite_id:
            errors.append(f"{lane_label}: inline suite {index} is missing a string id")
            continue
        tests = suite.get("tests")
        if not isinstance(tests, list):
            errors.append(f"{lane_label}: inline suite `{suite_id}` is missing a tests list")
            continue
        validate_suite_tests(lane_label, f"inline suite `{suite_id}`", tests, seen_test_ids, errors)


def main() -> int:
    errors: list[str] = []

    json_files = sorted(ROOT.rglob("*.json"))
    for path in json_files:
        load_json(path, errors)

    manifests = sorted(ROOT.glob("cts/*/v1/*.json"))
    manifest_count = 0
    for manifest_path in manifests:
        data = load_json(manifest_path, errors)
        if not isinstance(data, dict):
            continue
        suites = data.get("suites")
        if not isinstance(suites, list):
            continue
        manifest_count += 1
        if all(isinstance(entry, dict) and "file" in entry for entry in suites):
            validate_external_suite_manifest(manifest_path, data, errors)
        elif all(isinstance(entry, dict) and "tests" in entry for entry in suites):
            validate_inline_suite_manifest(manifest_path, data, errors)
        else:
            errors.append(
                f"{manifest_path.relative_to(ROOT)}: unsupported mixed manifest shape in suites array"
            )

    if errors:
        print(f"CTS repo validation failed: {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"CTS repo validation passed: json_files={len(json_files)} manifests={manifest_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
