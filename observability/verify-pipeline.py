"""Local Phase 4 validation/recovery. Never prints expanded Compose or secret payloads."""
import argparse
import base64
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tracing', ROOT / 'observability/verify-tracing.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
BASE = json.loads((ROOT / 'observability/phase4-baseline.log').read_text())
EVIDENCE = ROOT / 'observability/phase4-recovery-evidence.log'
AFFECTED = {'user-api', 'learning-api', 'jwks-api', 'fluent-bit', 'loki', 'opensearch',
            'opensearch-dashboards', 'prometheus', 'otel-collector', 'tempo', 'grafana'}
MODEL = None


def check(ok, label):
    if not ok:
        raise AssertionError(label)
    print('PASS:', label, flush=True)


def compose(*args):
    return v.docker(*v.COMPOSE, *args)


def model():
    global MODEL
    if MODEL is None:
        MODEL = json.loads(compose('config', '--format', 'json'))
    return MODEL


def port(service):
    return BASE['ports'][service]


def wait_for(function, label, attempts=60):
    for _ in range(attempts):
        try:
            result = function()
            if result:
                return result
        except (OSError, KeyError, RuntimeError):
            pass
        time.sleep(2)
    raise AssertionError('Timed out: ' + label)


def record(name, value):
    data = json.loads(EVIDENCE.read_text()) if EVIDENCE.is_file() else {}
    data[name] = value
    EVIDENCE.write_text(json.dumps(data, indent=2))


def request(service, path, method='GET', body=None):
    return v.request(port(service), path, method, body)


def grafana(path):
    env = model()['services']['grafana']['environment']
    basic = base64.b64encode((env['GF_SECURITY_ADMIN_USER'] + ':' + env['GF_SECURITY_ADMIN_PASSWORD']).encode()).decode()
    return v.request(port('grafana'), path, headers={'Authorization': 'Basic ' + basic})


def loki_hits(marker):
    now = time.time_ns()
    params = urllib.parse.urlencode({'query': '{service="jwks-service"} | json | correlationId="' + marker + '"',
                                     'start': str(now - 24 * 3600 * 10**9), 'end': str(now), 'limit': 100})
    response = request('loki', '/loki/api/v1/query_range?' + params)
    if response[0] != 200:
        return []
    return [json.loads(line) for stream in response[2]['data']['result'] for _, line in stream['values']
            if json.loads(line).get('event') == 'http.request.completed']


def os_hits(marker):
    body = {'query': {'bool': {'filter': [{'term': {'correlationId.keyword': marker}},
             {'term': {'event.keyword': 'http.request.completed'}}]}}, 'size': 100}
    response = request('opensearch', '/springboot-*-logs/_search', 'POST', body)
    return response[2].get('hits', {}).get('hits', []) if response[0] == 200 else []


def probe(label):
    marker, trace = 'phase4-' + label + '-' + uuid.uuid4().hex[:12], uuid.uuid4().hex
    port_number = int(next(p['published'] for p in model()['services']['jwks-api']['ports'] if int(p['target']) == 8080))
    status, headers, _ = v.request(port_number, '/api/v1/jwks/user', headers={
        'X-Correlation-ID': marker, 'traceparent': '00-' + trace + '-' + uuid.uuid4().hex[:16] + '-01'})
    check(status == 200 and headers.get('X-Correlation-ID') == marker, 'real safe JWKS probe ' + marker)
    return {'marker': marker, 'traceId': trace}


def trace(item):
    status, _, body = grafana('/api/datasources/proxy/uid/tempo/api/traces/' + item['traceId'])
    return body if status == 200 and isinstance(body, dict) else None


def buffer_state():
    return json.loads(v.internal('http://fluent-bit:2020/api/v1/storage'))


def retry_count():
    return json.loads(v.internal('http://fluent-bit:2020/api/v1/metrics'))['output']


def validate():
    compose('config', '--quiet')
    v.docker('compose', '-p', 'springboot_project', '--env-file', '.env', '-f', 'docker-compose.yml', 'config', '--quiet')
    m = model()
    for name, old in BASE['services'].items():
        current = m['services'][name]
        check(current.get('ports') == old.get('ports'), name + ' original published ports preserved')
        old_mounts = {x['target']: x for x in old.get('volumes') or []}
        new_mounts = {x['target']: x for x in current.get('volumes') or []}
        check(all(new_mounts.get(path) == mount for path, mount in old_mounts.items()), name + ' original mounts preserved')
        if name in AFFECTED:
            logging = current['logging']
            check(logging['driver'] == 'json-file' and logging['options']['max-file'] == '3'
                  and logging['options']['max-size'] == '10m', name + ' bounded Docker logging defaults')
        else:
            for field in ('logging', 'image', 'read_only', 'user', 'restart'):
                check(current.get(field) == old.get(field), name + ' unrelated setting preserved: ' + field)
    for name in ('otel-collector', 'tempo', 'fluent-bit', 'otel-queue-init'):
        check(not m['services'][name].get('ports'), name + ' no published ingestion/diagnostics')
    for name in ('user-api', 'learning-api', 'jwks-api'):
        env = m['services'][name]['environment']
        check(env['MANAGEMENT_TRACING_SAMPLING_PROBABILITY'] == '0.1', name + ' 10 percent sampling preserved')
    fb = (ROOT / 'observability/fluent-bit/fluent-bit.conf').read_text()
    check(fb.count('Name              tail') == 3 and fb.count('storage.type      filesystem') == 3,
          'three non-overlapping filesystem-backed application tails')
    check(fb.count('DB.sync           Full') == 3 and fb.count('DB.journal_mode   WAL') == 3,
          'tail databases synchronized and persistent')
    check(fb.count('storage.total_limit_size') == 4 and 'storage.sync      full' in fb, 'all four independent outputs bounded')
    check('*.log' not in fb and '.gz' not in fb, 'only exact current log paths; archives excluded')
    check('Logstash_DateFormat %Y.%m.%d-logs' in fb, 'dated indices preserve existing wildcard prefix/suffix')
    collector = (ROOT / 'observability/otel-collector/config.yml').read_text()
    check('sizer: bytes' in collector and 'storage: file_storage/queue' in collector and 'fsync: true' in collector,
          'Collector persistent byte-sized synchronized queue')
    check(int(m['services']['otel-collector']['environment']['OTEL_QUEUE_CAPACITY_BYTES']) == 67108864,
          'Collector default serialized queue budget 64 MiB')
    check(m['services']['otel-queue-init']['network_mode'] == 'none', 'new queue initializer has no network')
    check('retention_period: 720h' in (ROOT / 'observability/loki/loki-config.yml').read_text(), 'Loki retention preserved at 30 days')
    check('block_retention: 72h' in (ROOT / 'observability/tempo/tempo.yml').read_text(), 'Tempo retention preserved at 72 hours')
    check(not subprocess.check_output(['git', 'diff', '--', 'observability/prometheus/prometheus.yml']), 'Prometheus scrape configuration unchanged')
    print('Configuration contract validation complete', flush=True)


def history_snapshot():
    now = time.time()
    params = urllib.parse.urlencode({'query': 'http_server_requests_seconds_count{service="jwks-service"}', 'time': str(now)})
    response = request('prometheus', '/api/v1/query?' + params)[2]
    check(bool(response['data']['result']), 'pre-restart Prometheus samples available')
    old = {'traceId': 'fda09edbe0bd47da8dee413d1fa31ec9'}
    check(bool(trace(old)), 'previous authenticated Phase 3 trace still available')
    record('history', {'time': now, 'queryParams': params, 'prometheus': response['data']['result'],
                       'oldTraceId': old['traceId']})


def log_failure(destination):
    other_hits = os_hits if destination == 'loki' else loki_hits
    destination_hits = loki_hits if destination == 'loki' else os_hits
    started = time.time()
    evidence = {'startedUtc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    item = None
    try:
        compose('stop', '--timeout', '30', destination)
        item = probe(destination + '-outage')
        evidence.update(item)
        wait_for(lambda: len(other_hits(item['marker'])) == 1, 'independent log destination')
        check(True, destination + ' outage does not block the other log destination')
        time.sleep(6)
        state = buffer_state()
        evidence['storageDuringOutage'] = state
        evidence['outputMetricsDuringOutage'] = retry_count()
        check(state['storage_layer']['chunks']['fs_chunks'] > 0, 'filesystem chunks buffered during ' + destination + ' outage')
        retrying = evidence['outputMetricsDuringOutage']
        check(any(values.get('retries', 0) > 0 for key, values in retrying.items()
                  if key.startswith('loki' if destination == 'loki' else 'opensearch')), destination + ' output retry observed')
        # Normal Fluent Bit restart with destination still unavailable; same tail DB and chunk volume.
        compose('restart', '--no-deps', '--timeout', '40', 'fluent-bit')
        wait_for(buffer_state, 'Fluent Bit storage after restart')
        evidence['storageAfterCollectorRestart'] = buffer_state()
    finally:
        # Start the exact existing container; Compose start may rerun completed initializers.
        v.docker('start', 'springboot_project-' + destination + '-1')
    if item:
        wait_for(lambda: len(destination_hits(item['marker'])) == 1, destination + ' buffered marker recovered')
        wait_for(lambda: len(other_hits(item['marker'])) == 1, 'other output no duplicate')
        check(len(destination_hits(item['marker'])) == len(other_hits(item['marker'])) == 1,
              destination + ' backlog delivered once to both stores after restart')
        for record_value in loki_hits(item['marker']):
            check(record_value.get('traceId') == item['traceId'] and bool(re.fullmatch('[0-9a-f]{16}', record_value.get('spanId', ''))),
                  'trace/span/correlation fields preserved after ' + destination + ' outage')
        evidence['result'] = 'PASS'
        evidence['durationSeconds'] = round(time.time() - started, 2)
        record(destination + 'Failure', evidence)


def trace_failure():
    started = time.time()
    evidence = {'startedUtc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    items = []
    try:
        compose('stop', '--timeout', '30', 'tempo')
        items = [probe('tempo-outage') for _ in range(3)]
        for item in items:
            wait_for(lambda: len(loki_hits(item['marker'])) == len(os_hits(item['marker'])) == 1,
                     'logs continue independently of Tempo')
        time.sleep(8)
        logs = compose('logs', '--since', '1m', '--no-color', 'otel-collector')
        check('retry' in logs.lower(), 'Collector retry observed while Tempo unavailable')
        evidence['queueFilesDuringOutage'] = v.docker('run', '--rm', '--network', 'none', '--read-only',
            '--user', '10001:10001', '-v', 'springboot_project_otel_queue:/state:ro', '--entrypoint', '/bin/sh',
            'postgres:17.6', '-c', 'find /state -type f -exec ls -ln {} +')
        check('otlp' in evidence['queueFilesDuringOutage'], 'persistent exporter queue database present')
        compose('restart', '--no-deps', '--timeout', '30', 'otel-collector')
        wait_for(lambda: 'Server available' in v.internal('http://otel-collector:13133/'), 'Collector ready with destination down')
    finally:
        v.docker('start', 'springboot_project-tempo-1')
    wait_for(lambda: 'ready' in v.internal('http://tempo:3200/ready'), 'Tempo readiness')
    for item in items:
        wait_for(lambda: trace(item), 'persisted trace recovered after Collector restart')
        check(True, 'persisted trace recovered ' + item['traceId'])
    evidence['items'] = items
    evidence['result'] = 'PASS'
    evidence['durationSeconds'] = round(time.time() - started, 2)
    record('tempoFailure', evidence)


def regression():
    history = json.loads(EVIDENCE.read_text())['history']
    actual = request('prometheus', '/api/v1/query?' + history['queryParams'])[2]['data']['result']
    canonical = lambda rows: sorted((json.dumps(x['metric'], sort_keys=True), x['value']) for x in rows)
    check(canonical(actual) == canonical(history['prometheus']), 'original Prometheus samples survive normal recreation/restart')
    check(bool(trace({'traceId': history['oldTraceId']})), 'old authenticated trace survives Tempo restart')
    for path, original in BASE['jwks'].items():
        check(request('jwks-api', path)[2] == original, 'JWKS public response unchanged ' + path)
    legacy_rows = request('opensearch', '/_cat/indices?format=json')[2]
    for previous in BASE['opensearch']['/_cat/indices?format=json']:
        if previous['index'] in ('springboot-user-logs', 'springboot-learning-logs', 'springboot-jwks-logs'):
            current = next(r for r in legacy_rows if r['index'] == previous['index'])
            check(current['uuid'] == previous['uuid'] and int(current['docs.count']) >= int(previous['docs.count']),
                  'legacy index UUID/documents preserved ' + previous['index'])
    today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y.%m.%d')
    for service in ('user', 'learning', 'jwks'):
        name = 'springboot-' + service + '-' + today + '-logs'
        state = request('opensearch', '/_plugins/_ism/explain/' + name)[2]
        check(state.get(name, {}).get('policy_id') == 'springboot-dated-logs-retention', 'new dated index automatically managed ' + service)
        mapping = request('opensearch', '/' + name + '/_mapping')[2][name]['mappings']
        check(mapping == BASE['opensearch']['/springboot-*-logs/_mapping']['springboot-' + service + '-logs']['mappings'],
              'existing mapping types preserved ' + service)
    now = v.inventory()
    # Only explicitly affected existing services may have changed identity/start time.
    changed = []
    for name, old in BASE['containers'].items():
        new = now.get(name)
        check(new is not None, 'original container still present ' + name)
        relevant = {k: old[k] for k in ('Id', 'Image', 'RestartCount', 'Mounts', 'started', 'ports', 'networks')}
        current = {k: new[k] for k in relevant}
        service = name.removeprefix('/springboot_project-').removesuffix('-1')
        if relevant != current:
            changed.append(name)
            # The first Tempo restore used Compose start, which reran its existing
            # network-disabled initializer. Only StartedAt changed; no data was removed.
            init_restart = service == 'tempo-storage-init' and all(
                relevant[key] == current[key] for key in relevant if key != 'started')
            check(old['project'] == 'springboot_project' and (service in AFFECTED or init_restart),
                  'only affected service or exact Tempo initializer restart changed ' + name)
    for path, fingerprint in BASE['protected'].items():
        check(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == fingerprint, 'protected file unchanged ' + path)
    evidence = {'result': 'PASS', 'changedContainers': changed,
                'unrelatedUnchanged': len(BASE['containers']) - len(changed),
                'jpDevUnchanged': sum(c['project'] == 'jp_dev' for c in BASE['containers'].values())}
    record('preservation', evidence)


def authenticated():
    path = ROOT / 'observability/local-test-credentials.json'
    if not path.is_file():
        record('authenticated', {'result': 'NOT VERIFIED', 'reason': 'existing credentials file unavailable'})
        print('NOT VERIFIED: authenticated JWT and Learning -> User regression; credentials absent')
        return
    check(subprocess.run(['git', 'check-ignore', '--quiet', str(path)], capture_output=True).returncode == 0,
          'existing credentials file ignored')
    account = json.loads(path.read_text(encoding='utf-8-sig'))
    account = {key: account[key] for key in ('usernameOrEmail', 'password')}
    api_ports = {name: int(next(p['published'] for p in model()['services'][name]['ports'] if int(p['target']) == 8080))
                 for name in ('user-api', 'learning-api')}
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    marker, trace_id = 'phase4-auth-' + uuid.uuid4().hex[:16], uuid.uuid4().hex
    secrets = list(account.values())
    token = refresh = None
    parent_id = uuid.uuid4().hex[:16]
    try:
        status, _, body = v.request(api_ports['user-api'], '/auth/login', 'POST', account)
        check(status == 200, 'existing account login')
        token, refresh = body['data']['accessToken'], body['data']['refreshToken']
        secrets += [token, refresh]
        old_refresh = refresh
        status, _, body = v.request(api_ports['user-api'], '/auth/refresh', 'POST', {'refreshToken': refresh})
        check(status == 200, 'existing verification session refresh')
        token, refresh = body['data']['accessToken'], body['data']['refreshToken']
        secrets += [token, refresh]
        check(refresh != old_refresh, 'refresh rotates only verification session')
        claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '==='))
        subject = claims['sub']
        secrets.append(subject)
        status, headers, body = v.request(api_ports['learning-api'], '/api/v1/learning/internal-test/users/' + subject,
            headers={'Authorization': 'Bearer ' + token, 'traceparent': '00-' + trace_id + '-' + parent_id + '-01',
                     'X-Correlation-ID': marker})
        check(status == 200 and body.get('user', {}).get('id') == subject, 'live Learning -> User internal JWT communication')
        check(headers.get('X-Correlation-ID') == marker and marker != trace_id, 'independent correlation response preserved')
        secrets += [value for key, value in body['user'].items() if key in ('username', 'email') and isinstance(value, str)]
    finally:
        if refresh:
            status, _, _ = v.request(api_ports['user-api'], '/auth/logout', 'POST', {'refreshToken': refresh},
                                     {'Authorization': 'Bearer ' + token})
            check(status == 200, 'verification session logged out in cleanup')
    def get_spans():
        body = trace({'traceId': trace_id})
        values = []
        if not body:
            return None
        for batch in body.get('batches', body.get('resourceSpans', [])):
            service = next(a['value']['stringValue'] for a in batch['resource']['attributes'] if a['key'] == 'service.name')
            for scope in batch.get('scopeSpans', batch.get('instrumentationLibrarySpans', [])):
                values += [(service, span) for span in scope['spans']]
        server = [x for s, x in values if s == 'learning-api' and x['kind'] in (2, 'SPAN_KIND_SERVER')]
        user = [x for s, x in values if s == 'user-learning' and x['kind'] in (2, 'SPAN_KIND_SERVER')]
        client = [x for s, x in values if s == 'learning-api' and x['kind'] in (3, 'SPAN_KIND_CLIENT') and
                  any(a['key'] == 'client.name' and a['value'].get('stringValue') == 'user-api' for a in x.get('attributes', []))]
        return (body, server[0], client[0], user[0]) if len(server) == len(client) == len(user) == 1 else None
    body, server, client, user = wait_for(get_spans, 'complete authenticated trace through Grafana')
    def span_id(value):
        return value if re.fullmatch('[0-9a-f]{16,32}', value) else base64.b64decode(value).hex()
    check(span_id(server['parentSpanId']) == parent_id and span_id(client['parentSpanId']) == span_id(server['spanId'])
          and span_id(user['parentSpanId']) == span_id(client['spanId']), 'W3C server/client/server parent chain preserved')
    check(all(span_id(x['traceId']) == trace_id for x in (server, client, user)), 'Learning and User share actual trace ID')
    expected = {'learning-api': span_id(server['spanId']), 'user-learning': span_id(user['spanId'])}
    logs = []
    for backend in ('loki', 'opensearch'):
        def matches():
            if backend == 'loki':
                params = urllib.parse.urlencode({'query': '{service=~"learning-api|user-learning"} | json | correlationId="' + marker + '"',
                                                 'start': str(int((time.time() - 600) * 1e9)), 'limit': 100})
                records = [json.loads(line) for stream in request('loki', '/loki/api/v1/query_range?' + params)[2]['data']['result']
                           for _, line in stream['values']]
            else:
                query = {'query': {'term': {'correlationId.keyword': marker}}, 'size': 100}
                records = [h['_source'] for h in request('opensearch', '/springboot-*-logs/_search', 'POST', query)[2]['hits']['hits']]
            core = [r for r in records if r.get('event') == 'http.request.completed' and r.get('service') in expected]
            return (records, core) if len(core) >= 2 else None
        records, core = wait_for(matches, backend + ' authenticated completions')
        check(len(core) == 2 and all(r.get('traceId') == trace_id and r.get('spanId') == expected[r['service']]
              and r.get('correlationId') == marker and r.get('http.response.status_code') == 200 for r in core),
              backend + ' actual trace/span/correlation/status and once-only completion preserved')
        logs += records
    telemetry = json.dumps(body) + json.dumps(logs)
    for service in ('user-api', 'learning-api', 'jwks-api'):
        telemetry += compose('logs', '--since', start, '--no-color', '--no-log-prefix', service)
    check(not any(value in telemetry for value in secrets if value), 'actual credentials/tokens/identity absent from inspected auth telemetry')
    check(not re.search(r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{16,}', telemetry),
          'no JWT-shaped value captured in auth telemetry')
    record('authenticated', {'result': 'PASS', 'traceId': trace_id, 'correlationId': marker,
            'learningServer': span_id(server['spanId']), 'client': span_id(client['spanId']), 'userServer': span_id(user['spanId']),
            'remoteParent': parent_id})
    print('Verified authenticated trace:', trace_id)


def health():
    for service in ('user-api', 'learning-api', 'jwks-api'):
        number = int(next(p['published'] for p in model()['services'][service]['ports'] if int(p['target']) == 8080))
        check(v.request(number, '/actuator/health/readiness')[0] == 200, service + ' readiness')
    check(request('prometheus', '/-/ready')[0] == 200, 'Prometheus readiness')
    targets = request('prometheus', '/api/v1/targets')[2]['data']['activeTargets']
    check(len(targets) == 3 and all(t['health'] == 'up' for t in targets), 'all three scrape targets UP')
    check(request('loki', '/ready')[0] == 200, 'Loki readiness')
    cluster = request('opensearch', '/_cluster/health')[2]
    shards = request('opensearch', '/_cat/shards?format=json&h=index,prirep,state')[2]
    unassigned = [s for s in shards if s['state'] == 'UNASSIGNED']
    check(cluster['status'] in ('green', 'yellow') and all(
        s['prirep'] == 'r' and s['index'].startswith('.opendistro-ism-')
        for s in unassigned
    ) and all(s['state'] == 'STARTED' for s in shards if s['prirep'] == 'p'),
        'OpenSearch primaries active; only documented ISM system replicas unassigned')
    check('Server available' in v.internal('http://otel-collector:13133/'), 'Collector readiness')
    check('ready' in v.internal('http://tempo:3200/ready'), 'Tempo readiness')
    check(request('grafana', '/api/health')[2]['database'] == 'ok', 'Grafana operational')
    for uid in ('loki', 'prometheus'):
        check(grafana('/api/datasources/uid/' + uid + '/health')[0] == 200, 'Grafana datasource ' + uid)
    check(grafana('/api/datasources/proxy/uid/tempo/ready')[0] == 200, 'Grafana Tempo datasource proxy')
    item = probe('final')
    wait_for(lambda: trace(item), 'fresh trace exported after final Collector restart')
    wait_for(lambda: len(loki_hits(item['marker'])) == len(os_hits(item['marker'])) == 1, 'fresh logs in both stores')
    check(True, 'fresh trace in Tempo and exactly one completion in both log stores')
    state = buffer_state()
    outputs = retry_count()
    check(all(x.get('dropped_records') == 0 and x.get('retries_failed') == 0 for x in outputs.values()),
          'no permanently failed retries or output-dropped records in current process')
    inspected = json.loads(v.docker('inspect', *['springboot_project-' + name + '-1' for name in sorted(AFFECTED)]))
    for container in inspected:
        options = container['HostConfig']['LogConfig']
        check(options['Type'] == 'json-file' and options['Config'].get('max-size') == '10m' and
              options['Config'].get('max-file') == '3' and options['Config'].get('compress') == 'true',
              'effective bounded Docker logging ' + container['Name'])
    record('finalHealth', {'result': 'PASS', **item, 'storage': state, 'outputs': outputs,
                          'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('config', 'history', 'loki', 'opensearch', 'tempo', 'regression', 'auth', 'health'))
    args = parser.parse_args()
    try:
        {'config': validate, 'history': history_snapshot, 'loki': lambda: log_failure('loki'),
         'opensearch': lambda: log_failure('opensearch'), 'tempo': trace_failure, 'regression': regression,
         'auth': authenticated, 'health': health}[args.mode]()
    except Exception as error:
        # Labels/paths are controlled; never dump backend payloads or expanded models.
        print('FAIL:', type(error).__name__, str(error) if isinstance(error, AssertionError) else '(details withheld)', flush=True)
        raise SystemExit(1)
