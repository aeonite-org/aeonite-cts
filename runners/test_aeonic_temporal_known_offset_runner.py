"""Harness assertion/admission regressions; these mocks are not SUT conformance."""
import copy
import json
import os
import hashlib
import shutil
import shlex
import sys
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

if __name__=='__main__':unittest.main()
