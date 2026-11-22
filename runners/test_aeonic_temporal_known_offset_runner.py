"""Harness assertion/admission regressions; these mocks are not SUT conformance."""
import copy
import json
import os
import hashlib
import shutil
import shlex
import sys
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from run_aeonic_temporal_known_offset import ROOT, LANE, Runner
from temporal_known_offset_checks import (LIMITS, PROFILE, expected_positive,
    common, offset, relation_labels, decode_request, law_witnesses, compact_bytes)

SPECS=Path(os.environ.get('AEONIC_KNOWN_OFFSET_SPECS_ROOT', ROOT.parent/'aeonite-specs'))

class KnownOffsetRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.args=SimpleNamespace(manifest=ROOT/'cts'/LANE/'v1'/(LANE+'-cts.v1.next.json'),
            specs_root=SPECS,capability_set='all',sut=None,cwd=ROOT,timeout=2,report=None)
        cls.r=Runner(cls.args)

    def case(self,identity):return next(t for t in self.r.tests if t['id']==identity)

    @staticmethod
    def output(result):
        ok=result['outcome']=='value'
        return json.dumps(dict(ok=ok,result=result,warnings=[],errors=[] if ok else
            [dict(code=result['reason'],path=None,span=None,phase=None)]))

    def mutation(self,test,mutate):
        bad=copy.deepcopy(test['expected']);mutate(bad)
        with patch.object(self.r,'execute',return_value=self.output(bad)):
            with self.assertRaises(Exception):self.r.operation(test)

    @contextmanager
    def disposable_target(self, transform):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'v1'
            shutil.copytree(self.args.manifest.parent,target)
            path=target/self.args.manifest.name
            manifest=json.loads(path.read_text())
            for suite in manifest['suites']:
                file=target/suite['file'];data=json.loads(file.read_text())
                transform(manifest,data)
                file.write_text(json.dumps(data,ensure_ascii=True,indent=2)+'\n')
                suite['content_sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
            path.write_text(json.dumps(manifest,indent=2)+'\n')
            args=copy.copy(self.args);args.manifest=path
            yield args

    def test_missing_chain_law_suite_is_rejected_for_every_capability(self):
        with self.disposable_target(lambda m,d:None) as args:
            m=json.loads(args.manifest.read_text())
            m['suites']=[suite for suite in m['suites'] if suite['id']!='06-chains-laws']
            args.manifest.write_text(json.dumps(m))
            for choice in ('conversion','relations','all'):
                args.capability_set=choice
                with self.subTest(choice=choice),self.assertRaises(ValueError):Runner(args)

    def test_laws_cannot_be_removed_while_chains_remain(self):
        def remove(m,data):data['tests']=[t for t in data['tests'] if t.get('kind')!='laws']
        with self.disposable_target(remove) as args:
            for choice in ('relations','all'):
                args.capability_set=choice
                with self.assertRaises(ValueError):Runner(args)
            args.capability_set='conversion'
            self.assertEqual(Runner(args).run(True)['status'],'artifacts-validated')

    def test_combined_claim_requires_cross_capability_link(self):
        def remove(m,data):data['tests']=[t for t in data['tests'] if t.get('kind')!='chain' or len(t['requires'])==1]
        with self.disposable_target(remove) as args:
            with self.assertRaises(ValueError):Runner(args)
            for choice in ('conversion','relations'):
                args.capability_set=choice
                self.assertEqual(Runner(args).run(True)['status'],'artifacts-validated')

    def test_unlinked_chain_is_not_coverage(self):
        chain=copy.deepcopy(self.case('actual-returned-chain'));chain['links']=[]
        with self.assertRaises(ValueError):self.r.validate_test(chain)

    def test_vacuous_laws_are_rejected_when_loading_a_target(self):
        def collapse(m,data):
            for t in data['tests']:
                if t.get('kind')=='laws':t['values']=t['values'][:3]
        with self.disposable_target(collapse) as args:
            with self.assertRaisesRegex(ValueError,'strict-before'):Runner(args)

    def test_identical_logical_inputs_do_not_witness_distinct_equality(self):
        original=self.case('cross-frame-ordering-laws')['values']
        for variant in ('same-object','deep-copy','reordered-keys'):
            values=copy.deepcopy(original)
            duplicate=values[0] if variant=='same-object' else copy.deepcopy(values[0])
            if variant=='reordered-keys':
                duplicate=dict(reversed(list(duplicate.items())))
                duplicate['temporal']=dict(reversed(list(duplicate['temporal'].items())))
            values[1]=duplicate
            with self.subTest(variant=variant),self.assertRaisesRegex(ValueError,'distinct inputs'):
                law_witnesses(values)
        self.assertEqual(law_witnesses(original),2)

    def test_duplicate_equality_witness_is_rejected_when_loading_target(self):
        def duplicate(m,data):
            for test in data['tests']:
                if test.get('kind')=='laws':test['values'][1]=copy.deepcopy(test['values'][0])
        with self.disposable_target(duplicate) as args:
            for choice in ('relations','all'):
                args.capability_set=choice
                with self.subTest(capability=choice),self.assertRaisesRegex(ValueError,'distinct inputs'):
                    Runner(args)

    def test_loaded_target_cannot_drop_distinct_equality_witness(self):
        test=self.case('cross-frame-ordering-laws');original=test['values']
        try:
            test['values']=copy.deepcopy(original)
            test['values'][1]=copy.deepcopy(test['values'][0])
            report=self.r.run(True)
            self.assertEqual(report['status'],'failed')
            self.assertFalse(report['complete_passing_execution'])
            self.assertTrue(any(f['id']=='required-coverage' and 'distinct inputs' in f['failure'] for f in report['failures']))
        finally:test['values']=original

    def test_strict_before_transitivity_has_two_actual_witnesses(self):
        test=self.case('cross-frame-ordering-laws')
        self.assertEqual(law_witnesses(test['values']),2)
        before=self.r.strict_before_assertions
        with patch.object(self.r,'operation',side_effect=lambda t:t['expected']),patch.object(self.r,'assertion',wraps=self.r.assertion) as assertions:
            self.r.laws(test)
        self.assertEqual(self.r.strict_before_assertions-before,2)
        self.assertEqual(sum(call.args[1]=='strict-before transitivity' for call in assertions.call_args_list),2)

    def test_raw_only_positive_operation_coverage_is_valid(self):
        def raw(m,data):
            for t in data['tests']:
                if t.get('kind','operation')=='operation' and t['expected']['outcome']=='value':
                    request=t['fixture'].get('request')
                    if request is not None and request['operation']=='relate':
                        t['fixture']={'requestText':json.dumps(request)}
        with self.disposable_target(raw) as args:
            r=Runner(args)
            self.assertTrue(all('requestText' in t['fixture'] for t in r.tests if t.get('kind','operation')=='operation' and t['expected']['outcome']=='value' and 'relate' in json.dumps(t['fixture'])))
            self.assertEqual(r.run(True)['status'],'artifacts-validated')

    def test_wrapper_only_raw_positive_is_rejected(self):
        test=copy.deepcopy(self.case('preserve-all-markers'))
        request=json.dumps(test['fixture']['request'])
        raw=request+'},"ignored":{"request":'+request
        # This was valid in the old synthetic wrapper, but not standalone JSON.
        json.loads('{"fixture":{"request":'+raw+'}}')
        test['fixture']={'requestText':raw}
        with self.assertRaises(ValueError):self.r.validate_test(test)

    def test_standalone_raw_decoder_preserves_tokens_and_rejects_duplicates(self):
        value=decode_request('{"zero":-0,"large":1e1000000}')
        self.assertEqual(value['zero'].text,'-0');self.assertEqual(value['large'].text,'1e1000000')
        for raw in ('{} {}','{"a":1,"a":2}','{"x":NaN}'):
            with self.assertRaises(ValueError):decode_request(raw)

    def test_deep_raw_admission_fixture_reaches_real_stdio_adapter(self):
        test=self.case('raw-deep-depth-before-decoding')
        with patch('run_aeonic_temporal_known_offset.decode_request',side_effect=AssertionError('Do not decode stage-1 fixture')):
            self.r.validate_test(test)
        code=('import json,sys; e=json.load(sys.stdin); '
              'assert e["fixture"]["requestText"].count("[")==1051; '
              'r={"outcome":"diagnostic","reason":"resource_limit","context":{"stage":1,"path":None}}; '
              'print(json.dumps({"ok":False,"result":r,"warnings":[],"errors":[{"code":"resource_limit","path":None,"span":None,"phase":None}]}))')
        with patch.object(self.r.args,'sut',shlex.quote(sys.executable)+' -c '+shlex.quote(code)):
            self.assertEqual(self.r.operation(test)['context']['stage'],1)

    def test_structured_unicode_bytes_and_root_depth_are_exact(self):
        test=self.case('native-unicode-exact-bytes');request=test['fixture']['request']
        literal=len(json.dumps(request,ensure_ascii=False,separators=(',',':')).encode())
        escaped=len(json.dumps(request,ensure_ascii=True,separators=(',',':')).encode())
        self.assertGreater(escaped,literal)
        self.assertEqual(compact_bytes(request,literal),literal)
        with self.assertRaises(ValueError):expected_positive(request,dict(LIMITS,maxRequestBytes=literal-1))
        expected_positive(request,dict(LIMITS,maxRequestBytes=literal,maxRequestDepth=4))
        with self.assertRaises(ValueError):expected_positive(request,dict(LIMITS,maxRequestDepth=3))

    def test_artifacts_are_mutable_and_not_execution(self):
        report=self.r.run(True)
        self.assertEqual(report['status'],'artifacts-validated')
        self.assertFalse(report['semantic_execution']);self.assertFalse(report['stable_conformance_claim'])
        self.assertFalse(report['complete_passing_execution'])

    def test_each_complete_capability_is_independent(self):
        for choice in ('conversion','relations'):
            args=copy.copy(self.args);args.capability_set=choice;r=Runner(args)
            self.assertEqual(r.selected,{choice});self.assertTrue(r.excluded)
            self.assertTrue(all(set(t['requires'])<=r.selected for t in r.tests))
            self.assertEqual(r.run(True)['status'],'artifacts-validated')

    def test_every_diagnostic_reason_stage_path_is_asserted(self):
        for t in self.r.tests:
            if t.get('kind','operation')!='operation' or t['expected']['outcome']!='diagnostic':continue
            for field in ('reason','stage','path'):
                def mutate(v):
                    if field=='reason':v[field]='invalid_policy' if v[field]!='invalid_policy' else 'invalid_operand'
                    elif field=='stage':v['context'][field]=v['context'][field]%7+1
                    else:v['context'][field]='/deliberately-wrong'
                with self.subTest(case=t['id'],field=field):self.mutation(t,mutate)

    def test_every_positive_value_and_metadata_is_asserted(self):
        for t in self.r.tests:
            if t.get('kind','operation')!='operation' or t['expected']['outcome']!='value':continue
            with self.subTest(case=t['id']):self.mutation(t,lambda x:x['metadata']['effectivePolicy'].update(profile='wrong'))

    def test_offsets_originals_coordinates_and_fraction_are_asserted(self):
        t=self.case('preserve-all-markers')
        for change in (lambda v:v['value']['temporal'].update(offset='Z'),
                       lambda v:v['value'].update(originalOffset='Z'),
                       lambda v:v['value']['temporal']['pieces'][0].update(at='2024-03-01T08:00:00.2'),
                       lambda v:v['value']['history'].update(approximation='none-declared'),
                       lambda v:v['value']['history'].update(clamping='none-declared'),
                       lambda v:v['value'].update(originClockForm='second'),
                       lambda v:v['value'].update(originDateGranularity='day')):
            self.mutation(t,change)

    def test_missing_dates_and_endpoint_flags_are_asserted(self):
        self.mutation(self.case('leap-day-minute'),lambda x:x['value']['temporal']['pieces'].pop())
        self.mutation(self.case('flags-False-False'),lambda x:x['value']['temporal']['pieces'][0].update(includeStart=True))
        self.mutation(self.case('flags-True-False'),lambda x:x['value']['temporal']['pieces'][0].update(includeEnd=True))

    def test_symbol_and_per_operand_history_are_asserted(self):
        t=self.case('contains-start-relate')
        self.mutation(t,lambda x:x['value'].update(value='equal'))
        self.mutation(t,lambda x:x['metadata']['operandOriginalOffset'].update(left='+00:00'))
        self.mutation(t,lambda x:x['metadata']['operandHistory']['left'].update(approximation='approximation-declared'))
        self.mutation(t,lambda x:x['metadata']['operandOrigin']['right'].update(clockForm='minute'))

    def test_diagnostic_message_is_optional_but_values_are_forbidden(self):
        t=self.case('lower-domain');v=copy.deepcopy(t['expected']);v['message']='explanation'
        with patch.object(self.r,'execute',return_value=self.output(v)):self.r.operation(t)
        for key in ('value','metadata','extra'):
            with self.assertRaises(Exception):self.r.validate_result(dict(v,**{key:None}),LIMITS)

    def test_malformed_pointer_and_surrogate_messages_are_rejected(self):
        v=copy.deepcopy(self.case('lower-domain')['expected'])
        for path in ('/bad~x','missing-leading-slash','/bad'+chr(0xD800)):
            bad=copy.deepcopy(v);bad['context']['path']=path
            with self.assertRaises(Exception):self.r.validate_result(bad,LIMITS)
        v['message']=chr(0xD800)
        with self.assertRaises(Exception):self.r.validate_result(v,LIMITS)

    def test_result_schema_rejects_empty_noncanonical_or_out_of_domain(self):
        t=self.case('preserve-all-markers')
        for pieces in ([],[dict(kind='point',at='2024-02-30T00:00:00')],
                       [dict(kind='point',at='2024-03-01T00:00:00.10')],
                       [dict(kind='point',at='2024-03-01T00:00:00')]*2):
            v=copy.deepcopy(t['expected']);v['value']['temporal']['pieces']=pieces
            with self.assertRaises(Exception):self.r.validate_result(v,LIMITS)

    def test_positive_checker_enforces_aggregate_not_per_operand(self):
        t=self.case('two-input-exact-total')
        with self.assertRaises(Exception):expected_positive(t['fixture']['request'],dict(LIMITS,maxInputPieces=1))

    def test_conversion_does_not_erase_original_zero_form(self):
        a=expected_positive(self.case('source-Z')['fixture']['request'])
        b=expected_positive(self.case('source-+00:00')['fixture']['request'])
        self.assertEqual(a['value']['temporal'],b['value']['temporal'])
        self.assertNotEqual(a['value']['originalOffset'],b['value']['originalOffset'])

    def test_exact_common_positions_can_exceed_stored_bounds(self):
        t=self.case('below-zero-common-compare')
        self.assertLess(common(t['fixture']['request']['input']['left'],1)[0][0],0)
        self.assertEqual(t['expected']['value']['value'],'before')

    def test_bounded_offset_validation(self):
        for text in ('-00:00','+24:00','+99:99','+01:00:01','Z\n'):
            with self.assertRaises(Exception):offset(text)
        self.assertEqual(offset('-23:59'),-86340)

    def test_null_limits_and_unknown_trusted_fields_are_harness_errors(self):
        for value in (None,[],True,{'unknown':1},{'maxWork':True},{'maxWork':-1},{'maxWork':1.5},{'maxWork':9007199254740992}):
            envelope=dict(lane=LANE,case_id='invalid-limit',fixture=dict(request={}),policy=dict(resourceLimits=value))
            # jsonschema treats bool separately from JSON integers.
            with self.assertRaises(Exception):self.r.binding_schema.validate(envelope)

    def test_chain_uses_actual_returned_bundle(self):
        chain=self.case('actual-returned-chain')
        returned=[];requests=[]
        def operation(test):
            requests.append(test['fixture']['request'])
            out=copy.deepcopy(test['expected']);out['value']['probe']='actual-'+str(len(returned))
            returned.append(out);return out
        with patch.object(self.r,'operation',side_effect=operation):self.r.chain(chain)
        self.assertEqual(requests[1]['input']['value'],returned[0]['value'])
        self.assertNotIn('probe',chain['steps'][0]['expected']['value'])

    def test_unknown_case_fields_and_semantic_opt_outs_are_rejected(self):
        t=copy.deepcopy(self.case('preserve-all-markers'));t['skip']=True
        with self.assertRaises(Exception):self.r.validate_test(t)
        t.pop('skip');t['requires']=[]
        with self.assertRaises(Exception):self.r.validate_test(t)

    def test_protocol_ok_errors_and_warnings_are_asserted(self):
        t=self.case('lower-domain');out=json.loads(self.output(t['expected']))
        for key,value in [('ok',True),('errors',[]),('warnings',['unexpected'])]:
            bad=dict(out,**{key:value})
            with patch.object(self.r,'execute',return_value=json.dumps(bad)):
                with self.assertRaises(Exception):self.r.operation(t)

    def test_complete_fixture_replay_can_pass_without_a_stable_claim(self):
        # Mock replies exercise harness plumbing only, not product semantics.
        replies={}
        for test in self.r.tests:
            kind=test.get('kind','operation')
            if kind=='operation':replies[test['id']]=test['expected']
            elif kind=='chain':
                for i,step in enumerate(test['steps']):replies[test['id']+'/'+str(i)]=step['expected']
            else:
                for i,left in enumerate(test['values']):
                    for j,right in enumerate(test['values']):
                        for op in ('equal','compare','relate'):
                            logical=dict(operation=op,input=dict(left=left,right=right,context=dict(profile=PROFILE)))
                            replies[test['id']+'/%s-%d-%d'%(op,i,j)]=expected_positive(logical)
        with patch.object(self.r,'execute',side_effect=lambda env:self.output(replies[env['case_id']])):
            report=self.r.run(False)
        self.assertEqual(report['status'],'passed',report['failures'])
        self.assertTrue(report['complete_passing_execution'])
        self.assertFalse(report['stable_conformance_claim'])

    def test_noop_execution_cannot_pass(self):
        with patch.object(self.r,'operation'),patch.object(self.r,'chain'),patch.object(self.r,'laws'):
            report=self.r.run(False)
        self.assertEqual(report['status'],'failed')
        self.assertTrue(any(f['id']=='execution-completeness' for f in report['failures']))

    def test_mutated_case_inventory_cannot_pass(self):
        old=self.r.tests
        try:
            self.r.tests=old[:-1]
            with patch.object(self.r,'operation'),patch.object(self.r,'chain'),patch.object(self.r,'laws'):
                self.assertEqual(self.r.run(False)['status'],'failed')
        finally:self.r.tests=old

    def frozen_args(self, choice='all'):
        args=copy.copy(self.args);args.capability_set=choice
        args.manifest=args.manifest.with_name(LANE+'-cts.v1.snapshot-0.1.json')
        return args

    def test_frozen_artifact_checks_never_claim_semantic_conformance(self):
        for choice in ('conversion','relations','all'):
            r=Runner(self.frozen_args(choice))
            with patch.object(r,'execute') as execute:report=r.run(True)
            execute.assert_not_called()
            self.assertTrue(r.immutable);self.assertEqual(report['status'],'artifacts-validated')
            self.assertEqual(report['target_status'],'immutable-local')
            self.assertFalse(report['stable_conformance_claim']);self.assertFalse(report['semantic_execution'])
            self.assertFalse(report['complete_passing_execution']);self.assertEqual(report['sut_executions'],0)
            self.assertEqual(r.manifest['meta']['spec_snapshot_id'],LANE+'-specs-v1-snapshot-0.1')
            self.assertEqual(len(r.tests),{'all':224,'conversion':146,'relations':88}[choice])
        self.assertFalse(self.r.immutable)
        self.assertEqual(self.r.manifest['meta']['snapshot_id'],LANE+'-cts-v1-snapshot-0.2')

    def test_frozen_manifest_reencoding_mutations_and_next_relabel_reject(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.frozen_args();lane=Path(folder)/'v1'
            shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            original=json.loads(args.manifest.read_text())
            variants=[copy.deepcopy(original) for _ in range(6)]
            variants[1]['meta']['description']='edited'
            variants[2]['meta']['snapshot_id']=LANE+'-cts-v1-snapshot-9.9'
            variants[3]['meta']['spec_snapshot_id']='other-specs-v1-snapshot-0.1'
            variants[4]['suites'][0]['exclude_tests']=['one']
            variants[5]=json.loads((lane/(LANE+'-cts.v1.next.json')).read_text())
            variants[5]['meta']['conformance']=original['meta']['conformance']
            for variant in variants:
                args.manifest.write_text(json.dumps(variant))
                with self.assertRaisesRegex(ValueError,'Unrecognized or modified immutable'):Runner(args)

    def test_frozen_fixture_bytes_are_isolated_and_integrity_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.frozen_args();lane=Path(folder)/'v1'
            shutil.copytree(args.manifest.parent,lane);args.manifest=lane/args.manifest.name
            (lane/'suites/01-conversion.json').write_text('{}')
            (lane/'binding.schema.json').write_text('{}')
            r=Runner(args);self.assertEqual(r.run(True)['status'],'artifacts-validated')
            for suite in r.manifest['suites']:self.assertTrue(suite['file'].startswith('snapshots/0.1/suites/'))
            self.assertEqual(r.manifest['meta']['binding_schema'],'snapshots/0.1/cts-binding.schema.json')
            suite=lane/r.manifest['suites'][0]['file'];suite.write_text(suite.read_text()+'\n')
            report=r.run(True)
            self.assertEqual(report['status'],'failed');self.assertFalse(report['stable_conformance_claim'])
            self.assertTrue(any(f['id']=='artifact-integrity' for f in report['failures']))
            with self.assertRaisesRegex(ValueError,'Artifact digest mismatch'):Runner(args)

    def test_frozen_source_and_schema_are_isolated_from_working_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            args=self.frozen_args();args.specs_root=Path(folder)
            for key in ('specification_source','specification_schema'):
                relative=Runner(self.frozen_args()).manifest['meta'][key]
                target=args.specs_root/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(SPECS/relative,target)
            work=args.specs_root/'resources/aeonic-operations/v1/known-offset-contract.schema.json'
            work.write_text('{}')
            source=args.specs_root/'sources/aes/v1/aeonic-temporal-known-offset-v1.aeon'
            source.parent.mkdir(parents=True);source.write_text('invalid working source')
            r=Runner(args);self.assertEqual(r.run(True)['status'],'artifacts-validated')
            frozen=args.specs_root/r.manifest['meta']['specification_schema'];frozen.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Artifact digest mismatch'):Runner(args)

    def test_capture_preserves_schema_binding_suite_and_limit_semantics(self):
        r=Runner(self.frozen_args());meta=r.manifest['meta']
        working=json.loads((SPECS/'resources/aeonic-operations/v1/known-offset-contract.schema.json').read_text())
        frozen=json.loads((SPECS/meta['specification_schema']).read_text())
        self.assertEqual(frozen['$id'],'urn:aeonic-operations:temporal:known-offset:contract:v1:snapshot-0.1')
        self.assertEqual({k:v for k,v in working.items() if k not in ('$id','title')},{k:v for k,v in frozen.items() if k not in ('$id','title')})
        root=r.manifest_path.parent
        binding=json.loads((root/meta['binding_schema']).read_text());moving=json.loads((root/'binding.schema.json').read_text())
        self.assertEqual({k:v for k,v in binding.items() if k!='$id'},{k:v for k,v in moving.items() if k!='$id'})
        self.assertEqual(r.resource_limits,self.r.resource_limits);self.assertEqual(meta['helpers'],self.r.manifest['meta']['helpers'])
        for suite in r.manifest['suites']:
            self.assertEqual((root/suite['file']).read_bytes(),(root/'suites'/Path(suite['file']).name).read_bytes())

    def test_frozen_noop_and_filtered_execution_cannot_claim_conformance(self):
        for filtered in (False,True):
            r=Runner(self.frozen_args())
            if filtered:r.tests=r.tests[:-1]
            with patch.object(r,'operation'),patch.object(r,'chain'),patch.object(r,'laws'):report=r.run()
            self.assertEqual(report['status'],'failed');self.assertFalse(report['stable_conformance_claim'])
            self.assertFalse(report['complete_passing_execution'])

    def test_frozen_wrong_responses_cannot_claim_conformance(self):
        r=Runner(self.frozen_args())
        bad=self.output(dict(outcome='diagnostic',reason='invalid_operand',context=dict(stage=4,path=None)))
        with patch.object(r,'execute',return_value=bad):report=r.run()
        self.assertEqual(report['status'],'failed');self.assertFalse(report['stable_conformance_claim'])
        self.assertTrue(report['semantic_execution']);self.assertGreater(len(report['failures']),0)

    def test_cli_default_frozen_and_explicit_next_are_separate(self):
        for manifest,target in ((None,'0.1'),(self.args.manifest,'0.2')):
            command=[sys.executable,str(ROOT/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(SPECS),'--check']
            if manifest is not None:command+=['--manifest',str(manifest)]
            child=subprocess.run(command,text=True,capture_output=True,timeout=20)
            self.assertEqual(child.returncode,0,child.stderr+child.stdout);report=json.loads(child.stdout)
            self.assertEqual(report['status'],'artifacts-validated');self.assertTrue(report['target'].endswith(target))
            self.assertFalse(report['stable_conformance_claim']);self.assertFalse(report['semantic_execution'])
            self.assertEqual(report['sut_executions'],0)

    def test_generator_preserves_frozen_artifacts_and_next_identity(self):
        import generate_temporal_known_offset as generator
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'cts'/LANE/'v1';shutil.copytree(self.args.manifest.parent,target)
            binding=root/'cts/aeonic-temporal-civil-anchor/v1/binding.schema.json'
            binding.parent.mkdir(parents=True);shutil.copyfile(ROOT/'cts/aeonic-temporal-civil-anchor/v1/binding.schema.json',binding)
            for relative in self.r.manifest['meta']['helpers']:
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,path)
            files=[target/(LANE+'-cts.v1.snapshot-0.1.json'),*(target/'snapshots').rglob('*')]
            before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
            with patch.object(generator,'ROOT',root),patch.object(generator,'TARGET',target):generator.generate(SPECS)
            self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before},before)
            m=json.loads((target/(LANE+'-cts.v1.next.json')).read_text())
            self.assertEqual(m['meta']['version'],'0.2.0-dev.0');self.assertTrue(m['meta']['snapshot_id'].endswith('0.2'))
            self.assertEqual(m['meta']['conformance'],dict(surface='working-next',stable=False))

    def test_retained_genuine_reports_cover_frozen_and_mutable_capabilities(self):
        root=ROOT/'docs/conformance/known-offset-snapshot-0.1'
        verification=json.loads((root/'verification.json').read_text());r=Runner(self.frozen_args())
        self.assertEqual(verification['target'],r.manifest['meta']['snapshot_id'])
        self.assertEqual(verification['manifest_sha256'],r.artifacts[r.manifest_path])
        self.assertEqual(verification['runner_sha256'],hashlib.sha256((ROOT/'runners/run_aeonic_temporal_known_offset.py').read_bytes()).hexdigest())
        self.assertEqual(set(verification['implementations']),{'javascript','python39','python314'})
        for implementation in verification['implementations'].values():
            self.assertEqual(set(implementation['frozen_reports']),{'all','conversion','relations'})
            for cap,file in implementation['frozen_reports'].items():
                path=root/file;report=json.loads(path.read_text())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),verification['report_sha256'][file])
                self.assertEqual(report['status'],'passed');self.assertEqual(report['failures'],[])
                self.assertTrue(report['semantic_execution']);self.assertTrue(report['stable_conformance_claim'])
                self.assertTrue(report['complete_passing_execution']);self.assertEqual(report['target_status'],'immutable-local')
                self.assertEqual(report['target'],verification['target'])
                self.assertEqual(report['capabilities'],['conversion','relations'] if cap=='all' else [cap])
                self.assertEqual(report['sut_executions'],{'all':274,'conversion':147,'relations':135}[cap])
                self.assertEqual(report['assertions'],{'all':334,'conversion':147,'relations':195}[cap])
                self.assertEqual(report['strict_before_transitivity_assertions'],0 if cap=='conversion' else 2)
                for name in ['manifest_sha256','runner_sha256','specification_source_sha256','specification_schema_sha256']:
                    self.assertEqual(report[name],verification[name])
                self.assertEqual(report['resource_limits'],verification['resource_limits'])
                self.assertEqual(report['helper_hashes'],verification['helpers'])
            for key in ('mutable_report','capacity_report'):
                file=implementation[key];path=root/file;report=json.loads(path.read_text())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),verification['report_sha256'][file])
                self.assertEqual(report['status'],'passed');self.assertFalse(report['stable_conformance_claim'])
                if key=='mutable_report':self.assertEqual(report['target_status'],'mutable-working');self.assertEqual(report['sut_executions'],274)
                else:self.assertEqual(report['checks'],19);self.assertEqual(len(report['covered_dimensions']),9)

if __name__=='__main__':unittest.main()
