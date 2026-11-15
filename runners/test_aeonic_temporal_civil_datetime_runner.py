"""Assertion-sensitivity and bounded-admission controls; not SUT conformance."""
import argparse
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from run_aeonic_arithmetic import encode
from run_aeonic_temporal_civil_datetime import ROOT, Runner
from temporal_civil_datetime_checks import (LIMITS, PROFILE, B, compact_bytes,
    coordinate, coverage, decimal_properties, format_coordinate, positive_cost,
    relation_labels, subset)


class CivilDateTimeRunnerTests(unittest.TestCase):
    def args(self, selection='all'):
        return argparse.Namespace(manifest=ROOT/'cts/aeonic-temporal-civil-datetime/v1/aeonic-temporal-civil-datetime-cts.v1.next.json',
            specs_root=Path(os.environ.get('AEONIC_DATETIME_SPECS_ROOT', ROOT.parent/'aeonite-specs')),
            sut='unused-test-provider', cwd=ROOT, timeout=10, capability_set=selection)

    def runner(self): return Runner(self.args())

    def output(self,value,**extensions):
        ok=value['outcome']=='value'
        return json.dumps(dict(ok=ok,warnings=[],errors=[] if ok else [dict(code=value['reason'],path=None,span=None,phase=None)],result=value,**extensions))

    def operation(self, runner, id):
        return next(t for t in runner.tests if t['id']==id)

    def test_all_complete_selections_artifact_only_never_claim_stability(self):
        for choice in ['relations','arithmetic','all']:
            runner=Runner(self.args(choice))
            with patch.object(runner,'execute') as execute: report=runner.run(True)
            execute.assert_not_called()
            self.assertEqual(report['status'],'artifacts-validated')
            self.assertFalse(report['stable_conformance_claim']);self.assertFalse(report['semantic_execution'])
            self.assertEqual(report['sut_executions'],0)
            if choice!='all':self.assertGreater(report['excluded_unclaimed_capability_cases'],0)

    def test_wrong_temporal_value_and_endpoint_flags_fail(self):
        r=self.runner();test=self.operation(r,'source-day-reordered-clock-image')
        for key,value in [('includeStart',False),('end','2023-02-28T01:00:00.1')]:
            actual=copy.deepcopy(test['expected']);actual['value']['temporal']['pieces'][0][key]=value
            with patch.object(r,'execute',return_value=self.output(actual)):
                with self.assertRaises(ValueError):r.operation(test)
        with patch.object(r,'execute',return_value=self.output(test['expected'])):r.operation(test)

    def test_symbol_and_owned_metadata_are_asserted(self):
        r=self.runner();test=self.operation(r,'included-touch-contains')
        for mutate in [lambda x:x['value'].update(value='overlaps'),
                       lambda x:x['metadata']['operandHistory']['left'].update(approximation='approximation-declared'),
                       lambda x:x['metadata']['operandOrigin']['left'].update(clockForm='hour')]:
            actual=copy.deepcopy(test['expected']);mutate(actual)
            with patch.object(r,'execute',return_value=self.output(actual)):
                with self.assertRaises(ValueError):r.operation(test)

    def test_history_origin_current_operation_and_policy_are_asserted(self):
        r=self.runner();test=self.operation(r,'exact-clock-carry-with-history')
        for mutate in [lambda x:x['value']['history'].update(approximation='none-declared'),
                       lambda x:x['value'].update(originClockForm='minute'),
                       lambda x:x['metadata'].update(evaluation='exact-for-operands'),
                       lambda x:x['metadata']['effectivePolicy'].update(profile='wrong')]:
            actual=copy.deepcopy(test['expected']);mutate(actual)
            with patch.object(r,'execute',return_value=self.output(actual)):
                with self.assertRaises(Exception):r.operation(test)

    def test_diagnostic_reason_stage_and_path_are_asserted(self):
        r=self.runner();test=self.operation(r,'partial-minute-step-rejected')
        for mutate in [lambda x:x.update(reason='unrepresentable_result'),lambda x:x['context'].update(stage=7),lambda x:x['context'].update(path=None)]:
            actual=copy.deepcopy(test['expected']);mutate(actual)
            with patch.object(r,'execute',return_value=self.output(actual)):
                with self.assertRaises(ValueError):r.operation(test)

    def test_messages_are_optional_but_diagnostics_cannot_have_values(self):
        r=self.runner();test=self.operation(r,'partial-minute-step-rejected')
        actual=copy.deepcopy(test['expected']);actual['message']='explanation'
        with patch.object(r,'execute',return_value=self.output(actual)):r.operation(test)
        actual['value']=None
        with self.assertRaises(Exception):r.validate_result(actual,LIMITS)
        actual.pop('value');actual['message']='bad'+chr(0xD800)
        with self.assertRaises(Exception):r.validate_result(actual,LIMITS)

    def test_closed_results_and_protocol_consistency(self):
        r=self.runner();test=self.operation(r,'exact-clock-carry-with-history')
        actual=copy.deepcopy(test['expected']);actual['extra']=True
        with self.assertRaises(Exception):r.validate_result(actual,LIMITS)
        out=json.loads(self.output(test['expected']));out['ok']=False
        with patch.object(r,'execute',return_value=json.dumps(out)):
            with self.assertRaises(ValueError):r.operation(test)
        with patch.object(r,'execute',return_value=self.output(test['expected'],extension=True)):r.operation(test)

    def test_output_piece_guard_precedes_iteration_at_two_widths(self):
        r=self.runner();base=copy.deepcopy(self.operation(r,'source-day-reordered-clock-image')['expected'])
        class Observed(list):
            reads=0
            def __iter__(self):
                for x in super().__iter__():self.reads+=1;yield x
        for n in [32,64]:
            v=copy.deepcopy(base);raw=Observed(v['value']['temporal']['pieces']*n);v['value']['temporal']['pieces']=raw
            with self.assertRaisesRegex(ValueError,'output-piece'):r.validate_result(v,dict(LIMITS,maxOutputPieces=1))
            self.assertEqual(raw.reads,0)

    def test_literal_and_fraction_guards_precede_parse_or_integer_conversion(self):
        for n in [64,128]:
            with patch('temporal_civil_datetime_checks.COORD') as parser:
                with self.assertRaises(ValueError):coordinate('x'*n,dict(LIMITS,maxTemporalCharacters=8))
            parser.fullmatch.assert_not_called()
        with patch('temporal_civil_datetime_checks.int',create=True) as convert:
            with self.assertRaises(ValueError):coordinate('2024-03-01T09:30:00.'+'1'*64,dict(LIMITS,maxFractionDigits=8))
        convert.assert_not_called()

    def test_compact_byte_guard_and_exact_unicode_control(self):
        for n in [64,128]:
            with patch('temporal_civil_date_checks.json.dumps') as dumps:
                with self.assertRaises(ValueError):compact_bytes('x'*n,8)
            dumps.assert_not_called()
        value=dict(text='é😀',escaped='"\\\n')
        n=len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
        self.assertEqual(compact_bytes(value,n),n)
        with self.assertRaises(ValueError):compact_bytes(value,n-1)

    def test_huge_exponent_is_rejected_before_integer_conversion(self):
        for n in [64,128]:
            value=dict(number=dict(category='finiteNumber',value='1e'+'9'*n))
            with patch('temporal_civil_datetime_checks.int',create=True) as convert:
                with self.assertRaisesRegex(ValueError,'Authored exponent'):decimal_properties(value)
            convert.assert_not_called()

    def test_upper_boundary_and_canonical_set_rejections(self):
        r=self.runner();value=self.operation(r,'last-minute-boundary-preserved')['expected']['value']
        spans=coverage(value,1);self.assertEqual(spans[0][1],B);self.assertFalse(spans[0][3])
        for mutate in [lambda x:x['temporal']['pieces'][0].update(includeEnd=True),
                       lambda x:x['temporal']['pieces'][0].update(start='9999-12-31T23:59:00.0')]:
            bad=copy.deepcopy(value);mutate(bad)
            with self.assertRaises(ValueError):coverage(bad,1)

    def test_reduced_year_expansion_guard_precedes_fraction_construction(self):
        value=dict(temporal=dict(category='civilDateTime',value='2024-T09:30:00.1'))
        with patch('temporal_civil_datetime_checks.Fraction') as fraction:
            with self.assertRaises(ValueError):coverage(value,365)
        fraction.assert_not_called()
        self.assertEqual(len(coverage(value,366)),366)

    def test_template_guard_precedes_construction(self):
        r=self.runner();test=self.operation(r,'month-form-step-accounting');logical=test['fixture']['request']
        spans=[coverage(logical['input']['value'],512)]
        with patch('temporal_civil_datetime_checks.template') as make:
            with self.assertRaises(ValueError):positive_cost(logical,spans,dict(LIMITS,maxIntermediatePieces=28))
        make.assert_not_called()
        self.assertEqual(positive_cost(logical,spans),(89,60))

    def test_target_work_guard_precedes_target_template_at_two_period_sizes(self):
        for text,dg,n in [('2024-02T09:30','month',29),('2024-T09:30','year',366)]:
            logical=dict(operation='step',input=dict(value=dict(temporal=dict(category='civilDateTime',value=text)),policy=dict(profile=PROFILE,dateGranularity=dg,clockForm='minute',count='1')))
            spans=[coverage(logical['input']['value'],512)]
            with patch('temporal_civil_datetime_checks.coverage',wraps=coverage) as expand:
                with self.assertRaisesRegex(ValueError,'Target template work'):
                    positive_cost(logical,spans,dict(LIMITS,maxWork=2*n))
            self.assertEqual(expand.call_count,1)  # Source only; no target expansion.
            self.assertGreater(positive_cost(logical,spans)[0],2*n)

    def test_raised_decimal_allowances_do_not_use_host_integer_text_ceiling(self):
        import sys
        ceiling=sys.get_int_max_str_digits() if hasattr(sys,'get_int_max_str_digits') else None
        limits=dict(LIMITS,maxTemporalCharacters=6000,maxFractionDigits=5000,maxNumericCharacters=6000,maxWorkspaceDigits=6000)
        for n in [4400,5000]:
            text='2024-03-01T09:30:00.'+'1'*n
            value=coordinate(text,limits)
            self.assertEqual(format_coordinate(value),text)
            literal=dict(temporal=dict(category='civilDateTime',value=text))
            self.assertEqual(coverage(literal,1,limits)[0][0],value)
            amount=dict(number=dict(category='finiteNumber',value='1e'+'0'*n+'1'))
            self.assertEqual(decimal_properties(amount,limits),('1',1))
        if ceiling is not None:self.assertEqual(sys.get_int_max_str_digits(),ceiling)

    def test_numeric_workspace_guard_avoids_amount_expansion(self):
        logical=dict(operation='shiftClock',input=dict(amount=dict(number=dict(category='finiteNumber',value='1e-1000000'))))
        spans=[[(coordinate('2024-03-01T09:30:00'),)*2+(True,True)]]
        with self.assertRaisesRegex(ValueError,'workspace'):positive_cost(logical,spans)

    def test_actual_chain_values_not_expected_fixtures_are_forwarded(self):
        r=self.runner();test=next(t for t in r.tests if t.get('kind')=='chain');seen=[]
        actual=copy.deepcopy(test['steps'][0]['expected']);actual['value']['originClockForm']='undeclared'
        def operation(step):
            seen.append(copy.deepcopy(step['fixture']['request']))
            return actual if len(seen)==1 else step['expected']
        original=copy.deepcopy(test)
        with patch.object(r,'operation',side_effect=operation):r.chain(test)
        self.assertEqual(seen[1]['input']['value'],actual['value']);self.assertEqual(test,original)

    def test_chain_links_reject_symbols_and_duplicate_destinations(self):
        r=self.runner();test=copy.deepcopy(next(t for t in r.tests if t.get('kind')=='chain'))
        test['links'].append(copy.deepcopy(test['links'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate chain'):r.validate_test(test)
        test=copy.deepcopy(next(t for t in r.tests if t.get('kind')=='chain'));test['steps'][0]['expected']['value']=dict(category='symbol',value='equal')
        with self.assertRaisesRegex(ValueError,'Only temporal'):r.validate_test(test)

    def test_raw_negative_zero_and_duplicate_evidence_are_retained(self):
        r=self.runner();test=self.operation(r,'opaque-negative-zero-byte-budget');raw=test['fixture']['requestText']
        self.assertEqual(len(raw.encode()),235);self.assertIn('-0',raw)
        from temporal_civil_datetime_checks import decode_artifact
        parsed=decode_artifact('{"fixture":{"request":'+raw+'}}')
        self.assertIn('"opaque":-0',encode(parsed))

    def test_invalid_trusted_limits_are_harness_errors(self):
        r=self.runner()
        for limits in [None,[],True,{'maxWork':True},{'maxWork':-1},{'maxWork':0.5},{'maxWork':9007199254740992},{'typo':1}]:
            envelope=dict(lane='aeonic-temporal-civil-datetime',case_id='bad',fixture=dict(request={}),policy=dict(resourceLimits=limits))
            with self.assertRaises(Exception):r.binding_schema.validate(envelope)

    def test_relation_oracle_checks_missing_points_and_fractional_prefixes(self):
        a=coordinate('2024-03-01T09:30:00');b=a+1;c=b+1
        gap=[(a,b,True,False),(b,c,False,True)];p=[(b,b,True,True)]
        self.assertEqual(relation_labels(gap,p)['relate'],'disjoint')
        self.assertEqual(relation_labels(gap,p)['compare'],'indeterminate')
        self.assertFalse(subset(p,gap))
        self.assertEqual(format_coordinate(coordinate('2024-03-01T09:30:00.000000000001')),'2024-03-01T09:30:00.000000000001')


if __name__=='__main__':unittest.main()
