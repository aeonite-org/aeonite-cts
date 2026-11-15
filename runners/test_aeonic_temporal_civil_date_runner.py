import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from run_aeonic_arithmetic import encode
from run_aeonic_temporal_civil_date import ROOT, Runner
from temporal_civil_date_checks import (LIMITS, PROFILE, compact_bytes,
    decode_artifact, positive_work, relation_labels)


class TemporalRunnerTests(unittest.TestCase):
    def args(self, selection='all'):
        return argparse.Namespace(
            manifest=ROOT/'cts/aeonic-temporal-civil-date/v1/aeonic-temporal-civil-date-cts.v1.next.json',
            specs_root=Path(os.environ.get('AEONIC_TEMPORAL_SPECS_ROOT',
                            os.environ.get('AEONIC_SPECS_ROOT', ROOT.parent/'aeonite-specs'))),
            sut=sys.executable, cwd=ROOT, timeout=10, capability_set=selection)

    def output(self, value, **extensions):
        ok=value['outcome']=='value'
        return json.dumps(dict(ok=ok,warnings=[],errors=[] if ok else [dict(code=value['reason'],path=None,span=None,phase=None)],result=value,**extensions))

    def first(self, runner, outcome='value'):
        return next(t for t in runner.tests if t.get('kind','operation')=='operation' and t['expected']['outcome']==outcome)

    def test_artifact_only_checks_all_three_complete_selections(self):
        reports={}
        for choice in ['relations','calendar','all']:
            runner=Runner(self.args(choice))
            with patch.object(runner,'execute') as execute:
                reports[choice]=runner.run(check_only=True)
            execute.assert_not_called()
            self.assertEqual(reports[choice]['status'],'artifacts-validated')
            self.assertEqual(reports[choice]['sut_executions'],0)
            self.assertFalse(reports[choice]['stable_conformance_claim'])
            self.assertFalse(reports[choice]['semantic_execution'])
        self.assertEqual(reports['all']['operation_cases'],181)
        self.assertEqual(reports['all']['chains'],2)
        self.assertEqual(reports['all']['law_groups'],1)
        self.assertEqual(reports['relations']['chains'],0)
        self.assertEqual(reports['calendar']['law_groups'],0)
        self.assertGreater(reports['relations']['excluded_unclaimed_capability_cases'],0)

    def test_wrong_values_metadata_history_policy_and_paths_fail(self):
        runner=Runner(self.args());positive=self.first(runner);negative=self.first(runner,'diagnostic')
        variants=[]
        v=copy.deepcopy(positive['expected']);v['value']['temporal']['ranges'][0]['end']='2024-03-28';variants.append((positive,v))
        v=copy.deepcopy(positive['expected']);v['value']['history']='none-declared';variants.append((positive,v))
        v=copy.deepcopy(positive['expected']);v['metadata']['effectivePolicy']['count']='2';variants.append((positive,v))
        v=copy.deepcopy(negative['expected']);v['context']['path']='/wrong';variants.append((negative,v))
        for test,actual in variants:
            with self.subTest(actual=actual),patch.object(runner,'execute',return_value=self.output(actual)):
                with self.assertRaises(ValueError):runner.operation(test)
        with patch.object(runner,'execute',return_value=self.output(positive['expected'])):
            runner.operation(positive)

    def test_closed_results_no_diagnostic_value_and_intrinsic_date_checks(self):
        runner=Runner(self.args());base=copy.deepcopy(self.first(runner)['expected'])
        for mutate in [lambda v:v.update(extra=True),
                       lambda v:v['value']['temporal']['ranges'][0].update(end='2025-02-29'),
                       lambda v:v['value']['temporal']['ranges'].append(dict(start='2024-03-30',end='2024-03-31'))]:
            v=copy.deepcopy(base);mutate(v)
            with self.assertRaises(Exception):runner.validate_result(v,LIMITS)
        v=dict(outcome='diagnostic',reason='resource_limit',context=dict(stage=6,path=None),value=None)
        with self.assertRaises(Exception):runner.validate_result(v,LIMITS)
        v.pop('value');v['message']='bad'+chr(0xD800)
        with self.assertRaises(Exception):runner.validate_result(v,LIMITS)

    def test_range_allowance_precedes_all_range_iteration_at_two_widths(self):
        runner=Runner(self.args());base=copy.deepcopy(self.first(runner)['expected'])
        class Observed(list):
            reads=0
            def __iter__(self):
                for item in super().__iter__():
                    self.reads+=1;yield item
        for n in [32,64]:
            v=copy.deepcopy(base);ranges=Observed([dict(start='2024-03-01',end='2024-03-02')]*n)
            v['value']['temporal']['ranges']=ranges
            with self.assertRaisesRegex(ValueError,'output-range allowance'):
                runner.validate_result(v,dict(LIMITS,maxOutputRanges=1))
            self.assertEqual(ranges.reads,0)

    def test_bounded_byte_measurement_and_unicode_control(self):
        class Observed(list):
            reads=0
            def __iter__(self):
                for item in super().__iter__():
                    self.reads+=1;yield item
        counts=[]
        for n in [64,128]:
            value=Observed(['1234']*n)
            with self.assertRaisesRegex(ValueError,'byte allowance'):compact_bytes(value,8)
            counts.append(value.reads)
        self.assertEqual(counts,[2,2])
        for n in [64,128]:
            with patch('temporal_civil_date_checks.json.dumps') as dumps:
                with self.assertRaises(ValueError):compact_bytes('x'*n,8)
            dumps.assert_not_called()
        control=dict(a='é😀',b=['quote"','\n'])
        exact=len(json.dumps(control,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        self.assertEqual(compact_bytes(control,exact),exact)
        with self.assertRaises(ValueError):compact_bytes(control,exact-1)

    def test_large_count_lexical_guard_precedes_integer_conversion(self):
        logical=dict(operation='shift',input=dict(policy=dict(unit='month',count='1')))
        spans=[[('2024-01-01','2024-12-31')]]
        self.assertEqual(positive_work(logical,spans),12)
        for n in [64,128]:
            logical['input']['policy']['count']='9'*n
            with patch('temporal_civil_date_checks.int',create=True) as convert:
                with self.assertRaisesRegex(ValueError,'out-of-domain displacement'):positive_work(logical,spans)
            convert.assert_not_called()

    def test_logical_integer_and_float_tokens_survive_artifact_decoding(self):
        raw='{"meta":{"limit":32},"tests":[{"fixture":{"request":{"a":-0,"b":1e400,"c":1e-400}}}]}'
        value=decode_artifact(raw)
        self.assertEqual(value['meta']['limit'],32)
        logical=value['tests'][0]['fixture']['request']
        self.assertEqual(encode(logical),'{"a":-0,"b":1e400,"c":1e-400}')
        value=decode_artifact('{"tests":[{"steps":[{"request":{"a":-0}}]}]}')
        self.assertEqual(encode(value['tests'][0]['steps'][0]['request']),'{"a":-0}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):decode_artifact('{"x":1,"x":2}')

    def test_malformed_trusted_limits_do_not_invoke(self):
        runner=Runner(self.args());fixture=self.first(runner)['fixture']
        for limits in [None,[],dict(unknown=1),dict(maxCalendarWork=True),dict(maxCalendarWork=-1)]:
            with patch.object(runner,'execute') as execute:
                with self.assertRaises(Exception):runner.invoke('bad',fixture,dict(resourceLimits=limits))
            execute.assert_not_called()

    def test_actual_chain_bundles_and_history_are_reused(self):
        runner=Runner(self.args());chain=copy.deepcopy(next(t for t in runner.tests if t.get('kind')=='chain'))
        chain['steps'][1]['request']['input']['value']=dict(temporal=dict(category='civilDate',value='0001-01-01'))
        with patch.object(runner,'execute',side_effect=[self.output(s['expected']) for s in chain['steps']]) as execute:
            runner.chain(chain)
        second=execute.call_args_list[1].args[0]['fixture']['request']['input']['value']
        self.assertEqual(second,chain['steps'][0]['expected']['value'])

    def test_invalid_links_diagnostic_and_symbol_donors_are_rejected(self):
        runner=Runner(self.args());base=next(t for t in runner.tests if t.get('kind')=='chain')
        chain=copy.deepcopy(base);chain['links'][0]['fromStep']=True
        with self.assertRaisesRegex(ValueError,'chain order'):runner.validate_test(chain)
        for value in [dict(outcome='diagnostic'),dict(outcome='value',value=dict(category='symbol',value='equal'))]:
            chain=copy.deepcopy(base);chain['steps'][0]['expected']=value
            with self.assertRaisesRegex(ValueError,'Only temporal'):runner.validate_test(chain)

    def test_successful_fixture_cannot_clear_history_or_exceed_work(self):
        runner=Runner(self.args());test=copy.deepcopy(self.first(runner))
        test['expected']['value']['history']='none-declared'
        with self.assertRaisesRegex(ValueError,'history/origin'):runner.validate_test(test)
        test=copy.deepcopy(self.first(runner));test['policy']=dict(resourceLimits=dict(maxCalendarWork=0))
        with self.assertRaisesRegex(ValueError,'calendar-work'):runner.validate_test(test)

    def test_relation_oracle_is_exhaustive_for_small_nonempty_sets(self):
        from itertools import combinations
        sets=[set(c) for n in range(1,5) for c in combinations(range(1,5),n)]
        # Singleton canonical intervals separated by one day avoid adjacent pairs.
        for a in sets:
            for b in sets:
                spans=lambda x:[('2024-03-%02d'%(i*2),'2024-03-%02d'%(i*2)) for i in sorted(x)]
                actual=relation_labels(spans(a),spans(b))
                self.assertEqual(actual['equal'],'equal' if a==b else 'notEqual')
                expected='equal' if a==b else 'contains' if b<a else 'containedBy' if a<b else 'overlaps' if a&b else 'disjoint'
                self.assertEqual(actual['relate'],expected)
                chrono='equal' if a==b else 'before' if max(a)<min(b) else 'after' if max(b)<min(a) else 'indeterminate'
                self.assertEqual(actual['compare'],chrono)

    def test_optional_message_and_transport_extensions_remain_opaque(self):
        runner=Runner(self.args());test=copy.deepcopy(self.first(runner,'diagnostic'))
        test['expected']['message']='ignored expected explanation'
        actual=dict(test['expected'],message='different explanation')
        with patch.object(runner,'execute',return_value=self.output(actual,vendor_extension={'opaque':True})):
            runner.operation(test)

    def test_protocol_cap_uses_bounded_transport_before_decoding(self):
        runner=Runner(self.args());runner.args.sut=shlex.join([sys.executable,'-c','print("x"*129,end="")'])
        with patch('run_aeonic_rational_arithmetic.MAX_PROTOCOL_BYTES',128):
            with self.assertRaisesRegex(ValueError,'harness cap'):runner.execute({})

    def test_law_case_identity_must_be_transportable(self):
        runner=Runner(self.args());test=copy.deepcopy(next(t for t in runner.tests if t.get('kind')=='laws'))
        test['id']='bad'+chr(0xD800)
        with self.assertRaisesRegex(ValueError,'Unicode-scalar'):runner.validate_test(test)

    def test_malformed_diagnostic_pointer_rejects_before_schema(self):
        runner=Runner(self.args())
        for n in [10,14]:
            bad=dict(outcome='diagnostic',reason='invalid_operand',context=dict(stage=4,path='/'*n+'~2'))
            with patch.object(runner,'result_schema',wraps=runner.result_schema) as schema:
                with self.assertRaisesRegex(ValueError,'JSON Pointer escape'):
                    runner.validate_result(bad,dict(LIMITS,maxResultBytes=0))
                schema.validate.assert_not_called()
            good=copy.deepcopy(bad);good['context']['path']='/'*n+'~02'
            runner.validate_result(good,dict(LIMITS,maxResultBytes=0))

    def test_stable_or_excluding_manifest_cannot_validate(self):
        runner=Runner(self.args())
        bad=copy.deepcopy(runner.manifest);bad['meta']['conformance']['stable']=True
        with patch.object(Runner,'read',return_value=bad):
            with self.assertRaisesRegex(ValueError,'Expected mutable next'):Runner(self.args())
        bad=copy.deepcopy(runner.manifest);bad['exclude_cases']=['something']
        with patch.object(Runner,'read',return_value=bad):
            with self.assertRaisesRegex(ValueError,'Unknown manifest'):Runner(self.args())

    def test_post_run_artifact_mutation_prevents_pass(self):
        runner=Runner(self.args());test=self.first(runner);runner.tests=[test]
        with tempfile.TemporaryDirectory() as temp:
            artifact=Path(temp)/'owned.txt';artifact.write_text('before')
            runner.artifacts[artifact]=hashlib.sha256(artifact.read_bytes()).hexdigest()
            def changed(envelope):
                artifact.write_text('after');return self.output(test['expected'])
            with patch.object(runner,'execute',side_effect=changed):report=runner.run()
        self.assertEqual(report['status'],'failed')
        self.assertTrue(any(f['id']=='artifact-integrity' for f in report['failures']))

    def test_cli_assertion_sensitivity_has_passing_and_nonzero_controls(self):
        """Replay-only SUT controls verify the runner, not temporal conformance."""
        runner=Runner(self.args())
        chosen=[]
        for op in ['equal','compare','relate','shift','step','materialize']:
            chosen.append(copy.deepcopy(next(t for t in runner.tests if t.get('kind','operation')=='operation'
                               and t['expected']['outcome']=='value' and t['fixture'].get('request',{}).get('operation')==op)))
        chosen.append(copy.deepcopy(self.first(runner,'diagnostic')))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);suite=root/'suite.json';suite.write_text(json.dumps(dict(id='sensitivity',tests=chosen)))
            shutil.copy2(runner.manifest_path.parent/'binding.schema.json',root/'binding.schema.json')
            manifest=copy.deepcopy(runner.manifest)
            manifest['suites']=[dict(id='sensitivity',file='suite.json',content_sha256=hashlib.sha256(suite.read_bytes()).hexdigest())]
            path=root/'manifest.json';path.write_text(json.dumps(manifest))
            sut=root/'sut.py';sut.write_text('import json,sys\nfrom pathlib import Path\ne=json.load(sys.stdin)\nr=json.loads(Path(__file__).with_name("responses.json").read_text())[e["case_id"]]\nok=r["outcome"]=="value"\nprint(json.dumps(dict(ok=ok,result=r,warnings=[],errors=[] if ok else [dict(code=r["reason"],path=None,span=None,phase=None)])))\n')
            responses={t['id']:t['expected'] for t in chosen}
            command=[sys.executable,str(ROOT/'runners/run_aeonic_temporal_civil_date.py'),'--manifest',str(path),
                     '--specs-root',str(runner.args.specs_root),'--capability-set','all','--sut',shlex.join([sys.executable,str(sut)])]
            for variant in ['control','wrong-symbol','wrong-history','wrong-policy','wrong-path']:
                data=copy.deepcopy(responses)
                if variant=='wrong-symbol':data[chosen[0]['id']]['value']['value']='notEqual'
                if variant=='wrong-history':data[chosen[0]['id']]['metadata']['operandHistory']['left']='clamping-declared'
                if variant=='wrong-policy':data[chosen[3]['id']]['metadata']['effectivePolicy']['count']='2'
                if variant=='wrong-path':data[chosen[6]['id']]['context']['path']='/wrong'
                (root/'responses.json').write_text(json.dumps(data))
                result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=30)
                with self.subTest(variant=variant):
                    self.assertEqual(result.returncode,0 if variant=='control' else 1,result.stderr+result.stdout)
                    report=json.loads(result.stdout);self.assertFalse(report['stable_conformance_claim'])
                    self.assertEqual(len(report['failures']),0 if variant=='control' else 1)

    def frozen_args(self, selection='all'):
        args=self.args(selection)
        args.manifest=args.manifest.with_name('aeonic-temporal-civil-date-cts.v1.snapshot-0.1.json')
        return args

    def test_frozen_checks_never_claim_semantic_conformance(self):
        for choice in ['relations','calendar','all']:
            runner=Runner(self.frozen_args(choice))
            with patch.object(runner,'execute') as execute:report=runner.run(check_only=True)
            execute.assert_not_called()
            self.assertTrue(runner.immutable)
            self.assertEqual(report['target_status'],'immutable-local')
            self.assertEqual(report['target'],'aeonic-temporal-civil-date-cts-v1-snapshot-0.1')
            self.assertFalse(report['stable_conformance_claim'])
            self.assertFalse(report['semantic_execution'])
            self.assertEqual(report['sut_executions'],0)

    def test_frozen_reencoding_edits_exclusions_and_next_relabel_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.frozen_args();lane=Path(folder)/'lane'
            shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            original=json.loads(args.manifest.read_text())
            variants=[copy.deepcopy(original) for _ in range(5)]
            variants[1]['meta']['description']='edited'
            variants[2]['meta']['snapshot_id']='aeonic-temporal-civil-date-cts-v1-snapshot-9.9'
            variants[3]['exclude_cases']=['one']
            variants[4]=json.loads((lane/'aeonic-temporal-civil-date-cts.v1.next.json').read_text())
            variants[4]['meta']['conformance']=original['meta']['conformance']
            for variant in variants:
                args.manifest.write_text(json.dumps(variant))
                with self.assertRaisesRegex(ValueError,'Unrecognized or modified immutable'):Runner(args)

    def test_frozen_wrong_response_cannot_claim_conformance(self):
        runner=Runner(self.frozen_args())
        with patch.object(runner,'execute',return_value=self.output(dict(outcome='diagnostic',reason='invalid_operand',context=dict(stage=4,path=None)))):
            report=runner.run()
        self.assertEqual(report['status'],'failed')
        self.assertTrue(report['semantic_execution'])
        self.assertFalse(report['stable_conformance_claim'])
        self.assertGreater(len(report['failures']),0)

    def test_frozen_suite_mutation_rejected_before_and_after_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.frozen_args();lane=Path(folder)/'lane'
            shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            runner=Runner(args);suite=lane/runner.manifest['suites'][0]['file']
            suite.write_text(suite.read_text()+'\n')
            report=runner.run(check_only=True)
            self.assertEqual(report['status'],'failed');self.assertFalse(report['stable_conformance_claim'])
            self.assertTrue(any(f['id']=='artifact-integrity' for f in report['failures']))
            with self.assertRaisesRegex(ValueError,'Artifact digest mismatch'):Runner(args)


if __name__=='__main__':unittest.main()
