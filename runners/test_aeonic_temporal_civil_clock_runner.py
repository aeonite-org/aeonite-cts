"""Civil-clock assertion sensitivity and admission controls, not SUT conformance."""
import argparse
import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from run_aeonic_arithmetic import encode, RawNumber
from run_aeonic_temporal_civil_clock import ROOT, LANE, Runner
from temporal_civil_clock_checks import (LIMITS, PROFILE, compact_bytes, coordinate, coverage,
    format_coordinate, positive_cost, workspace, relation_labels, template, decimal_properties)


class CivilClockRunnerTests(unittest.TestCase):
    def args(self, selection='all'):
        return argparse.Namespace(manifest=ROOT/'cts/aeonic-temporal-civil-clock/v1/aeonic-temporal-civil-clock-cts.v1.next.json',
            specs_root=Path(os.environ.get('AEONIC_CLOCK_SPECS_ROOT', ROOT.parent/'aeonite-specs')),
            sut='unused-fixture-provider', cwd=ROOT, timeout=10, capability_set=selection)

    def runner(self): return Runner(self.args())

    def operation(self, r, id): return next(t for t in r.tests if t['id'] == id)

    def output(self, value, **extension):
        ok = value['outcome'] == 'value'
        return json.dumps(dict(ok=ok, warnings=[], errors=[] if ok else [dict(code=value['reason'], path=None, span=None, phase=None)], result=value, **extension))

    def assert_mutations(self, ident, mutations):
        r = self.runner(); test = self.operation(r, ident)
        with patch.object(r, 'execute', return_value=self.output(test['expected'])): r.operation(test)
        for change in mutations:
            actual = copy.deepcopy(test['expected']); change(actual)
            with patch.object(r, 'execute', return_value=self.output(actual)):
                with self.assertRaises(Exception): r.operation(test)

    def test_complete_selections_are_artifact_checks_without_stability(self):
        for choice in ['relations', 'arithmetic', 'all']:
            r=Runner(self.args(choice))
            with patch.object(r,'execute') as execute: report=r.run(True)
            execute.assert_not_called(); self.assertEqual(report['status'],'artifacts-validated')
            self.assertFalse(report['semantic_execution']);self.assertFalse(report['stable_conformance_claim'])
            self.assertEqual(report['sut_executions'],0)
            if choice != 'all': self.assertGreater(report['excluded_unclaimed_capability_cases'],0)

    def test_relative_day_and_exact_fraction_are_asserted(self):
        self.assert_mutations('positive-midnight-carry', [lambda x:x['value']['temporal']['pieces'][0]['at'].update(day='0'), lambda x:x['value']['temporal']['pieces'][0]['at'].update(time='01:30:00.1')])

    def test_endpoint_membership_and_piece_gaps_are_asserted(self):
        self.assert_mutations('minute-crosses-midnight-continuously', [lambda x:x['value']['temporal']['pieces'][0].update(includeEnd=True), lambda x:x['value']['temporal']['pieces'][0].update(includeStart=False)])
        self.assert_mutations('two-points-keep-gap', [lambda x:x['value']['temporal']['pieces'].pop()])

    def test_history_origin_and_effective_policy_are_asserted(self):
        self.assert_mutations('marked-zero-amount-propagates', [lambda x:x['value'].update(history='none-declared'), lambda x:x['value'].update(originClockForm='undeclared'), lambda x:x['metadata'].update(evaluation='rounded-for-operands'), lambda x:x['metadata']['effectivePolicy'].update(profile='unavailable')])

    def test_symbols_and_operand_metadata_are_asserted(self):
        self.assert_mutations('minute-contains-point', [lambda x:x['value'].update(value='overlaps'), lambda x:x['metadata']['operandHistory'].update(left='approximation-declared'), lambda x:x['metadata']['operandOrigin'].update(right='hour')])

    def test_diagnostic_reason_stage_and_path_are_asserted(self):
        self.assert_mutations('off-grid-minute-does-not-step', [lambda x:x.update(reason='unrepresentable_result'), lambda x:x['context'].update(stage=7), lambda x:x['context'].update(path=None)])

    def test_closed_envelopes_and_optional_message(self):
        r=self.runner();test=self.operation(r,'off-grid-minute-does-not-step');actual=copy.deepcopy(test['expected']);actual['message']='explanation'
        with patch.object(r,'execute',return_value=self.output(actual)):r.operation(test)
        for key in ['value','metadata','unknown']:
            bad=copy.deepcopy(actual);bad[key]=None
            with self.assertRaises(Exception):r.validate_result(bad,LIMITS)
        bad=copy.deepcopy(actual);bad['message']='bad'+chr(0xD800)
        with self.assertRaises(Exception):r.validate_result(bad,LIMITS)
        actual['context']['path']='/bad~x'
        with self.assertRaises(ValueError):r.validate_result(actual,LIMITS)

    def test_protocol_consistency_and_outer_extensions(self):
        r=self.runner();test=self.operation(r,'positive-midnight-carry')
        out=json.loads(self.output(test['expected']));out['ok']=False
        with patch.object(r,'execute',return_value=json.dumps(out)):
            with self.assertRaises(ValueError):r.operation(test)
        out=json.loads(self.output(test['expected']));out['warnings']=['surprise']
        with patch.object(r,'execute',return_value=json.dumps(out)):
            with self.assertRaises(ValueError):r.operation(test)
        with patch.object(r,'execute',return_value=self.output(test['expected'],extension=True)):r.operation(test)

    def test_fixture_admission_rejects_wrong_arithmetic_before_execution(self):
        r=self.runner();test=copy.deepcopy(self.operation(r,'positive-midnight-carry'))
        test['expected']['value']['temporal']['pieces'][0]['at']['day']='2'
        with self.assertRaisesRegex(ValueError,'expected coverage'):r.validate_test(test)

    def test_declared_form_and_output_spelling_are_checked(self):
        r=self.runner();test=copy.deepcopy(self.operation(r,'materialize-second-trims-fraction'))
        test['expected']['value']['temporal']['value']+='0'
        with self.assertRaisesRegex(ValueError,'noncanonical fraction'):r.validate_test(test)
        test=copy.deepcopy(self.operation(r,'materialize-minute'));test['expected']['value']['temporal']['value']='09:'
        with self.assertRaises(ValueError):r.validate_test(test)

    def test_piece_guards_precede_iteration_at_two_widths(self):
        class Observed(list):
            reads=0
            def __iter__(self):
                for x in super().__iter__():self.reads+=1;yield x
        r=self.runner();base=self.operation(r,'two-points-keep-gap')['expected']
        for n in [32,64]:
            bad=copy.deepcopy(base);raw=Observed(bad['value']['temporal']['pieces']*n);bad['value']['temporal']['pieces']=raw
            with self.assertRaisesRegex(ValueError,'output-piece'):r.validate_result(bad,dict(LIMITS,maxOutputPieces=1))
            self.assertEqual(raw.reads,0)
            raw=Observed(base['value']['temporal']['pieces']*n);bundle=copy.deepcopy(base['value']);bundle['temporal']['pieces']=raw
            with self.assertRaises(ValueError):coverage(bundle,1)
            self.assertEqual(raw.reads,0)

    def test_day_guard_precedes_integer_conversion_at_two_widths(self):
        for n in [64,128]:
            with patch('temporal_civil_clock_checks.decimal_integer') as convert:
                with self.assertRaisesRegex(ValueError,'Day exceeds'):coordinate(dict(day='1'*n,time='00:00:00'),dict(LIMITS,maxRelativeDayDigits=8))
            convert.assert_not_called()

    def test_clock_and_fraction_guards_precede_conversion(self):
        for n in [64,128]:
            with patch('temporal_civil_clock_checks.COORD') as parser:
                with self.assertRaisesRegex(ValueError,'text allowance'):coordinate(dict(day='0',time='x'*n),dict(LIMITS,maxTemporalCharacters=8))
            parser.fullmatch.assert_not_called()
            with patch('temporal_civil_clock_checks.decimal_integer') as convert:
                with self.assertRaisesRegex(ValueError,'Fraction exceeds'):coordinate(dict(day='0',time='00:00:00.'+'1'*n),dict(LIMITS,maxFractionDigits=8))
            convert.assert_not_called()

    def test_matching_guard_precedes_reference_construction(self):
        r=self.runner();q=self.operation(r,'step-hour-forward')['fixture']['request'];spans=[coverage(q['input']['value'],512)]
        with patch('temporal_civil_clock_checks.template') as make:
            with self.assertRaisesRegex(ValueError,'Source matching'):positive_cost(q,spans,dict(LIMITS,maxWork=1))
        make.assert_not_called()
        self.assertEqual(positive_cost(q,spans),(3,2))

    def test_target_guard_precedes_numeric_workspace(self):
        r=self.runner();q=self.operation(r,'step-hour-forward')['fixture']['request'];spans=[coverage(q['input']['value'],512)]
        with patch('temporal_civil_clock_checks.workspace') as work:
            with self.assertRaisesRegex(ValueError,'Target matching'):positive_cost(q,spans,dict(LIMITS,maxIntermediatePieces=1))
        work.assert_not_called()

    def test_compact_workspace_formulas_and_zero_shortcut(self):
        r=self.runner();q=copy.deepcopy(self.operation(r,'positive-midnight-carry')['fixture']['request'])
        self.assertEqual(workspace(q),(7,0))
        q['input']['amount']['number']['value']='1e-1000000'
        with self.assertRaisesRegex(ValueError,'workspace'):workspace(q)
        q['input']['amount']['number']['value']='1e1000000'
        with self.assertRaisesRegex(ValueError,'workspace'):workspace(q)
        q['input']['amount']['number']['value']='0e1000000'
        self.assertEqual(workspace(q,dict(LIMITS,maxWorkspaceDigits=0)),(0,0))
        q['input']['amount']['number']['value']='0e1000001'
        with self.assertRaisesRegex(ValueError,'Authored exponent'):workspace(q)

    def test_negative_floor_and_large_day_roundtrips(self):
        self.assertEqual(format_coordinate(Fraction(-1,2)),dict(day='-1',time='23:59:59.5'))
        for day in ['-10000000000000000000000','0','10000000000000000000000']:
            p=dict(day=day,time='00:00:00.000000000001')
            self.assertEqual(format_coordinate(coordinate(p)),p)

    def test_raised_day_fraction_limits_avoid_python_integer_ceiling(self):
        ceiling=sys.get_int_max_str_digits() if hasattr(sys,'get_int_max_str_digits') else None
        limits=dict(LIMITS,maxRelativeDayDigits=5000,maxTemporalCharacters=5100,maxFractionDigits=5000)
        for n in [4400,5000]:
            p=dict(day='-'+'1'*n,time='00:00:00.'+'1'*n)
            self.assertEqual(format_coordinate(coordinate(p,limits)),p)
        if ceiling is not None:self.assertEqual(sys.get_int_max_str_digits(),ceiling)

    def test_missing_boundary_and_numeric_day_relation(self):
        a=coordinate(dict(day='-1',time='23:59:59'));b=a+1;c=b+1
        gaps=[(a,b,True,False),(b,c,False,True)];point=[(b,b,True,True)]
        self.assertEqual(relation_labels(gaps,point)['relate'],'disjoint')
        self.assertEqual(relation_labels(gaps,point)['compare'],'indeterminate')
        self.assertLess(coordinate(dict(day='2',time='00:00:00')),coordinate(dict(day='10',time='00:00:00')))

    def test_actual_results_feed_chains_without_mutating_fixtures(self):
        r=self.runner();test=next(t for t in r.tests if t.get('kind')=='chain');original=copy.deepcopy(test);seen=[]
        actual=copy.deepcopy(test['steps'][0]['expected']);actual['value']['history']='approximation-declared'
        def operation(step):
            seen.append(copy.deepcopy(step['fixture']['request']))
            return actual if len(seen)==1 else step['expected']
        with patch.object(r,'operation',side_effect=operation):r.chain(test)
        self.assertEqual(seen[1]['input']['value'],actual['value']);self.assertEqual(test,original)

    def test_chain_links_reject_duplicate_targets_and_symbol_sources(self):
        r=self.runner();test=copy.deepcopy(next(t for t in r.tests if t.get('kind')=='chain'))
        test['links'].append(copy.deepcopy(test['links'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate chain'):r.validate_test(test)
        test=copy.deepcopy(next(t for t in r.tests if t.get('kind')=='chain'));test['steps'][0]['expected']['value']=dict(category='symbol',value='equal')
        with self.assertRaisesRegex(ValueError,'Only temporal'):r.validate_test(test)

    def test_raw_and_structured_tokens_survive_transport_encoding(self):
        r=self.runner()
        for token in ['-0','9007199254740993','1e1000000','1e-1000000']:
            test=self.operation(r,'structured-token-'+token);raw=test['fixture']['request']['input']['left']['temporal']['payload']
            self.assertIsInstance(raw,RawNumber);self.assertEqual(raw.text,token)
            sent=[]
            with patch.object(r,'execute',side_effect=lambda envelope:(sent.append(encode(envelope)) or self.output(test['expected']))):r.operation(test)
            self.assertIn('"payload":'+token,sent[0])

    def test_invalid_trusted_limits_are_harness_errors(self):
        r=self.runner()
        for limits in [None,[],True,{'maxWork':True},{'maxWork':-1},{'maxWork':0.5},{'maxWork':9007199254740992},{'typo':1}]:
            with self.assertRaises(Exception):r.binding_schema.validate(dict(lane=LANE,case_id='bad',fixture=dict(request={}),policy=dict(resourceLimits=limits)))

    def test_bounded_bytes_and_multibyte_control(self):
        for n in [64,128]:
            with patch('temporal_civil_date_checks.json.dumps') as dumps:
                with self.assertRaises(ValueError):compact_bytes('x'*n,8)
            dumps.assert_not_called()
        obj=dict(text='é😀',escaped='"\\\n');n=len(json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode())
        self.assertEqual(compact_bytes(obj,n),n)
        with self.assertRaises(ValueError):compact_bytes(obj,n-1)

    def test_relabeling_mutable_as_stable_and_manifest_edits_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.args();lane=Path(folder)/'lane';shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            original=json.loads(args.manifest.read_text());original['meta']['conformance']=dict(surface='civil-clock',stable=True)
            args.manifest.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError,'Expected mutable next'):Runner(args)
        r=self.runner()
        with patch.object(r,'execute',return_value=self.output(dict(outcome='diagnostic',reason='invalid_operand',context=dict(stage=4,path=None)))):report=r.run()
        self.assertEqual(report['status'],'failed');self.assertFalse(report['stable_conformance_claim'])

    def test_pinned_artifacts_checked_before_and_after_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.args();lane=Path(folder)/'lane';shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            r=Runner(args);suite=lane/r.manifest['suites'][0]['file'];suite.write_text(suite.read_text()+'\n')
            self.assertEqual(r.run(True)['status'],'failed')
            with self.assertRaisesRegex(ValueError,'Artifact digest'):Runner(args)

    def test_cli_check_defaults_to_frozen_lane_without_semantic_claim(self):
        child=subprocess.run([sys.executable,str(ROOT/'runners/run_aeonic_temporal_civil_clock.py'),'--specs-root',str(self.args().specs_root),'--check'],text=True,capture_output=True,timeout=20)
        self.assertEqual(child.returncode,0,child.stderr+child.stdout);report=json.loads(child.stdout)
        self.assertFalse(report['semantic_execution']);self.assertFalse(report['stable_conformance_claim'])
        self.assertEqual(report['target_status'], 'immutable-local')
        self.assertTrue(report['target'].endswith('0.1'))

    def test_stdio_transport_uses_complete_limits_and_preserves_raw_tokens(self):
        import shlex
        r=self.runner();test=self.operation(r,'structured-token--0')
        with tempfile.TemporaryDirectory() as folder:
            provider=Path(folder)/'provider.py'
            provider.write_text('import json,sys\nraw=sys.stdin.read()\nassert \'"payload":-0\' in raw\nx=json.loads(raw)\nassert len(x["policy"]["resourceLimits"]) == 16\nprint('+repr(self.output(test['expected']))+')\n')
            r.args.sut=shlex.join([sys.executable,str(provider)])
            r.operation(test)
            provider.write_text('import sys\nprint("bad fixture",file=sys.stderr)\nsys.exit(2)\n')
            with self.assertRaisesRegex(ValueError,'harness failure'):r.operation(test)

    def test_full_fixture_provider_replay_checks_transport_without_conformance(self):
        r=self.runner();test_by_id={}
        for test in r.tests:
            if test.get('kind','operation')=='operation':test_by_id[test['id']]=test['expected']
            elif test['kind']=='chain':
                for i,step in enumerate(test['steps']):test_by_id[test['id']+'/'+str(i)]=step['expected']
        # CommonRunner names chain calls with /step-N; law calls use exact relation oracle.
        def provider(envelope):
            ident=envelope['case_id']
            if ident in test_by_id:return self.output(test_by_id[ident])
            for test in r.tests:
                if test.get('kind')=='chain' and ident.startswith(test['id']+'/step-'):
                    return self.output(test['steps'][int(ident.rsplit('-',1)[1])]['expected'])
            q=envelope['fixture']['request'];data=q['input']
            from temporal_civil_clock_checks import relation_result
            spans=[coverage(data[s],512) for s in ['left','right']]
            return self.output(relation_result(q['operation'],data['left'],data['right'],relation_labels(*spans)[q['operation']]))
        with patch.object(r,'execute',side_effect=provider):report=r.run()
        self.assertEqual(report['status'],'passed',report['failures'])
        self.assertEqual(report['sut_executions'],378);self.assertFalse(report['stable_conformance_claim'])


    def test_retained_runs_bind_frozen_identity_and_complete_capabilities(self):
        root=ROOT/'docs/conformance/civil-clock-snapshot-0.1'
        verification=json.loads((root/'verification.json').read_text())
        r=Runner(self.frozen_args())
        self.assertEqual(verification['target'],r.manifest['meta']['snapshot_id'])
        self.assertEqual(verification['manifest_sha256'],r.artifacts[r.manifest_path])
        self.assertEqual(set(verification['implementations']),{'javascript','python39','python314'})
        for implementation in verification['implementations'].values():
            self.assertEqual(set(implementation['frozen_reports']),{'all','relations','arithmetic'})
            for capability,path in implementation['frozen_reports'].items():
                report=json.loads((root/path).read_text())
                self.assertEqual(report['status'],'passed');self.assertEqual(report['failures'],[])
                self.assertTrue(report['semantic_execution']);self.assertTrue(report['stable_conformance_claim'])
                self.assertEqual(report['target_status'],'immutable-local')
                self.assertEqual(report['target'],verification['target'])
                self.assertEqual(report['capabilities'],['arithmetic','relations'] if capability=='all' else [capability])
                self.assertEqual(report['sut_executions'],{'all':378,'relations':261,'arithmetic':116}[capability])
                self.assertEqual(report['assertions'],{'all':420,'relations':303,'arithmetic':116}[capability])
                for name in ['manifest_sha256','runner_sha256','specification_source_sha256','specification_schema_sha256']:
                    self.assertEqual(report[name],verification[name])
                self.assertEqual(report['resource_limits'],verification['resource_limits'])
                self.assertEqual(report['helper_hashes'],verification['helpers'])
            mutable=json.loads((root/implementation['mutable_report']).read_text())
            self.assertEqual(mutable['status'],'passed');self.assertEqual(mutable['target_status'],'mutable-working')
            self.assertTrue(mutable['semantic_execution']);self.assertFalse(mutable['stable_conformance_claim'])

    def frozen_args(self, selection='all'):
        args=self.args(selection)
        args.manifest=args.manifest.with_name('aeonic-temporal-civil-clock-cts.v1.snapshot-0.1.json')
        return args

    def test_frozen_checks_never_claim_semantic_conformance(self):
        for choice in ['relations','arithmetic','all']:
            r=Runner(self.frozen_args(choice))
            with patch.object(r,'execute') as execute:report=r.run(check_only=True)
            execute.assert_not_called()
            self.assertTrue(r.immutable)
            self.assertEqual(report['target_status'],'immutable-local')
            self.assertEqual(report['target'],'aeonic-temporal-civil-clock-cts-v1-snapshot-0.1')
            self.assertFalse(report['stable_conformance_claim']);self.assertFalse(report['semantic_execution'])
            self.assertEqual(report['sut_executions'],0)
            self.assertEqual(r.manifest['meta']['spec_snapshot_id'],'aeonic-temporal-civil-clock-specs-v1-snapshot-0.1')

    def test_frozen_reencoding_edits_exclusions_and_next_relabel_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.frozen_args();lane=Path(folder)/'lane'
            shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            original=json.loads(args.manifest.read_text())
            variants=[copy.deepcopy(original) for _ in range(5)]
            variants[1]['meta']['description']='edited'
            variants[2]['meta']['snapshot_id']='aeonic-temporal-civil-clock-cts-v1-snapshot-9.9'
            variants[3]['exclude_cases']=['one']
            variants[4]=json.loads((lane/'aeonic-temporal-civil-clock-cts.v1.next.json').read_text())
            variants[4]['meta']['conformance']=original['meta']['conformance']
            for variant in variants:
                args.manifest.write_text(json.dumps(variant))
                with self.assertRaisesRegex(ValueError,'Unrecognized or modified immutable'):Runner(args)

    def test_frozen_wrong_responses_cannot_claim_conformance(self):
        r=Runner(self.frozen_args())
        with patch.object(r,'execute',return_value=self.output(dict(outcome='diagnostic',reason='invalid_operand',context=dict(stage=4,path=None)))):
            report=r.run()
        self.assertEqual(report['status'],'failed');self.assertTrue(report['semantic_execution'])
        self.assertFalse(report['stable_conformance_claim']);self.assertGreater(len(report['failures']),0)

    def test_frozen_artifacts_are_isolated_and_rechecked_after_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.frozen_args();lane=Path(folder)/'lane'
            shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            # Evolving working fixtures cannot change the frozen copy.
            (lane/'suites/01-arithmetic.json').write_text('{}')
            r=Runner(args);self.assertEqual(r.run(True)['status'],'artifacts-validated')
            suite=lane/r.manifest['suites'][0]['file'];suite.write_text(suite.read_text()+'\n')
            report=r.run(True)
            self.assertEqual(report['status'],'failed');self.assertFalse(report['stable_conformance_claim'])
            self.assertTrue(any(f['id']=='artifact-integrity' for f in report['failures']))
            with self.assertRaisesRegex(ValueError,'Artifact digest mismatch'):Runner(args)

    def test_default_cli_selects_frozen_and_explicit_next_remains_mutable(self):
        for manifest,target in [(None,'0.1'),(self.args().manifest,'0.2')]:
            command=[sys.executable,str(ROOT/'runners/run_aeonic_temporal_civil_clock.py'),'--specs-root',str(self.args().specs_root),'--check']
            if manifest is not None:command+=['--manifest',str(manifest)]
            child=subprocess.run(command,text=True,capture_output=True,timeout=20)
            self.assertEqual(child.returncode,0,child.stderr+child.stdout)
            report=json.loads(child.stdout);self.assertTrue(report['target'].endswith(target))
            self.assertFalse(report['stable_conformance_claim']);self.assertFalse(report['semantic_execution'])
            self.assertEqual(report['sut_executions'],0)


if __name__=='__main__':unittest.main()
