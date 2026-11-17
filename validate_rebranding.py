"""Read-only naming checks; renders Compose without contacting the Docker daemon."""
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def main():
    baseline = json.loads((ROOT / 'REBRANDING-AUDIT.json').read_text())
    assert git('-C', 'springboot-jwks-api', 'rev-parse', 'HEAD') == baseline['jwks_head']
    assert git('-C', 'springboot-jwks-api', 'status', '--porcelain=v1') == baseline['jwks_status']
    assert git('ls-files', '--stage', 'springboot-jwks-api') == baseline['jwks_gitlink']
    print('PASS: protected JWKS HEAD, working tree and parent index gitlink unchanged')
    for module, artifact in [('springboot-user-api', 'hospital-user-api'),
                             ('springboot-hospital-api', 'hospital-api')]:
        tree = ET.parse(ROOT / module / 'pom.xml')
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
        assert tree.findtext('m:groupId', namespaces=ns) == 'com.hospitalmanagement'
        assert tree.findtext('m:artifactId', namespaces=ns) == artifact
        for path in (ROOT / module / 'src').rglob('*.java'):
            text = path.read_text()
            package = re.search(r'^package ([\w.]+);', text, re.M).group(1)
            assert path.parent.as_posix().endswith('/' + package.replace('.', '/')), path
            assert 'com.japaneselearning' not in text, path
    print('PASS: Maven coordinates and all User/Hospital Java package paths')
    assert not (ROOT / 'springboot-learning-api').exists()
    hospital = ROOT / 'springboot-hospital-api'
    properties = (hospital / 'src/main/resources/application.properties').read_text()
    for setting in ['spring.jpa.hibernate.ddl-auto=validate',
                    'spring.sql.init.mode=never', 'spring.flyway.enabled=true',
                    'spring.flyway.clean-disabled=true',
                    'spring.datasource.driver-class-name=org.postgresql.Driver']:
        assert setting in properties, setting
    assert (hospital / 'src/main/resources/db/migration').is_dir()
    mappings = '\n'.join(p.read_text() for p in (hospital / 'src/main/java').rglob('*.java'))
    assert '/api/v1/learning' not in mappings
    assert 'LearningController' not in mappings
    print('PASS: retired module/routes absent; PostgreSQL and Flyway schema safeguards')
    for path in (ROOT / 'observability').rglob('*.json'):
        json.loads(path.read_text(encoding='utf-8-sig'))
    print('PASS: observability JSON syntax')
    environment = dict(os.environ)
    environment['GRAFANA_ALERT_WEBHOOK_URL'] = 'https://validation.invalid/webhook'
    for key in ['OBS_TLS_DIR', 'OS_SECURITY_CONFIG_DIR', 'OS_ADMIN_DN', 'OS_NODE_DN',
                'OS_DASHBOARDS_PASSWORD', 'OBS_GRAFANA_ROOT_URL', 'GRAFANA_METRICS_PASSWORD',
                'GRAFANA_TLS_CA_PEM', 'GRAFANA_TLS_CLIENT_CERT_PEM', 'GRAFANA_TLS_CLIENT_KEY_PEM']:
        environment[key] = 'validation-only'
    for overlays in [[], ['docker-compose.debug.yml'],
                     ['observability/secure-production/compose.json'],
                     ['observability/grafana/docker-compose.notifications.yml.example']]:
        command = ['docker', 'compose', '-f', 'docker-compose.yml']
        for overlay in overlays:
            command += ['-f', overlay]
        result = subprocess.check_output(command + ['config', '--format', 'json'],
                                         cwd=ROOT, env=environment, text=True)
        config = json.loads(result)
        assert config['name'] == 'hospital_dev'
        services = config['services']
        assert {'hospital-user-api', 'hospital-jwks-api', 'hospital-api'} <= services.keys()
        assert 'user-api' not in services and 'jwks-api' not in services
        assert config['networks']['default']['name'] == 'hospital-network'
        for name, service in services.items():
            assert set(service.get('depends_on', {})) <= services.keys(), name
            mode = service.get('network_mode', '')
            if mode.startswith('service:'):
                assert mode[8:] in services, name
        for name in ['hospital-user-api', 'hospital-api', 'hospital-jwks-api']:
            env = services[name]['environment']
            assert env['SPRING_APPLICATION_NAME'] == name
            assert env['APP_NAME'] == name
        assert services['postgres']['environment']['POSTGRES_DB'] == 'hospital_db'
        hospital_env = services['hospital-api']['environment']
        assert hospital_env['SPRING_DATASOURCE_URL'].endswith('/hospital_db')
        assert hospital_env['SPRING_DATASOURCE_USERNAME'] == services['postgres']['environment']['POSTGRES_USER']
        assert hospital_env['SPRING_DATASOURCE_PASSWORD'] == services['postgres']['environment']['POSTGRES_PASSWORD']
        assert services['hospital-user-api']['environment']['INTERNAL_JWT_ISSUER'] == hospital_env['HOSPITAL_INTERNAL_JWT_ISSUER']
        assert services['hospital-user-api']['environment']['INTERNAL_JWT_SUBJECT'] == hospital_env['HOSPITAL_INTERNAL_JWT_ISSUER']
        for service in services.values():
            for key, value in service.get('environment', {}).items():
                if key.endswith(('BASE_URL', 'JWK_SET_URI')) and isinstance(value, str):
                    assert 'http://user-api:' not in value and 'http://jwks-api:' not in value
        print('PASS: Compose project, network, service dependencies, identity and URLs:', overlays or 'base')
    targets = json.loads((ROOT / 'observability/prometheus/targets/applications.json').read_text())
    for target in targets:
        name = target['targets'][0].split(':')[0]
        assert name in services
        assert target['labels']['service'] == name
    print('PASS: Prometheus service DNS and labels')


if __name__ == '__main__':
    main()
