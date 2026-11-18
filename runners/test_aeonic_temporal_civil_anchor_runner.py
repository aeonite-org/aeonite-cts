"""Anchoring harness sensitivity and bounded fixture admission, not SUT conformance."""
import argparse
import copy
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from run_aeonic_arithmetic import RawNumber, encode
from run_aeonic_temporal_civil_anchor import ROOT, LANE, Runner
from temporal_civil_anchor_checks import (LIMITS, PROFILE, clock, coordinate, dates,
    pieces, target_ordinal, expected_positive, compact_bytes, compare, decode_artifact)


class CivilAnchorRunnerTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(manifest=ROOT/'cts/aeonic-temporal-civil-anchor/v1/aeonic-temporal-civil-anchor-cts.v1.next.json',
            specs_root=Path(os.environ.get('AEONIC_ANCHOR_SPECS_ROOT', ROOT.parent/'aeonite-specs')),
            sut='unused-fixture-provider', cwd=ROOT, timeout=10)

    def runner(self): return Runner(self.args())

    def case(self, r, ident): return next(t for t in r.tests if t['id'] == ident)

    def output(self, result, **extensions):
        ok = result['outcome'] == 'value'
        return json.dumps(dict(ok=ok, warnings=[], errors=[] if ok else
            [dict(code=result['reason'], path=None, span=None, phase=None)], result=result, **extensions))

    def mutations(self, ident, changes):
        r = self.runner(); test = self.case(r, ident)
        with patch.object(r, 'execute', return_value=self.output(test['expected'])): r.operation(test)
        for change in changes:
            value = copy.deepcopy(test['expected']); change(value)
            with patch.object(r, 'execute', return_value=self.output(value)):
                with self.assertRaises(Exception): r.operation(test)

    def test_check_executes_no_provider_and_makes_no_stable_claim(self):
        r = self.runner()
        with patch.object(r, 'execute') as execute: report = r.run(True)
        execute.assert_not_called(); self.assertEqual(report['status'], 'artifacts-validated')
        self.assertFalse(report['semantic_execution']); self.assertFalse(report['stable_conformance_claim'])
        self.assertEqual(report['sut_executions'], 0)

    def test_complete_fixture_replay_is_only_harness_evidence(self):
        r = self.runner(); cases = {t['id']: t for t in r.tests}
        with patch.object(r, 'execute', side_effect=lambda env:self.output(cases[env['case_id']]['expected'])):
            report = r.run()
        self.assertEqual(report['status'], 'passed'); self.assertEqual(report['sut_executions'], len(r.tests))
        self.assertEqual(report['assertions'], len(r.tests)); self.assertFalse(report['stable_conformance_claim'])

    def test_every_diagnostic_asserts_reason_stage_and_path(self):
        r = self.runner()
        for test in r.tests:
            if test['expected']['outcome'] != 'diagnostic': continue
            with patch.object(r, 'execute', return_value=self.output(test['expected'])): r.operation(test)
            for field in ['reason', 'stage', 'path']:
                value = copy.deepcopy(test['expected'])
                if field == 'reason': value[field] = 'invalid_policy' if value[field] != 'invalid_policy' else 'invalid_operand'
                elif field == 'stage': value['context'][field] = value['context'][field] % 7 + 1
                else: value['context'][field] = '/deliberately-wrong'
                with self.subTest(case=test['id'], field=field), patch.object(r, 'execute', return_value=self.output(value)):
                    with self.assertRaises(Exception): r.operation(test)

    def test_date_and_fraction_are_asserted(self):
        self.mutations('same-day-point', [lambda x:x['value']['temporal']['pieces'][0].update(at='2024-02-29T09:30:00'),
            lambda x:x['value']['temporal']['pieces'][0].update(at='2024-02-28T09:30:00.1')])

    def test_all_positive_images_and_metadata_are_asserted(self):
        r = self.runner()
        for test in r.tests:
            if test['expected']['outcome'] != 'value': continue
            wrong = copy.deepcopy(test['expected']); wrong['metadata']['effectivePolicy']['profile'] = 'wrong'
            with self.subTest(case=test['id']), patch.object(r, 'execute', return_value=self.output(wrong)):
                with self.assertRaises(Exception): r.operation(test)

    def test_flags_and_gaps_are_asserted(self):
        r = self.runner()
        interval = next(t for t in r.tests if t['expected']['outcome'] == 'value' and t['expected']['value']['temporal']['pieces'][0]['kind'] == 'interval')
        self.mutations(interval['id'], [lambda x:x['value']['temporal']['pieces'][0].update(includeStart=False),
            lambda x:x['value']['temporal']['pieces'][0].update(includeEnd=True)])
        many = next(t for t in r.tests if t['expected']['outcome'] == 'value' and len(t['expected']['value']['temporal']['pieces']) > 1)
        self.mutations(many['id'], [lambda x:x['value']['temporal']['pieces'].pop()])

    def test_both_histories_and_origins_are_asserted(self):
        r = self.runner()
        marked = next(t for t in r.tests if t['expected']['outcome'] == 'value' and t['expected']['value']['history']['clamping'] == 'clamping-declared' and t['expected']['value']['history']['approximation'] == 'approximation-declared')
        self.mutations(marked['id'], [lambda x:x['value']['history'].update(clamping='none-declared'),
            lambda x:x['value']['history'].update(approximation='none-declared'),
            lambda x:x['value'].update(originDateGranularity='year'),
            lambda x:x['value'].update(originClockForm='hour'),
            lambda x:x['metadata'].update(clamping='applied')])

    def test_optional_message_is_ignored_but_diagnostic_value_is_rejected(self):
        r = self.runner(); test = self.case(r, 'month-anchor'); value = copy.deepcopy(test['expected'])
        value['message'] = 'explanation'
        with patch.object(r, 'execute', return_value=self.output(value)): r.operation(test)
        for key in ['value', 'metadata', 'unknown']:
            bad = dict(value, **{key:None})
            with self.assertRaises(Exception): r.validate_result(bad, LIMITS)
        for text in ['bad'+chr(0xD800), '/bad~x']:
            bad = copy.deepcopy(value)
            if text.startswith('/'): bad['context']['path'] = text
            else: bad['message'] = text
            with self.assertRaises(Exception): r.validate_result(bad, LIMITS)

    def test_protocol_consistency_and_extensions(self):
        r = self.runner(); test = self.case(r, 'same-day-point')
        for field, value in [('ok',False), ('warnings',['unexpected']), ('errors',[{}])]:
            out = json.loads(self.output(test['expected'])); out[field] = value
            with patch.object(r, 'execute', return_value=json.dumps(out)):
                with self.assertRaises(ValueError): r.operation(test)
        with patch.object(r, 'execute', return_value=self.output(test['expected'], extension=True)): r.operation(test)
        test = self.case(r, 'month-anchor'); out = json.loads(self.output(test['expected']))
        out['errors'][0]['code'] = 'wrong'
        with patch.object(r, 'execute', return_value=json.dumps(out)):
            with self.assertRaises(ValueError): r.operation(test)

    def test_binding_rejects_malformed_trusted_limits(self):
        r = self.runner()
        for value in [None, [], {'maxWork':None}, {'maxWork':True}, {'maxWork':0.5},
                      {'maxWork':-1}, {'maxWork':9007199254740992}, {'unknown':1}]:
            with self.subTest(value=value), self.assertRaises(Exception):
                r.binding_schema.validate(dict(lane=LANE,case_id='bad',fixture=dict(request={}),policy=dict(resourceLimits=value)))
        with self.assertRaises(Exception):
            r.binding_schema.validate(dict(lane=LANE,case_id='bad',fixture=dict(request={},requestText='{}'),policy={}))
        r.binding_schema.validate(dict(lane=LANE,case_id='extension',fixture=dict(request={}),policy={},extension=True))

    def test_raw_numbers_survive_both_boundary_forms(self):
        r = self.runner()
        for token in ['-0','1e1000000','1e-1000000','9007199254740993']:
            t = self.case(r, 'raw-token-structured-'+token); raw = t['fixture']['request']['input']['anchor']['temporal']['opaque']
            self.assertIsInstance(raw, RawNumber); self.assertEqual(raw.text, token)
            captured = []
            with patch.object(r, 'execute', side_effect=lambda e:(captured.append(encode(e)) or self.output(t['expected']))): r.operation(t)
            self.assertIn('"opaque":'+token, captured[0])
            self.assertEqual(compact_bytes(t['fixture']['request'], 65536), t['policy']['resourceLimits']['maxRequestBytes'])
            text = self.case(r, 'raw-token-text-'+token)['fixture']['requestText']
            self.assertIn('"opaque":'+token, text)

    def test_input_guards_precede_element_iteration_at_two_widths(self):
        class Observed(list):
            reads = 0
            def __iter__(self):
                for item in super().__iter__(): self.reads += 1; yield item
        for width in [32,64]:
            raw = Observed([{}]*width)
            with self.assertRaisesRegex(ValueError, 'Input range'): dates(dict(temporal=dict(category='civilDateSet',ranges=raw)),dict(LIMITS,maxInputRanges=1))
            self.assertEqual(raw.reads,0)
            raw = Observed([{}]*width)
            with self.assertRaisesRegex(ValueError, 'Input piece'): pieces(dict(temporal=dict(category='civilClockSet',pieces=raw)),dict(LIMITS,maxInputPieces=1))
            self.assertEqual(raw.reads,0)

    def test_day_admission_precedes_grammar_or_calendar_at_two_widths(self):
        for width in [64,128]:
            with patch('temporal_civil_anchor_checks.INTEGER') as grammar:
                with self.assertRaisesRegex(ValueError, 'Day digit'): coordinate(dict(day='1'*width,time='09:30:00'),dict(LIMITS,maxRelativeDayDigits=8))
            grammar.fullmatch.assert_not_called()
            with patch('temporal_civil_anchor_checks.date') as calendar:
                with self.assertRaisesRegex(ValueError, 'outside date-time domain'): target_ordinal(('1'*width,0,''),date(2024,1,1))
            calendar.fromordinal.assert_not_called()

    def test_clock_text_and_fraction_guards_precede_numeric_expansion(self):
        for width in [64,128]:
            with patch('temporal_civil_anchor_checks.FULL') as grammar:
                with self.assertRaisesRegex(ValueError,'Clock text'): clock('1'*width,dict(LIMITS,maxTemporalCharacters=8))
            grammar.fullmatch.assert_not_called()
            with self.assertRaisesRegex(ValueError,'Fraction allowance'): clock('09:30:00.'+'1'*width,dict(LIMITS,maxFractionDigits=8))
            self.assertEqual(compare(('0',0,'1'),('0',0,'1'+'0'*(width-2)+'1')),-1)

    def test_work_and_candidates_guard_translation(self):
        r = self.runner(); request = self.case(r,'same-day-point')['fixture']['request']
        for limits in [dict(LIMITS,maxWork=1),dict(LIMITS,maxIntermediatePieces=0)]:
            with patch('temporal_civil_anchor_checks.target_ordinal') as transform:
                with self.assertRaises(ValueError): expected_positive(request,limits)
            transform.assert_not_called()

    def test_output_count_guards_calendar_rendering_after_domain(self):
        r = self.runner(); request = self.case(r,'same-day-point')['fixture']['request']
        with patch('temporal_civil_anchor_checks.translated') as render:
            with self.assertRaisesRegex(ValueError,'Output allowance'): expected_positive(request,dict(LIMITS,maxOutputPieces=0))
        render.assert_not_called()

    def test_result_piece_guard_precedes_iteration(self):
        class Observed(list):
            def __iter__(self): raise AssertionError('Unexpected traversal')
        r = self.runner()
        for width in [32,64]:
            value = copy.deepcopy(self.case(r,'same-day-point')['expected'])
            value['value']['temporal']['pieces'] = Observed([{}]*width)
            with self.assertRaisesRegex(ValueError,'output-piece'): r.validate_result(value,dict(LIMITS,maxOutputPieces=1))

    def test_success_byte_guard_precedes_oversized_string_escaping(self):
        for width in [64,128]:
            with patch('temporal_civil_date_checks.json.dumps') as escape:
                with self.assertRaisesRegex(ValueError, 'byte allowance'):
                    compact_bytes('x'*width, 8)
            escape.assert_not_called()

    def test_closed_success_envelope_and_metadata(self):
        r = self.runner(); result = self.case(r,'same-day-point')['expected']
        for location in [(),('value',),('metadata',),('metadata','effectivePolicy'),('value','history')]:
            bad = copy.deepcopy(result); node = bad
            for field in location: node = node[field]
            node['unknown'] = None
            with self.subTest(location=location), self.assertRaises(Exception): r.validate_result(bad,LIMITS)

    def test_frozen_value_projection_matches_owning_schemas(self):
        r = self.runner()
        # These are exact syntax projections, with only profile-local deferred
        # category vocabulary changes. Check every embedded reachable definition.
        for prefix, family in [('date_','civil-date'),('clock_','civil-clock'),('datetime_','civil-datetime')]:
            frozen = json.loads((r.args.specs_root/'resources/aeonic-operations/v1/snapshots/0.1'/
                                (family+'-contract.schema.json')).read_text())['$defs']
            def rewrite(value):
                if isinstance(value,dict):
                    return {k:('#/$defs/'+prefix+v[len('#/$defs/'):] if k=='$ref' else rewrite(v)) for k,v in value.items()}
                if isinstance(value,list): return [rewrite(v) for v in value]
                return value
            for name, definition in r.schema['$defs'].items():
                if not name.startswith(prefix) or name in [prefix+'bundle',prefix+'deferred',prefix+'deferredTemporal']:continue
                self.assertEqual(definition,rewrite(frozen[name[len(prefix):]]))

    def test_positive_oracle_rejects_corrupt_expectation_before_execution(self):
        r = self.runner(); test = copy.deepcopy(self.case(r,'same-day-point'))
        test['expected']['value']['temporal']['pieces'][0]['at'] = '2024-02-29T09:30:00'
        with self.assertRaisesRegex(ValueError,'exact image'): r.validate_test(test)

    def test_all_eleven_dimensions_have_independent_success_and_denial_companions(self):
        r = self.runner(); coverage = {key:set() for key in LIMITS}
        for test in r.tests:
            overrides = test.get('policy',{}).get('resourceLimits',{})
            if len(overrides) == 1:
                coverage[next(iter(overrides))].add(test['expected']['outcome'])
        self.assertEqual(coverage,{key:{'value','diagnostic'} for key in LIMITS})

    def test_artifact_pins_and_postrun_integrity_are_checked(self):
        r = self.runner()
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            r.pinned(ROOT,'runners/temporal_civil_anchor_checks.py','0'*64)
        with self.assertRaisesRegex(ValueError,'escapes'):
            r.pinned(ROOT,'../outside','0'*64)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'changed';path.write_text('changed');r.artifacts[path]='0'*64
            report = r.run(True)
        self.assertEqual(report['status'],'failed');self.assertFalse(report['stable_conformance_claim'])

    def test_cannot_promote_mutable_artifacts_or_skip_cases(self):
        r = self.runner(); test = copy.deepcopy(r.tests[0]); test['skip'] = True
        with self.assertRaisesRegex(ValueError,'opt-outs'): r.validate_test(test)

    def test_subprocess_transport_has_a_passing_and_wrong_response_control(self):
        # This deliberately synthetic fixture provider tests framing/assertions;
        # it is not a staged anchoring implementation or conformance evidence.
        r = self.runner(); test = self.case(r,'same-day-point')
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'replay.py'
            script.write_text('import json,sys\ne=json.load(sys.stdin)\nassert e["lane"]=='+repr(LANE)+'\nassert len(e["policy"]["resourceLimits"])==11\nprint('+repr(self.output(test['expected']))+')\n')
            r.args.sut = '"'+sys.executable+'" "'+str(script)+'"'
            self.assertEqual(r.operation(test),test['expected'])
            bad = copy.deepcopy(test['expected']);bad['value']['originDateGranularity']='year'
            script.write_text('print('+repr(self.output(bad))+')\n')
            with self.assertRaisesRegex(ValueError,'result mismatch'):r.operation(test)


if __name__ == '__main__': unittest.main()
