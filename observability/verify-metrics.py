"""Read-only metrics probes plus requests/login/logout against existing accounts.

Run after deployment. Optional --credentials is an ignored local JSON file.
No user creation/role changes; the refresh session created by this probe is logged out.
Docker commands always target springboot_project. Never print responses or tokens.
"""
import argparse
import base64
import datetime
import json
import math
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def request(port, path, method='GET', body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data,
        headers={'Content-Type': 'application/json', **(headers or {})}, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw.decode(errors='replace')
    return response.status, response.headers, value


def check(value, name):
    if not value:
        raise AssertionError(name)
    print('PASS:', name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', default='observability/local-test-credentials.json')
    parser.add_argument('--prometheus-port', type=int, default=9090)
    args = parser.parse_args()
    marker = 'phase2-' + uuid.uuid4().hex[:16]
    print('Probe correlation:', marker, flush=True)
    start = time.time()
    prom_port = args.prometheus_port
    credentials = Path(args.credentials)
    account = None
    if credentials.is_file():
        check(subprocess.run(['git', 'check-ignore', '--quiet', str(credentials)],
                            capture_output=True).returncode == 0, 'credentials file is ignored')
        account = json.loads(credentials.read_text(encoding='utf-8-sig'))
        check(isinstance(account.get('usernameOrEmail'), str) and isinstance(account.get('password'), str),
              'credentials schema (values withheld)')
    else:
        print('NOT VERIFIED: successful login/logout and authenticated Learning -> User; credentials file unavailable', flush=True)

    def query(expression):
        result = request(prom_port, '/api/v1/query?' + urllib.parse.urlencode({'query': expression}))[2]
        check(result.get('status') == 'success', 'PromQL accepted: ' + expression)
        return result['data']['result']

    token = refresh = None
    secrets = ['METRICS_QUERY_SECRET', 'METRICS_TOKEN_SECRET', marker]
    try:
        for port, service in [(8781, 'user-api'), (8782, 'learning-api'), (8783, 'jwks-api')]:
            check(request(port, '/actuator/health/readiness')[0] == 200, service + ' readiness')
            check(request(port, '/actuator/prometheus', headers={'X-Correlation-ID': marker})[0] == 403,
                  service + ' public scrape denied')
            for i in range(6):
                path = '/api/v1/jwks/user' if port == 8783 else (
                    '/internal/users/' + str(uuid.uuid4()) if port == 8781 else '/api/v1/learning/me')
                status, headers, _ = request(port, path + '?secret=METRICS_QUERY_SECRET',
                    headers={'X-Correlation-ID': marker + '-' + service, 'Cookie': 'secret=METRICS_TOKEN_SECRET'})
                check(status == (200 if port == 8783 else 401), service + ' real request')
                check(headers.get('X-Correlation-ID') == marker + '-' + service, service + ' correlation retained')
        rejected = request(8781, '/auth/login', 'POST',
            {'usernameOrEmail': 'phase2-nonexistent-' + uuid.uuid4().hex,
             'password': 'METRICS_TOKEN_SECRET'}, {'X-Correlation-ID': marker + '-rejected'})[0]
        check(rejected in [400, 401, 404], 'invalid login rejected without account mutation')
        if account:
            secrets += list(account.values())
            status, _, body = request(8781, '/auth/login', 'POST', account,
                                     {'X-Correlation-ID': marker + '-login'})
            check(status == 200, 'existing account login')
            token, refresh = body['data']['accessToken'], body['data']['refreshToken']
            secrets += [token, refresh]
            claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '==='))
            linked = marker + '-linked'
            status, headers, body = request(8782, '/api/v1/learning/internal-test/users/' + claims['sub'],
                headers={'Authorization': 'Bearer ' + token, 'X-Correlation-ID': linked})
            check(status == 200 and headers.get('X-Correlation-ID') == linked, 'Learning -> User internal JWT/correlation')
            status, _, _ = request(8781, '/actuator/prometheus', headers={'Authorization': 'Bearer ' + token})
            check(status == 403, 'authenticated account cannot scrape published application port')
    finally:
        if refresh:
            status, _, _ = request(8781, '/auth/logout', 'POST', {'refreshToken': refresh},
                                  {'Authorization': 'Bearer ' + token, 'X-Correlation-ID': marker + '-logout'})
            check(status == 200, 'verification refresh session logged out')

    # Wait for two scrape intervals so counters and rate-based percentile queries have samples.
    for _ in range(9):
        targets = request(prom_port, '/api/v1/targets')[2]['data']['activeTargets']
        targets = [t for t in targets if t['labels'].get('job') == 'springboot']
        if len(targets) == 3 and all(t['health'] == 'up' for t in targets):
            break
        time.sleep(5)
    check(len(targets) == 3 and all(t['health'] == 'up' for t in targets), 'all three scrape targets UP')
    time.sleep(16)
    for name in ['up', 'jvm_memory_used_bytes', 'jvm_gc_pause_seconds_count',
                 'jvm_threads_live_threads', 'process_uptime_seconds', 'process_cpu_usage',
                 'system_cpu_usage', 'app_build_info', 'http_server_requests_seconds_count',
                 'http_server_requests_seconds_bucket']:
        values = query(name)
        check(bool(values), name + ' stored in Prometheus')
        if name not in ['up']:
            check({v['metric'].get('service') for v in values} == {'user-learning', 'learning-api', 'jwks-service'},
                  name + ' available across all three services')
    for name in ['hikaricp_connections_active', 'hikaricp_connections_idle', 'hikaricp_connections_pending',
                 'hikaricp_connections_max', 'hikaricp_connections_acquire_seconds_count']:
        values = query(name)
        check({v['metric'].get('service') for v in values} == {'user-learning', 'learning-api'}, name + ' database services only')
    check(any(float(v['value'][1]) > 0 for v in query('app_security_events_total{operation="login",result="failure"}')),
          'authentication failure counter incremented')
    check(any(float(v['value'][1]) > 0 for v in query('app_security_events_total{operation="internal_authentication",result="failure"}')),
          'internal authentication rejection counter incremented')
    if account:
        values = query('http_client_requests_seconds_count{service="learning-api",uri="/internal/users/{id}",status="200"}')
        check(bool(values) and any(float(v['value'][1]) > 0 for v in values), 'real internal client timer')
    for percentile in ['0.5', '0.95', '0.99']:
        expression = 'histogram_quantile(' + percentile + ', sum by (le,service) (rate(http_server_requests_seconds_bucket[5m])))'
        values = query(expression)
        check({v['metric'].get('service') for v in values if math.isfinite(float(v['value'][1]))}
              == {'user-learning', 'learning-api', 'jwks-service'}, 'finite percentile ' + percentile + ' for all services')

    for service, identity, index in [('user-api','user-learning','user'), ('learning-api','learning-api','learning'), ('jwks-api','jwks-service','jwks')]:
        scrape = subprocess.run(['docker','compose','-p','springboot_project','exec','-T','prometheus',
            'wget','-q','-O','-',f'http://{service}:9091/actuator/prometheus'], capture_output=True, text=True, check=True).stdout
        check(not any(str(secret) in scrape for secret in secrets if secret), service + ' no tested sensitive metric values')
        check(not re.search(r'(correlationId|traceId|spanId|username|email|sessionId)=', scrape), service + ' no sensitive label keys')
        forbidden = subprocess.run(['docker','compose','-p','springboot_project','exec','-T','prometheus',
            'wget','-q','-O','-',f'http://{service}:9091/actuator/env'], capture_output=True, text=True)
        check(forbidden.returncode != 0 and '403' in forbidden.stderr, service + ' private listener denies other endpoints')
        selector = '{service="' + identity + '"} | json | correlationId="' + marker + '-' + service + '"'
        params = urllib.parse.urlencode({'query':selector, 'start':str(int(start*1e9)), 'limit':100})
        check(bool(request(3177, '/loki/api/v1/query_range?' + params)[2]['data']['result']), service + ' fresh Loki ingestion')
        body = {'query':{'term':{'correlationId.keyword':marker+'-'+service}}}
        check(request(9277, '/springboot-'+index+'*-logs/_search', 'POST', body)[2]['hits']['total']['value'] >= 6,
              service + ' fresh OpenSearch ingestion')
        raw = subprocess.run(['docker','compose','-p','springboot_project','logs','--no-color','--no-log-prefix',service],
                             capture_output=True,text=True,check=True).stdout
        sensitive = [s for s in secrets if s and s != marker]
        check(not any(str(secret) in raw for secret in sensitive), service + ' tested secrets absent from logs')
        records=[]
        for line in raw.splitlines():
            try: records.append(json.loads(line))
            except ValueError: pass
        check(not any(r.get('level') in ['WARN','ERROR'] and re.search(r'otlp|opentelemetry.*export',r.get('logger_name',''),re.I)
                      for r in records), service + ' no unexpected OTLP export errors')
    print('Metrics runtime verification complete.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('FAIL: ' + type(error).__name__ + ': ' + str(error))
