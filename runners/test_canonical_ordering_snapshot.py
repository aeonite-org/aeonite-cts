"""Guard the reviewed canonical target without coupling it to moving next files."""
import hashlib
import json
import unittest

import validate_cts_repo as validator


ROOT = validator.ROOT / "cts/canonical/v1"
SNAPSHOT = ROOT / "canonical-cts.v1.snapshot-0.4.json"
EXCLUSIONS = {
    "baseline": ["canonical-baseline-016-reference-whitespace-after-sigil-normalized"],
    "string-escapes": ["canonical-string-002c-trimtick-payload-indentation-survives-canonicalization"],
}


def selected_cases(snapshot):
    result = {}
    for ref in snapshot["suites"]:
        suite = json.loads((ROOT / ref["file"]).read_text(encoding="utf-8"))
        for case in suite["tests"]:
            if case["id"] not in ref.get("exclude_tests", []):
                if case["id"] in result:
                    raise AssertionError(f"duplicate selected id: {case['id']}")
                result[case["id"]] = case
    return result


class CanonicalOrderingSnapshotTests(unittest.TestCase):
    def test_snapshot_pins_reviewed_selection_and_specification(self):
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        errors = []
        validator.validate_manifest_metadata(SNAPSHOT, snapshot, {}, errors)
        validator.validate_external_suite_manifest(SNAPSHOT, snapshot, errors)
        self.assertEqual([], errors)
        meta = snapshot["meta"]
        self.assertEqual("released", meta["status"])
        self.assertEqual("0.4.0", meta["version"])
        self.assertEqual("canonical", meta["lane"])
        self.assertEqual("cts.protocol.v1", meta["sut_protocol"])
        self.assertEqual("canonical-cts-v1-snapshot-0.4", meta["snapshot_id"])
        self.assertEqual("ae427af77568518a71aaf86ec0dc620e07658944", meta["specification_revision"])
        self.assertNotIn("spec_snapshot_id", meta)
        self.assertNotIn("conformance", meta)
        self.assertEqual([
            ("baseline", 17), ("node-canonicalization", 6),
            ("whitespace-boundary-canonicalization", 2),
            ("structural-identity-canonicalization", 1), ("string-escapes", 20),
            ("canonical-symbolic-literals", 3), ("canonical-temporal-literals", 3),
            ("next-canonical-literal-flow", 9), ("next-canonical-reference-ordering", 105),
            ("next-canonical-type-only-generics", 31),
        ], [(ref["id"], len(selected_cases({"suites": [ref]}))) for ref in snapshot["suites"]])
        for ref in snapshot["suites"]:
            raw = (ROOT / ref["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), ref["content_sha256"])
            self.assertEqual(EXCLUSIONS.get(ref["id"], []), ref.get("exclude_tests", []))
        selected = selected_cases(snapshot)
        self.assertEqual(197, len(selected))
        self.assertEqual(153, sum(case["expected"]["ok"] for case in selected.values()))
        self.assertEqual(44, sum(not case["expected"]["ok"] for case in selected.values()))

    def test_reference_fixed_points_rejections_and_replacement_coverage(self):
        selected = selected_cases(json.loads(SNAPSHOT.read_text(encoding="utf-8")))
        references = [case for case in selected.values() if case["id"].startswith("canonical-reference-order-")]
        fixed_points = [case for case in references if case["id"].endswith("-fixed-point")]
        self.assertEqual(46, len(fixed_points))
        for fixed in fixed_points:
            original = selected[fixed["id"].removesuffix("-fixed-point")]
            self.assertTrue(original["expected"]["ok"])
            self.assertTrue(fixed["expected"]["ok"])
            text = original["expected"]["result"]["canonical_text"]
            self.assertEqual(text, fixed["input"]["source"])
            self.assertEqual(text, fixed["expected"]["result"]["canonical_text"])
        rejected = [case for case in references if not case["expected"]["ok"]]
        self.assertEqual(13, len(rejected))
        for case in rejected:
            self.assertTrue(case["expected"]["errors"])
            self.assertEqual("", case["expected"]["result"]["canonical_text"])
        for excluded in EXCLUSIONS.values():
            self.assertNotIn(excluded[0], selected)
        replacement = selected["canonical-reference-order-003-reference-sigil-whitespace"]
        text = replacement["expected"]["result"]["canonical_text"]
        self.assertLess(text.index("order:o"), text.index("clone:n"))
        historical = json.loads((ROOT / "suites/05-string-escapes.json").read_text(encoding="utf-8"))
        old_trimtick = next(case for case in historical["tests"] if case["id"] == EXCLUSIONS["string-escapes"][0])
        replacement = selected["canonical-literal-flow-009-common-leading-space-protection"]
        self.assertEqual(old_trimtick["input"], replacement["input"])
        self.assertEqual(old_trimtick["expected"], replacement["expected"])

    def test_historical_manifests_remain_byte_identical(self):
        for filename, digest in (
            ("canonical-cts.v1.json", "61b5b258d64f1e80327046be67d8db73d9e352056e91d88d64f5d3d9b4da23bb"),
            ("canonical-cts.v1.snapshot-0.2.json", "6d78e37f1985dfd4543368f5f25386714aa1c8b1a08a45f755edf64b8f2b3a3a"),
            ("canonical-cts.v1.snapshot-0.3.json", "91c30bc5b1e31e64ad522abbaf55f27a96246a8540d3c8bb16dc255716fb1b67"),
        ):
            self.assertEqual(digest, hashlib.sha256((ROOT / filename).read_bytes()).hexdigest(), filename)


if __name__ == "__main__":
    unittest.main()
