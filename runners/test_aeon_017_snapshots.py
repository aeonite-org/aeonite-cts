"""Protect the exact promoted selection without coupling it to mutable next."""
import copy
import hashlib
import json
import unittest

import validate_cts_repo as validator

ROOT = validator.ROOT
INVENTORY = ROOT / "docs/conformance/aeon-0.17-snapshots.json"
REMOVED = {
    "core": {
        "core-addr-001b-empty-quoted-key-reject",
        "core-addr-001c-empty-quoted-path-segment-reject",
        "core-baseline-015-strict-stale-radix-alias-reject",
        "core-snippet-transport-003-empty-quoted-keys-reject",
    },
    "aes": {
        "aes-baseline-009-stale-radix-alias-reject",
        "aes-emission-001b-empty-quoted-key-reject",
    },
    "canonical": set(),
}


def selected(path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cases = {}
    for ref in manifest["suites"]:
        suite = json.loads((path.parent / ref["file"]).read_text(encoding="utf-8"))
        for case in suite["tests"]:
            if case["id"] not in ref.get("exclude_tests", []):
                if case["id"] in cases:
                    raise AssertionError("Duplicate selected case: " + case["id"])
                cases[case["id"]] = case
    return cases


class Aeon017SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_exact_metadata_counts_and_content_pins(self):
        self.assertEqual("4bc227f0e042c9c4514a0f2d75492cb6634cab60", self.inventory["source_revision"])
        self.assertEqual("a6948968e4e2741f2342249024b266ca6adbfeb7", self.inventory["specification_revision"])
        self.assertFalse(self.inventory["release_combination_acceptance"])
        expected = {"core": ("0.6", 657), "aes": ("0.6", 87), "canonical": ("0.5", 209)}
        seen = {}
        for record in self.inventory["snapshots"]:
            lane = record["lane"]
            version, count = expected[lane]
            path = ROOT / record["manifest"]
            raw = path.read_bytes()
            manifest = json.loads(raw)
            self.assertEqual(record["manifest_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(lane + "-cts-v1-snapshot-" + version, manifest["meta"]["snapshot_id"])
            self.assertEqual(version + ".0", manifest["meta"]["version"])
            self.assertEqual("released", manifest["meta"]["status"])
            self.assertEqual(self.inventory["specification_revision"], manifest["meta"]["specification_revision"])
            self.assertNotIn("conformance", manifest["meta"])
            self.assertNotIn("spec_snapshot_id", manifest["meta"])
            errors = []
            validator.validate_manifest_metadata(path, manifest, seen, errors)
            validator.validate_external_suite_manifest(path, manifest, errors)
            self.assertEqual([], errors)
            self.assertEqual(count, record["cases"])
            self.assertEqual(count, len(selected(path)))
            for ref in manifest["suites"]:
                self.assertEqual(hashlib.sha256((path.parent / ref["file"]).read_bytes()).hexdigest(), ref["content_sha256"])
        self.assertEqual(3, len(seen))

    def test_only_explicit_superseded_cases_leave_the_previous_selection(self):
        additions = {"core": 362, "aes": 6, "canonical": 12}
        for record in self.inventory["snapshots"]:
            old = selected(ROOT / record["previous_manifest"])
            new = selected(ROOT / record["manifest"])
            self.assertEqual(REMOVED[record["lane"]], old.keys() - new.keys())
            self.assertEqual(additions[record["lane"]], len(new.keys() - old.keys()))
            for key in old.keys() & new.keys():
                self.assertEqual(old[key], new[key], key)
            self.assertTrue(any(not case["expected"]["ok"] for case in new.values()))
            self.assertTrue(any(case["expected"]["ok"] for case in new.values()))

    def test_newly_promoted_copies_are_self_contained(self):
        frozen_count = 0
        for record in self.inventory["snapshots"]:
            for asset in record["assets"]:
                path = ROOT / asset["frozen"]
                self.assertEqual(asset["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                if asset["frozen"] != asset["source"]:
                    self.assertIn("/snapshots/", asset["frozen"])
                    frozen_count += 1
        self.assertEqual(11, frozen_count)
        # The reserved moving AES 0.5 identifier is retained, not renamed.
        moving = json.loads((ROOT / "cts/aes/v1/aes-cts.v1.next.json").read_text())
        self.assertEqual("aes-cts-v1-snapshot-0.5", moving["meta"]["snapshot_id"])
        self.assertEqual("experimental", moving["meta"]["conformance"]["surface"])

    def test_corrupted_digest_and_unknown_exclusion_fail_validation(self):
        for record in self.inventory["snapshots"]:
            path = ROOT / record["manifest"]
            original = json.loads(path.read_text())
            bad = copy.deepcopy(original)
            bad["suites"][0]["content_sha256"] = "0" * 64
            errors = []
            validator.validate_external_suite_manifest(path, bad, errors)
            self.assertTrue(any("content digest mismatch" in error for error in errors))
            bad = copy.deepcopy(original)
            bad["suites"][0].setdefault("exclude_tests", []).append("nonexistent-release-control")
            errors = []
            validator.validate_external_suite_manifest(path, bad, errors)
            self.assertTrue(any("excludes unknown test id" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
