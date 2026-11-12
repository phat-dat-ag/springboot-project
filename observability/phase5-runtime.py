"""Phase 5 local API helpers. Expanded Compose/secrets stay in memory."""
import base64
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import urllib.request
import urllib.error
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '-p', 'springboot_project', '--env-file', '.env',
           '-f', 'docker-compose.yml', '-f', 'docker-compose.debug.yml']

def command(*args):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
    if p.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(args[:4]) + '\n' + p.stderr)
    return p.stdout

@lru_cache(maxsize=1)
def model():
    return json.loads(command(*COMPOSE, 'config', '--format', 'json'))

def api(path, service='grafana', body=None):
    m = model()['services']
    port = next(p['published'] for p in m[service]['ports'] if p['target'] in (3000, 9090, 3100, 9200))
    headers = {}
    if service == 'grafana':
        e = m[service]['environment']
        auth = e['GF_SECURITY_ADMIN_USER'] + ':' + e['GF_SECURITY_ADMIN_PASSWORD']
        headers['Authorization'] = 'Basic ' + base64.b64encode(auth.encode()).decode()
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request('http://127.0.0.1:' + str(port) + path,
        data=json.dumps(body).encode() if body is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read().decode()
        try:
            return json.loads(raw)
        except ValueError:
            return raw

def query(expr):
    return api('/api/v1/query?' + urllib.parse.urlencode({'query': expr}), 'prometheus')['data']['result']

def inventory():
    ids = command('docker', 'ps', '-aq').split()
    rows = json.loads(command('docker', 'inspect', *ids))
    return [{ 'id': r['Id'], 'name': r['Name'], 'image': r['Config']['Image'],
        'project': r['Config'].get('Labels', {}).get('com.docker.compose.project'),
        'service': r['Config'].get('Labels', {}).get('com.docker.compose.service'),
        'started': r['State']['StartedAt'], 'status': r['State']['Status'],
        'mounts': r['Mounts'], 'ports': r['HostConfig']['PortBindings'],
        'logging': r['HostConfig']['LogConfig']} for r in rows]

def snapshot():
    target = ROOT / 'observability/phase5-baseline.log'
    if target.exists():
        raise RuntimeError('Baseline already exists; refusing to overwrite')
    dashboards = api('/api/search?type=dash-db&limit=5000')
    def health(path, service='grafana'):
        try:
            return api(path, service)
        except urllib.error.HTTPError as e:
            return {'http_status': e.code}
    data = {'containers': inventory(), 'volumes': command('docker', 'volume', 'ls', '-q').split(),
        'datasources': api('/api/datasources'), 'dashboards': dashboards,
        'dashboard_bodies': [api('/api/dashboards/uid/' + d['uid']) for d in dashboards],
        'alerts': api('/api/v1/provisioning/alert-rules'),
        'policies': api('/api/v1/provisioning/policies'),
        'contacts': api('/api/v1/provisioning/contact-points'),
        'targets': api('/api/v1/targets', 'prometheus'),
        'grafana_health': api('/api/health'),
        'prometheus_version': api('/api/v1/status/buildinfo', 'prometheus'),
        'loki_ready': health('/ready', 'loki'),
        'tempo_ready': health('/api/datasources/proxy/uid/tempo/ready')}
    target.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print('Baseline saved locally (ignored); containers:', len(data['containers']),
          'dashboards:', len(dashboards), 'alerts:', len(data['alerts']))
    print('Grafana:', data['grafana_health']['version'],
          'Prometheus:', data['prometheus_version']['data']['version'])
    print('Datasource UIDs:', [d['uid'] for d in data['datasources']])
    print('Contact types:', [c['type'] for c in data['contacts']])

if __name__ == '__main__':
    snapshot()
