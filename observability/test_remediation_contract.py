"""Offline contract checks for the remediation's safety-critical configuration."""
import json
import re
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SECURE = ROOT / 'observability/secure-production'
MODULES = ['springboot-user-api', 'springboot-learning-api', 'springboot-jwks-api']


class RemediationContract(unittest.TestCase):
    def test_immutable_bounded_spool(self):
        for module in MODULES:
            with self.subTest(module=module):
                tree = ET.parse(ROOT / module / 'src/main/resources/logback-spring.xml')
                appender = tree.find(".//appender[@name='STRUCTURED_FILE']")
                if appender is None:
                    appender = next(a for a in tree.findall('.//appender') if a.find('rollingPolicy') is not None)
                self.assertIsNone(appender.find('file'))
                policy = appender.find('rollingPolicy')
                pattern = policy.findtext('fileNamePattern')
                self.assertIn('/spool/', pattern)
                self.assertIn('%d{yyyy-MM-dd}.%i.log', pattern)
                self.assertNotIn('.gz', pattern)
                for name in ['maxFileSize', 'maxHistory', 'totalSizeCap']:
                    self.assertTrue(policy.findtext(name))

    def test_legacy_and_spool_share_persistent_tail_database(self):
        raw = (ROOT / 'observability/fluent-bit/fluent-bit.conf').read_text()
        self.assertEqual(3, raw.count('DB.compare_filename Off'))
        self.assertEqual(3, len(re.findall(r'^\s*Path\s+\S+/spool/\S+\.log$', raw, re.M)))
        self.assertEqual(3, len(re.findall(r'^\s*Exclude_Path\s+/[^ ]+/archive/\*\.gz$', raw, re.M)))
        self.assertEqual(3, len(re.findall(r'^\s*storage.type\s+filesystem$', raw, re.M)))

    def test_no_candidate_is_loaded_by_default(self):
        self.assertNotIn('secure-production', (ROOT / 'docker-compose.yml').read_text())

    def test_proxies_do_not_publish_or_join_other_networks(self):
        services = json.loads((SECURE / 'compose.json').read_text())['services']
        proxies = {k: v for k, v in services.items() if k.endswith('-metrics-tls')}
        self.assertEqual(5, len(proxies))
        for name, service in proxies.items():
            self.assertNotIn('ports', service)
            self.assertNotIn('networks', service)
            self.assertEqual('service:' + name.removesuffix('-metrics-tls'), service['network_mode'])
            self.assertTrue(service['read_only'])
            self.assertEqual(['ALL'], service['cap_drop'])

    def test_proxies_require_certificates(self):
        for path in SECURE.glob('*-metrics-tls.conf'):
            raw = path.read_text()
            self.assertIn('ssl_verify_client on;', raw)
            self.assertIn('return 403', raw)
            self.assertIn('proxy_pass http://127.0.0.1:', raw)

    def test_opensearch_security_fails_closed(self):
        raw = (SECURE / 'opensearch.yml').read_text()
        for text in ['plugins.security.disabled: false', 'allow_default_init_securityindex: false',
                     'clientauth_mode: REQUIRE', 'enforce_hostname_verification: true']:
            self.assertIn(text, raw)

    def test_datasource_identity_and_verification(self):
        for name in ['loki', 'prometheus', 'tempo']:
            raw = (SECURE / 'datasources' / (name + '.yml')).read_text()
            self.assertIn('uid: ' + name, raw)
            self.assertIn('tlsSkipVerify: false', raw)

    def test_alerts_stay_muted_and_unique(self):
        rules = json.loads((SECURE / 'alerting.json').read_text())['groups'][0]['rules']
        self.assertEqual(21, len(rules))
        self.assertEqual(21, len({r['uid'] for r in rules}))
        for rule in rules:
            self.assertEqual(['phase5-delivery-disabled'], rule['notification_settings']['mute_time_intervals'])


if __name__ == '__main__':
    unittest.main()
