"""Harness tests: do not count these as an operation implementation's CTS pass."""

import argparse
import copy
import json
from pathlib import Path
import runpy
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
Runner = runpy.run_path(str(ROOT / "runners/run_aeonic_operations.py"), run_name="runner_library")["Runner"]


class RunnerChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="aeonic-runner-check-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.output = self.folder / "output.json"
        self.fake = self.folder / "fake.py"
        self.fake.write_text("import pathlib,sys\nsys.stdin.read()\nsys.stdout.write(pathlib.Path(sys.argv[1]).read_text())\n")
        self.command = " ".join(shlex.quote(str(item)) for item in [sys.executable, self.fake, self.output])
        self.args = argparse.Namespace(
            manifest=ROOT / "cts/aeonic-operations/v1/aeonic-operations-cts.v1.next.json",
            specs_root=ROOT.parent / "aeonite-specs", capability_set="baseline-with-declared-order",
            sut=self.command, without_declared_order_sut=self.command,
            cwd=self.folder, timeout=5.0)
        self.runner = Runner(self.args)
        self.cases = {case["id"]: case for case in self.runner.tests if "expected" in case}

    def test_twenty_normative_matching_examples(self):
        examples = json.loads((ROOT / "fixtures/aeonic-operations/v1/runner-matching.json").read_text())["examples"]
        for example in examples:
            with self.subTest(example=example["id"]):
                self.output.write_text(json.dumps(example["output"]))
                accepted = True
                try:
                    case = self.cases[example["caseId"]]
                    self.runner.match(case, self.runner.invoke(case))
                except Exception:
                    accepted = False
                self.assertEqual(accepted, example["expectedMatch"])

    def test_crash_is_a_harness_failure(self):
        self.fake.write_text("import sys\nsys.stdin.read()\nsys.exit(7)\n")
        with self.assertRaisesRegex(ValueError, "harness failure"):
            self.runner.invoke(next(iter(self.cases.values())))

    def test_timeout_never_becomes_an_operation_resource_value(self):
        self.fake.write_text("import sys,time\nsys.stdin.read()\ntime.sleep(1)\n")
        self.args.timeout = 0.05
        with self.assertRaises(subprocess.TimeoutExpired):
            self.runner.invoke(next(iter(self.cases.values())))

    def test_modified_schema_digest_is_rejected(self):
        manifest = json.loads(self.args.manifest.read_text())
        manifest["meta"]["specification_schema_sha256"] = "0" * 64
        for suite in manifest["suites"]:
            suite["file"] = str(self.args.manifest.parent / suite["file"])
        (self.folder / "schemas").mkdir()
        (self.folder / "schemas/cts-binding.schema.json").write_bytes(
            (self.args.manifest.parent / "schemas/cts-binding.schema.json").read_bytes())
        altered = self.folder / "altered.next.json"
        altered.write_text(json.dumps(manifest))
        args = copy.copy(self.args)
        args.manifest = altered
        with self.assertRaisesRegex(ValueError, "Specification schema digest mismatch"):
            Runner(args)

    def test_manifest_changed_during_execution_cannot_be_reported_as_passed(self):
        case = next(iter(self.cases.values()))
        expected = case["expected"]
        self.output.write_text(json.dumps({"ok": True, "errors": [], "warnings": [], "result": expected}))
        manifest = json.loads(self.args.manifest.read_text())
        suite = self.folder / "suite.json"
        suite.write_text(json.dumps({"id": "single", "tests": [case]}))
        import hashlib
        manifest["suites"] = [{"id": "single", "file": str(suite),
                               "content_sha256": hashlib.sha256(suite.read_bytes()).hexdigest()}]
        (self.folder / "schemas").mkdir()
        (self.folder / "schemas/cts-binding.schema.json").write_bytes(
            (self.args.manifest.parent / "schemas/cts-binding.schema.json").read_bytes())
        target = self.folder / "target.next.json"
        target.write_text(json.dumps(manifest))
        args = copy.copy(self.args); args.manifest = target
        runner = Runner(args)
        target.write_text(target.read_text() + "\n")
        report = runner.run()
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(f["id"] == "artifact-integrity" for f in report["failures"]))


if __name__ == "__main__":
    unittest.main()
