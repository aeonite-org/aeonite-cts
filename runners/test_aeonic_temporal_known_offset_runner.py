"""Harness assertion/admission regressions; these mocks are not SUT conformance."""
import copy
import json
import os
import hashlib
import shutil
import shlex
import stat
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

    def test_capture_preserves_fixed_capture_time_semantics(self):
        r=Runner(self.frozen_args());meta=r.manifest['meta'];root=r.manifest_path.parent
        capture=json.loads((ROOT/'docs/conformance/known-offset-snapshot-0.1/verification.json').read_text())['capture_semantics']
        def projection(value,ignored):
            encoded=json.dumps({k:v for k,v in value.items() if k not in ignored},sort_keys=True,separators=(',',':')).encode()
            return hashlib.sha256(encoded).hexdigest()
        frozen=json.loads((SPECS/meta['specification_schema']).read_text())
        binding=json.loads((root/meta['binding_schema']).read_text())
        self.assertEqual(frozen['$id'],'urn:aeonic-operations:temporal:known-offset:contract:v1:snapshot-0.1')
        self.assertEqual(projection(frozen,{'$id','title'}),capture['schema_projection_sha256'])
        self.assertEqual(projection(binding,{'$id'}),capture['binding_projection_sha256'])
        self.assertEqual(r.resource_limits,capture['resource_limits']);self.assertEqual(meta['helpers'],capture['helpers'])
        self.assertEqual({suite['id']:suite['content_sha256'] for suite in r.manifest['suites']},capture['suite_sha256'])
        for suite in r.manifest['suites']:
            self.assertEqual(hashlib.sha256((root/suite['file']).read_bytes()).hexdigest(),capture['suite_sha256'][suite['id']])

    def test_valid_mutable_only_addition_does_not_redefine_capture(self):
        def append(manifest,data):
            if data['id']=='01-conversion':
                case=copy.deepcopy(next(t for t in data['tests'] if t['expected']['outcome']=='value'))
                case['id']='next-only-valid-conversion';data['tests'].append(case)
        with self.disposable_target(append) as args:
            with patch.object(self,'args',args):
                frozen=Runner(self.frozen_args());moving=Runner(args)
                self.assertEqual(frozen.run(True)['operation_cases'],221)
                self.assertEqual(moving.run(True)['operation_cases'],222)
                self.assertEqual(moving.run(True)['status'],'artifacts-validated')
                self.test_capture_preserves_fixed_capture_time_semantics()

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
        self.assertFalse(report['semantic_execution']);self.assertTrue(report['protocol_execution']);self.assertGreater(len(report['failures']),0)

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
            qualification=implementation['qualification']
            self.assertEqual(qualification['basis'],'reviewed-source-and-controlled-provider-execution')
            self.assertTrue(qualification['stable_conformance_claim']);self.assertTrue(qualification['semantic_execution'])
            self.assertEqual(qualification['provider_revision'],verification['provider_revision'])
            self.assertEqual(qualification['provider_tree'],verification['provider_tree'])
            self.assertEqual(qualification['report_sha256'],{file:verification['report_sha256'][file] for file in implementation['frozen_reports'].values()})
            for cap,file in implementation['frozen_reports'].items():
                path=root/file;report=json.loads(path.read_text())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),verification['report_sha256'][file])
                self.assertEqual(report['status'],'passed');self.assertEqual(report['failures'],[])
                self.assertFalse(report['semantic_execution']);self.assertFalse(report['stable_conformance_claim'])
                self.assertTrue(report['protocol_execution']);self.assertFalse(report['provider_execution_verified'])
                self.assertTrue(report['complete_passing_execution']);self.assertEqual(report['target_status'],'immutable-local')
                self.assertEqual(report['target'],verification['target'])
                self.assertEqual(report['capabilities'],['conversion','relations'] if cap=='all' else [cap])
                self.assertEqual(report['sut_executions'],{'all':274,'conversion':147,'relations':135}[cap])
                self.assertEqual(report['sut_attempts'],report['sut_executions'])
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

    def test_frozen_fixture_replay_subprocess_cannot_earn_semantic_claim(self):
        r=Runner(self.frozen_args('conversion'));replies={}
        for case in r.tests:
            if case.get('kind','operation')=='operation':replies[case['id']]=case['expected']
            elif case['kind']=='chain':
                for i,step in enumerate(case['steps']):replies[case['id']+'/'+str(i)]=step['expected']
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);data=folder/'answers.json';data.write_text(json.dumps(replies))
            provider=folder/'replay.py';provider.write_text('import json,sys\nx=json.load(sys.stdin)\ny=json.load(open(sys.argv[1]))[x["case_id"]]\nok=y["outcome"]=="value"\nprint(json.dumps(dict(ok=ok,result=y,warnings=[],errors=[] if ok else [dict(code=y["reason"],path=None,span=None,phase=None)])))\n')
            cmd=[sys.executable,str(ROOT/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(SPECS),'--capability-set','conversion','--sut',shlex.join([sys.executable,str(provider),str(data)])]
            child=subprocess.run(cmd,text=True,capture_output=True,timeout=40)
            self.assertEqual(child.returncode,0,child.stderr);report=json.loads(child.stdout)
            self.assertEqual(report['status'],'passed');self.assertTrue(report['complete_passing_execution'])
            self.assertEqual(report['sut_executions'],147);self.assertEqual(report['assertions'],147)
            self.assertTrue(report['protocol_execution']);self.assertFalse(report['provider_execution_verified'])
            self.assertFalse(report['stable_conformance_claim']);self.assertFalse(report['semantic_execution'])

    def test_report_aliases_reject_before_execution_and_preserve_inputs(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);cts=folder/'cts';owner=folder/'owner'
            shutil.copytree(ROOT,cts,ignore=shutil.ignore_patterns('.git','__pycache__'))
            r=Runner(self.frozen_args())
            for key in ('specification_source','specification_schema'):
                relative=r.manifest['meta'][key];dest=owner/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SPECS/relative,dest)
            manifest=cts/r.manifest_path.relative_to(ROOT)
            inputs=[manifest,manifest.parent/r.manifest['meta']['binding_schema'],manifest.parent/r.manifest['suites'][0]['file'],owner/r.manifest['meta']['specification_source'],owner/r.manifest['meta']['specification_schema'],cts/'runners/run_aeonic_arithmetic.py',cts/'runners/run_aeonic_temporal_known_offset.py']
            before={p:p.read_bytes() for p in inputs};marker=folder/'executed';provider=folder/'provider.py'
            provider.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("ran")\n')
            aliases=[]
            for kind in ('hard','symbolic'):
                alias=folder/(kind+'.json')
                try:
                    if kind=='hard':os.link(manifest,alias)
                    else:alias.symlink_to(manifest)
                except (OSError,NotImplementedError):continue
                aliases.append(alias)
            base=[sys.executable,str(cts/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(owner)]
            for destination in [*inputs,*aliases]:
                child=subprocess.run([*base,'--sut',shlex.join([sys.executable,str(provider)]),'--report',str(destination)],text=True,capture_output=True,timeout=20)
                self.assertEqual(child.returncode,2,child.stdout);self.assertEqual(child.stdout,'');self.assertIn('overlaps',child.stderr)
                self.assertFalse(marker.exists());self.assertEqual({p:p.read_bytes() for p in inputs},before)
            report=folder/'report.json'
            child=subprocess.run([*base,'--check','--report',str(report)],text=True,capture_output=True,timeout=20)
            self.assertEqual(child.returncode,0,child.stderr);self.assertEqual(json.loads(report.read_text()),json.loads(child.stdout))
            self.assertEqual({p:p.read_bytes() for p in inputs},before)

    def test_clean_git_crlf_checkout_preserves_every_pinned_frozen_input(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);repo=folder/'index';checkout=folder/'checkout';repo.mkdir();checkout.mkdir()
            r=Runner(self.frozen_args());files={}
            for source in r.artifacts:
                if ROOT in source.parents:files[source.relative_to(ROOT)]=source
                else:files[Path('owner')/source.relative_to(SPECS.resolve())]=source
            for relative,source in list(files.items()):
                origin=ROOT if ROOT in source.parents else SPECS.resolve()
                for parent in source.parents:
                    if parent==origin.parent:break
                    attr=parent/'.gitattributes'
                    if attr.exists():
                        dest=attr.relative_to(origin) if origin==ROOT else Path('owner')/attr.relative_to(origin)
                        files[dest]=attr
            for relative,source in files.items():
                dest=repo/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
            (repo/'conversion-control.txt').write_bytes(b'convert\nthese\n')
            for args in (['init','--quiet'],['config','core.autocrlf','true'],['add','--all'],['checkout-index','--all','--force','--prefix='+str(checkout)+os.sep]):
                result=subprocess.run(['git',*args],cwd=repo,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((checkout/'conversion-control.txt').read_bytes(),b'convert\r\nthese\r\n')
            for relative,source in files.items():
                if source in r.artifacts:self.assertEqual((checkout/relative).read_bytes(),source.read_bytes(),str(relative))
            child=subprocess.run([sys.executable,str(checkout/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(checkout/'owner'),'--check'],text=True,capture_output=True,timeout=20)
            self.assertEqual(child.returncode,0,child.stderr);self.assertEqual(json.loads(child.stdout)['status'],'artifacts-validated')

    def test_readme_working_command_selects_next_even_when_default_frozen_is_valid(self):
        import re
        section=(ROOT/'README.md').read_text().split('## Known-offset coordinate working target',1)[1].split('## ',1)[0]
        command=re.search(r'python3 runners/run_aeonic_temporal_known_offset.py[^\n]+',section).group()
        args=shlex.split(command)[1:];self.assertIn('--manifest',args)
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);lane=folder/'v1';shutil.copytree(self.args.manifest.parent,lane)
            path=lane/self.args.manifest.name;manifest=json.loads(path.read_text());manifest['meta']['version']='invalid';path.write_text(json.dumps(manifest))
            args[0]=str(ROOT/args[0]);args[args.index('--manifest')+1]=str(path);args[args.index('--specs-root')+1]=str(SPECS)
            child=subprocess.run([sys.executable,*args],text=True,capture_output=True,timeout=20)
            self.assertEqual(child.returncode,2);self.assertIn('Wrong target version',child.stderr)
            self.assertEqual(Runner(self.frozen_args()).run(True)['status'],'artifacts-validated')

    def test_protected_output_entries_reject_outgoing_and_dangling_links(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);cts=folder/'cts';owner=folder/'owner'
            shutil.copytree(ROOT,cts,ignore=shutil.ignore_patterns('.git','__pycache__'))
            frozen=Runner(self.frozen_args());moving=Runner(self.args)
            for runner in (frozen,moving):
                for key in ('specification_source','specification_schema'):
                    relative=runner.manifest['meta'][key];target=owner/relative
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SPECS/relative,target)
            lane=cts/'cts'/LANE/'v1';outside=folder/'external-lane';shutil.copytree(lane,outside)
            entry=lane/self.args.manifest.name;entry.unlink();referent=outside/entry.name
            entry.symlink_to(referent)
            directory_alias=folder/'lane-alias';directory_alias.symlink_to(lane,target_is_directory=True)
            base=[sys.executable,str(cts/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(owner),'--check']
            def check_next():
                result=subprocess.run([*base,'--manifest',str(entry)],text=True,capture_output=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
            check_next();before=referent.read_bytes()
            entries=[entry,directory_alias/entry.name]
            case_alias=cts/'CTS'/LANE/'v1'/entry.name
            if case_alias.exists():entries.append(case_alias)
            dangling=[]
            for root in (cts/'runners',owner):
                link=root/'dangling-report.json';link.symlink_to(folder/'absent.json');dangling.append(link)
            for destination in [*entries,*dangling]:
                result=subprocess.run([*base,'--report',str(destination)],text=True,capture_output=True,timeout=20)
                self.assertEqual(result.returncode,2,result.stdout);self.assertIn('overlaps',result.stderr)
                self.assertTrue(destination.is_symlink());self.assertEqual(referent.read_bytes(),before);check_next()
            # A separate output link can be replaced without changing its referent.
            target=folder/'outside.txt';target.write_text('unchanged');output=folder/'report.json';output.symlink_to(target)
            result=subprocess.run([*base,'--report',str(output)],text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(output.is_symlink())
            self.assertEqual(target.read_text(),'unchanged');self.assertEqual(json.loads(output.read_text())['status'],'artifacts-validated')
            # The same protected leaf entry must reject when its referent is absent.
            referent.unlink()
            result=subprocess.run([*base,'--report',str(entry)],text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,2);self.assertTrue(entry.is_symlink());self.assertFalse(referent.exists())

    @unittest.skipUnless(os.name == 'posix', 'POSIX permission bits required')
    def test_atomic_report_replacement_preserves_existing_regular_file_permissions(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);report=folder/'report.json'
            base=[sys.executable,str(ROOT/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(SPECS),'--check','--report',str(report)]
            for mode in (0o640,0o644,0o600):
                report.write_text('old report');report.chmod(mode)
                result=subprocess.run(base,text=True,capture_output=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(stat.S_IMODE(report.stat().st_mode),mode)
                self.assertEqual(json.loads(report.read_text()),json.loads(result.stdout))
                self.assertEqual(list(folder.glob('.known-offset-report-*')),[])
            report.unlink()
            result=subprocess.run(base,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(stat.S_IMODE(report.stat().st_mode),0o600)
            report.unlink();target=folder/'external.json';target.write_text('original');target.chmod(0o640)
            report.symlink_to(target)
            result=subprocess.run(base,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(report.is_symlink())
            self.assertEqual(target.read_text(),'original');self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o640)
            self.assertEqual(stat.S_IMODE(report.stat().st_mode),0o600)

    def test_report_parent_symlink_then_dotdot_uses_filesystem_resolution(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);cts=folder/'cts';owner=folder/'owner'
            shutil.copytree(ROOT,cts,ignore=shutil.ignore_patterns('.git','__pycache__'))
            r=Runner(self.frozen_args())
            for key in ('specification_source','specification_schema'):
                relative=r.manifest['meta'][key];target=owner/relative
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SPECS/relative,target)
            external=folder/'external';(external/'child').mkdir(parents=True)
            alias=cts/'cts'/'external-alias';alias.symlink_to(external/'child',target_is_directory=True)
            direct=external/'report.json';indirect=alias/'..'/'report.json'
            self.assertEqual(indirect.parent.resolve()/indirect.name,direct.resolve())
            base=[sys.executable,str(cts/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(owner),'--check']
            for destination in (direct,indirect,indirect.relative_to(cts)):
                direct.unlink(missing_ok=True)
                result=subprocess.run([*base,'--report',str(destination)],cwd=cts,text=True,capture_output=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(direct.read_text()),json.loads(result.stdout))
                self.assertFalse((cts/'cts'/'report.json').exists());self.assertTrue(alias.is_symlink())
            with patch('tempfile.NamedTemporaryFile',wraps=tempfile.NamedTemporaryFile) as temporary:
                r.write_report(indirect,'external report')
            self.assertEqual(temporary.call_args.kwargs['dir'],external.resolve())
            self.assertEqual(direct.read_text(),'external report')
            # The reverse traversal actually ends in an input tree and must reject.
            child=cts/'runners'/'child';child.mkdir()
            protected_alias=external/'protected-alias';protected_alias.symlink_to(child,target_is_directory=True)
            protected=cts/'runners'/'run_aeonic_temporal_known_offset.py';before=protected.read_bytes()
            result=subprocess.run([*base,'--report',str(protected_alias/'..'/protected.name)],text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,2);self.assertIn('overlaps',result.stderr)
            self.assertEqual(protected.read_bytes(),before)

    def test_untraversable_report_paths_reject_before_execution_without_writes(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);report=folder/'report.json';report.write_text('existing report')
            regular=folder/'regular-file';regular.write_text('not a directory')
            alias=folder/'file-alias';alias.symlink_to(regular)
            marker=folder/'executed';provider=folder/'provider.py'
            provider.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("ran")\n')
            base=[sys.executable,str(ROOT/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(SPECS),'--sut',shlex.join([sys.executable,str(provider)])]
            paths=[regular/'..'/report.name,alias/'..'/report.name,
                   regular/'child'/'..'/'..'/report.name,
                   folder/'missing'/'..'/report.name]
            for destination in paths:
                result=subprocess.run([*base,'--report',str(destination)],text=True,capture_output=True,timeout=20)
                self.assertEqual(result.returncode,2,result.stdout);self.assertEqual(result.stdout,'')
                self.assertFalse(marker.exists());self.assertEqual(report.read_text(),'existing report')
                self.assertEqual(regular.read_text(),'not a directory');self.assertTrue(alias.is_symlink())
                self.assertFalse((folder/'missing').exists());self.assertEqual(list(folder.glob('.known-offset-report-*')),[])
            # A normal missing output directory is still created.
            valid=folder/'new'/'nested'/'report.json'
            result=subprocess.run([*base[:base.index('--sut')],'--check','--report',str(valid)],text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(valid.read_text()),json.loads(result.stdout))

    @unittest.skipUnless(os.name == 'posix', 'POSIX file ownership required')
    def test_atomic_report_preserves_a_distinct_shared_group(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);report=folder/'report.json';report.write_text('shared report')
            groups=(set(os.getgroups())|{os.getegid()})-{folder.stat().st_gid}
            if not groups:self.skipTest('No second permitted group available')
            os.chown(report,-1,min(groups));report.chmod(0o640);before=report.stat()
            result=subprocess.run([sys.executable,str(ROOT/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(SPECS),'--check','--report',str(report)],text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);after=report.stat()
            self.assertEqual((after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)),
                             (before.st_uid,before.st_gid,0o640))
            self.assertEqual(json.loads(report.read_text()),json.loads(result.stdout))

    @unittest.skipUnless(os.name == 'posix', 'POSIX file ownership required')
    def test_ownership_preservation_failure_retains_original_report(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);report=folder/'report.json';report.write_text('shared report');report.chmod(0o640)
            before=report.stat();r=Runner(self.frozen_args())
            with patch('os.chown',side_effect=PermissionError('Cannot retain ownership')):
                with self.assertRaises(PermissionError):r.write_report(report,'replacement')
            after=report.stat();self.assertEqual(report.read_text(),'shared report')
            self.assertEqual((after.st_ino,after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)),
                             (before.st_ino,before.st_uid,before.st_gid,0o640))
            self.assertEqual(list(folder.glob('.known-offset-report-*')),[])

    def test_missing_adapter_launch_reports_attempts_without_protocol_execution(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);missing=folder/'missing-adapter';report=folder/'report.json'
            command=[sys.executable,str(ROOT/'runners/run_aeonic_temporal_known_offset.py'),'--specs-root',str(SPECS),'--sut',shlex.join([str(missing)]),'--report',str(report)]
            result=subprocess.run(command,text=True,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,1,result.stderr);data=json.loads(report.read_text())
            self.assertEqual(data,json.loads(result.stdout));self.assertEqual(data['status'],'failed')
            self.assertGreater(data['sut_attempts'],0);self.assertEqual(data['sut_executions'],0);self.assertEqual(data['assertions'],0)
            self.assertFalse(data['protocol_execution']);self.assertFalse(data['complete_passing_execution'])
            self.assertFalse(data['semantic_execution']);self.assertFalse(data['stable_conformance_claim'])

    def test_execution_flags_and_counts_are_local_to_each_run(self):
        r=Runner(self.frozen_args('conversion'));case=next(t for t in r.tests if t.get('kind','operation')=='operation')
        with patch.object(r,'execute',return_value=self.output(case['expected'])):r.operation(case)
        self.assertEqual(r.executions,1)
        for error in (FileNotFoundError('missing adapter'),subprocess.TimeoutExpired('adapter',0.01),ValueError('SUT harness failure')):
            with patch.object(r,'execute',side_effect=error):report=r.run()
            self.assertEqual(report['status'],'failed');self.assertGreater(report['sut_attempts'],0)
            self.assertEqual(report['sut_executions'],0);self.assertEqual(report['assertions'],0)
            self.assertFalse(report['protocol_execution']);self.assertFalse(report['complete_passing_execution'])
        checked=r.run(True)
        self.assertEqual(checked['sut_attempts'],0);self.assertEqual(checked['sut_executions'],0)
        self.assertEqual(checked['assertions'],0);self.assertFalse(checked['protocol_execution'])

if __name__=='__main__':unittest.main()
