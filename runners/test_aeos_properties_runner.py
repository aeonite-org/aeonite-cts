"""Artifact and oracle-sensitivity tests; the fake SUT tests checker plumbing only."""
from argparse import Namespace
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
import unittest
import run_aeos_properties as runner


class AeosPropertyRunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.lane = self.root / 'lane'
        self.specs = self.root / 'specs'
        original = runner.load(runner.DEFAULT)
        self.manifest = self.lane / runner.DEFAULT.name
        for entry in original['suites'] + [original['fixture_schema']]:
            target = self.lane / entry['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(runner.DEFAULT.parent / entry['file'], target)
        self.manifest.write_text(json.dumps(original))
        owner = Path(os.environ.get('AEOS_PROPERTY_SPECS_ROOT', str(runner.ROOT.parent / 'aeonite-specs')))
        for entry in original['specification']['assets']:
            target = self.specs / entry['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(owner / entry['file'], target)

    def test_preparation_and_guide_pin(self):
        manifest, suite = runner.prepare(self.manifest, self.specs)
        self.assertEqual(len(suite['tests']), 52)
        guide = (runner.ROOT / 'docs/protocol/v1/lane-aeos-properties.md').read_text()
        self.assertIn(manifest['meta']['specification_revision'], guide)

    def test_fixture_digest_guard(self):
        path = self.lane / 'fixtures/property-selectors-v1.json'
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'digest'):
            runner.prepare(self.manifest, self.specs)

    def test_unknown_expected_fields_are_not_silent(self):
        path = self.lane / 'fixtures/property-selectors-v1.json'
        suite = runner.load(path)
        suite['tests'][0]['expected']['unasserted'] = True
        path.write_text(json.dumps(suite))
        manifest = runner.load(self.manifest)
        manifest['suites'][0]['content_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaises(runner.ValidationError):
            runner.prepare(self.manifest, self.specs)

    def test_specification_assets_cannot_be_omitted(self):
        manifest = runner.load(self.manifest)
        manifest['specification']['assets'] = []
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'profile artifacts'):
            runner.prepare(self.manifest, self.specs)

    def fake_sut(self, mutation):
        source = self.root / 'fake.py'
        # This intentionally uses fixture answers: it verifies the runner's
        # assertions, and is never evidence of implementation conformance.
        source.write_text('''import json,sys
from pathlib import Path
suite=json.loads(Path(sys.argv[1]).read_text())
expected=[]
for case in suite['tests']:
 for repeat in range(2):
  for mode in (['legacy'] if case['entrypoint']=='legacy' else ['records','telex']):
   expected.append(case['expected'])
mutation=sys.argv[2]
for index,line in enumerate(sys.stdin):
 answer=expected[index]
 reply={'result':{'ok':answer['ok'],'errors':[dict(error) for error in answer['errors']],'guarantees':{},'warnings':[]},'inputUnchanged':True}
 if index==2:
  if mutation=='ok':reply['result']['ok']=not reply['result']['ok']
  elif mutation=='code':reply['result']['errors'][0]['code']='wrong_code'
  elif mutation=='path':reply['result']['errors'][0]['path']='$.wrong'
  elif mutation=='input':reply['inputUnchanged']=False
  elif mutation=='guarantees':reply['result']['guarantees']={'$.wrong':['present']}
 if mutation!='count' or index!=len(expected)-1: print(json.dumps(reply),flush=True)
''')
        return shlex.join([sys.executable, str(source), str(self.lane / 'fixtures/property-selectors-v1.json'), mutation])

    def test_each_expected_field_and_repeated_response_is_checked(self):
        def execute(mutation):
            return runner.run(Namespace(manifest=self.manifest, specs_root=self.specs, check=False, sut=self.fake_sut(mutation)))
        report, status = execute('none')
        self.assertEqual(status, 0)
        self.assertEqual(report['executions'], 206)
        for mutation, assertion in [('ok','ok'), ('code','errors-code-path'), ('path','errors-code-path'), ('input','input-mutated'), ('guarantees','partial-guarantees')]:
            with self.subTest(mutation=mutation):
                report, status = execute(mutation)
                self.assertEqual(status, 1)
                self.assertEqual(len(report['failures']), 1)
                self.assertEqual(report['failures'][0]['repeat'], 1)
                self.assertIn(assertion, report['failures'][0]['assertions'])

    def test_missing_response_fails(self):
        with self.assertRaisesRegex(ValueError, 'response count'):
            runner.run(Namespace(manifest=self.manifest, specs_root=self.specs, check=False, sut=self.fake_sut('count')))
