import hashlib
import json
import unittest

import validate_cts_repo as validator


class FilmDepthSnapshotTests(unittest.TestCase):
    def test_snapshot_freezes_reviewed_selection_and_spec_revision(self):
        root = validator.ROOT / "cts/film/v1"
        path = root / "film-cts.v1.snapshot-0.4.json"
        snapshot = json.loads(path.read_text())
        errors = []
        validator.validate_manifest_metadata(path, snapshot, {}, errors)
        self.assertEqual([], errors)
        self.assertEqual("released", snapshot["meta"]["status"])
        self.assertEqual("0.4.0", snapshot["meta"]["version"])
        self.assertEqual("film-cts-v1-snapshot-0.4", snapshot["meta"]["snapshot_id"])
        self.assertEqual("242daa4214237cdc70d512b593c126615ab0556b", snapshot["meta"]["specification_revision"])
        self.assertNotIn("spec_snapshot_id", snapshot["meta"])
        self.assertNotIn("conformance", snapshot["meta"])
        # Do not couple this frozen target to the future moving next manifest.
        self.assertEqual([
            "framing-and-canonicalization", "records-and-transcoding",
            "records-and-symbolic-literals", "resource-limits",
            "next-film-type-only-generics", "next-film-logical-generic-depth",
        ], [ref["id"] for ref in snapshot["suites"]])
        selected = {}
        for ref in snapshot["suites"]:
            raw = (root / ref["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), ref["content_sha256"])
            for test in json.loads(raw)["tests"]:
                if test["id"] not in ref.get("exclude_tests", []):
                    self.assertNotIn(test["id"], selected)
                    selected[test["id"]] = test
        self.assertEqual(128, len(selected))
        self.assertEqual(103, sum(t["operation"] == "decode" for t in selected.values()))
        new = json.loads((root / "suites/06-next-logical-generic-depth.json").read_text())
        self.assertEqual(37, len(new["tests"]))
        self.assertTrue(all(test["id"] in selected for test in new["tests"]))
        self.assertNotIn("film-type-generics-limit-014-generic-depth-one-over", selected)
        self.assertTrue(selected["film-depth-026-superseded-optional-record"]["expected"]["ok"])
        old = json.loads((root / "film-cts.v1.snapshot-0.3.json").read_text())
        self.assertFalse(any(ref["id"] == new["id"] for ref in old["suites"]))
        old_ref = next(ref for ref in old["suites"] if ref["id"] == "next-film-type-only-generics")
        self.assertNotIn("film-type-generics-limit-014-generic-depth-one-over", old_ref.get("exclude_tests", []))


if __name__ == "__main__":
    unittest.main()
