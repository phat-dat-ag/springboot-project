"""Read-only Phase 0 checks. Never prints expanded config, credentials, IDs or log bodies."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
APIS = {'user-api': ('user-learning', 5005), 'learning-api': ('learning-api', 5006),
        'jwks-api': ('jwks-service', 5007)}


def docker(*args, input_text=None):
    result = subprocess.run(['docker', *args], cwd=ROOT, input=input_text,
                            capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Docker command failed; diagnostic output withheld to protect expanded values')
    return result.stdout


def model(project, debug=False, previous=False):
    args = ['compose', '-p', project, '--env-file', '.env', '-f', '-' if previous else 'docker-compose.yml']
    if debug:
        args += ['-f', 'docker-compose.debug.yml']
    previous_text = None
    if previous:
        result = subprocess.run(['git', 'show', 'HEAD:docker-compose.yml'], cwd=ROOT,
                                capture_output=True, text=True, check=True)
        previous_text = result.stdout
    return json.loads(docker(*args, 'config', '--format', 'json', input_text=previous_text))


def rows(raw):
    if raw.lstrip().startswith('['):
        return json.loads(raw)
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def get_json(url):
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', help='Override detected project; only use the project belonging to this checkout')
    parser.add_argument('--runtime', action='store_true', help='Read health, Loki/OpenSearch, mounts and container status')
    args = parser.parse_args()
    projects = json.loads(docker('compose', 'ls', '--format', 'json'))
    matching = [p for p in projects if any(Path(f.strip()).resolve() == ROOT / 'docker-compose.yml'
                                          for f in p.get('ConfigFiles', '').split(','))]
    if args.project:
        project = args.project
        selected = next((p for p in projects if p['Name'] == project), None)
        if selected is not None and selected not in matching:
            raise RuntimeError('Selected running project belongs to another checkout; refusing runtime inspection')
    elif len(matching) == 1:
        project = matching[0]['Name']
    else:
        raise RuntimeError('Cannot detect one project for this checkout; pass --project explicitly')
    print('UTC:', datetime.now(timezone.utc).isoformat(), 'project:', project)
    base, debug, previous = model(project), model(project, True), model(project, previous=True)
    assert base['name'] == debug['name'] == previous['name'] == project
    expected_volumes = dict(previous['volumes'])
    expected_volumes['prometheus_data'] = base['volumes']['prometheus_data']
    expected_volumes['tempo_data'] = base['volumes']['tempo_data']
    assert base['volumes'] == expected_volumes
    assert base.get('networks') == previous.get('networks')
    for name, service in base['services'].items():
        if name in {'tempo', 'tempo-storage-init', 'otel-collector'}:
            assert not service.get('ports'), 'Tracing infrastructure must remain unpublished'
            assert service.get('read_only') is True
            if name == 'tempo':
                assert service['image'] == 'grafana/tempo:2.9.0'
                assert service['user'] == '10001:10001'
            elif name == 'otel-collector':
                assert service['image'] == 'otel/opentelemetry-collector-contrib:0.143.0'
                assert service['user'] == '10001:10001'
            else:
                assert service['network_mode'] == 'none'
            continue
        if name == 'prometheus':
            assert service['image'] == 'prom/prometheus:v3.13.5'
            assert all(port['host_ip'] == '127.0.0.1' for port in service['ports'])
            assert len(service['volumes']) == 2
            continue
        old = previous['services'][name]
        assert service.get('ports') == old.get('ports'), 'A non-debug published port changed'
        if name == 'fluent-bit':
            # Phase 1 adds one read-only parser file; existing log/state mounts remain unchanged.
            parsers = [v for v in service.get('volumes', []) if v['target'] == '/fluent-bit/etc/application-parsers.conf']
            assert len(parsers) == 1 and parsers[0]['type'] == 'bind' and parsers[0]['read_only']
            assert Path(parsers[0]['source']).resolve() == ROOT / 'observability/fluent-bit/parsers.conf'
            previous_mounts = [v for v in old.get('volumes', []) if v['target'] != '/fluent-bit/etc/application-parsers.conf']
            assert [v for v in service['volumes'] if v not in parsers] == previous_mounts, 'An existing collector mount changed'
        elif name == 'grafana':
            targets = {'/etc/grafana/provisioning/datasources/' + name + '.yml'
                       for name in ('prometheus', 'tempo')}
            added = [v for v in service['volumes'] if v['target'] in targets]
            assert len(added) == 2 and all(v['read_only'] for v in added)
            for mount in added:
                assert Path(mount['source']).resolve() == ROOT / 'observability/grafana/provisioning/datasources' / Path(mount['target']).name
            assert [v for v in service['volumes'] if v not in added] == [v for v in old['volumes'] if v['target'] not in targets]
        else:
            assert service.get('volumes') == old.get('volumes'), 'A mount changed'
        expected = dict(old)
        if name in APIS or name == 'fluent-bit':
            expected['environment'] = dict(old.get('environment', {}))
            expected['environment']['DEPLOYMENT_ENVIRONMENT'] = service['environment']['DEPLOYMENT_ENVIRONMENT']
        if name in APIS:
            expected['environment'].update(METRICS_LISTENER_ENABLED='true', METRICS_LISTENER_PORT='9091', MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE='health,prometheus')
            expected['environment'].update(
                MANAGEMENT_TRACING_EXPORT_OTLP_ENABLED='true',
                MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_ENDPOINT='http://otel-collector:4318/v1/traces',
                MANAGEMENT_TRACING_SAMPLING_PROBABILITY=service['environment']['MANAGEMENT_TRACING_SAMPLING_PROBABILITY'])
        if name in {'fluent-bit', 'grafana'}:
            expected['volumes'] = service['volumes']
        assert service == expected, 'An unrelated Compose setting changed'
    environment = base['services']['fluent-bit']['environment']['DEPLOYMENT_ENVIRONMENT']
    assert environment in {'development', 'test', 'staging', 'production'}, 'Use a documented deployment environment'
    for name in APIS:
        service = base['services'][name]
        assert service['environment']['DEPLOYMENT_ENVIRONMENT'] == environment
        assert 'jdwp' not in (service['environment'].get('JAVA_TOOL_OPTIONS') or '')
        for key in ['MANAGEMENT_OTLP_METRICS_EXPORT_ENABLED',
                    'MANAGEMENT_LOGGING_EXPORT_OTLP_ENABLED']:
            assert str(service['environment'].get(key, 'false')).lower() == 'false', 'Existing export override requires review'
        assert service['environment']['MANAGEMENT_TRACING_EXPORT_OTLP_ENABLED'] == 'true'
        assert 0 <= float(service['environment']['MANAGEMENT_TRACING_SAMPLING_PROBABILITY']) <= 1
        assert service['environment'].get('MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE') == 'health,prometheus'
        assert all(port['target'] != 9091 for port in service['ports']), 'Private scrape port must not be published'
        options = debug['services'][name]['environment']['JAVA_TOOL_OPTIONS']
        assert '-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:' in options
        bindings = [b for b in debug['services'][name]['ports'] if b not in service['ports']]
        assert len(bindings) == 1 and bindings[0]['host_ip'] == '127.0.0.1'
        assert f"address=*:{bindings[0]['target']}" in options
        assert str(bindings[0]['target']) == str(bindings[0]['published'])
    print('PASS: base/debug Compose validation; exporter defaults, health and port-protected Prometheus exposure, loopback JDWP.')
    print('PASS: only reviewed Phase 0-3 additions allowed; existing ports, log/state mounts, volumes, networks, limits and dependencies preserved.')
    if not args.runtime:
        return

    statuses = rows(docker('compose', '-p', project, 'ps', '--all', '--format', 'json'))
    required = set(APIS) | {'fluent-bit', 'loki', 'grafana', 'opensearch', 'opensearch-dashboards'}
    live = {r['Service']: r for r in statuses}
    for name in sorted(required):
        item = live.get(name)
        print('CONTAINER:', name, 'state=', item.get('State') if item else 'missing',
              'health=', item.get('Health', 'not configured') if item else 'unknown')
    inspect_names = [live[name]['Name'] for name in required if name in live]
    inspected = json.loads(docker('inspect', *inspect_names))
    for container in inspected:
        name = container['Config']['Labels']['com.docker.compose.service']
        config = container['HostConfig'].get('LogConfig', {})
        print('DOCKER LOGGING:', name, config.get('Type'),
              {k: v for k, v in config.get('Config', {}).items() if k in {'max-size', 'max-file'}})
        # Compare config without claiming mounted/rebuilt applications contain the new source.
        if name in APIS:
            env = dict(v.split('=', 1) for v in container['Config'].get('Env', []) if '=' in v)
            print('LIVE SOURCE APPLICATION:', name, 'shared env applied=', 'DEPLOYMENT_ENVIRONMENT' in env,
                  'otel override names=', sorted(k for k in env if k.startswith(('OTEL_', 'MANAGEMENT_TRACING_', 'MANAGEMENT_OTLP_'))))

    def origin(name):
        ports = [p for p in live[name].get('Publishers', []) if p.get('PublishedPort') and p.get('TargetPort') in {8080, 3100, 3000, 9200, 5601}]
        if not ports:
            raise RuntimeError('No host HTTP endpoint')
        return 'http://127.0.0.1:' + str(ports[0]['PublishedPort'])

    for name in APIS:
        try:
            url = origin(name)
            health = get_json(url + '/actuator/health/readiness')
            request = urllib.request.Request(url + '/actuator/health', headers={'X-Correlation-ID': 'phase0-baseline-check'})
            with urllib.request.urlopen(request, timeout=8) as response:
                accepted = response.headers.get('X-Correlation-ID') == 'phase0-baseline-check'
            print('HEALTH:', name, health.get('status'), 'accepts valid incoming correlation=', accepted)
        except Exception as error:
            print('NOT VERIFIED: health/correlation', name, type(error).__name__)

    try:
        loki = origin('loki')
        labels = get_json(loki + '/loki/api/v1/label/service/values')['data']
        print('LOKI labels:', labels)
        now = time.time_ns()
        for name, (service, _) in APIS.items():
            query = urllib.parse.urlencode({'query': '{job="springboot",service="' + service + '"}',
                                           'start': str(now - 3600 * 10**9), 'end': str(now),
                                           'limit': '5000', 'direction': 'backward'})
            result = get_json(loki + '/loki/api/v1/query_range?' + query)
            counts = Counter()
            latest = 0
            for stream in result['data']['result']:
                for timestamp, line in stream['values']:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    latest = max(latest, int(timestamp))
                    counts['jsonRecords'] += 1
                    for field in ['correlationId', 'traceId', 'spanId', 'serviceVersion', 'environment']:
                        if record.get(field):
                            counts[field] += 1
            print('LOKI last-hour sample:', service, dict(counts),
                  'latestAgeSeconds=', round((now - latest) / 1e9) if latest else None)
    except Exception as error:
        print('NOT VERIFIED: Loki', type(error).__name__)
    try:
        search = origin('opensearch')
        print('OPENSEARCH health:', get_json(search + '/_cluster/health')['status'])
        indexes = get_json(search + '/_cat/indices/springboot*?format=json&h=index,docs.count,store.size')
        print('OPENSEARCH index summary:', indexes)
        # Count stored records without retrieving log messages, paths or identifiers.
        query = {'size': 0, 'aggs': {'by_index': {'terms': {'field': '_index'}, 'aggs': {
            'newest': {'max': {'field': '@timestamp'}},
            'recent': {'filter': {'range': {'@timestamp': {'gte': 'now-15m'}}}}}}}}
        request = urllib.request.Request(search + '/springboot-*-logs/_search',
                                         data=json.dumps(query).encode(),
                                         headers={'Content-Type': 'application/json'}, method='GET')
        with urllib.request.urlopen(request, timeout=8) as response:
            freshness = json.load(response)
        print('OPENSEARCH freshness:', [{'index': bucket['key'],
              'newest': bucket['newest'].get('value_as_string'), 'last15m': bucket['recent']['doc_count']}
              for bucket in freshness['aggregations']['by_index']['buckets']])
        mapping = get_json(search + '/springboot-*-logs/_mapping')
        print('OPENSEARCH field types:', {name: {field: value.get('mappings', {}).get('properties', {}).get(field, {}).get('type')
              for field in ['@timestamp', 'elapsed_ms', 'status']} for name, value in mapping.items()})
    except Exception as error:
        print('NOT VERIFIED: OpenSearch', type(error).__name__)
    try:
        print('GRAFANA health:', get_json(origin('grafana') + '/api/health').get('database'))
    except Exception as error:
        print('NOT VERIFIED: Grafana', type(error).__name__)
    print('NOT VERIFIED by this baseline script: live meter inventory, authenticated Grafana datasource API, retention deletion and complete distributed traces. See phase2-verification.md for separate metrics/datasource checks.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'FAIL: {type(error).__name__}: {error}')
