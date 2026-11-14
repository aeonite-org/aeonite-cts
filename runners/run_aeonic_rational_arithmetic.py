#!/usr/bin/env python3
"""Validate or execute pinned rational-arithmetic targets; Python 3.9+."""
import argparse
import copy
import hashlib
import itertools
import json
from math import gcd
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from run_aeonic_arithmetic import Runner as CommonRunner, decode, digest, encode, equal, require

ROOT = Path(__file__).resolve().parents[1]
LANE = 'aeonic-rational-arithmetic'
PROFILE = 'aeonic.operations.arithmetic.rational.v1'
NONE, MARKED = 'none-declared', 'approximation-declared'
MODES = ('half-even', 'half-away-from-zero', 'half-toward-zero',
         'toward-zero', 'away-from-zero', 'floor', 'ceiling')
MAX_PROTOCOL_BYTES = 8 * 1024 * 1024
IMMUTABLE_TARGETS = {'aeonic-rational-arithmetic-cts-v1-snapshot-0.2': '1165459e1151e5cca325bc86c7d1e92de97c2b4ec115c02b10a30c59d4bc57a7'}  # Exact reviewed manifest bytes; next targets never enter this map.


def exact(c, e='0', d=None, history=NONE):
    descriptor = dict(category='exactNumber' if d is None else 'exactRational',
                      coefficient=c, exponent=e)
    if d is not None:
        descriptor['denominator'] = d
    return dict(number=descriptor, history=history)


def request(operation, a, b=None, policy=None):
    data = dict(value=a) if operation in {'quantize', 'materialize'} else dict(left=a, right=b)
    data['context'] = dict(profile=PROFILE)
    if policy is not None:
        data['policy'] = policy
    return dict(operation=operation, input=data)


def success(value, evaluation='exact-for-operands', policy=None):
    return dict(outcome='value', value=value,
                metadata=dict(evaluation=evaluation, effectivePolicy=dict(profile=PROFILE, **(policy or {}))))


def decimal_integer(text):
    """Avoid changing the interpreter's global integer-string conversion limit."""
    negative = text.startswith('-')
    magnitude = text[1:] if negative else text
    result = 0
    for offset in range(0, len(magnitude), 9):
        part = magnitude[offset:offset + 9]
        result = result * 10 ** len(part) + int(part)
    return -result if negative else result


class Runner(CommonRunner):
    """Reuse only the frozen runner's strict JSON and operation/chain plumbing.

    This class never changes its globals, target recognition or stable claims.
    The fixed imported helper is pinned in this lane's manifest and after a run.
    """

    def __init__(self, args):
        self.args = args
        self.artifacts = {}
        self.executions = self.assertions = 0
        self.immutable = False
        self.manifest_path = args.manifest.resolve()
        self.manifest = self.read(self.manifest_path)
        meta = self.manifest['meta']
        require(meta['lane'] == LANE and meta['profile'] == PROFILE, 'Wrong rational target identity')
        self.immutable = meta['conformance'] == dict(surface='rational-exact-arithmetic', stable=True, publication='local-only')
        if self.immutable:
            require(IMMUTABLE_TARGETS.get(meta['snapshot_id']) == self.artifacts[self.manifest_path],
                    'Unrecognized or modified immutable rational target')
        else:
            require(meta['conformance'] == dict(surface='working-next', stable=False),
                    'Expected mutable next or recognized immutable rational target')
            require(meta['snapshot_id'] == 'aeonic-rational-arithmetic-cts-v1-snapshot-0.3',
                    'Unexpected working target identifier')
        root = self.manifest_path.parent

        def pinned(base, relative, sha, json_content=True):
            path = (base / relative).resolve()
            require(base.resolve() in path.parents, 'Artifact escapes its owning root')
            content = path.read_bytes()
            require(hashlib.sha256(content).hexdigest() == sha, 'Artifact digest mismatch: ' + relative)
            self.artifacts[path] = sha
            return decode(content.decode('utf-8')) if json_content else content

        require(meta['shared_runner'] == 'runners/run_aeonic_arithmetic.py', 'Unexpected shared helper path')
        pinned(ROOT, meta['shared_runner'], meta['shared_runner_sha256'], False)
        own = Path(__file__).resolve()
        self.artifacts[own] = digest(own)
        schema = pinned(args.specs_root, meta['specification_schema'], meta['specification_schema_sha256'])
        binding = pinned(root, meta['binding_schema'], meta['binding_schema_sha256'])
        pinned(args.specs_root, meta['specification_source'], meta['specification_source_sha256'], False)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator.check_schema(binding)
        registry = Registry().with_resource(schema['$id'], Resource.from_contents(schema))
        self.result_schema = Draft202012Validator({'$ref': schema['$id'] + '#/$defs/result'}, registry=registry)
        self.request_schema = Draft202012Validator(schema, registry=registry)
        self.binding_schema = Draft202012Validator(binding)
        self.resource_limits = meta['resource_limits']
        names = set(binding['properties']['policy']['properties']['resourceLimits']['properties'])
        require(isinstance(self.resource_limits, dict) and set(self.resource_limits) == names,
                'Target must explicitly select every trusted limit')
        self.binding_schema.validate(dict(lane=LANE, case_id='limits', fixture=dict(request={}),
                                          policy=dict(resourceLimits=self.resource_limits)))
        self.tests = []
        seen = set()
        for suite in self.manifest['suites']:
            data = pinned(root, suite['file'], suite['content_sha256'])
            require(data['id'] == suite['id'] and isinstance(data['tests'], list), 'Invalid suite')
            for test in data['tests']:
                require(isinstance(test.get('id'), str) and test['id'] and test['id'] not in seen,
                        'Missing or duplicate case ID')
                seen.add(test['id'])
                self.validate_test(test)
                self.tests.append(test)
        require(bool(self.tests), 'An empty target cannot validate or pass')

    def limits(self, policy):
        return dict(self.resource_limits, **policy.get('resourceLimits', {}))

    def validate_result(self, result, limits):
        self.result_schema.validate(result)
        if result['outcome'] != 'value':
            return
        descriptor = result['value']['number']
        if descriptor['category'] == 'finiteNumber':
            require(len(descriptor['value']) <= limits['maxOutputCharacters'], 'Output exceeds selected allowance')
            return
        c, e = descriptor['coefficient'], descriptor['exponent']
        require(len(c.lstrip('-')) <= limits['maxCoefficientDigits'], 'Result coefficient exceeds selected allowance')
        bound = str(limits['maxExponentMagnitude'])
        magnitude = e.lstrip('-')
        require((len(magnitude), magnitude) <= (len(bound), bound), 'Result exponent exceeds selected allowance')
        if descriptor['category'] == 'exactRational':
            d = descriptor['denominator']
            require(len(d) <= limits['maxDenominatorDigits'], 'Result denominator exceeds selected allowance')
            # Shape and selected widths precede expensive conversion/GCD. The
            # schema cannot itself express reduced numerator/denominator pairs.
            require(gcd(abs(decimal_integer(c)), decimal_integer(d)) == 1, 'Result rational is not reduced')

    def validate_operation(self, test):
        policy = test.get('policy', {})
        self.binding_schema.validate(dict(lane=LANE, case_id=test['id'], fixture=test['fixture'], policy=policy))
        self.validate_result(test['expected'], self.limits(policy))
        if test['expected']['outcome'] == 'value' and 'request' in test['fixture']:
            self.request_schema.validate(test['fixture']['request'])

    def validate_test(self, test):
        kind = test.get('kind', 'operation')
        if kind == 'operation':
            self.validate_operation(test)
        elif kind == 'chain':
            require(isinstance(test['steps'], list) and test['steps'], 'A chain cannot be empty')
            targets = set()
            for i, step in enumerate(test['steps']):
                self.validate_operation(dict(id=test['id'] + '/' + str(i), fixture=dict(request=step['request']),
                                             expected=step['expected'], policy=step.get('policy', {})))
            for link in test['links']:
                require(set(link) == {'fromStep', 'toStep', 'input'}, 'Malformed chain link')
                a, b = link['fromStep'], link['toStep']
                require(type(a) is int and type(b) is int and 0 <= a < b < len(test['steps']), 'Invalid chain link order')
                require(link['input'] in {'left', 'right', 'value'} and link['input'] in test['steps'][b]['request']['input'],
                        'Invalid chain destination')
                require(test['steps'][a]['expected']['outcome'] == 'value', 'Diagnostics cannot feed values')
                target = (b, link['input'])
                require(target not in targets, 'Duplicate chain destination')
                targets.add(target)
        elif kind == 'laws':
            require(len(test['values']) >= 3, 'Law group needs three values')
            require(sorted(test['ascending']) == list(range(len(test['values'])))
                    and all(type(i) is int for i in test['ascending']), 'Invalid ascending value indices')
            for value in test['values']:
                self.request_schema.validate(request('add', value['input'], exact('0')))
                self.validate_result(success(value['expected']), self.resource_limits)
            self.request_schema.validate(request('quantize', exact('1'), policy=dict(increment=test['increment'], rounding='half-even')))
        else:
            raise ValueError('Unknown test kind: ' + str(kind))

    def execute(self, envelope):
        """Do not read arbitrarily large SUT output into controller memory.

        The post-process file-size cap is a harness check, not a disk-growth or
        arbitrary executable resource guarantee. The trusted SUT command has a
        separate process timeout; no shell is used.
        """
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            result = subprocess.run(shlex.split(self.args.sut), input=encode(envelope), text=True,
                                    encoding='utf-8', stdout=output, stderr=errors,
                                    cwd=self.args.cwd, timeout=self.args.timeout)
            errors.seek(0)
            message = errors.read(4096).decode('utf-8', errors='replace')
            require(result.returncode == 0, 'SUT harness failure: ' + message[:300])
            require(output.tell() <= MAX_PROTOCOL_BYTES, 'SUT protocol output exceeds harness cap')
            output.seek(0)
            return output.read(MAX_PROTOCOL_BYTES + 1).decode('utf-8')

    def invoke(self, case_id, fixture, policy):
        envelope = dict(lane=LANE, case_id=case_id, fixture=fixture, policy=policy)
        self.binding_schema.validate(envelope)
        limits = self.limits(policy)
        envelope['policy'] = dict(resourceLimits=limits)
        self.executions += 1
        output = decode(self.execute(envelope))
        require(isinstance(output, dict), 'Protocol output must be an object')
        actual = output.get('result')
        self.validate_result(actual, limits)
        ok = actual['outcome'] == 'value'
        require(type(output.get('ok')) is bool and output['ok'] == ok, 'Protocol ok mismatch')
        require(output.get('warnings') == [], 'Unexpected warnings')
        errors = output.get('errors')
        if ok:
            require(errors == [], 'Unexpected errors')
        else:
            require(isinstance(errors, list) and len(errors) == 1 and isinstance(errors[0], dict), 'One error is required')
            for key, value in dict(code=actual['reason'], path=None, span=None, phase=None).items():
                require(key in errors[0] and equal(errors[0][key], value), 'Protocol diagnostic mismatch')
        return actual

    def operation(self, test):
        result = super().operation(test)
        self.assertions += 1
        return result

    def binary(self, operation, a, b):
        actual = self.invoke('law-' + str(self.executions), dict(request=request(operation, a, b)), {})
        history = MARKED if MARKED in {a.get('history', NONE), b.get('history', NONE)} else NONE
        require(actual['outcome'] == 'value', 'Law operation must produce a value')
        require(actual['value']['number']['category'] in {'exactNumber', 'exactRational'}, 'Law result must remain derived')
        require(actual['value']['history'] == history, 'History union law')
        require(actual['metadata'] == success(actual['value'])['metadata'], 'Exact law metadata mismatch')
        self.assertions += 1
        return actual['value']

    def quantum(self, value, increment, mode):
        policy = dict(increment=increment, rounding=mode)
        actual = self.invoke('law-' + str(self.executions), dict(request=request('quantize', value, policy=policy)), {})
        require(actual['outcome'] == 'value' and actual['value']['number']['category'] == 'exactNumber',
                'Quantization law must produce a finite derived value')
        changed = not equal(actual['value']['number'], value['number'])
        history = MARKED if changed or value['history'] == MARKED else NONE
        evaluation = 'rounded-for-operands' if changed else 'exact-for-operands'
        require(actual == success(dict(number=actual['value']['number'], history=history), evaluation, policy),
                'Quantization law history/metadata mismatch')
        self.assertions += 1
        return actual['value']

    def laws(self, test):
        values = []
        for i, value in enumerate(test['values']):
            values.append(self.operation(dict(id=test['id'] + '/canonical-' + str(i),
                                              fixture=dict(request=request('add', value['input'], exact('0'))),
                                              expected=success(value['expected'])))['value'])
        for a, b in itertools.product(values, repeat=2):
            for op in ('add', 'multiply'):
                self.assertion(equal(self.binary(op, a, b), self.binary(op, b, a)), op + ' commutativity')
            left, right = self.binary('subtract', a, b), self.binary('subtract', b, a)
            inverse = copy.deepcopy(right['number'])
            c = inverse['coefficient']
            inverse['coefficient'] = c if c == '0' else c[1:] if c.startswith('-') else '-' + c
            self.assertion(equal(left['number'], inverse), 'subtraction reversal')
            if b['number']['coefficient'] != '0':
                quotient = self.binary('divide', a, b)
                restored = self.binary('multiply', quotient, b)
                self.assertion(equal(restored['number'], a['number']), 'exact division round-trip')
        increment = dict(number=test['increment'], history=NONE)
        rounded = {}
        for i, a in enumerate(values):
            for mode in MODES:
                first = self.quantum(a, test['increment'], mode)
                second = self.quantum(first, test['increment'], mode)
                rounded[(i, mode)] = first
                self.assertion(equal(first, second), 'quantization idempotence and history')
                multiple = self.binary('divide', first, increment)['number']
                self.assertion(multiple['category'] == 'exactNumber' and not multiple['exponent'].startswith('-'),
                               'quantization grid membership')
        for mode in MODES:
            for a, b in zip(test['ascending'], test['ascending'][1:]):
                difference = self.binary('subtract', rounded[(a, mode)], rounded[(b, mode)])['number']['coefficient']
                self.assertion(difference == '0' or difference.startswith('-'), 'quantization monotonicity')

    def run(self, check_only=False):
        failures = []
        counts = dict(operation_cases=0, chains=0, law_groups=0)
        for test in self.tests:
            kind = test.get('kind', 'operation')
            counts[dict(operation='operation_cases', chain='chains', laws='law_groups')[kind]] += 1
            if check_only:
                continue
            try:
                if kind == 'chain':
                    self.chain(test)
                elif kind == 'laws':
                    self.laws(test)
                else:
                    self.operation(test)
            except Exception as error:
                failures.append(dict(id=test['id'], failure=str(error)[:1500]))
        for path, sha in self.artifacts.items():
            if not path.exists() or digest(path) != sha:
                failures.append(dict(id='artifact-integrity', failure='Artifact changed during run: ' + path.name))
        status = 'failed' if failures else 'artifacts-validated' if check_only else 'passed'
        return dict(status=status, target=self.manifest['meta']['snapshot_id'], target_status='immutable-local' if self.immutable else 'mutable-working',
                    stable_conformance_claim=self.immutable and not check_only and not failures, semantic_execution=not check_only, **counts,
                    sut_executions=self.executions, assertions=self.assertions,
                    manifest_sha256=self.artifacts[self.manifest_path], runner_sha256=self.artifacts[Path(__file__).resolve()],
                    specification_source_sha256=self.manifest['meta']['specification_source_sha256'],
                    specification_schema_sha256=self.manifest['meta']['specification_schema_sha256'],
                    shared_runner_sha256=self.manifest['meta']['shared_runner_sha256'],
                    resource_limits=self.resource_limits, sut=self.args.sut,
                    cwd=str(self.args.cwd.resolve()), failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'cts/aeonic-rational-arithmetic/v1/aeonic-rational-arithmetic-cts.v1.snapshot-0.2.json')
    parser.add_argument('--specs-root', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Validate artifacts only; no semantic execution or conformance pass')
    parser.add_argument('--sut')
    parser.add_argument('--cwd', type=Path, default=Path.cwd())
    parser.add_argument('--timeout', type=float, default=20)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    require(args.check or args.sut, '--sut is required unless --check is selected')
    require(0 < args.timeout < float('inf'), 'Timeout must be positive and finite')
    report = Runner(args).run(check_only=args.check)
    output = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding='utf-8')
    print(output, end='')
    return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('CTS harness failure: ' + str(error), file=sys.stderr)
        sys.exit(2)
