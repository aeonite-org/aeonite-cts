"""Harness assertion/admission regressions; these mocks are not SUT conformance."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from run_aeonic_temporal_known_offset import ROOT, LANE, Runner
from temporal_known_offset_checks import (LIMITS, PROFILE, expected_positive,
    common, offset, relation_labels)

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
