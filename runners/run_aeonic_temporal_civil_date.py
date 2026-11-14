#!/usr/bin/env python3
"""Pinned mutable civil-date CTS; independent complete capabilities, Python 3.9+."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from run_aeonic_arithmetic import Runner as CommonRunner, decode, digest, equal, require
from run_aeonic_rational_arithmetic import Runner as BoundedTransport
from temporal_civil_date_checks import (PROFILE, CAPABILITIES, LIMITS, MARKED,
    compact_bytes, coverage, decode_artifact, effective, history, origin, positive_work,
    relation_labels, relation_result, validate_pointer_text)

ROOT = Path(__file__).resolve().parents[1]
LANE = 'aeonic-temporal-civil-date'
TARGET = LANE + '-cts-v1-snapshot-0.1'
HELPERS = ['runners/run_aeonic_arithmetic.py', 'runners/run_aeonic_rational_arithmetic.py',
           'runners/temporal_civil_date_checks.py']


class Runner(CommonRunner):
    def __init__(self, args):
        self.args = args; self.artifacts = {}; self.executions = self.assertions = 0
        self.immutable = False
        choice = getattr(args, 'capability_set', 'all')
        require(choice in {'relations', 'calendar', 'all'}, 'Unknown capability selection')
        self.selected = set(CAPABILITIES) if choice == 'all' else {choice}
        self.manifest_path = args.manifest.resolve()
        self.manifest = self.read(self.manifest_path)
        meta = self.manifest['meta']
        require(set(self.manifest) == {'meta', 'suites'}, 'Unknown manifest fields')
        require(set(meta) == {'version', 'lane', 'profile', 'capabilities', 'sut_protocol',
                'conformance', 'description', 'snapshot_id', 'specification_schema',
                'specification_source', 'binding_schema', 'helpers', 'resource_limits',
                'specification_schema_sha256', 'specification_source_sha256',
                'binding_schema_sha256', 'specification_revision'}, 'Unknown or missing target metadata')
        require(meta['version'] == '0.1.0-dev.0' and meta['sut_protocol'] == 'cts.protocol.v1', 'Wrong target version/protocol')
        require(meta['lane'] == LANE and meta['profile'] == PROFILE and meta['snapshot_id'] == TARGET,
                'Wrong civil-date working identity')
        require(meta['conformance'] == dict(surface='working-next', stable=False),
                'Civil-date target is mutable only; no immutable recognition exists')
        require(meta['capabilities'] == {k: dict(id=v[0], operations=list(v[1])) for k, v in CAPABILITIES.items()},
                'Capability boundaries differ from the working contract')
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
        for suite in self.manifest['suites']:
            require(set(suite) == {'id', 'file', 'content_sha256'}, 'Unknown suite fields; semantic exclusions are not allowed')
            data = pinned(root, suite['file'], suite['content_sha256'])
            require(data['id'] == suite['id'] and isinstance(data['tests'], list), 'Invalid suite identity')
            for test in data['tests']:
                require(isinstance(test.get('id'), str) and test['id'] and test['id'] not in seen,
                        'Missing or duplicate case identity')
                seen.add(test['id']); self.validate_test(test)
                if set(test['requires']) <= self.selected:
                    self.tests.append(test)
                    if test.get('kind', 'operation') == 'operation' and test['expected']['outcome'] == 'value':
                        logical = test['fixture'].get('request')
                        if logical:
                            operation_coverage.add(logical['operation'])
                else:
                    self.excluded.append(test['id'])
        required_ops = {op for key in self.selected for op in CAPABILITIES[key][1]}
        require(required_ops <= operation_coverage, 'Selected capability lacks positive operation coverage')
        require(bool(self.tests), 'Empty capability target cannot validate or pass')

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
            # Work/input/output allowances are distinct. Stop on successful
            # envelope/range size before JSON Schema iterates every range.
            value = result.get('value')
            descriptor = value.get('temporal') if isinstance(value, dict) else None
            if isinstance(descriptor, dict) and descriptor.get('category') == 'civilDateSet':
                raw = descriptor.get('ranges')
                if isinstance(raw, list):
                    require(len(raw) <= limits['maxOutputRanges'], 'Result exceeds output-range allowance')
            compact_bytes(result, limits['maxResultBytes'])
        self.result_schema.validate(result)
        if result['outcome'] != 'value':
            return
        value = result['value']
        if 'temporal' in value:
            descriptor = value['temporal']
            coverage(value, limits['maxOutputRanges'] if descriptor['category'] == 'civilDateSet' else 1)
            if descriptor['category'] == 'civilDate':
                require(len(descriptor['value']) <= limits['maxOutputCharacters'], 'Result exceeds emitted-date allowance')
            if result['metadata']['clamping'] == 'applied':
                require(value['history'] == MARKED, 'Current clamping must declare history')

    def validate_positive(self, logical, result, limits):
        data = logical['input']; binary = logical['operation'] in CAPABILITIES['relations'][1]
        operands = [data['left'], data['right']] if binary else [data['value']]
        for operand in operands:
            descriptor = operand.get('temporal', {})
            if descriptor.get('category') == 'civilDateSet' and isinstance(descriptor.get('ranges'), list):
                require(len(descriptor['ranges']) <= limits['maxInputRanges'], 'Successful fixture exceeds input-range allowance')
        policy = data.get('policy', {})
        if isinstance(policy.get('count'), str):
            require(len(policy['count']) <= limits['maxCountCharacters'], 'Successful count exceeds selected allowance')
        self.request_schema.validate(logical)
        spans = []
        for operand in operands:
            require(operand['temporal']['category'] in {'civilDate', 'civilDateSet'}, 'Successful fixture has deferred operand')
            spans.append(coverage(operand, limits['maxInputRanges']))
        require(positive_work(logical, spans) <= limits['maxCalendarWork'], 'Successful fixture exceeds selected calendar-work allowance')
        require(result['metadata']['effectivePolicy'] == effective(logical), 'Fixture effective-policy mismatch')
        if binary:
            expected = dict(left=history(operands[0]), right=history(operands[1]))
            require(result['metadata']['operandHistory'] == expected, 'Fixture operand-history mismatch')
        else:
            value = result['value']; clamped = result['metadata']['clamping'] == 'applied'
            marker = MARKED if clamped or history(operands[0]) == MARKED else 'none-declared'
            require(value['history'] == marker and value['originGranularity'] == origin(operands[0]),
                    'Fixture history/origin propagation mismatch')
            if logical['operation'] == 'materialize':
                require(coverage(value, 1) == spans[0], 'Materialized fixture changes exact coverage')

    def validate_operation(self, test):
        policy = test.get('policy', {})
        self.binding_schema.validate(dict(lane=LANE, case_id=test['id'], fixture=test['fixture'], policy=policy))
        limits = self.limits(policy); self.validate_result(test['expected'], limits)
        if test['expected']['outcome'] == 'value':
            fixture = test['fixture']
            logical = fixture['request'] if 'request' in fixture else decode_artifact('{"fixture":{"request":' + fixture['requestText'] + '}}')['fixture']['request']
            self.validate_positive(logical, test['expected'], limits)

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
        kind = test.get('kind', 'operation'); required = set()
        if kind == 'operation':
            require(set(test) <= {'id', 'kind', 'requires', 'fixture', 'policy', 'expected'}, 'Unknown operation case field')
            self.validate_operation(test)
            fixture = test['fixture']
            if 'request' in fixture:
                required = self.requirements(fixture['request'])
            else:
                try:
                    logical = decode(fixture['requestText'])
                except (ValueError, json.JSONDecodeError):
                    logical = None
                required = self.requirements(logical)
        elif kind == 'chain':
            require(set(test) == {'id', 'kind', 'requires', 'steps', 'links'}, 'Unknown chain fields')
            require(isinstance(test['steps'], list) and test['steps'], 'Chain cannot be empty')
            targets = set()
            for link in test['links']:
                require(set(link) == {'fromStep', 'toStep', 'input'}, 'Malformed link')
                a, b = link['fromStep'], link['toStep']
                require(type(a) is int and type(b) is int and 0 <= a < b < len(test['steps']), 'Invalid chain order')
                require(link['input'] in {'left', 'right', 'value'} and link['input'] in test['steps'][b]['request']['input'], 'Invalid chain destination')
                require(test['steps'][a]['expected']['outcome'] == 'value' and 'temporal' in test['steps'][a]['expected']['value'], 'Only temporal values can feed a date chain')
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
                self.bundle_schema.validate(value); coverage(value, self.resource_limits['maxInputRanges'])
        else:
            raise ValueError('Unknown case kind')
        require(set(test['requires']) == required, 'Case capability requirements differ from its operations: ' + test['id'])

    execute = BoundedTransport.execute

    def invoke(self, case_id, fixture, policy):
        envelope = dict(lane=LANE, case_id=case_id, fixture=fixture, policy=policy)
        self.binding_schema.validate(envelope)
        limits = self.limits(policy); envelope['policy'] = dict(resourceLimits=limits)
        self.executions += 1; output = decode(self.execute(envelope))
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
        values = test['values']; spans = [coverage(v, self.resource_limits['maxInputRanges']) for v in values]
        observed = {}
        for i, j in itertools.product(range(len(values)), repeat=2):
            labels = relation_labels(spans[i], spans[j])
            for op in CAPABILITIES['relations'][1]:
                logical = dict(operation=op, input=dict(left=values[i], right=values[j], context=dict(profile=PROFILE)))
                expected = relation_result(op, values[i], values[j], labels[op])
                actual = self.operation(dict(id=test['id'] + '/%s-%d-%d' % (op, i, j), fixture=dict(request=logical), expected=expected))
                observed[(op, i, j)] = actual['value']['value']
        for i, j, k in itertools.product(range(len(values)), repeat=3):
            if observed[('equal', i, j)] == observed[('equal', j, k)] == 'equal':
                self.assertion(observed[('equal', i, k)] == 'equal', 'extent equality transitivity')
            if observed[('compare', i, j)] == observed[('compare', j, k)] == 'before':
                self.assertion(observed[('compare', i, k)] == 'before', 'strict-before transitivity')

    def run(self, check_only=False):
        failures = []; counts = dict(operation_cases=0, chains=0, law_groups=0)
        for test in self.tests:
            kind = test.get('kind', 'operation'); counts[{'operation':'operation_cases','chain':'chains','laws':'law_groups'}[kind]] += 1
            if check_only:
                continue
            try:
                getattr(self, {'operation':'operation','chain':'chain','laws':'laws'}[kind])(test)
            except Exception as error:
                failures.append(dict(id=test['id'], failure=str(error)[:1500]))
        for path, sha in self.artifacts.items():
            if not path.exists() or digest(path) != sha:
                failures.append(dict(id='artifact-integrity', failure='Artifact changed during run: ' + path.name))
        return dict(status='failed' if failures else 'artifacts-validated' if check_only else 'passed',
                    target=TARGET, target_status='mutable-working', stable_conformance_claim=False,
                    semantic_execution=not check_only, capabilities=sorted(self.selected),
                    excluded_unclaimed_capability_cases=len(self.excluded), **counts,
                    sut_executions=self.executions, assertions=self.assertions,
                    manifest_sha256=self.artifacts[self.manifest_path], runner_sha256=self.artifacts[Path(__file__).resolve()],
                    specification_source_sha256=self.manifest['meta']['specification_source_sha256'],
                    specification_schema_sha256=self.manifest['meta']['specification_schema_sha256'],
                    helper_hashes=self.manifest['meta']['helpers'], resource_limits=self.resource_limits,
                    sut=self.args.sut, cwd=str(self.args.cwd.resolve()), failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'cts/aeonic-temporal-civil-date/v1/aeonic-temporal-civil-date-cts.v1.next.json')
    parser.add_argument('--specs-root', type=Path, required=True)
    parser.add_argument('--capability-set', choices=['relations', 'calendar', 'all'], default='all')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--sut'); parser.add_argument('--cwd', type=Path, default=Path.cwd())
    parser.add_argument('--timeout', type=float, default=20); parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    require(args.check or args.sut, '--sut required unless --check selected')
    require(0 < args.timeout < float('inf'), 'Timeout must be positive and finite')
    report = Runner(args).run(check_only=args.check); text = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(text, encoding='utf-8')
    print(text, end=''); return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('CTS harness failure: ' + str(error), file=sys.stderr); sys.exit(2)
