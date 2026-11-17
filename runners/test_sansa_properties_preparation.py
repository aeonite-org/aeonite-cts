"""Structural preparation checks; no property-selector implementation is exercised."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import check_sansa_properties as checker


class PropertyPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.lane = root / 'lane'
        self.lane.mkdir()
        self.manifest = self.lane / checker.DEFAULT.name
        original = checker.load(checker.DEFAULT)
        for entry in original['assets'] + original['suites']:
            target = self.lane / entry['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checker.DEFAULT.parent / entry['file'], target)
        shutil.copyfile(checker.DEFAULT, self.manifest)
        self.specs = root / 'specs'
        # Standard sibling checkout by default, configurable for isolated exports.
        owner = Path(os.environ.get('SANSA_PROPERTY_SPECS_ROOT', str(checker.ROOT.parent / 'aeonite-specs')))
        for field in ('source', 'resource', 'schema'):
            relative = original['specification'][field]
            target = self.specs / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(owner / relative, target)

    def save(self, path, data):
        path.write_text(json.dumps(data, indent=2) + '\n')

    def manifest_change(self, mutation):
        data = checker.load(self.manifest)
        mutation(data)
        self.save(self.manifest, data)

    def suite_change(self, mutation):
        manifest = checker.load(self.manifest)
        ref = manifest['suites'][1]
        path = self.lane / ref['file']
        suite = checker.load(path)
        mutation(suite)
        self.save(path, suite)
        ref['content_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save(self.manifest, manifest)

    def reject(self):
        with self.assertRaises(Exception):
            checker.check(self.manifest, self.specs)

    def test_prepared_is_not_executed_conformance(self):
        result = checker.check(self.manifest, self.specs)
        self.assertEqual(167, result['cases'])
        self.assertEqual('prepared', result['status'])
        self.assertFalse(result['sutExecuted'])
        self.assertFalse(result['acceptanceQualification'])
        self.assertEqual('exclude', result['defaultSelection'])

    def test_default_admission_rejected(self):
        self.manifest_change(lambda d: d['meta']['conformance'].update(experimental_default='include'))
        self.reject()

    def test_zero_specification_pin_rejected(self):
        self.manifest_change(lambda d: d['meta'].update(specification_revision='0' * 40))
        self.reject()

    def test_specification_digest_mismatch_rejected(self):
        self.manifest_change(lambda d: d['specification'].update(source_sha256='0' * 64))
        self.reject()

    def test_suite_digest_mismatch_rejected(self):
        self.manifest_change(lambda d: d['suites'][0].update(content_sha256='0' * 64))
        self.reject()

    def test_path_escape_rejected(self):
        self.manifest_change(lambda d: d['suites'][0].update(file='../escape.json'))
        self.reject()

    def test_unknown_expectation_rejected_even_with_updated_digest(self):
        self.suite_change(lambda d: d['tests'][0]['expected'].update(ignoredAssertion=True))
        self.reject()

    def test_unknown_callback_rejected_even_with_updated_digest(self):
        self.suite_change(lambda d: d['tests'][0]['expected'].update(calls={'madeUpCounter': 0}))
        self.reject()

    def test_missing_binding_assertion_rejected(self):
        self.suite_change(lambda d: d['tests'][0]['expected'].pop('bindings'))
        self.reject()

    def test_address_witness_mismatch_rejected(self):
        self.suite_change(lambda d: d['tests'][0]['expected'].update(bindings=['doc'], addresses=['$.wrong']))
        self.reject()

    def test_duplicate_suite_rejected(self):
        self.manifest_change(lambda d: d['suites'].append(d['suites'][0]))
        self.reject()

    def test_duplicate_asset_rejected(self):
        self.manifest_change(lambda d: d['assets'].append(d['assets'][0]))
        self.reject()

    def test_generated_size_is_bounded(self):
        with self.assertRaises(checker.PreparationError):
            checker.expand({'kind': 'payload', 'form': 'text', 'count': 65538})
        address = checker.expand({'kind': 'canonical', 'form': 'text', 'count': 65536})
        self.assertEqual(65536, len(address))
        text = checker.expand({'kind': 'payload', 'form': 'text', 'count': 2, 'scalar': '😀', 'encoding': 'escaped'})
        self.assertEqual('$&key("\\u{1F600}\\u{1F600}")', text)


if __name__ == '__main__':
    unittest.main()
