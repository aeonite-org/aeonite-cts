import hashlib
import json
import unittest

import validate_cts_repo as validator


class TypeOnlySnapshotTests(unittest.TestCase):
    def test_promoted_snapshots_pin_suites_and_expected_coverage(self):
        for lane, surface, version, count in (
            ("aes", "aes-events", "0.2", 48),
            ("telex", "telex", "0.2", 61),
            ("film", "film", "0.3", 92),
        ):
            path = validator.ROOT / "cts" / lane / "v1" / f"{surface}-cts.v1.snapshot-{version}.json"
            manifest = json.loads(path.read_text())
            with self.subTest(surface=surface):
                errors = []
                validator.validate_manifest_metadata(path, manifest, {}, errors)
                self.assertEqual([], errors)
                self.assertEqual("released", manifest["meta"]["status"])
                self.assertEqual("ae427af77568518a71aaf86ec0dc620e07658944", manifest["meta"]["specification_revision"])
                self.assertNotIn("spec_snapshot_id", manifest["meta"])
                selected = 0
                for reference in manifest["suites"]:
                    raw = (path.parent / reference["file"]).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), reference["content_sha256"])
                    excluded = set(reference.get("exclude_tests", []))
                    selected += sum(test["id"] not in excluded for test in json.loads(raw)["tests"])
                self.assertEqual(count, selected)

    def test_revision_metadata_rejects_invalid_commit_ids(self):
        path = validator.ROOT / "cts/aes/v1/aes-events-cts.v1.snapshot-0.2.json"
        for revision in ("main", "ae427af", "G" * 40, 123):
            errors = []
            validator.validate_manifest_metadata(path, {
                "meta": {"snapshot_id": "example-cts-v1-snapshot-0.1", "specification_revision": revision}
            }, {}, errors)
            self.assertTrue(any("specification_revision" in error for error in errors), revision)


if __name__ == "__main__":
    unittest.main()
