import argparse
import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from run_aeonic_rational_arithmetic import ROOT, Runner, exact, request, success


class RunnerTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(
            manifest=ROOT / 'cts/aeonic-rational-arithmetic/v1/aeonic-rational-arithmetic-cts.v1.next.json',
            specs_root=Path(os.environ.get('AEONIC_SPECS_ROOT', ROOT.parent / 'aeonite-specs')),
            sut=sys.executable, cwd=ROOT, timeout=10)

    def output(self, result, **extensions):
        ok = result['outcome'] == 'value'
        output = dict(ok=ok, warnings=[], errors=[] if ok else [dict(code=result['reason'], path=None, span=None, phase=None)], result=result)
        output.update(extensions)
        return json.dumps(output)

    def invoke(self, runner, result, policy=None):
        with patch.object(runner, 'execute', return_value=self.output(result)):
            return runner.invoke('test', dict(request=request('add', exact('1'), exact('2'))), policy or {})

    def test_artifact_check_cannot_report_semantic_or_stable_pass(self):
        runner = Runner(self.args())
        with patch.object(runner, 'execute') as execute:
            report = runner.run(check_only=True)
        execute.assert_not_called()
        self.assertEqual(report['status'], 'artifacts-validated')
        self.assertFalse(report['stable_conformance_claim'])
        self.assertFalse(report['semantic_execution'])
        self.assertEqual(report['sut_executions'], 0)
        self.assertEqual(report['operation_cases'], 333)
        self.assertEqual(report['chains'], 3)

    def test_successful_mock_execution_remains_mutable(self):
        runner = Runner(self.args())
        runner.tests = runner.tests[:1]
        with patch.object(runner, 'execute', return_value=self.output(runner.tests[0]['expected'])):
            report = runner.run()
        self.assertEqual(report['status'], 'passed')
        self.assertFalse(report['stable_conformance_claim'])
        self.assertTrue(report['semantic_execution'])

    def test_result_matching_catches_numerically_wrong_value(self):
        runner = Runner(self.args())
        test = runner.tests[0]
        with patch.object(runner, 'execute', return_value=self.output(success(exact('99')))):
            with self.assertRaisesRegex(ValueError, 'Result mismatch'):
                runner.operation(test)

    def test_closed_results_and_diagnostic_no_value(self):
        runner = Runner(self.args())
        value = success(exact('3')); value['extra'] = True
        with self.assertRaises(Exception):
            self.invoke(runner, value)
        value = dict(outcome='diagnostic', reason='division_by_zero', context=dict(stage=6, path='/input/right/number'), value=None)
        with self.assertRaises(Exception):
            self.invoke(runner, value)

    def test_semantic_coprimality_is_checked_beyond_schema(self):
        runner = Runner(self.args())
        with self.assertRaisesRegex(ValueError, 'not reduced'):
            self.invoke(runner, success(exact('3', '0', '9')))

    def test_result_width_precedes_integer_conversion_and_gcd(self):
        runner = Runner(self.args())
        with patch('run_aeonic_rational_arithmetic.decimal_integer') as convert:
            with self.assertRaisesRegex(ValueError, 'denominator exceeds'):
                self.invoke(runner, success(exact('1', '0', '1001')), dict(resourceLimits=dict(maxDenominatorDigits=3)))
        convert.assert_not_called()

    def test_malformed_trusted_limits_never_invoke_sut(self):
        runner = Runner(self.args())
        bad = [None, [], dict(maxDenominatorDigits=True), dict(maxDenominatorDigits=-1), dict(unknownLimit=1)]
        for limits in bad:
            with self.subTest(limits=limits), patch.object(runner, 'execute') as execute:
                with self.assertRaises(Exception):
                    runner.invoke('invalid', dict(request={}), dict(resourceLimits=limits))
                execute.assert_not_called()

    def test_every_invocation_supplies_full_selected_limits(self):
        runner = Runner(self.args())
        with patch.object(runner, 'execute', return_value=self.output(success(exact('3')))) as execute:
            runner.invoke('limits', dict(request=request('add', exact('1'), exact('2'))), dict(resourceLimits=dict(maxWorkspaceDigits=7)))
        envelope = execute.call_args.args[0]
        selected = envelope['policy']['resourceLimits']
        self.assertEqual(selected, dict(runner.resource_limits, maxWorkspaceDigits=7))
        self.assertEqual(envelope['lane'], 'aeonic-rational-arithmetic')

    def test_chain_feeds_actual_success_bundle(self):
        runner = Runner(self.args())
        chain = copy.deepcopy(next(test for test in runner.tests if test.get('kind') == 'chain'))
        chain['steps'][1]['request']['input']['left'] = exact('0')
        outputs = [self.output(step['expected']) for step in chain['steps']]
        with patch.object(runner, 'execute', side_effect=outputs) as execute:
            runner.chain(chain)
        actual = execute.call_args_list[1].args[0]['fixture']['request']['input']['left']
        self.assertEqual(actual, exact('1', '0', '3'))

    def test_invalid_chain_links_and_diagnostic_donors_fail_artifact_validation(self):
        runner = Runner(self.args())
        chain = copy.deepcopy(next(test for test in runner.tests if test.get('kind') == 'chain'))
        chain['links'][0]['fromStep'] = True
        with self.assertRaisesRegex(ValueError, 'link order'):
            runner.validate_test(chain)
        chain = copy.deepcopy(next(test for test in runner.tests if test.get('kind') == 'chain'))
        chain['steps'][0]['expected'] = dict(outcome='diagnostic', reason='division_by_zero', context=dict(stage=6, path=None))
        with self.assertRaisesRegex(ValueError, 'Diagnostics cannot feed'):
            runner.validate_test(chain)

    def test_quantization_law_keeps_current_status_separate_from_history(self):
        runner = Runner(self.args())
        value = exact('33', '-2', history='approximation-declared')
        increment = exact('1', '-2')['number']
        policy = dict(increment=increment, rounding='half-even')
        expected = success(value, policy=policy)
        with patch.object(runner, 'execute', return_value=self.output(expected)):
            self.assertEqual(runner.quantum(value, increment, 'half-even'), value)
        bad = success(value, 'rounded-for-operands', policy)
        with patch.object(runner, 'execute', return_value=self.output(bad)):
            with self.assertRaisesRegex(ValueError, 'history/metadata mismatch'):
                runner.quantum(value, increment, 'half-even')

    def test_optional_message_and_opaque_transport_extension(self):
        runner = Runner(self.args())
        result = dict(outcome='diagnostic', reason='resource_limit', context=dict(stage=6, path=None))
        test = dict(id='message', fixture=dict(request={}), expected=result)
        with patch.object(runner, 'execute', return_value=self.output(dict(result, message='details'))):
            runner.operation(test)
        output = self.output(success(exact('3')))[:-1] + ',"vendor_extension":1e1000000}'
        with patch.object(runner, 'execute', return_value=output):
            runner.invoke('extension', dict(request=request('add', exact('1'), exact('2'))), {})

    def test_artifact_drift_and_stable_relabel_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            args = self.args()
            lane = Path(folder) / 'lane'
            shutil.copytree(args.manifest.parent, lane)
            args.manifest = lane / args.manifest.name
            runner = Runner(args)
            suite = lane / runner.manifest['suites'][0]['file']
            suite.write_text(suite.read_text() + '\n')
            report = runner.run(check_only=True)
            self.assertEqual(report['status'], 'failed')
            self.assertTrue(any(x['id'] == 'artifact-integrity' for x in report['failures']))
            data = json.loads(args.manifest.read_text())
            data['meta']['conformance']['stable'] = True
            args.manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'mutable working targets only'):
                Runner(args)

    def test_real_execute_reads_utf8_without_shell_and_checks_output_cap(self):
        runner = Runner(self.args())
        result = success(exact('3'))
        output = self.output(result)
        runner.args.sut = shlex.join([sys.executable, '-c', 'import sys; sys.stdin.read(); sys.stdout.write(' + repr(output) + ')'])
        actual = runner.invoke('child', dict(request=request('add', exact('1'), exact('2'))), {})
        self.assertEqual(actual, result)
        runner.args.sut = shlex.join([sys.executable, '-c', "import sys; sys.stdout.write('x'*65)"])
        with patch('run_aeonic_rational_arithmetic.MAX_PROTOCOL_BYTES', 64):
            with self.assertRaisesRegex(ValueError, 'protocol output exceeds'):
                runner.execute({})

    def test_law_group_runs_through_controlled_exact_oracle(self):
        # This is a tooling test double, not a shipped implementation/adapter or
        # an implementation conformance result. Its floor-grid reference differs
        # from the contract's absolute-ratio rounding recipe.
        runner = Runner(self.args())
        runner.tests = [test for test in runner.tests if test.get('kind') == 'laws']
        def numeric(bundle):
            n = bundle['number']
            if n['category'] == 'finiteNumber':
                return Fraction(n['value'])
            return Fraction(int(n['coefficient']), int(n.get('denominator', '1'))) * Fraction(10)**int(n['exponent'])
        def derived(value, history):
            c, d = value.numerator, value.denominator
            if c == 0:
                return exact('0', history=history)
            a = b = 0
            while d % 2 == 0:
                d //= 2; a += 1
            while d % 5 == 0:
                d //= 5; b += 1
            t = max(a, b)
            c *= 2**(t-a) * 5**(t-b); e = -t
            while c % 10 == 0:
                c //= 10; e += 1
            return exact(str(c), str(e), None if d == 1 else str(d), history)
        def oracle(envelope):
            req = envelope['fixture']['request']; data = req['input']; op = req['operation']
            if op != 'quantize':
                left, right = numeric(data['left']), numeric(data['right'])
                value = {'add': lambda: left+right, 'subtract': lambda: left-right,
                         'multiply': lambda: left*right, 'divide': lambda: left/right}[op]()
                history = 'approximation-declared' if 'approximation-declared' in {
                    data['left'].get('history', 'none-declared'), data['right'].get('history', 'none-declared')} else 'none-declared'
                return self.output(success(derived(value, history)))
            value = numeric(data['value']); policy = data['policy']
            h = numeric(dict(number=policy['increment'])); ratio = value/h
            low = ratio.numerator // ratio.denominator; high = low+1; mode = policy['rounding']
            if ratio.denominator == 1:
                selected = low
            elif mode == 'floor': selected = low
            elif mode == 'ceiling': selected = high
            elif mode == 'toward-zero': selected = low if ratio > 0 else high
            elif mode == 'away-from-zero': selected = high if ratio > 0 else low
            else:
                l, r = ratio-low, high-ratio
                if l != r: selected = low if l < r else high
                elif mode == 'half-even': selected = low if low % 2 == 0 else high
                elif mode == 'half-away-from-zero': selected = max((low, high), key=abs)
                else: selected = min((low, high), key=abs)
            result = selected*h; changed = result != value
            history = 'approximation-declared' if changed or data['value']['history'] == 'approximation-declared' else 'none-declared'
            return self.output(success(derived(result, history), 'rounded-for-operands' if changed else 'exact-for-operands', policy))
        with patch.object(runner, 'execute', side_effect=oracle):
            report = runner.run()
        self.assertEqual(report['status'], 'passed', report['failures'])
        self.assertGreater(report['sut_executions'], 100)
        self.assertFalse(report['stable_conformance_claim'])


if __name__ == '__main__':
    unittest.main()
