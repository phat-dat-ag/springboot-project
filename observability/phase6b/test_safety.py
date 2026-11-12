"""Isolation gates must reject a bad model before any Docker mutation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lab


class IsolationTests(unittest.TestCase):
    def setUp(self):
        parent = lab.ROOT / 'data/phase6b-unit'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.subject = lab.Lab.__new__(lab.Lab)
        self.subject.folder = self.folder
        self.subject.run = 'test'
        lab.write(self.folder / 'baseline.json', {'volumes': ['existing_data'], 'networks': ['existing_default']})
        self.model = {'name': lab.PROJECT, 'services': {'probe': {
            'labels': {lab.LABEL: 'test'}, 'mem_limit': 1024, 'cpus': 0.5, 'pids_limit': 32,
            'volumes': [{'type': 'bind', 'source': str(self.folder / 'config'), 'target': '/config', 'read_only': True}],
            'networks': {'isolated': {}}}},
            'volumes': {'test': {'name': lab.PROJECT + '_test_test', 'driver_opts': {'type': 'tmpfs', 'o': 'size=2m'}}},
            'networks': {'isolated': {'name': lab.PROJECT + '_test', 'internal': True}}}
        self.subject.compose = lambda *a: json.dumps(self.model)
        self.subject.result = lambda *a, **kw: None

    def test_valid_model(self):
        self.subject.validate()

    def test_reject_existing_volume(self):
        self.model['volumes']['test']['name'] = 'existing_data'
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_reject_unbounded_storage(self):
        self.model['volumes']['test']['driver_opts']['type'] = 'ext4'
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_reject_existing_bind(self):
        self.model['services']['probe']['volumes'][0]['source'] = str(self.folder.parent / 'live-key')
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_reject_writable_configuration(self):
        self.model['services']['probe']['volumes'][0]['read_only'] = False
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_reject_published_port(self):
        self.model['services']['probe']['ports'] = [{'target': 8080, 'published': '9999'}]
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_reject_shared_namespace(self):
        self.model['services']['probe']['network_mode'] = 'container:existing'
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_reject_external_network(self):
        self.model['networks']['isolated']['external'] = True
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_reject_missing_resource_limits(self):
        del self.model['services']['probe']['mem_limit']
        with self.assertRaises(AssertionError):
            self.subject.validate()

    def test_cleanup_requires_exact_confirmation(self):
        with patch('lab.cmd') as command:
            with self.assertRaises(RuntimeError):
                lab.cleanup(self.subject, None)
            command.assert_not_called()

    def test_mutation_rejects_wrong_project(self):
        self.subject.compose = lambda *a: 'container-id'
        row = {'Config': {'Labels': {'com.docker.compose.project': 'jp_dev', lab.LABEL: 'test'}}, 'NetworkSettings': {'Networks': {}}}
        with patch('lab.cmd', return_value=json.dumps([row])):
            with self.assertRaises(AssertionError):
                self.subject.owned('probe')

    def test_failure_exit_precedes_unverified(self):
        self.assertEqual(1, lab.exit_status([{'status': 'FAIL'}, {'status': 'NOT VERIFIED'}]))

    def test_incomplete_evidence_is_not_green(self):
        self.assertEqual(2, lab.exit_status([{'status': 'PASS'}, {'status': 'BLOCKED'}]))

    def test_executed_pass_exit(self):
        self.assertEqual(0, lab.exit_status([{'status': 'PASS'}]))


if __name__ == '__main__':
    unittest.main()
