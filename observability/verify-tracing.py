"""Phase 3 runtime evidence. Never prints credentials, JWTs, bodies or expanded Compose."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'observability/.phase3-state.json'
COMPOSE = ['compose', '-p', 'springboot_project', '--env-file', '.env',
           '-f', 'docker-compose.yml', '-f', 'docker-compose.debug.yml']
spec = importlib.util.spec_from_file_location('metrics', ROOT / 'observability/verify-metrics.py')
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)
request, check = metrics.request, metrics.check


def docker(*args):
    result = subprocess.run(['docker', *args], cwd=ROOT, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Docker operation failed; output withheld')
    return result.stdout


def inventory():
    ids = docker('ps', '-aq').split()
    result = {}
    for item in json.loads(docker('inspect', *ids)):
        result[item['Name']] = {key: item[key] for key in ('Id', 'Image', 'RestartCount', 'Mounts')}
        result[item['Name']]['Mounts'] = sorted(item['Mounts'], key=lambda mount: mount['Destination'])
        result[item['Name']]['started'] = item['State']['StartedAt']
        result[item['Name']]['ports'] = item['HostConfig']['PortBindings']
        result[item['Name']]['networks'] = sorted(item['NetworkSettings']['Networks'])
    return result


def fingerprints():
    paths = list(ROOT.glob('.env*')) + list((ROOT / 'key').glob('*.pem'))
    paths += list((ROOT / 'data/keys/learning').glob('*.pem'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file() and not p.name.endswith('.example')}


def internal(url, post=False):
    args = [*COMPOSE, 'exec', '-T', 'prometheus', 'wget', '-q', '-O', '-']
    if post:
        args += ['--post-data=']
    return docker(*args, url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--restart-tempo', action='store_true')
    parser.add_argument('--credentials', default='observability/local-test-credentials.json')
    args = parser.parse_args()
    model = json.loads(docker(*COMPOSE, 'config', '--format', 'json'))
    ports = {s: int(model['services'][s]['ports'][0]['published'])
             for s in ('user-api', 'learning-api', 'jwks-api', 'grafana', 'loki', 'opensearch', 'prometheus')}
    if args.snapshot:
        keys = {path: request(ports['jwks-api'], path)[1:] for path in
                ('/api/v1/jwks/user', '/api/v1/jwks/learning')}
        # Persist only public response fingerprints, no keys or environment values.
        jwks = {p: {'body': hashlib.sha256(json.dumps(v[1], sort_keys=True).encode()).hexdigest(),
                    'contentType': v[0].get('Content-Type'), 'cache': v[0].get('Cache-Control')}
                for p, v in keys.items()}
        STATE.write_text(json.dumps({'containers': inventory(), 'files': fingerprints(), 'jwks': jwks}))
        print('PASS: before-deployment inventory, protected fingerprints and public JWKS snapshot')
        return

    start = time.time()
    marker = 'phase3-' + uuid.uuid4().hex[:16]
    print('Correlation marker:', marker, flush=True)
    for service in ('user-api', 'learning-api', 'jwks-api'):
        check(request(ports[service], '/actuator/health/readiness')[0] == 200, service + ' readiness')
        exposition = internal('http://' + service + ':9091/actuator/prometheus')
        check('spring_security_http_secured_requests_seconds_count' in exposition,
              service + ' framework security metrics preserved')
    check('Server available' in internal('http://otel-collector:13133/'), 'Collector health extension')
    check('ready' in internal('http://tempo:3200/ready').lower(), 'Tempo readiness')
    targets = request(ports['prometheus'], '/api/v1/targets')[2]['data']['activeTargets']
    targets = [t for t in targets if t['labels'].get('job') == 'springboot']
    check(len(targets) == 3 and all(t['health'] == 'up' for t in targets), 'three Prometheus targets UP')

    grafana = model['services']['grafana']['environment']
    basic = base64.b64encode((grafana['GF_SECURITY_ADMIN_USER'] + ':' +
                             grafana['GF_SECURITY_ADMIN_PASSWORD']).encode()).decode()
    auth = {'Authorization': 'Basic ' + basic}
    status, _, health = request(ports['grafana'], '/api/datasources/uid/tempo/health', headers=auth)
    if status == 404 and health.get('messageId') == 'plugin.notImplemented':
        print('INFO: Tempo plugin health method unsupported; verifying proxied readiness and query', flush=True)
        check(request(ports['grafana'], '/api/datasources/proxy/uid/tempo/ready', headers=auth)[0] == 200,
              'Grafana Tempo proxied readiness')
        query = '/api/datasources/proxy/uid/tempo/api/search?' + urllib.parse.urlencode({'q': '{}'})
        check(request(ports['grafana'], query, headers=auth)[0] == 200, 'Grafana Tempo TraceQL connectivity')
    else:
        check(status == 200 and health['status'] == 'OK', 'Grafana Tempo datasource connectivity')
    for uid in ('loki', 'prometheus'):
        check(request(ports['grafana'], '/api/datasources/uid/' + uid + '/health', headers=auth)[0] == 200,
              'Grafana ' + uid + ' datasource retained')
    loki_settings = request(ports['grafana'], '/api/datasources/uid/loki', headers=auth)[2]
    derived = loki_settings['jsonData']['derivedFields'][0]
    check(derived.get('datasourceUid') == 'tempo' and derived.get('url') == '${__value.raw}',
          'Grafana rendered Loki trace link and Tempo UID')

    def tempo(trace):
        status, _, body = request(ports['grafana'], '/api/datasources/proxy/uid/tempo/api/traces/' + trace,
                                  headers=auth)
        return body if status == 200 else None

    probes = []
    for service, path, expected in [('user-api', '/internal/users/' + str(uuid.uuid4()), 401),
                                    ('learning-api', '/api/v1/learning/me', 401),
                                    ('jwks-api', '/api/v1/jwks/user', 200)]:
        trace, parent = uuid.uuid4().hex, uuid.uuid4().hex[:16]
        correlation = marker + '-' + service
        status, headers, _ = request(ports[service], path + '?password=TRACE_QUERY_SECRET', headers={
            'traceparent': f'00-{trace}-{parent}-01', 'tracestate': 'verify=value',
            'X-Correlation-ID': correlation, 'Cookie': 'test=TRACE_COOKIE_SECRET'})
        check(status == expected and headers.get('X-Correlation-ID') == correlation,
              service + ' status/correlation retained')
        probes.append((service, trace, parent, correlation))

    trace, parent = uuid.uuid4().hex, uuid.uuid4().hex[:16]
    correlation = marker + '-jwks-linked'
    status, headers, _ = request(ports['learning-api'], '/api/v1/integration/jwks', headers={
        'traceparent': f'00-{trace}-{parent}-01', 'X-Correlation-ID': correlation})
    check(status == 200 and headers.get('X-Correlation-ID') == correlation,
          'live public Learning -> JWKS request (distinct from Learning -> User)')
    probes.append(('jwks-linked', trace, parent, correlation))

    credentials = ROOT / args.credentials
    linked_trace = None
    if credentials.is_file():
        check(subprocess.run(['git', 'check-ignore', '--quiet', str(credentials)], cwd=ROOT).returncode == 0,
              'credentials file ignored')
        account = json.loads(credentials.read_text(encoding='utf-8-sig'))
        refresh = token = None
        try:
            status, _, body = request(ports['user-api'], '/auth/login', 'POST', account)
            check(status == 200, 'existing account login')
            token, refresh = body['data']['accessToken'], body['data']['refreshToken']
            claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '==='))
            linked_trace, parent = uuid.uuid4().hex, uuid.uuid4().hex[:16]
            status, headers, _ = request(ports['learning-api'],
                '/api/v1/learning/internal-test/users/' + claims['sub'], headers={
                    'Authorization': 'Bearer ' + token, 'X-Correlation-ID': marker + '-linked',
                    'traceparent': f'00-{linked_trace}-{parent}-01'})
            check(status == 200 and headers.get('X-Correlation-ID') == marker + '-linked',
                  'live authenticated Learning -> User request')
            probes.append(('linked', linked_trace, parent, marker + '-linked'))
        finally:
            if refresh:
                check(request(ports['user-api'], '/auth/logout', 'POST', {'refreshToken': refresh},
                              {'Authorization': 'Bearer ' + token})[0] == 200, 'verification session logout')
    else:
        print('NOT VERIFIED: positive login/logout, internal JWT and live Learning -> User; no credentials', flush=True)

    traces = {}
    for service, trace, parent, correlation in probes:
        body = None
        for _ in range(20):
            body = tempo(trace)
            if body:
                break
            time.sleep(2)
        check(body is not None, service + ' stored trace ' + trace)
        traces[trace] = body
        spans = []
        for batch in body.get('batches', body.get('resourceSpans', [])):
            attrs = {a['key']: a['value'].get('stringValue') for a in batch['resource']['attributes']}
            identity = attrs.get('service.name')
            check(bool(re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}', attrs.get('service.version', '')))
                  and attrs.get('deployment.environment.name') ==
                  model['services']['learning-api']['environment']['DEPLOYMENT_ENVIRONMENT']
                  and 'deployment.environment' not in attrs, service + ' version/environment resource conventions')
            for scope in batch.get('scopeSpans', batch.get('instrumentationLibrarySpans', [])):
                spans += [(identity, span) for span in scope['spans']]
        def hexid(value):
            return value if re.fullmatch('[0-9a-f]{16,32}', value) else base64.b64decode(value).hex()
        check(bool(spans) and all(hexid(span['traceId']) == trace and
              int(span['endTimeUnixNano']) > int(span['startTimeUnixNano']) for _, span in spans),
              service + ' common trace ID and positive span durations')
        check(len({span['spanId'] for _, span in spans}) == len(spans), service + ' distinct span IDs')
        servers = [(s, v) for s, v in spans if v['kind'] in (2, 'SPAN_KIND_SERVER')]
        if service not in ('linked', 'jwks-linked'):
            expected = {'user-api': 'user-learning', 'learning-api': 'learning-api', 'jwks-api': 'jwks-service'}[service]
            chosen = [v for s, v in servers if s == expected]
            check(len(chosen) == 1 and hexid(chosen[0]['parentSpanId']) == parent,
                  service + ' exactly one server span with remote parent')
        else:
            destination = 'user-api' if service == 'linked' else 'jwks-api'
            destination_identity = 'user-learning' if service == 'linked' else 'jwks-service'
            outgoing = [v for s, v in spans if s == 'learning-api' and v['kind'] in (3, 'SPAN_KIND_CLIENT')
                        and any(a['key'] == 'client.name' and a['value'].get('stringValue') == destination
                                for a in v.get('attributes', []))]
            user = [v for s, v in servers if s == destination_identity]
            learning = [v for s, v in servers if s == 'learning-api']
            check(len(outgoing) == len(user) == len(learning) == 1, service + ' one source/client/destination span')
            check(hexid(outgoing[0]['parentSpanId']) == hexid(learning[0]['spanId'])
                  and hexid(user[0]['parentSpanId']) == hexid(outgoing[0]['spanId']),
                  service + ' live Learning server -> client -> destination server parent relationship')
        encoded = json.dumps(body)
        check('TRACE_QUERY_SECRET' not in encoded and 'TRACE_COOKIE_SECRET' not in encoded,
              service + ' sensitive probes absent from stored trace')
        check(not any(key in encoded.lower() for key in
              ('authorization', 'http.url', 'url.full', 'exception.message', 'exception.stacktrace')),
              service + ' forbidden credential/URL/exception attributes absent')
        print('Observed spans:', [(s, hexid(v['spanId']), hexid(v.get('parentSpanId', '0' * 16)),
                                   v['name']) for s, v in spans], flush=True)

    # Verify fresh completions in both pre-existing backends, including SDK-owned IDs.
    for service, trace, parent, correlation in probes:
        query = '{service=~"user-learning|learning-api|jwks-service"} |= "' + correlation + '"'
        loki = '/loki/api/v1/query_range?' + urllib.parse.urlencode({
            'query': query, 'start': str(int(start * 1e9)), 'end': str(time.time_ns()), 'limit': 200})
        hits = []
        for _ in range(15):
            streams = request(ports['loki'], loki)[2]['data']['result']
            hits = [json.loads(line) for stream in streams for _, line in stream['values']
                    if json.loads(line).get('event') == 'http.request.completed']
            if hits:
                break
            time.sleep(2)
        expected_count = 2 if service in ('linked', 'jwks-linked') else 1
        check(len(hits) == expected_count and all(h.get('traceId') == trace and
              re.fullmatch('[0-9a-f]{16}', h.get('spanId', '')) for h in hits),
              service + ' Loki completion count, correlation and trace/span fields')
        check(all(re.search(derived['matcherRegex'], json.dumps(hit)).group(1) == trace for hit in hits),
              service + ' derived link matches actual ingested JSON trace ID')
        search = {'query': {'bool': {'filter': [{'term': {'correlationId.keyword': correlation}},
                   {'term': {'event.keyword': 'http.request.completed'}}]}}, 'size': 20}
        found = []
        for _ in range(20):
            result = request(ports['opensearch'], '/springboot-*-logs/_search', 'POST', search)[2]
            found = result.get('hits', {}).get('hits', [])
            if len(found) >= expected_count:
                break
            time.sleep(2)
        check(len(found) == expected_count and all(h['_source'].get('traceId') == trace for h in found),
              service + ' OpenSearch ingestion and trace field')

    if args.restart_tempo:
        # Controlled ordinary restart only; never deletes volume or claims crash durability.
        docker(*COMPOSE, 'restart', '--no-deps', '--timeout', '45', 'tempo')
        for _ in range(20):
            try:
                if 'ready' in internal('http://tempo:3200/ready').lower():
                    break
            except RuntimeError:
                pass
            time.sleep(2)
        check(all(tempo(trace) for trace in traces), 'stored traces queryable after ordinary Tempo restart')

    before = json.loads(STATE.read_text())
    for item in before['containers'].values():
        item['Mounts'] = sorted(item['Mounts'], key=lambda mount: mount['Destination'])
    after = inventory()
    affected = {'/springboot_project-' + s + '-1' for s in ('user-api', 'learning-api', 'jwks-api', 'grafana')}
    unchanged = [name for name in before['containers'] if name not in affected]
    check(all(after.get(name) == before['containers'][name] for name in unchanged),
          str(len(unchanged)) + ' unrelated containers unchanged, including jp_dev')
    check(fingerprints() == before['files'], 'environment/key fingerprints unchanged')
    for path, original in before['jwks'].items():
        status, headers, body = request(ports['jwks-api'], path)
        check(status == 200 and hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() == original['body']
              and headers.get('Content-Type') == original['contentType']
              and headers.get('Cache-Control') == original['cache'], 'JWKS public response unchanged: ' + path)
    for service in ('user-api', 'learning-api', 'jwks-api'):
        lines = docker(*COMPOSE, 'logs', '--since', '10m', '--no-color', '--no-log-prefix', service)
        errors = [line for line in lines.splitlines() if re.search('export.*(fail|error)|failed to export', line, re.I)]
        check(not errors, service + ' no exporter errors in checked window')
    print('PASS: Phase 3 available runtime probes; credential gaps above remain NOT VERIFIED', flush=True)


if __name__ == '__main__':
    main()
