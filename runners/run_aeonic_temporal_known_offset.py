#!/usr/bin/env python3
"""Pinned known-offset snapshot and mutable CTS; Python 3.9+."""
import argparse
import copy
import hashlib
import itertools
import json
import os
import re
from pathlib import Path
import sys
import tempfile

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from run_aeonic_arithmetic import Runner as CommonRunner, decode, digest, equal, require
from run_aeonic_rational_arithmetic import Runner as BoundedTransport
from temporal_known_offset_checks import (PROFILE, CAPABILITIES, LIMITS,
    compact_bytes, coverage, common, decode_artifact, expected_positive,
    relation_labels, relation_result, validate_pointer_text, decode_request, law_witnesses)

ROOT = Path(__file__).resolve().parents[1]
LANE = 'aeonic-temporal-known-offset'
NEXT_TARGET = LANE + '-cts-v1-snapshot-0.2'
IMMUTABLE_TARGETS = {LANE + '-cts-v1-snapshot-0.1': '274d203eb8d24636f135bca290b21f19b2022f6e43c636b950da4248df36226b'}  # Exact recognized manifest bytes.
HELPERS = ['runners/run_aeonic_arithmetic.py', 'runners/run_aeonic_rational_arithmetic.py',
           'runners/temporal_civil_date_checks.py', 'runners/temporal_civil_datetime_checks.py',
           'runners/temporal_known_offset_checks.py']


class Runner(CommonRunner):
    def __init__(self, args):
        self.args = args; self.artifacts = {}; self.attempts = self.executions = self.assertions = 0
        self.strict_before_assertions = 0
        choice = getattr(args, 'capability_set', 'all')
        require(choice in {'relations', 'conversion', 'all'}, 'Unknown capability selection')
        self.selected = set(CAPABILITIES) if choice == 'all' else {choice}
        self.manifest_path = args.manifest.resolve()
        self.manifest = self.read(self.manifest_path)
        meta = self.manifest['meta']
        self.immutable = meta['conformance'] == dict(surface='known-offset', stable=True, publication='local-only')
        if self.immutable:
            require(IMMUTABLE_TARGETS.get(meta['snapshot_id']) == self.artifacts[self.manifest_path],
                    'Unrecognized or modified immutable known-offset target')
        else:
            require(meta['conformance'] == dict(surface='working-next', stable=False),
                    'Expected mutable next or recognized immutable known-offset target')
        require(set(self.manifest) == {'meta', 'suites'}, 'Unknown manifest fields')
        require(set(meta) == {'version', 'lane', 'profile', 'capabilities', 'sut_protocol',
                'conformance', 'description', 'snapshot_id', 'specification_schema',
                'specification_source', 'binding_schema', 'helpers', 'resource_limits',
                'specification_schema_sha256', 'specification_source_sha256',
                'binding_schema_sha256', 'specification_revision'} | ({'spec_snapshot_id'} if self.immutable else set()), 'Unknown or missing target metadata')
        require(meta['version'] == ('0.1.0' if self.immutable else '0.2.0-dev.0') and meta['sut_protocol'] == 'cts.protocol.v1', 'Wrong target version/protocol')
        require(meta['lane'] == LANE and meta['profile'] == PROFILE and (self.immutable or meta['snapshot_id'] == NEXT_TARGET),
                'Wrong known-offset target identity')
        require(meta['capabilities'] == {k: dict(id=v[0], operations=list(v[1])) for k, v in CAPABILITIES.items()},
                'Capability boundaries differ from the working contract')
        require(isinstance(meta['specification_revision'], str) and re.fullmatch('[0-9a-f]{40}', meta['specification_revision']), 'Exact specification revision required')
        root = self.manifest_path.parent

        def pinned(base, relative, sha, json_content=True):
            path = (base / relative).resolve()
            require(base.resolve() in path.parents, 'Pinned artifact escapes its owning root')
            content = path.read_bytes()
            require(hashlib.sha256(content).hexdigest() == sha, 'Artifact digest mismatch: ' + relative)
            self.artifacts[path] = sha
            return decode_artifact(content.decode('utf-8')) if json_content else content

        require(set(meta['helpers']) == set(HELPERS), 'Missing or unexpected checker helper')
        for relative, sha in meta['helpers'].items():
            pinned(ROOT, relative, sha, False)
        self.artifacts[Path(__file__).resolve()] = digest(Path(__file__).resolve())
        schema = pinned(args.specs_root, meta['specification_schema'], meta['specification_schema_sha256'])
        pinned(args.specs_root, meta['specification_source'], meta['specification_source_sha256'], False)
        binding = pinned(root, meta['binding_schema'], meta['binding_schema_sha256'])
        Draft202012Validator.check_schema(schema); Draft202012Validator.check_schema(binding)
        registry = Registry().with_resource(schema['$id'], Resource.from_contents(schema))
        self.request_schema = Draft202012Validator(schema, registry=registry)
        self.bundle_schema = Draft202012Validator({'$ref':schema['$id'] + '#/$defs/bundle'}, registry=registry)
        self.result_schema = Draft202012Validator({'$ref':schema['$id'] + '#/$defs/result'}, registry=registry)
        self.binding_schema = Draft202012Validator(binding)
        self.resource_limits = meta['resource_limits']
        names = set(binding['properties']['policy']['properties']['resourceLimits']['properties'])
        require(isinstance(self.resource_limits, dict) and set(self.resource_limits) == set(LIMITS) == names
                == set(schema['$defs']['resourceLimits']['properties']),
                'Every trusted limit must be explicitly selected')
        self.binding_schema.validate(dict(lane=LANE, case_id='limits', fixture=dict(request={}),
                                         policy=dict(resourceLimits=self.resource_limits)))
        self.tests = []; self.excluded = []; seen = set(); operation_coverage = set()
        require(isinstance(self.manifest['suites'], list) and self.manifest['suites'], 'Empty suite inventory')
        seen_suites = set()
        for suite in self.manifest['suites']:
            require(set(suite) == {'id', 'file', 'content_sha256'}, 'Unknown suite fields; semantic exclusions are not allowed')
            require(suite['id'] not in seen_suites, 'Duplicate suite identity')
            seen_suites.add(suite['id'])
            data = pinned(root, suite['file'], suite['content_sha256'])
            require(set(data) == {'id', 'tests'} and data['id'] == suite['id']
                    and isinstance(data['tests'], list) and data['tests'], 'Invalid or empty suite')
            for test in data['tests']:
                require(isinstance(test.get('id'), str) and test['id'] and test['id'] not in seen,
                        'Missing or duplicate case identity')
                seen.add(test['id']); positive_operation = self.validate_test(test)
                if set(test['requires']) <= self.selected:
                    self.tests.append(test)
                    if positive_operation:
                        operation_coverage.add(positive_operation)
                else:
                    self.excluded.append(test['id'])
        required_ops = {op for key in self.selected for op in CAPABILITIES[key][1]}
        require(required_ops <= operation_coverage, 'Selected capability lacks positive operation coverage')
        require(bool(self.tests), 'Empty capability target cannot validate or pass')
        self.validate_required_coverage()
        self.target_case_ids = tuple(t['id'] for t in self.tests)

    def validate_required_coverage(self):
        chains = set()
        has_laws = False
        for test in self.tests:
            kind = test.get('kind', 'operation')
            if kind == 'laws':
                law_witnesses(test['values'], self.resource_limits)
                has_laws = True
            elif kind == 'chain':
                for link in test['links']:
                    source, target = (test['steps'][link[k]] for k in ('fromStep', 'toStep'))
                    if source['expected']['outcome'] != 'value' or target['expected']['outcome'] != 'value':
                        continue
                    if source['request']['operation'] == target['request']['operation'] == 'convert' and link['input'] == 'value':
                        chains.add('conversion')
                    if (source['request']['operation'] == 'convert' and
                            target['request']['operation'] in CAPABILITIES['relations'][1] and link['input'] in {'left', 'right'}):
                        chains.add('combined')
        if 'conversion' in self.selected:
            require('conversion' in chains, 'Conversion requires a linked successful conversion-to-conversion chain')
        if 'relations' in self.selected:
            require(has_laws, 'Relations requires non-vacuous relation laws')
        if self.selected == set(CAPABILITIES):
            require('combined' in chains, 'Combined capability requires a linked conversion-to-relation chain')

    def read(self, path):
        content = path.read_bytes(); self.artifacts[path] = hashlib.sha256(content).hexdigest()
        return decode_artifact(content.decode('utf-8'))

    def limits(self, policy):
        return dict(self.resource_limits, **policy.get('resourceLimits', {}))

    def validate_result(self, result, limits):
        if isinstance(result, dict) and result.get('outcome') == 'diagnostic':
            context = result.get('context')
            if isinstance(context, dict) and isinstance(context.get('path'), str):
                validate_pointer_text(context['path'])
        if isinstance(result, dict) and result.get('outcome') == 'value':
            value = result.get('value')
            descriptor = value.get('temporal') if isinstance(value, dict) else None
            if isinstance(descriptor, dict) and descriptor.get('category') == 'knownOffsetDateTimeSet':
                raw = descriptor.get('pieces')
                if isinstance(raw, list):
                    require(len(raw) <= limits['maxOutputPieces'], 'Result exceeds output-piece allowance')
            compact_bytes(result, limits['maxResultBytes'])
        self.result_schema.validate(result)
        if result['outcome'] != 'value':
            return
        value = result['value']
        if 'temporal' in value:
            coverage(value, limits['maxOutputPieces'], limits, generated=True)

    def validate_positive(self, logical, result, limits):
        # Bounded admission/expansion precedes recursive schema traversal.
        expected = expected_positive(logical, limits)
        self.request_schema.validate(logical)
        require(equal(result, expected), 'Exact positive image, relation or metadata mismatch')

    def validate_operation(self, test):
        policy = test.get('policy', {})
        self.binding_schema.validate(dict(lane=LANE, case_id=test['id'], fixture=test['fixture'], policy=policy))
        limits = self.limits(policy); self.validate_result(test['expected'], limits)
        if test['expected']['outcome'] == 'value':
            fixture = test['fixture']
            if 'requestText' in fixture:
                require(len(fixture['requestText'].encode('utf-8')) <= limits['maxRequestBytes'], 'Successful text fixture exceeds byte allowance')
            else:
                compact_bytes(fixture['request'], limits['maxRequestBytes'])
            logical = fixture['request'] if 'request' in fixture else decode_request(fixture['requestText'])
            self.validate_positive(logical, test['expected'], limits)
            return logical
        return None

    def requirements(self, logical):
        if not isinstance(logical, dict):
            return set()
        op = logical.get('operation')
        return {key for key, (_, operations) in CAPABILITIES.items() if op in operations}

    def validate_test(self, test):
        require(isinstance(test.get('id'), str) and test['id']
                and not any(0xD800 <= ord(ch) <= 0xDFFF for ch in test['id']), 'Case identity must be nonempty Unicode-scalar text')
        require(isinstance(test.get('requires'), list) and len(test['requires']) == len(set(test['requires']))
                and set(test['requires']) <= set(CAPABILITIES), 'Invalid capability requirement')
        kind = test.get('kind', 'operation'); required = set(); positive_operation = None
        if kind == 'operation':
            require(set(test) <= {'id', 'kind', 'requires', 'fixture', 'policy', 'expected'}, 'Unknown operation case field')
            logical = self.validate_operation(test)
            fixture = test['fixture']
            if test['expected']['outcome'] == 'diagnostic' and test['expected']['context']['stage'] == 1:
                # Admission precedes dispatch: shared by all capabilities. Do not
                # recursively decode a raw body that the adapter must reject.
                required = set()
            elif logical is not None:
                required = self.requirements(logical)
                positive_operation = logical['operation']
            elif 'request' in fixture:
                required = self.requirements(fixture['request'])
            else:
                try:
                    logical = decode_request(fixture['requestText'])
                except (ValueError, RecursionError):
                    logical = None
                required = self.requirements(logical)
        elif kind == 'chain':
            require(set(test) == {'id', 'kind', 'requires', 'steps', 'links'}, 'Unknown chain fields')
            require(isinstance(test['steps'], list) and test['steps'], 'Chain cannot be empty')
            require(isinstance(test['links'], list) and test['links'], 'Chain needs actual returned-value links')
            targets = set()
            for link in test['links']:
                require(set(link) == {'fromStep', 'toStep', 'input'}, 'Malformed link')
                a, b = link['fromStep'], link['toStep']
                require(type(a) is int and type(b) is int and 0 <= a < b < len(test['steps']), 'Invalid chain order')
                require(link['input'] in {'left', 'right', 'value'} and link['input'] in test['steps'][b]['request']['input'], 'Invalid chain destination')
                require(test['steps'][a]['expected']['outcome'] == 'value' and 'temporal' in test['steps'][a]['expected']['value'], 'Only temporal values can feed a known-offset chain')
                target = (b, link['input']); require(target not in targets, 'Duplicate chain destination'); targets.add(target)
            for i, step in enumerate(test['steps']):
                require(set(step) <= {'request', 'policy', 'expected'} and {'request', 'expected'} <= set(step), 'Invalid chain step')
                logical = copy.deepcopy(step['request'])
                for link in test['links']:
                    if link['toStep'] == i:
                        logical['input'][link['input']] = copy.deepcopy(test['steps'][link['fromStep']]['expected']['value'])
                required |= self.requirements(logical)
                self.validate_operation(dict(id=test['id'] + '/' + str(i), fixture=dict(request=logical), expected=step['expected'], policy=step.get('policy', {})))
        elif kind == 'laws':
            require(set(test) == {'id', 'kind', 'requires', 'values'}, 'Unknown law fields')
            require(isinstance(test['values'], list) and 3 <= len(test['values']) <= 8, 'Law group needs 3–8 values')
            required = {'relations'}
            for value in test['values']:
                self.bundle_schema.validate(value); coverage(value, self.resource_limits['maxInputPieces'], self.resource_limits)
            law_witnesses(test['values'], self.resource_limits)
            for left, right in itertools.product(test['values'], repeat=2):
                for op in CAPABILITIES['relations'][1]:
                    expected_positive(dict(operation=op, input=dict(left=left, right=right, context=dict(profile=PROFILE))), self.resource_limits)
        else:
            raise ValueError('Unknown case kind')
        require(set(test['requires']) == required, 'Case capability requirements differ from its operations: ' + test['id'])
        return positive_operation

    execute = BoundedTransport.execute

    def invoke(self, case_id, fixture, policy):
        envelope = dict(lane=LANE, case_id=case_id, fixture=fixture, policy=policy)
        self.binding_schema.validate(envelope)
        limits = self.limits(policy); envelope['policy'] = dict(resourceLimits=limits)
        self.attempts += 1
        raw = self.execute(envelope)
        self.executions += 1
        output = decode(raw)
        require(isinstance(output, dict), 'Protocol output must be an object')
        actual = output.get('result'); self.validate_result(actual, limits)
        ok = actual['outcome'] == 'value'
        require(type(output.get('ok')) is bool and output['ok'] == ok, 'Protocol ok mismatch')
        require(output.get('warnings') == [], 'Unexpected warnings')
        errors = output.get('errors')
        if ok:
            require(errors == [], 'Unexpected errors')
        else:
            require(isinstance(errors, list) and len(errors) == 1 and isinstance(errors[0], dict), 'One protocol error required')
            for key, value in dict(code=actual['reason'], path=None, span=None, phase=None).items():
                require(key in errors[0] and equal(errors[0][key], value), 'Protocol diagnostic mismatch')
        return actual

    def operation(self, test):
        actual = self.invoke(test['id'], test['fixture'], test.get('policy', {}))
        expected = test['expected']
        if actual['outcome'] == 'diagnostic':
            actual = {k:v for k,v in actual.items() if k != 'message'}
        if expected['outcome'] == 'diagnostic':
            expected = {k:v for k,v in expected.items() if k != 'message'}
        require(equal(actual, expected), 'Result mismatch: ' + repr(actual)[:300])
        self.assertions += 1
        return actual

    def laws(self, test):
        values = test['values']; spans = [common(v, self.resource_limits['maxInputPieces'], self.resource_limits) for v in values]
        observed = {}
        for i, j in itertools.product(range(len(values)), repeat=2):
            labels = relation_labels(spans[i], spans[j])
            for op in CAPABILITIES['relations'][1]:
                logical = dict(operation=op, input=dict(left=values[i], right=values[j], context=dict(profile=PROFILE)))
                expected = relation_result(op, values[i], values[j], labels[op])
                actual = self.operation(dict(id=test['id'] + '/%s-%d-%d' % (op, i, j), fixture=dict(request=logical), expected=expected))
                observed[(op, i, j)] = actual['value']['value']
        inverse = dict(equal='equal', before='after', after='before', indeterminate='indeterminate')
        inverse_set = dict(equal='equal', contains='containedBy', containedBy='contains', overlaps='overlaps', disjoint='disjoint')
        for i, j in itertools.product(range(len(values)), repeat=2):
            self.assertion(observed['equal',i,j] == observed['equal',j,i], 'equality symmetry')
            self.assertion(observed['compare',i,j] == inverse[observed['compare',j,i]], 'chronology inversion')
            self.assertion(observed['relate',i,j] == inverse_set[observed['relate',j,i]], 'set relation inversion')
        start_before = self.strict_before_assertions
        for i, j, k in itertools.product(range(len(values)), repeat=3):
            if observed[('equal', i, j)] == observed[('equal', j, k)] == 'equal':
                self.assertion(observed[('equal', i, k)] == 'equal', 'extent equality transitivity')
            if observed[('compare', i, j)] == observed[('compare', j, k)] == 'before':
                self.assertion(observed[('compare', i, k)] == 'before', 'strict-before transitivity')
                self.strict_before_assertions += 1

        require(self.strict_before_assertions > start_before, 'No strict-before transitivity assertions executed')

    def run(self, check_only=False):
        failures = []; counts = dict(operation_cases=0, chains=0, law_groups=0)
        coverage_valid = True
        try:
            self.validate_required_coverage()
        except ValueError as error:
            coverage_valid = False
            failures.append(dict(id='required-coverage', failure=str(error)))
        start_attempts, start_executions, start_assertions = self.attempts, self.executions, self.assertions
        start_before = self.strict_before_assertions
        expected_executions = sum(1 if t.get('kind', 'operation') == 'operation' else
            len(t['steps']) if t['kind'] == 'chain' else 3 * len(t['values']) ** 2 for t in self.tests)
        for test in self.tests:
            kind = test.get('kind', 'operation'); counts[{'operation':'operation_cases','chain':'chains','laws':'law_groups'}[kind]] += 1
            if check_only:
                continue
            try:
                getattr(self, {'operation':'operation','chain':'chain','laws':'laws'}[kind])(test)
            except Exception as error:
                failures.append(dict(id=test['id'], failure=str(error)[:1500]))
        complete = (not check_only and coverage_valid
                    and ('relations' not in self.selected or self.strict_before_assertions > start_before)
                    and tuple(t['id'] for t in self.tests) == self.target_case_ids
                    and self.executions - start_executions == expected_executions
                    and self.assertions - start_assertions >= expected_executions)
        if not check_only and not complete:
            failures.append(dict(id='execution-completeness', failure='Every selected case and chain/law invocation must execute and assert'))
        for path, sha in self.artifacts.items():
            if not path.exists() or digest(path) != sha:
                failures.append(dict(id='artifact-integrity', failure='Artifact changed during run: ' + path.name))
        return dict(status='failed' if failures else 'artifacts-validated' if check_only else 'passed',
                    target=self.manifest['meta']['snapshot_id'],
                    target_status='immutable-local' if self.immutable else 'mutable-working',
                    # Replies establish a protocol result, not how the provider
                    # computed it. Genuine implementation qualification is external.
                    stable_conformance_claim=False, semantic_execution=False,
                    protocol_execution=self.executions > start_executions, provider_execution_verified=False,
                    complete_passing_execution=complete and not failures,
                    capabilities=sorted(self.selected),
                    excluded_unclaimed_capability_cases=len(self.excluded), **counts,
                    sut_attempts=self.attempts - start_attempts,
                    sut_executions=self.executions - start_executions, assertions=self.assertions - start_assertions,
                    strict_before_transitivity_assertions=self.strict_before_assertions - start_before,
                    manifest_sha256=self.artifacts[self.manifest_path], runner_sha256=self.artifacts[Path(__file__).resolve()],
                    specification_source_sha256=self.manifest['meta']['specification_source_sha256'],
                    specification_schema_sha256=self.manifest['meta']['specification_schema_sha256'],
                    helper_hashes=self.manifest['meta']['helpers'], resource_limits=self.resource_limits,
                    sut=self.args.sut, cwd=str(self.args.cwd.resolve()), failures=failures)

    def validate_report_destination(self, destination):
        # replace() changes the leaf entry, not a leaf symlink's referent. Check
        # both, including entry paths reached through parent-directory symlinks.
        paths = {Path(os.path.abspath(destination)),
                 destination.parent.resolve() / destination.name, destination.resolve()}
        def inside(path, root):
            if path == root or root in path.parents:
                return True
            # Filesystem identity also covers case aliases on case-insensitive
            # hosts without treating the leaf referent as the replacement entry.
            return root.exists() and any(parent.exists() and os.path.samefile(parent, root)
                                         for parent in (path, *path.parents))
        reserved = [ROOT / 'cts', ROOT / 'runners', self.args.specs_root]
        for root in reserved:
            for location in {Path(os.path.abspath(root)), root.resolve()}:
                require(not any(inside(path, location) for path in paths),
                        'Report destination overlaps an input tree')
        for artifact in self.artifacts:
            require(artifact.resolve() not in paths and
                    not (destination.exists() and artifact.exists() and os.path.samefile(destination, artifact)),
                    'Report destination overlaps a pinned input')

    def write_report(self, destination, text):
        self.validate_report_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                    dir=destination.parent, prefix='.known-offset-report-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(text)
            self.validate_report_destination(destination)
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'cts/aeonic-temporal-known-offset/v1/aeonic-temporal-known-offset-cts.v1.snapshot-0.1.json')
    parser.add_argument('--specs-root', type=Path, required=True)
    parser.add_argument('--capability-set', choices=['relations', 'conversion', 'all'], default='all')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--sut'); parser.add_argument('--cwd', type=Path, default=Path.cwd())
    parser.add_argument('--timeout', type=float, default=20); parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    require(args.check or args.sut, '--sut required unless --check selected')
    require(0 < args.timeout < float('inf'), 'Timeout must be positive and finite')
    runner = Runner(args)
    if args.report:
        runner.validate_report_destination(args.report)
    report = runner.run(check_only=args.check); text = json.dumps(report, indent=2) + '\n'
    if args.report:
        runner.write_report(args.report, text)
    print(text, end=''); return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('CTS harness failure: ' + str(error), file=sys.stderr); sys.exit(2)
