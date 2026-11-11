import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from run_aeonic_arithmetic import ROOT, Runner, boundary, exact, number, request, success


class RunnerTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(manifest=ROOT / 'cts/aeonic-arithmetic/v1/aeonic-arithmetic-cts.v1.next.json',
                                  specs_root=Path(os.environ.get('AEONIC_SPECS_ROOT', ROOT.parent / 'aeonite-specs')),
                                  sut=sys.executable, cwd=ROOT, timeout=10)

    def output(self, result):
        ok = result['outcome'] == 'value'
        return dict(ok=ok, warnings=[], errors=[] if ok else [dict(code=result['reason'], path=None, span=None, phase=None)], result=result)

    def invoke(self, runner, result):
        completed = subprocess.CompletedProcess([], 0, json.dumps(self.output(result)), '')
        with patch('run_aeonic_arithmetic.subprocess.run', return_value=completed):
            return runner.invoke('test', {'request': request('add', number('1'), number('2'))}, {})

    def test_rejects_unknown_result_fields_and_diagnostic_values(self):
        runner = Runner(self.args())
        bad = success(exact('3', '0')); bad['extra'] = 'ignored?'
        with self.assertRaises(Exception):
            self.invoke(runner, bad)
        with self.assertRaises(Exception):
            self.invoke(runner, dict(outcome='diagnostic', reason='resource_limit', context=dict(stage=6, path=None), value=None))

    def test_result_matching_rejects_numerically_wrong_success(self):
        runner = Runner(self.args())
        completed = subprocess.CompletedProcess([], 0, json.dumps(self.output(success(exact('4', '0')))), '')
        with patch('run_aeonic_arithmetic.subprocess.run', return_value=completed), self.assertRaises(ValueError):
            runner.operation(dict(id='wrong', fixture={'request': request('add', number('1'), number('2'))}, expected=success(exact('3', '0'))))

    def test_malformed_harness_limits_rejected_before_sut(self):
        runner = Runner(self.args())
        with patch('run_aeonic_arithmetic.subprocess.run') as execute, self.assertRaises(Exception):
            runner.invoke('bad', {'request': {}}, {'resourceLimits': None})
        execute.assert_not_called()

    def test_unknown_generator_and_bad_chain_links_cannot_silently_pass(self):
        with self.assertRaises(ValueError):
            boundary('not-a-reviewed-generator')
        with self.assertRaises(ValueError):
            boundary('numeric-typo')
        runner = Runner(self.args())
        with self.assertRaises(ValueError):
            runner.chain(dict(id='bad-link', steps=[dict(request=request('add', number('1'), number('2')))], links=[dict(fromStep=0, toStep=5, input='left')]))

    def test_source_and_suite_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.args(); manifest = json.loads(args.manifest.read_text()); temp = Path(folder)
            lane = temp / 'lane'; shutil.copytree(args.manifest.parent, lane)
            args.manifest = lane / args.manifest.name
            runner = Runner(args)
            runner.tests = []
            suite = lane / manifest['suites'][0]['file']; suite.write_text(suite.read_text() + '\n')
            report = runner.run()
            self.assertEqual(report['status'], 'failed')
            self.assertTrue(any(f['id'] == 'artifact-integrity' for f in report['failures']))
            manifest['meta']['specification_schema_sha256'] = '0' * 64
            args.manifest.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                Runner(args)

    def test_optional_diagnostic_message_and_transport_extensions(self):
        runner = Runner(self.args())
        result = dict(outcome='diagnostic', reason='resource_limit', context=dict(stage=6, path=None), message='details')
        completed = subprocess.CompletedProcess([], 0, json.dumps(dict(self.output(result), extension={'vendor': 1})), '')
        with patch('run_aeonic_arithmetic.subprocess.run', return_value=completed):
            actual = runner.operation(dict(id='diagnostic', fixture={'request': {}}, expected={k: v for k, v in result.items() if k != 'message'}))
        self.assertEqual(actual['reason'], 'resource_limit')

    def test_json_integer_equivalence_does_not_conflate_booleans(self):
        runner = Runner(self.args())
        expected = dict(outcome='diagnostic', reason='invalid_operand', context=dict(stage=4, path='/input/left'))
        actual = copy.deepcopy(expected); actual['context']['stage'] = 4.0
        completed = subprocess.CompletedProcess([], 0, json.dumps(self.output(actual)), '')
        with patch('run_aeonic_arithmetic.subprocess.run', return_value=completed):
            runner.operation(dict(id='integer-equivalence', fixture={'request': {}}, expected=expected))
        actual['context']['stage'] = True
        with self.assertRaises(Exception):
            self.invoke(runner, actual)


if __name__ == '__main__':
    unittest.main()
