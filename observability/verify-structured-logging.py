"""Local Phase 1 runtime probes; credentials are read only from process environment.

No account/role changes. Login creates one refresh session; finally logs it out.
Requires the existing springboot_project deployment and local backend ports.
Never prints response bodies, credentials or tokens. Does not upload test events.
"""
import base64
import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def http(port, path, method='GET', body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data,
        headers={'Content-Type': 'application/json', **(headers or {})}, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    try:
        value = json.loads(raw)
    except ValueError:
        value = None
    return response.status, dict(response.headers), value


def check(condition, name):
    if not condition:
        raise AssertionError(name)
    print('PASS:', name, flush=True)


def main():
    username = os.environ.pop('OBS_TEST_USERNAME', None)
    password = os.environ.pop('OBS_TEST_PASSWORD', None)
    marker = 'phase1-' + uuid.uuid4().hex[:16]
    print('Verification correlation:', marker, flush=True)
    begin = time.time()
    expected = {}
    token = refresh = None
    secrets = ['SENSITIVE_QUERY_SENTINEL', 'SENSITIVE_HEADER_SENTINEL',
               'SENSITIVE_REFRESH_SENTINEL', 'SENSITIVE_PATH_SENTINEL']
    if username and password:
        secrets += [username, password]

    def probe(name, port, path, status, method='GET', body=None, auth=None, cid=None):
        correlation = cid or marker + '-' + name
        headers = {'X-Correlation-ID': correlation,
                   'Cookie': 'session=SENSITIVE_HEADER_SENTINEL'}
        if auth:
            headers['Authorization'] = 'Bearer ' + auth
        actual, response_headers, value = http(port, path, method, body, headers)
        check(actual == status, f'{name}: HTTP {status} (observed {actual})')
        effective = next((v for k, v in response_headers.items() if k.lower() == 'x-correlation-id'), '')
        valid = re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', correlation)
        check(effective == correlation if valid else bool(re.fullmatch(r'[0-9a-f-]{36}', effective)),
              name + ': correlation response')
        expected[(port, effective)] = status
        return value

    try:
        for port in [8781, 8782, 8783]:
            check(http(port, '/actuator/health/readiness')[0] == 200, f'{port}: readiness')
        for name, path, cid in [('valid', '/api/v1/jwks/user', marker),
                                ('malformed', '/api/v1/jwks/user', 'bad id'),
                                ('oversized', '/api/v1/jwks/user', 'x' * 65)]:
            probe(name, 8783, path, 200, cid=cid)
        probe('jwks404', 8783, '/api/v1/jwks/SENSITIVE_PATH_SENTINEL?secret=SENSITIVE_QUERY_SENTINEL', 404)
        probe('user401', 8781, '/internal/users/' + str(uuid.uuid4()), 401)
        probe('learning401', 8782, '/api/v1/learning/me', 401)
        probe('badjwt', 8782, '/api/v1/learning/me', 401, auth='SENSITIVE_HEADER_SENTINEL')
        if not username or not password:
            print('NOT VERIFIED: authenticated login/logout/internal JWT checks: no process credentials')
        else:
            login = probe('login', 8781, '/auth/login', 200, 'POST',
                          {'usernameOrEmail': username, 'password': password})
            token, refresh = login['data']['accessToken'], login['data']['refreshToken']
            secrets += [token, refresh]
            claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '==='))
            subject = claims['sub']
            probe('identity', 8782, '/api/v1/learning/me', 200, auth=token)
            linked = probe('linked', 8782, '/api/v1/learning/internal-test/users/' + subject,
                           200, auth=token)
            check(subject in json.dumps(linked), 'Learning -> User authenticated subject')
            expected[(8781, marker + '-linked')] = 200
            probe('userjwtinternal', 8781, '/internal/users/' + subject, 401, auth=token)
            print('NOT VERIFIED: real non-admin account rejection; account roles are preserved')
            probe('missinguser', 8782, '/api/v1/learning/internal-test/users/' + str(uuid.uuid4()),
                  500, auth=token)
            expected[(8781, marker + '-missinguser')] = 404
            probe('refresh404', 8781, '/auth/refresh', 404, 'POST',
                  {'refreshToken': 'SENSITIVE_REFRESH_SENTINEL'})
    finally:
        if refresh:
            probe('logout', 8781, '/auth/logout', 200, 'POST', {'refreshToken': refresh}, token)

    services = {8781: ('user-api', 'user-learning'), 8782: ('learning-api', 'learning-api'),
                8783: ('jwks-api', 'jwks-service')}
    records = {}
    for port, (service, identity) in services.items():
        result = subprocess.run(['docker', 'compose', '-p', 'springboot_project',
            'logs', '--no-color', '--no-log-prefix', '--since', str(int(begin)), service],
            capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        parsed = []
        for line in lines:
            try:
                parsed.append(json.loads(line))
            except ValueError:
                pass
        records[port] = [r for r in parsed if r.get('event') == 'http.request.completed']
        check(bool(parsed) and all(r.get('service') == identity and r.get('serviceVersion') and
                  r.get('environment') == 'development' for r in parsed), service + ': metadata')
        check(not any(secret in result.stdout for secret in secrets), service + ': no tested sensitive values')
        check(not any(r.get('level') in ['WARN', 'ERROR'] and
                      re.search(r'otlp|opentelemetry.*export', r.get('logger_name', ''), re.I)
                      for r in parsed), service + ': no OTLP exporter errors')
        check(not any(r.get('level') == 'INFO' and str(r.get('http.route', '')).startswith('/actuator/health')
                      for r in parsed), service + ': quiet successful health checks')
    for (port, cid), status in expected.items():
        matching = [r for r in records[port] if r.get('correlationId') == cid]
        check(len(matching) == 1, f'{services[port][0]}: exactly one completion for {cid}')
        record = matching[0]
        check(type(record.get('http.response.status_code')) is int and
              record['http.response.status_code'] == status and
              type(record.get('durationMs')) in [int, float] and record['durationMs'] >= 0,
              f'{services[port][0]}: typed final HTTP fields')
        check(record.get('http.route') and '?' not in record['http.route'] and
              not any(s in record['http.route'] for s in secrets), 'safe route')
    deadline = time.time() + 45
    for port, (_, identity) in services.items():
        query = '{service="' + identity + '"} | json | event="http.request.completed" | correlationId=~"' + marker + '.*"'
        found = []
        while time.time() < deadline:
            params = urllib.parse.urlencode({'query': query, 'start': str(int(begin * 1e9)),
                'end': str(time.time_ns()), 'limit': 200})
            result = http(3177, '/loki/api/v1/query_range?' + params)[2]
            found = [(stamp, json.loads(line)) for stream in result['data']['result']
                     for stamp, line in stream['values']]
            if found:
                break
            time.sleep(2)
        check(bool(found), identity + ': fresh Loki ingestion')
        check(all(abs(int(stamp) / 1e9 - dt.datetime.fromisoformat(r['@timestamp'].replace('Z', '+00:00')).timestamp()) < .002
                  for stamp, r in found), identity + ': Loki uses application timestamp')
        index = {8781: 'user', 8782: 'learning', 8783: 'jwks'}[port]
        query = {'size': 100, 'query': {'bool': {'filter': [
            {'prefix': {'correlationId.keyword': marker}}, {'term': {'event.keyword': 'http.request.completed'}}]}}}
        result = http(9277, f'/springboot-{index}-logs/_search', 'POST', query)[2]
        check(result['hits']['total']['value'] > 0, identity + ': fresh OpenSearch ingestion')
        stored = [item['_source'] for item in result['hits']['hits']]
        check(all(type(r.get('durationMs')) in [int, float] and
                  type(r.get('http.response.status_code')) is int for r in stored), identity + ': stored numeric types')
    print('Phase 1 live probes complete; no account or role modifications.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('FAIL: ' + type(error).__name__ + ': ' + str(error))
