#!/usr/bin/env python3
"""Run recognized civil anchoring snapshot0.1 or explicit mutable next; Python 3.9+."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from run_aeonic_arithmetic import decode, digest, equal, require
from run_aeonic_rational_arithmetic import Runner as BoundedTransport
from temporal_civil_anchor_checks import (PROFILE, CAPABILITY, LIMITS, compact_bytes,
    decode_artifact, expected_positive, validate_pointer_text)

ROOT = Path(__file__).resolve().parents[1]
LANE = 'aeonic-temporal-civil-anchor'
NEXT_TARGET = LANE+'-cts-v1-snapshot-0.2'
IMMUTABLE_TARGETS = {LANE+'-cts-v1-snapshot-0.1': '2512f3524c0bc0ba0dd561a769a7a4dc548c3c48fef72c4a945980193eca2b9b'}
HELPERS = ['runners/run_aeonic_arithmetic.py', 'runners/run_aeonic_rational_arithmetic.py',
           'runners/temporal_civil_date_checks.py', 'runners/temporal_civil_anchor_checks.py']


class Runner:
    def __init__(self, args):
        self.args = args; self.artifacts = {}; self.executions = self.assertions = 0
        self.manifest_path = args.manifest.resolve()
        self.manifest = self.read(self.manifest_path)
        require(set(self.manifest) == {'meta', 'suites'}, 'Unknown manifest fields')
        meta = self.manifest['meta']
        self.immutable = meta.get('conformance') == dict(surface='civil-anchor', stable=True, publication='local-only')
        if self.immutable:
            require(IMMUTABLE_TARGETS.get(meta.get('snapshot_id')) == self.artifacts[self.manifest_path],
                    'Unrecognized or modified immutable civil-anchor target')
        else:
            require(meta.get('conformance') == dict(surface='working-next', stable=False),
                    'Expected mutable next or recognized immutable civil-anchor target')
        require(set(meta) == {'version', 'lane', 'profile', 'capability', 'operations',
                'sut_protocol', 'conformance', 'description', 'snapshot_id',
                'specification_revision', 'specification_source', 'specification_schema',
                'specification_source_sha256', 'specification_schema_sha256',
                'reuse_inventory', 'reuse_inventory_sha256', 'binding_schema',
                'binding_schema_sha256', 'helpers', 'resource_limits'} | ({'spec_snapshot_id'} if self.immutable else set()), 'Unknown or missing metadata')
        require(meta['version'] == ('0.1.0' if self.immutable else '0.2.0-dev.0') and meta['lane'] == LANE and
                meta['profile'] == PROFILE and meta['capability'] == CAPABILITY and
                meta['operations'] == ['anchor'] and meta['sut_protocol'] == 'cts.protocol.v1', 'Wrong lane identity')
        if self.immutable:
            require(meta['spec_snapshot_id'] == LANE+'-specs-v1-snapshot-0.1', 'Wrong owning specification snapshot')
        else:
            require(meta['snapshot_id'] == NEXT_TARGET, 'Wrong mutable next identity')
        require(isinstance(meta['specification_revision'], str) and
                re.fullmatch('[0-9a-f]{40}', meta['specification_revision']) is not None, 'Exact specs revision required')
        require(set(meta['helpers']) == set(HELPERS), 'Unexpected or missing helper')
        for file, sha in meta['helpers'].items(): self.pinned(ROOT, file, sha, False)
        self.artifacts[Path(__file__).resolve()] = digest(Path(__file__).resolve())
        schema = self.pinned(args.specs_root, meta['specification_schema'], meta['specification_schema_sha256'])
        self.pinned(args.specs_root, meta['specification_source'], meta['specification_source_sha256'], False)
        reuse = self.pinned(args.specs_root, meta['reuse_inventory'], meta['reuse_inventory_sha256'])
        require(set(reuse) == {'description', 'revision', 'artifacts'} and
                reuse['revision'] == '29b3a0b52d9709a9937d9b48f23eefcab0e35aea', 'Wrong frozen reuse authority')
        expected_files = {'resources/aeonic-operations/v1/snapshots/0.1/'+f
            for family in ['civil-date','civil-clock','civil-datetime']
            for f in [family+'-contract.schema.json','aeonic-temporal-'+family+'-v1.aeon']}
        require(isinstance(reuse['artifacts'], list) and len(reuse['artifacts']) == 6 and
                {v['file'] for v in reuse['artifacts']} == expected_files, 'Incomplete reuse inventory')
        for record in reuse['artifacts']:
            require(set(record) == {'file', 'sha256'}, 'Unknown reuse fields')
            self.pinned(args.specs_root, record['file'], record['sha256'], False)
        binding = self.pinned(self.manifest_path.parent, meta['binding_schema'], meta['binding_schema_sha256'])
        Draft202012Validator.check_schema(schema); Draft202012Validator.check_schema(binding)
        self.schema = schema
        registry = Registry().with_resource(schema['$id'], Resource.from_contents(schema))
        self.request_schema = Draft202012Validator(schema, registry=registry)
        self.result_schema = Draft202012Validator({'$ref':schema['$id']+'#/$defs/result'}, registry=registry)
        self.binding_schema = Draft202012Validator(binding)
        self.resource_limits = meta['resource_limits']
        require(isinstance(self.resource_limits, dict) and set(self.resource_limits) == set(LIMITS)
                == set(schema['$defs']['resourceLimits']['properties'])
                == set(binding['properties']['policy']['properties']['resourceLimits']['properties']), 'Complete limits required')
        self.binding_schema.validate(dict(lane=LANE, case_id='limits', fixture=dict(request={}),
                                         policy=dict(resourceLimits=self.resource_limits)))
        require(isinstance(self.manifest['suites'], list) and self.manifest['suites'], 'Empty target')
        self.tests = []; seen = set(); suites = set()
        for suite in self.manifest['suites']:
            require(set(suite) == {'id', 'file', 'content_sha256'} and suite['id'] not in suites, 'Invalid suite reference')
            suites.add(suite['id'])
            data = self.pinned(self.manifest_path.parent, suite['file'], suite['content_sha256'])
            require(set(data) == {'id', 'tests'} and data['id'] == suite['id'] and
                    isinstance(data['tests'], list) and data['tests'], 'Invalid or empty suite')
            for test in data['tests']:
                require(isinstance(test.get('id'), str) and bool(test['id']) and test['id'] not in seen, 'Missing or duplicate case id')
                seen.add(test['id']); self.validate_test(test); self.tests.append(test)
        require(any(t['expected']['outcome'] == 'value' for t in self.tests), 'No positive operation coverage')
        require(any(t['expected']['outcome'] == 'diagnostic' for t in self.tests), 'No diagnostic coverage')
        self.target_case_ids = tuple(test['id'] for test in self.tests)

    def read(self, path):
        data = path.read_bytes(); self.artifacts[path] = hashlib.sha256(data).hexdigest()
        return decode_artifact(data.decode('utf-8'))

    def pinned(self, base, relative, sha, structured=True):
        require(isinstance(relative, str) and isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha), 'Invalid artifact pin')
        path = (base/relative).resolve()
        require(base.resolve() in path.parents, 'Artifact escapes owning root')
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == sha, 'Artifact digest mismatch: '+relative)
        self.artifacts[path] = sha
        return decode_artifact(data.decode('utf-8')) if structured else data

    def limits(self, policy):
        return dict(self.resource_limits, **policy.get('resourceLimits', {}))

    def validate_result(self, result, limits):
        if isinstance(result, dict) and result.get('outcome') == 'diagnostic':
            context = result.get('context')
            if isinstance(context, dict) and isinstance(context.get('path'), str):
                validate_pointer_text(context['path'])
        if isinstance(result, dict) and result.get('outcome') == 'value':
            value = result.get('value'); td = value.get('temporal') if isinstance(value, dict) else None
            if isinstance(td, dict) and isinstance(td.get('pieces'), list):
                require(len(td['pieces']) <= limits['maxOutputPieces'], 'Result exceeds output-piece allowance')
            compact_bytes(result, limits['maxResultBytes'])
        self.result_schema.validate(result)

    def validate_test(self, test):
        require(set(test) <= {'id', 'fixture', 'policy', 'expected'} and
                {'id', 'fixture', 'expected'} <= set(test), 'Unknown or missing case field; no opt-outs')
        policy = test.get('policy', {})
        self.binding_schema.validate(dict(lane=LANE, case_id=test['id'], fixture=test['fixture'], policy=policy))
        limits = self.limits(policy); self.validate_result(test['expected'], limits)
        if test['expected']['outcome'] == 'value':
            fixture = test['fixture']
            if 'request' in fixture:
                logical = fixture['request']
            else:
                text = fixture['requestText']
                require(len(text.encode('utf-8')) <= limits['maxRequestBytes'], 'Successful text exceeds byte limit')
                logical = decode_artifact('{"fixture":{"request":'+text+'}}')['fixture']['request']
            # Bounded positive admission precedes schema traversal of potentially
            # oversized payloads. This helper never creates staged diagnostics.
            expected = expected_positive(logical, limits)
            self.request_schema.validate(logical)
            require(equal(expected, test['expected']), 'Positive exact image/metadata mismatch')

    execute = BoundedTransport.execute

    def invoke(self, test):
        policy = test.get('policy', {}); limits = self.limits(policy)
        envelope = dict(lane=LANE, case_id=test['id'], fixture=test['fixture'], policy=dict(resourceLimits=limits))
        self.binding_schema.validate(envelope)
        self.executions += 1; output = decode(self.execute(envelope))
        require(isinstance(output, dict), 'Protocol output must be an object')
        actual = output.get('result'); self.validate_result(actual, limits)
        ok = actual['outcome'] == 'value'
        require(type(output.get('ok')) is bool and output['ok'] == ok, 'Protocol ok mismatch')
        require(output.get('warnings') == [], 'Unexpected warnings')
        errors = output.get('errors')
        if ok:
            require(errors == [], 'Unexpected protocol errors')
        else:
            require(isinstance(errors, list) and len(errors) == 1 and isinstance(errors[0], dict), 'One protocol error required')
            for key, value in dict(code=actual['reason'], path=None, span=None, phase=None).items():
                require(key in errors[0] and equal(errors[0][key], value), 'Protocol diagnostic mismatch')
        return actual

    def operation(self, test):
        actual = self.invoke(test); expected = test['expected']
        if actual['outcome'] == 'diagnostic': actual = {k:v for k,v in actual.items() if k != 'message'}
        if expected['outcome'] == 'diagnostic': expected = {k:v for k,v in expected.items() if k != 'message'}
        require(equal(actual, expected), 'Complete result mismatch: '+repr(actual)[:300])
        self.assertions += 1
        return actual

    def run(self, check_only=False):
        failures = []
        initial_executions, initial_assertions = self.executions, self.assertions
        if not check_only:
            for test in self.tests:
                try: self.operation(test)
                except Exception as error: failures.append(dict(id=test['id'], failure=str(error)[:1500]))
        complete = (not check_only and tuple(t['id'] for t in self.tests) == self.target_case_ids
                    and self.executions-initial_executions == len(self.target_case_ids)
                    and self.assertions-initial_assertions == len(self.target_case_ids))
        if not check_only and not complete:
            failures.append(dict(id='execution-completeness', failure='Every mandatory case must execute and pass in this run'))
        for path, sha in self.artifacts.items():
            if not path.exists() or digest(path) != sha:
                failures.append(dict(id='artifact-integrity', failure='Artifact changed during run: '+path.name))
        return dict(status='failed' if failures else 'artifacts-validated' if check_only else 'passed',
                    target=self.manifest['meta']['snapshot_id'], target_status='immutable-local' if self.immutable else 'mutable-working',
                    stable_conformance_claim=self.immutable and not check_only and not failures, semantic_execution=not check_only,
                    complete_passing_execution=complete and not failures,
                    capability=CAPABILITY, operation_cases=len(self.tests),
                    sut_executions=self.executions, assertions=self.assertions,
                    manifest_sha256=self.artifacts[self.manifest_path], runner_sha256=digest(Path(__file__).resolve()),
                    specification_revision=self.manifest['meta']['specification_revision'],
                    specification_source_sha256=self.manifest['meta']['specification_source_sha256'],
                    specification_schema_sha256=self.manifest['meta']['specification_schema_sha256'],
                    helper_hashes=self.manifest['meta']['helpers'], resource_limits=self.resource_limits,
                    sut=self.args.sut, cwd=str(self.args.cwd.resolve()), failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'cts/aeonic-temporal-civil-anchor/v1/aeonic-temporal-civil-anchor-cts.v1.snapshot-0.1.json')
    parser.add_argument('--specs-root', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--sut'); parser.add_argument('--cwd', type=Path, default=Path.cwd())
    parser.add_argument('--timeout', type=float, default=20); parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    require(args.check or args.sut, '--sut required unless --check selected')
    require(0 < args.timeout < float('inf'), 'Timeout must be positive and finite')
    report = Runner(args).run(args.check); text = json.dumps(report, indent=2)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(text, encoding='utf-8')
    print(text, end=''); return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as error:
        print('CTS harness failure: '+str(error), file=sys.stderr); sys.exit(2)
