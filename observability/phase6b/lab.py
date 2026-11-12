"""Disposable Phase6B laboratory. No inherited Compose, keys, accounts or data.

Commands: prepare, validate, start, test, preserve, stop, cleanup --confirm <run>.
All Docker mutations are exact-ID/label guarded. Secrets never enter reports.
"""
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'observability'))
sys.dont_write_bytecode = True
PROJECT = 'springboot_phase6b'
LABEL = 'observability.phase6b.run'
POINTER = ROOT / 'data/phase6b-current.json'
IMAGES = {'probe': 'python:3.14-alpine', 'loki': 'grafana/loki:3.5.8', 'tempo': 'grafana/tempo:2.9.0',
          'collector': 'otel/opentelemetry-collector-contrib:0.143.0', 'fluent-bit': 'cr.fluentbit.io/fluent/fluent-bit:3.2.10',
          'prometheus': 'prom/prometheus:v3.13.5', 'grafana': 'grafana/grafana:12.2.0', 'opensearch': 'opensearchproject/opensearch:3.9.0'}


def now():
    return datetime.now(timezone.utc).isoformat()


def cmd(*args, input=None, timeout=90):
    result = subprocess.run(args, cwd=ROOT, input=input, text=True, capture_output=True, timeout=timeout, encoding='utf-8')
    if result.returncode:
        # Expanded Compose, envs and security bootstrap responses can carry secrets.
        raise RuntimeError('Subprocess failed; output withheld: ' + args[0] + ' code=' + str(result.returncode))
    return result.stdout


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n' if isinstance(value, (dict, list)) else value, encoding='utf-8', newline='\n')


def inventory():
    ids = cmd('docker', 'ps', '-aq').split()
    rows = json.loads(cmd('docker', 'inspect', *ids)) if ids else []
    return [{key: value for key, value in {
        'id': r['Id'], 'name': r['Name'], 'started': r['State']['StartedAt'], 'restarts': r['RestartCount'],
        'state': r['State']['Status'], 'image': r['Image'], 'mounts': r['Mounts'],
        'ports': r['HostConfig']['PortBindings'], 'networks': sorted(r['NetworkSettings']['Networks']),
        'project': r['Config'].get('Labels', {}).get('com.docker.compose.project'),
        'run': r['Config'].get('Labels', {}).get(LABEL)}.items()} for r in rows]


def git_state():
    return {module: {'head': cmd('git', '-C', str(ROOT / module), 'rev-parse', 'HEAD').strip(),
                     'branch': cmd('git', '-C', str(ROOT / module), 'branch', '--show-current').strip(),
                     'status': cmd('git', '-C', str(ROOT / module), 'status', '--short')}
            for module in ['.', 'springboot-user-api', 'springboot-learning-api', 'springboot-jwks-api']}


def dev_state():
    p = importlib.import_module('phase5-runtime')
    return {'dashboards': p.api('/api/search?type=dash-db'), 'alerts': p.api('/api/v1/provisioning/alert-rules'),
            'datasources': p.api('/api/datasources'), 'policies': p.api('/api/v1/provisioning/policies'),
            'contacts': p.api('/api/v1/provisioning/contact-points'),
            'targets': p.api('/api/v1/targets', 'prometheus')['data']['activeTargets']}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def exit_status(rows):
    statuses = {row['status'] for row in rows}
    return 1 if 'FAIL' in statuses else 2 if statuses & {'NOT VERIFIED', 'BLOCKED'} else 0


class Lab:
    def __init__(self):
        state = json.loads(POINTER.read_text())
        self.run = state['run']
        self.folder = (ROOT / 'data/phase6b' / self.run).resolve()
        assert self.folder.is_relative_to((ROOT / 'data/phase6b').resolve())
        self.file = self.folder / 'compose.json'
        self.results = self.folder / 'evidence/results.json'
        self.rows = json.loads(self.results.read_text()) if self.results.exists() else []

    def compose(self, *args, input=None, timeout=90):
        return cmd('docker', 'compose', '-p', PROJECT, '--env-file', str(self.folder / 'test.env'),
                   '-f', str(self.file), *args, input=input, timeout=timeout)

    def result(self, status, test, actual, started=None, expected='', command='python observability/phase6b/lab.py test'):
        row = {'status': status, 'test': test, 'start': started or now(), 'end': now(),
               'expected': expected or 'The named test condition holds within its documented scope', 'actual': actual,
               'command': getattr(self, 'invocation', command), 'suite': getattr(self, 'active_suite', 'environment'),
               'attempt': getattr(self, 'attempt', 'setup'),
               'evidence': str(self.folder.relative_to(ROOT) / 'evidence'), 'scope': 'isolated Phase6B'}
        row['duration_seconds'] = round((datetime.fromisoformat(row['end']) - datetime.fromisoformat(row['start'])).total_seconds(), 3)
        self.rows.append(row)
        write(self.results, self.rows)
        print(status + ': ' + test, flush=True)

    def check(self, condition, test, actual='', **kwargs):
        self.result('PASS' if condition else 'FAIL', test, actual, **kwargs)
        return bool(condition)

    def validate(self):
        model = json.loads(self.compose('config', '--format', 'json'))
        base = json.loads((self.folder / 'baseline.json').read_text())
        original_volumes = set(base['volumes'])
        original_networks = set(base['networks'])
        assert model['name'] == PROJECT
        for key, service in model['services'].items():
            assert not any(k in service for k in ['container_name', 'network_mode', 'pid', 'ipc', 'build'])
            assert not service.get('ports') and not service.get('privileged')
            assert service['labels'][LABEL] == self.run
            assert service.get('mem_limit') and service.get('cpus') and service.get('pids_limit')
            for mount in service.get('volumes', []):
                if mount['type'] == 'bind':
                    source = Path(mount['source']).resolve()
                    assert source.is_relative_to(self.folder)
                    assert mount.get('read_only') or source == self.folder / 'evidence'
                else:
                    assert mount['type'] == 'volume' and mount['source'] in model['volumes']
            assert set(service.get('networks', {})) == {'isolated'}
        for key, volume in model['volumes'].items():
            assert not volume.get('external') and volume['name'] not in original_volumes
            assert volume['name'] == PROJECT + '_' + self.run + '_' + key
            assert volume['driver_opts']['type'] == 'tmpfs'
            assert 'size=' in volume['driver_opts']['o']
        for network in model['networks'].values():
            assert network['internal'] and not network.get('external') and network['name'] not in original_networks
        write(self.folder / 'evidence/isolation.json', {'run': self.run, 'project': PROJECT,
              'service_names': sorted(model['services']), 'volumes': [v['name'] for v in model['volumes'].values()],
              'networks': [v['name'] for v in model['networks'].values()], 'host_ports': [],
              'maximum_generated_log_bytes': 4 * 1024 * 1024, 'maximum_spans': 300,
              'max_run_seconds': 1800, 'abort_mem_available_mib': 2048, 'model_digest': digest(model)})
        self.result('PASS', 'fully rendered Compose isolation gate', 'No inherited services, host ports, external networks/volumes, existing mounts or keys', command='python observability/phase6b/lab.py validate')

    def owned(self, service):
        ids = self.compose('ps', '-aq', service).split()
        assert len(ids) == 1
        row = json.loads(cmd('docker', 'inspect', ids[0]))[0]
        labels = row['Config']['Labels']
        assert labels['com.docker.compose.project'] == PROJECT and labels[LABEL] == self.run
        assert all(n == PROJECT + '_' + self.run for n in row['NetworkSettings']['Networks'])
        return ids[0]

    def audit_runtime(self):
        model = json.loads(self.file.read_text())
        allowed_volumes = {v['name'] for v in model['volumes'].values()}
        folder = str(self.folder).replace('\\', '/').lower()
        linux_folder = '/run/desktop/mnt/host/' + folder[0] + folder[2:]
        rows = [r for r in inventory() if r['project'] == PROJECT]
        assert rows
        for row in rows:
            assert row['run'] == self.run and not any(row['ports'].values())
            assert set(row['networks']) <= {PROJECT + '_' + self.run}
            for mount in row['mounts']:
                if mount['Type'] == 'volume':
                    assert mount['Name'] in allowed_volumes
                elif mount['Type'] == 'bind':
                    source = mount['Source'].replace('\\', '/').lower()
                    assert source.startswith(folder + '/') or source.startswith(linux_folder + '/')
                    assert not mount['RW'] or source.endswith('/evidence')
                else:
                    assert mount['Type'] == 'tmpfs'
        write(self.folder / 'evidence/runtime-isolation.json', rows)
        self.result('PASS', 'actual container mounts/ports/network isolation audited', len(rows))

    def headroom(self):
        text = self.compose('exec', '-T', 'probe', 'cat', '/proc/meminfo')
        available = int(next(line.split()[1] for line in text.splitlines() if line.startswith('MemAvailable:'))) // 1024
        assert available >= 2048, 'Host memory safety threshold reached'
        return available

    def mutate(self, action, service):
        self.headroom()
        target = self.owned(service)
        begun = now()
        if action == 'kill':
            cmd('docker', 'kill', '--signal', 'KILL', target)
        elif action == 'stop':
            cmd('docker', 'stop', '--time', '25', target)
        elif action == 'start':
            cmd('docker', 'start', target)
        else:
            raise ValueError(action)
        path = self.folder / 'evidence/actions.json'
        actions = json.loads(path.read_text()) if path.exists() else []
        actions.append({'action': action, 'service': service, 'container_id': target, 'project': PROJECT,
                        'run': self.run, 'start': begun, 'end': now()})
        write(path, actions)

    def http(self, url, body=None, method=None, role='probe', **options):
        spec = {'url': url, 'role': role, **options}
        if body is not None:
            spec['body'] = body
        if method:
            spec['method'] = method
        return json.loads(self.compose('exec', '-T', 'probe', 'python', '/suite/probe.py', 'request', input=json.dumps(spec)))

    def http_many(self, urls):
        assert len(urls) <= 300
        return json.loads(self.compose('exec', '-T', 'probe', 'python', '/suite/probe.py', 'batch',
                                      input=json.dumps([{'url': url, 'timeout': 2} for url in urls])))

    def wait(self, function, seconds=90):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            last = function()
            if last:
                return last
            time.sleep(2)
        raise TimeoutError('Bounded isolated wait expired')

    def ready(self, service):
        paths = {'loki': ':3100/ready', 'tempo': ':3200/ready', 'prometheus': ':9090/-/ready',
                 'grafana': ':3000/api/health', 'opensearch': ':9200/_cluster/health'}
        base = service.removesuffix('-restore')
        return self.wait(lambda: self.http('https://' + service + paths[base], role='admin' if base == 'opensearch' else 'probe')['status'] == 200, 150)

    def resources(self, name):
        ids = self.compose('ps', '-q').split()
        if ids:
            raw = cmd('docker', 'stats', '--no-stream', '--format', '{{json .}}', *ids)
            write(self.folder / ('evidence/resources-' + name + '.json'), [json.loads(r) for r in raw.splitlines()])
        self.headroom()

    def bootstrap(self, host='opensearch'):
        self.compose('run', '--rm', '--no-deps', 'security-init', '-h', host, '-p', '9200', '-cn', 'phase6b',
                     '-cacert', '/pki/ca.pem', '-cert', '/pki/admin/client.crt', '-key', '/pki/admin/client.key',
                     '-cd', '/security', timeout=150)

    def start(self):
        self.validate()
        self.compose('up', '-d', '--no-build', '--pull', 'never', 'probe', 'loki', 'tempo', 'prometheus', 'grafana', 'collector', 'fluent-bit')
        self.headroom()
        for service in ['loki', 'tempo', 'prometheus', 'grafana']:
            self.ready(service)
        self.resources('initial')
        self.audit_runtime()
        write(self.folder / 'evidence/manifest.json', inventory())
        self.result('PASS', 'isolated telemetry stack started', 'Exact pinned local images; dedicated internal network and bounded tmpfs-backed volumes')

    def os_start(self, service='opensearch'):
        self.headroom()
        self.compose('up', '-d', '--no-build', '--pull', 'never', service)
        # TLS comes up before the security index; 503 is expected until bootstrap.
        self.wait(lambda: self.http('https://' + service + ':9200', role='admin')['status'] in [200, 503], 150)
        self.bootstrap(service)
        self.ready(service)
        write(self.folder / 'evidence/manifest.json', inventory())

    def preserve(self):
        base = json.loads((self.folder / 'baseline.json').read_text())
        current = {r['id']: r for r in inventory()}
        failures = []
        for row in base['containers']:
            actual = current.get(row['id'])
            normalize = lambda value: {**value, 'mounts': sorted(value['mounts'], key=lambda mount: mount['Destination'])} if value else None
            if normalize(actual) != normalize(row):
                failures.append(row['name'])
        volumes = set(cmd('docker', 'volume', 'ls', '-q').split())
        networks = set(cmd('docker', 'network', 'ls', '--format', '{{.Name}}').split())
        self.check(not failures, 'all original container identities/start times/mounts/networks unchanged', failures)
        self.check(set(base['volumes']) <= volumes and set(base['networks']) <= networks, 'all original volumes and networks preserved')
        actual_git = git_state()
        self.check(all(actual_git[k] == base['git'][k] for k in base['git'] if k != '.'), 'three submodule HEADs/branches/worktrees preserved')
        self.check(actual_git['.']['head'] == base['git']['.']['head'] and actual_git['.']['branch'] == base['git']['.']['branch'], 'root HEAD and branch preserved')
        try:
            state = dev_state()
            self.check(all(digest(state[key]) == value for key, value in base['dev_digests'].items()), 'development Grafana resource fingerprints unchanged')
            self.check(len(state['targets']) == 9 and all(t['health'] == 'up' for t in state['targets']), 'development nine scrape targets still UP')
        except Exception:
            self.result('NOT VERIFIED', 'development Grafana/Prometheus preservation', 'Read-only endpoint query failed; no disruptive recovery attempted')
        write(self.folder / 'evidence/final-git.json', actual_git)

    def collect(self):
        self.resources('final')
        rows = [r for r in inventory() if r['project'] == PROJECT and r['run'] == self.run]
        write(self.folder / 'evidence/final-manifest.json', rows)
        secret_values = [line.split('=', 1)[1] for line in (self.folder / 'test.env').read_text().splitlines()
                         if line.startswith('TEST_GRAFANA_PASSWORD=')]
        logs = {}
        leaked = False
        for row in rows:
            result = subprocess.run(['docker', 'logs', '--tail', '1000', row['id']], capture_output=True, text=True, timeout=15)
            text = result.stdout + result.stderr
            if any(value in text for value in secret_values) or '-----BEGIN PRIVATE KEY-----' in text:
                leaked = True
            for value in secret_values:
                text = text.replace(value, '[REDACTED]')
            logs[row['name']] = text
        write(self.folder / 'evidence/container-logs.json', logs)
        self.check(not leaked, 'fixture logs contain no test password or private PEM', 'Last1000 lines/container scanned; not a historical global guarantee')
        code = "import json,pathlib,hashlib,tarfile; roots=['source','fb','queue','snapshots']; result={};\nfor key in roots:\n p=pathlib.Path('/stores')/key; out=pathlib.Path('/lab/evidence')/(key+'-forensic.tar');\n with tarfile.open(out,'w') as tar: tar.add(p,arcname=key)\n assert out.stat().st_size<=134217728\n h=hashlib.file_digest(out.open('rb'),'sha256').hexdigest(); result[key]={'bytes':out.stat().st_size,'sha256':h}\nprint(json.dumps(result))"
        snapshots = json.loads(self.compose('exec', '-T', 'probe', 'python', '-c', code))
        write(self.folder / 'evidence/forensic-artifacts.json', snapshots)
        self.result('PASS', 'fixture evidence and bounded source/queue/repository artifacts retained',
                    'Forensic copies may be hot; they are not substitutes for verified native/cold backup restores')

    def stop(self):
        # Exact manifest IDs; no down/prune or volume deletion.
        targets = [r['id'] for r in inventory() if r['project'] == PROJECT and r['run'] == self.run and r['state'] == 'running']
        for target in targets:
            row = next(r for r in inventory() if r['id'] == target)
            assert row['run'] == self.run and row['project'] == PROJECT
            cmd('docker', 'stop', '--time', '25', target)
        self.result('PASS', 'fixture containers safely stopped; volumes/evidence retained', len(targets), command='python observability/phase6b/lab.py stop')


def prepare():
    # Capture before creating any Phase6B Docker resources.
    if any(r['project'] == PROJECT for r in inventory()):
        raise RuntimeError('Phase6B resources already exist; select the current run instead of overlapping')
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
    folder = ROOT / 'data/phase6b' / run
    folder.mkdir(parents=True, exist_ok=False)
    write(POINTER, {'run': run})
    for child in ['evidence', 'config', 'pki', 'suite']:
        (folder / child).mkdir()
    baseline = {'utc': now(), 'containers': inventory(), 'volumes': cmd('docker', 'volume', 'ls', '-q').split(),
                'networks': cmd('docker', 'network', 'ls', '--format', '{{.Name}}').split(), 'git': git_state()}
    try:
        state = dev_state()
        baseline['dev_digests'] = {k: digest(state[k]) for k in ['dashboards', 'alerts', 'datasources', 'policies', 'contacts']}
    except Exception:
        baseline['dev_digests'] = {}
    write(folder / 'baseline.json', baseline)
    write(folder / 'test.env', 'TEST_GRAFANA_USER=phase6b\nTEST_GRAFANA_PASSWORD=' + secrets.token_hex(24) + '\n')
    shutil.copy2(HERE / 'probe.py', folder / 'suite/probe.py')
    # Supply only newly generated disposable identities, never inspect/copy live keys.
    script = '''set -eu
cd /work/pki
openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.pem -days 2 -subj /CN=phase6b-disposable-ca -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign >/dev/null 2>&1
openssl req -x509 -newkey rsa:2048 -nodes -keyout untrusted-ca.key -out untrusted-ca.pem -days 2 -subj /CN=untrusted-fixture-ca -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign >/dev/null 2>&1
for role in probe fluent-bit collector loki tempo prometheus grafana opensearch admin reader unknown rotated; do
  mkdir -p "$role"
  openssl req -new -newkey rsa:2048 -nodes -keyout "$role/client.key" -out "$role/request.csr" -subj "/CN=$role" >/dev/null 2>&1
  printf 'subjectAltName=DNS:%s,DNS:%s-restore,DNS:localhost\nextendedKeyUsage=serverAuth,clientAuth\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n' "$role" "$role" > "$role/ext.cnf"
  openssl x509 -req -in "$role/request.csr" -CA ca.pem -CAkey ca.key -CAcreateserial -out "$role/client.crt" -days 2 -extfile "$role/ext.cnf" >/dev/null 2>&1
  cp "$role/client.crt" "$role/server.crt"; cp "$role/client.key" "$role/server.key"
done
# Unknown leaf is signed by a different CA for mTLS negative tests.
openssl x509 -req -in unknown/request.csr -CA untrusted-ca.pem -CAkey untrusted-ca.key -CAcreateserial -out unknown/client.crt -days 2 -extfile unknown/ext.cnf >/dev/null 2>&1
chmod -R a+rX /work/pki
'''
    write(folder / 'pki-create.sh', script)
    cmd('docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--read-only', '--memory', '128m', '--cpus', '0.5',
        '--pids-limit', '32', '--label', LABEL + '=' + run, '-v', str(folder) + ':/work', '--entrypoint', '/bin/sh',
        'postgres:17.6', '/work/pki-create.sh', timeout=90)
    # Vendor definitions are version-specific; copy no demo users or credentials.
    security = folder / 'config/security'
    security.mkdir()
    for name in ['roles.yml', 'action_groups.yml', 'tenants.yml', 'nodes_dn.yml', 'allowlist.yml', 'audit.yml']:
        raw = cmd('docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--read-only', '--memory', '64m',
                  '--pids-limit', '32', '--label', LABEL + '=' + run, '--entrypoint', 'cat', IMAGES['opensearch'],
                  '/usr/share/opensearch/config/opensearch-security/' + name)
        write(security / name, raw)
    generate(folder, run)
    lab = Lab()
    lab.validate()
    print('Prepared disposable run:', run, flush=True)


def generate(folder, run):
    secure = ROOT / 'observability/secure-production'
    config = folder / 'config'
    for role in (folder / 'pki').iterdir():
        if role.is_dir():
            shutil.copy2(folder / 'pki/ca.pem', role / 'ca.pem')
    # Native candidate paths/TLS settings retained; only fixture budgets/retention differ.
    for name in ['loki.yml', 'tempo.yml', 'collector.yml', 'opensearch.yml']:
        raw = (secure / name).read_text().replace('/run/tls/', '/tls/').replace('${env:OTEL_QUEUE_CAPACITY_BYTES}', '16384')
        if name == 'loki.yml':
            raw = raw.replace('720h', '24h').replace('compaction_interval: 10m', 'compaction_interval: 5s').replace('retention_delete_delay: 2h', 'retention_delete_delay: 5s')
        if name == 'tempo.yml':
            raw = raw.replace('max_block_duration: 5m', 'max_block_duration: 10s\n  trace_idle_period: 2s\n  flush_check_period: 1s')
            raw = raw.replace('block_retention: 72h', 'block_retention: 10m\n    compacted_block_retention: 5s\n    compaction_cycle: 5s')
            raw = raw.replace('backend: local', 'backend: local\n    blocklist_poll: 5s')
        if name == 'collector.yml':
            raw = raw.replace('endpoint: tempo:4317', 'endpoint: tempo:4317').replace('host: 127.0.0.1', 'host: 0.0.0.0')
            # Fixture-only metric listener is not a model for secure production metrics.
        if name == 'opensearch.yml':
            raw = raw.replace('springboot-observability-secure', 'phase6b').replace('telemetry-tls/', 'telemetry-tls/')
            raw = raw.replace('${OS_ADMIN_DN}', 'CN=admin').replace('${OS_NODE_DN}', 'CN=opensearch')
            raw += '\npath.repo: [/snapshots]\nplugins.index_state_management.job_interval: 1\n'
        write(config / name, raw)
    roles = (config / 'security/roles.yml').read_text().split('\ntelemetry_writer:')[0] + '''
telemetry_writer:
  cluster_permissions: [cluster_composite_ops]
  index_permissions:
    - index_patterns: ["springboot-user-20*-logs", "springboot-learning-20*-logs", "springboot-jwks-20*-logs"]
      allowed_actions: ["indices:data/write/bulk*", "indices:data/write/index*", "indices:data/write/create*", "indices:admin/create", "indices:admin/mapping/put"]
telemetry_reader:
  cluster_permissions: ["cluster:monitor/health"]
  index_permissions:
    - index_patterns: ["springboot-*-logs"]
      allowed_actions: [read]
'''
    write(config / 'security/roles.yml', roles)
    write(config / 'security/config.yml', (secure / 'security-config.example/config.yml').read_text())
    write(config / 'security/internal_users.yml', {'_meta': {'type': 'internalusers', 'config_version': 2}})
    write(config / 'security/roles_mapping.yml', {'_meta': {'type': 'rolesmapping', 'config_version': 2},
          'telemetry_writer': {'users': ['fluent-bit']}, 'telemetry_reader': {'users': ['reader']}})
    write(config / 'prometheus.json', {'global': {'scrape_interval': '2s', 'evaluation_interval': '2s'},
          'scrape_configs': [{'job_name': 'phase6b', 'scheme': 'https', 'tls_config': {'ca_file': '/tls/ca.pem',
          'cert_file': '/tls/client.crt', 'key_file': '/tls/client.key', 'insecure_skip_verify': False},
          'static_configs': [{'targets': ['probe:8443', 'loki:3100', 'tempo:3200', 'prometheus:9090']}]}]})
    write(config / 'prometheus-web.json', {'tls_server_config': {'cert_file': '/tls/server.crt', 'key_file': '/tls/server.key',
          'client_ca_file': '/tls/ca.pem', 'client_auth_type': 'RequireAndVerifyClientCert'}})
    datasources = {'apiVersion': 1, 'datasources': []}
    for name, port in [('loki', 3100), ('tempo', 3200), ('prometheus', 9090)]:
        datasources['datasources'].append({'name': name, 'uid': name, 'type': name, 'access': 'proxy',
            'url': 'https://' + name + ':' + str(port), 'jsonData': {'tlsAuth': True, 'tlsAuthWithCACert': True, 'tlsSkipVerify': False},
            'secureJsonData': {'tlsCACert': (folder / 'pki/ca.pem').read_text(),
            'tlsClientCert': (folder / 'pki/grafana/client.crt').read_text(),
            'tlsClientKey': (folder / 'pki/grafana/client.key').read_text()}})
    write(folder / 'grafana-provisioning/datasources.yml', datasources)
    write(config / 'parsers.conf', '[PARSER]\n    Name json\n    Format json\n')
    write(config / 'fluent-bit.conf', '''[SERVICE]
    Flush 1
    Grace 5
    Log_Level info
    scheduler.base 1
    scheduler.cap 3
    Parsers_File /config/parsers.conf
    storage.path /state/buffer
    storage.sync full
    storage.checksum on
    storage.metrics on
    HTTP_Server On
    HTTP_Listen 0.0.0.0
    HTTP_Port 2020
[INPUT]
    Name tail
    Tag fixture
    Path /source/spool/*.log
    Parser json
    DB /state/tail.db
    DB.sync Full
    DB.journal_mode WAL
    Read_from_Head On
    Refresh_Interval 1
    storage.type filesystem
[OUTPUT]
    Name loki
    Match *
    Host loki
    Port 3100
    Labels job=phase6b,service=fixture,environment=test
    Line_Format json
    Retry_Limit False
    storage.total_limit_size 64k
    tls On
    tls.verify On
    tls.verify_hostname On
    tls.ca_file /tls/ca.pem
    tls.crt_file /tls/client.crt
    tls.key_file /tls/client.key
[OUTPUT]
    Name opensearch
    Match *
    Host opensearch
    Port 9200
    Logstash_Format On
    Logstash_Prefix springboot-user
    Logstash_DateFormat %Y.%m.%d-logs
    Suppress_Type_Name On
    Generate_ID On
    Retry_Limit False
    storage.total_limit_size 1M
    tls On
    tls.verify On
    tls.verify_hostname On
    tls.ca_file /tls/ca.pem
    tls.crt_file /tls/client.crt
    tls.key_file /tls/client.key
''')
    volumes = {'source': 8, 'fb': 16, 'queue': 16, 'loki': 128, 'tempo': 128, 'prometheus': 128,
               'grafana': 64, 'os': 768, 'snapshots': 128, 'diskfull': 2}
    for key in ['loki', 'tempo', 'prometheus', 'grafana', 'os']:
        volumes[key + '-restore'] = volumes[key]
    def bind(source, target):
        return {'type': 'bind', 'source': str(source), 'target': target, 'read_only': True, 'bind': {'create_host_path': False}}
    def service(image, role, memory, mounts=None, command=None):
        value = {'image': image, 'pull_policy': 'never', 'labels': {LABEL: run}, 'networks': ['isolated'],
          'restart': 'no', 'read_only': True, 'user': '0:0', 'cap_drop': ['ALL'],
          'security_opt': ['no-new-privileges:true'], 'mem_limit': memory, 'memswap_limit': memory,
          'cpus': 0.5, 'pids_limit': 128, 'tmpfs': ['/tmp:rw,nosuid,nodev,size=32m,mode=1777'],
          'logging': {'driver': 'json-file', 'options': {'max-size': '2m', 'max-file': '2'}},
          'volumes': [bind(config, '/config'), bind(folder / 'pki' / role, '/tls')] + (mounts or [])}
        if command:
            value['command'] = command
        return value
    services = {}
    services['probe'] = service(IMAGES['probe'], 'probe', '128m',
        [bind(folder / 'suite', '/suite'), bind(folder / 'pki', '/pki'),
         {'type': 'bind', 'source': str(folder / 'evidence'), 'target': '/lab/evidence'},
         *[key + ':/stores/' + key for key in volumes]], ['python', '/suite/probe.py'])
    services['probe']['env_file'] = [str(folder / 'test.env')]
    for name, directory in [('loki', '/loki'), ('tempo', '/var/tempo')]:
        services[name] = service(IMAGES[name], name, '384m', [name + ':' + directory], ['-config.file=/config/' + name + '.yml'])
    services['collector'] = service(IMAGES['collector'], 'collector', '192m', ['queue:/var/lib/otelcol'], ['--config=/config/collector.yml'])
    services['fluent-bit'] = service(IMAGES['fluent-bit'], 'fluent-bit', '96m', ['source:/source:ro', 'fb:/state'], ['-c', '/config/fluent-bit.conf'])
    services['prometheus'] = service(IMAGES['prometheus'], 'prometheus', '256m', ['prometheus:/prometheus'],
        ['--config.file=/config/prometheus.json', '--web.config.file=/config/prometheus-web.json', '--storage.tsdb.path=/prometheus',
         '--storage.tsdb.retention.time=15m', '--storage.tsdb.retention.size=32MB', '--web.enable-admin-api'])
    services['prometheus']['command'] += ['--storage.tsdb.wal-segment-size=16MB', '--storage.tsdb.max-block-chunk-segment-size=16MB']
    services['grafana'] = service(IMAGES['grafana'], 'grafana', '256m', ['grafana:/var/lib/grafana',
        bind(folder / 'grafana-provisioning', '/etc/grafana/provisioning/datasources')])
    services['grafana']['environment'] = {'GF_SECURITY_ADMIN_USER': '${TEST_GRAFANA_USER:?test-only identity required}',
        'GF_SECURITY_ADMIN_PASSWORD': '${TEST_GRAFANA_PASSWORD:?test-only secret required}', 'GF_SERVER_PROTOCOL': 'https',
        'GF_SERVER_CERT_FILE': '/tls/server.crt', 'GF_SERVER_CERT_KEY': '/tls/server.key', 'GF_ANALYTICS_REPORTING_ENABLED': 'false',
        'GF_ANALYTICS_CHECK_FOR_UPDATES': 'false', 'GF_ALERTING_ENABLED': 'false', 'GF_UNIFIED_ALERTING_ENABLED': 'true',
        'GF_UNIFIED_ALERTING_MIN_INTERVAL': '10s'}
    services['opensearch'] = service(IMAGES['opensearch'], 'opensearch', '1280m', ['os:/usr/share/opensearch/data',
        'snapshots:/snapshots', bind(config / 'opensearch.yml', '/usr/share/opensearch/config/opensearch.yml'),
        bind(folder / 'pki/opensearch', '/usr/share/opensearch/config/telemetry-tls')])
    services['opensearch']['user'] = '1000:1000'
    # Native startup creates its keystore. Data/repository/temp/log writes remain bounded.
    services['opensearch']['read_only'] = False
    services['opensearch']['tmpfs'][0] = '/tmp:rw,exec,nosuid,nodev,size=64m,mode=1777'
    services['opensearch']['cpus'] = 1
    services['opensearch']['pids_limit'] = 256
    services['opensearch']['environment'] = {'DISABLE_SECURITY_PLUGIN': 'false', 'DISABLE_INSTALL_DEMO_CONFIG': 'true',
          'OPENSEARCH_JAVA_OPTS': '-Xms384m -Xmx384m'}
    services['opensearch']['tmpfs'].append('/usr/share/opensearch/logs:rw,size=16m,uid=1000,gid=1000')
    services['opensearch']['entrypoint'] = ['/usr/share/opensearch/bin/opensearch']
    services['security-init'] = service(IMAGES['opensearch'], 'admin', '256m', [bind(folder / 'pki', '/pki'), bind(config / 'security', '/security')])
    services['security-init']['profiles'] = ['bootstrap']
    services['security-init']['user'] = '1000:1000'
    services['security-init']['tmpfs'][0] = '/tmp:rw,exec,nosuid,nodev,size=32m,mode=1777'
    services['security-init']['entrypoint'] = ['/usr/share/opensearch/plugins/opensearch-security/tools/securityadmin.sh']
    services['security-init']['environment'] = {'JAVA_HOME': '/usr/share/opensearch/jdk', 'JAVA_OPTS': '-Xmx128m'}
    import copy
    for name in ['loki', 'tempo', 'prometheus', 'grafana', 'opensearch']:
        target = name + '-restore'
        services[target] = copy.deepcopy(services[name])
        services[target]['profiles'] = ['restore']
        key = 'os' if name == 'opensearch' else name
        services[target]['volumes'] = [mount.replace(key + ':', key + '-restore:', 1) if isinstance(mount, str) and mount.startswith(key + ':') else mount for mount in services[target]['volumes']]
    model = {'name': PROJECT, 'services': services, 'networks': {'isolated': {'name': PROJECT + '_' + run, 'internal': True, 'labels': {LABEL: run}}},
        'volumes': {key: {'name': PROJECT + '_' + run + '_' + key, 'driver': 'local', 'labels': {LABEL: run},
            'driver_opts': {'type': 'tmpfs', 'device': 'tmpfs', 'o': 'size=' + str(size) + 'm,mode=0777'}} for key, size in volumes.items()}}
    write(folder / 'compose.json', model)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'validate', 'start', 'test', 'preserve', 'collect', 'stop', 'cleanup'])
    parser.add_argument('--confirm')
    parser.add_argument('--suite', choices=['security', 'opensearch', 'crash', 'overflow', 'lifecycle', 'performance', 'backup', 'backup-native', 'retention'])
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
        return
    lab = Lab()
    if args.mode == 'test':
        from suites import execute
        lab.invocation = 'python observability/phase6b/lab.py ' + ' '.join(sys.argv[1:])
        first = len(lab.rows)
        execute(lab, args.suite)
        sys.exit(exit_status(lab.rows[first:]))
    elif args.mode == 'cleanup':
        cleanup(lab, args.confirm)
    else:
        getattr(lab, args.mode)()


def cleanup(lab, confirmation):
    if confirmation != lab.run:
        raise RuntimeError('Volume deletion requires --confirm ' + lab.run + '; evidence is never deleted')
    lab.stop()
    model = json.loads(lab.file.read_text())
    targets = [r for r in inventory() if r['project'] == PROJECT and r['run'] == lab.run]
    for row in targets:
        cmd('docker', 'rm', row['id'])
    for volume in model['volumes'].values():
        row = json.loads(cmd('docker', 'volume', 'inspect', volume['name']))[0]
        assert row.get('Labels', {}).get(LABEL) == lab.run
        cmd('docker', 'volume', 'rm', volume['name'])
    for network in model['networks'].values():
        row = json.loads(cmd('docker', 'network', 'inspect', network['name']))[0]
        assert row.get('Labels', {}).get(LABEL) == lab.run
        cmd('docker', 'network', 'rm', network['name'])
    lab.result('PASS', 'explicitly confirmed task-owned cleanup', 'Evidence retained; exact labelled resource names only')


if __name__ == '__main__':
    main()
