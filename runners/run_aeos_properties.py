#!/usr/bin/env python3
"""Explicit mutable AEOS property-consumer target; no stable conformance claim."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
from jsonschema import Draft202012Validator, ValidationError, SchemaError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'cts/aeos/v1/aeos-property-selectors-cts.v1.next.json'

def load(path):
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Oversized target artifact')
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-JSON constant')))

def verified(root, entry):
    path = (root / entry['file']).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Artifact path escapes root or is absent')
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['content_sha256']:
        raise ValueError('Artifact digest mismatch: ' + entry['file'])
    return path

def prepare(manifest_path, specs):
    manifest = load(manifest_path)
    meta = manifest['meta']
    if (meta['profile'] != 'aeos-properties-0.1' or meta['sut_protocol'] != 'aeos-properties-v0.1'
        or meta['conformance'] != {'surface':'experimental', 'experimental_default':'exclude'}):
        raise ValueError('Wrong profile/protocol or widened default admission')
    if re.fullmatch(r'[0-9a-f]{40}', meta.get('specification_revision', '')) is None or meta['specification_revision'] == '0' * 40:
        raise ValueError('Missing owning specification revision')
    assets = manifest['specification']['assets']
    if len(assets) != 2 or {entry['file'] for entry in assets} != {'sources/aeos/v1/sansa-property-selectors-v1.aeon', 'resources/aeos/v1/sansa-property-selectors-candidate.json'}:
        raise ValueError('Wrong owning profile artifacts')
    if len(manifest['suites']) != 1 or manifest['suites'][0]['file'] != 'fixtures/property-selectors-v1.json' or manifest['fixture_schema']['file'] != 'aeos-properties-fixture.schema.json':
        raise ValueError('Wrong fixture/schema artifacts')
    for entry in assets:
        verified(specs, entry)
    schema = load(verified(manifest_path.parent, manifest['fixture_schema']))
    Draft202012Validator.check_schema(schema)
    suite = load(verified(manifest_path.parent, manifest['suites'][0]))
    Draft202012Validator(schema).validate(suite)
    ids = [case['id'] for case in suite['tests']]
    if len(set(ids)) != len(ids) or len(ids) != 52:
        raise ValueError('Duplicate or missing fixture IDs')
    return manifest, suite

def invoke(command, requests):
    # Explicit caller-selected SUT, no shell. Files avoid pipe-buffer deadlocks;
    # output and elapsed-time guards apply while the child is running.
    with tempfile.TemporaryDirectory(prefix='aeos-property-cts-') as directory:
        root = Path(directory)
        input_path, output_path, error_path = [root / name for name in ['input', 'output', 'errors']]
        input_path.write_text(''.join(json.dumps(request, ensure_ascii=False) + '\n' for request in requests), encoding='utf-8')
        with input_path.open('rb') as source, output_path.open('wb') as output, error_path.open('wb') as errors:
            child = subprocess.Popen(shlex.split(command), stdin=source, stdout=output, stderr=errors)
            deadline = time.monotonic() + 90
            try:
                while child.poll() is None:
                    if time.monotonic() > deadline or output_path.stat().st_size + error_path.stat().st_size > 8 * 1024 * 1024:
                        raise ValueError('SUT elapsed/output guard exceeded')
                    time.sleep(0.02)
                if child.returncode != 0:
                    raise ValueError('SUT exited nonzero: ' + str(child.returncode))
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait()
        if output_path.stat().st_size + error_path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('SUT output guard exceeded')
        lines = output_path.read_text(encoding='utf-8').splitlines()
        if len(lines) != len(requests):
            raise ValueError('SUT response count mismatch')
        return [json.loads(line) for line in lines]

def run(args):
    manifest, suite = prepare(args.manifest.resolve(), args.specs_root.resolve())
    report = {'target':manifest['meta']['snapshot_id'], 'status':'prepared', 'stable_conformance_claim':False,
              'semantic_execution':False, 'cases':len(suite['tests']), 'executions':0, 'failures':[]}
    if args.check:
        return report, 0
    if not args.sut:
        raise ValueError('Select --check or an explicit --sut command')
    requests, labels, expected = [], [], []
    for case in suite['tests']:
        modes = ['legacy'] if case['entrypoint'] == 'legacy' else ['records', 'telex']
        for repeat in range(2):
            for mode in modes:
                requests.append({key:case[key] for key in ['entrypoint', 'records', 'schema']} | {'representation':mode, 'options':case.get('options', {})})
                labels.append({'id':case['id'], 'representation':mode, 'repeat':repeat})
                expected.append(case['expected'])
    responses = invoke(args.sut, requests)
    for label, wanted, response in zip(labels, expected, responses):
        reasons = []
        if not isinstance(response, dict):
            report['failures'].append(label | {'assertions':['response-shape']})
            continue
        result = response.get('result')
        if not isinstance(result, dict) or type(result.get('ok')) is not bool or not isinstance(result.get('errors'), list):
            reasons.append('result-shape')
        else:
            if result['ok'] != wanted['ok']:
                reasons.append('ok')
            actual = []
            for error in result['errors']:
                if not isinstance(error, dict) or type(error.get('code')) is not str or type(error.get('path')) is not str:
                    reasons.append('error-shape')
                    continue
                actual.append((error['code'], error['path']))
            if sorted(actual) != sorted((error['code'], error['path']) for error in wanted['errors']):
                reasons.append('errors-code-path')
            if not result['ok'] and result.get('guarantees') != {}:
                reasons.append('partial-guarantees')
        if response.get('inputUnchanged') is not True:
            reasons.append('input-mutated')
        if reasons:
            report['failures'].append(label | {'assertions':reasons})
    report.update(status='passed' if not report['failures'] else 'failed', semantic_execution=True, executions=len(requests))
    return report, 0 if not report['failures'] else 1

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT)
    parser.add_argument('--specs-root', type=Path, required=True)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--check', action='store_true')
    choice.add_argument('--sut')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        report, status = run(args)
    except (OSError, ValueError, KeyError, TypeError, ValidationError, SchemaError) as error:
        report, status = {'status':'invalid', 'stable_conformance_claim':False, 'semantic_execution':False, 'error':str(error)}, 2
    text = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.write_text(text, encoding='utf-8')
    print(text, end='')
    return status

if __name__ == '__main__':
    raise SystemExit(main())
