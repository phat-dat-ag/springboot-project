import importlib
import json
v = importlib.import_module('phase5-runtime')
names = sorted(x['metric']['__name__'] for x in v.query('count by (__name__) ({job="springboot"})'))
print('Application metric names:', ', '.join(names))
print('Security labels:', [x['metric'] for x in v.query('app_security_events_total')][:7])
for url in ['http://fluent-bit:2020/api/v1/metrics/prometheus', 'http://loki:3100/metrics',
            'http://tempo:3200/metrics', 'http://grafana:3000/metrics']:
    raw = v.command('docker', 'compose', '-p', 'springboot_project', 'exec', '-T', 'prometheus',
                    'wget', '-q', '-O', '-', url)
    out = v.ROOT / ('observability/phase5-' + url.split('/')[2].split(':')[0] + '-metrics.log')
    out.write_text(raw, encoding='utf-8')
    print(url, 'metric names:', sorted({line.split('{')[0].split(' ')[0] for line in raw.splitlines()
        if line and not line.startswith('#') and any(x in line.lower() for x in
            ['fail', 'error', 'queue', 'storage', 'discard', 'buffer', 'received', 'ingest'])})[:65])
b = json.loads((v.ROOT / 'observability/phase5-baseline.log').read_text())
print('Baseline policy:', {k:val for k,val in b['policies'].items() if k != 'routes'})
print('Project containers:', [(c['service'],c['status']) for c in b['containers'] if c['project']=='springboot_project'])
