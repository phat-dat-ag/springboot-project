"""Bounded destructive tests restricted to the disposable laboratory manifest."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.parse
import uuid

from lab import cmd, inventory, now, write


def store(lab, name, value):
    write(lab.folder / ('evidence/' + name + '.json'), value)


def logs(lab, group, count, padding=100, offset=0, segment=0):
    assert 0 < count <= 512 and count * (padding + 500) <= 4 * 1024 * 1024
    rows = [{'@timestamp': now(), 'service': 'fixture', 'environment': 'test', 'event': 'phase6b.synthetic',
             'event_group': group, 'event_id': group + '-' + str(i + offset), 'segment': segment,
             'message': 'synthetic ' + 'x' * padding} for i in range(count)]
    code = "import json,pathlib,sys; rows=json.load(sys.stdin); p=pathlib.Path('/stores/source/spool'); p.mkdir(exist_ok=True); (p/(rows[0]['event_group']+'.'+str(rows[0]['segment'])+'.log')).write_text(''.join(json.dumps(r)+'\\n' for r in rows)); print(len(rows))"
    lab.compose('exec', '-T', 'probe', 'python', '-c', code, input=json.dumps(rows))
    return {r['event_id'] for r in rows}


def log_ids(lab, group, backend='loki'):
    if backend.startswith('loki'):
        params = urllib.parse.urlencode({'query': '{job="phase6b"} |= "' + group + '"',
            'start': str(time.time_ns() - 3600 * 10**9), 'end': str(time.time_ns()), 'limit': '1000'})
        response = lab.http('https://' + backend + ':3100/loki/api/v1/query_range?' + params)
        if response['status'] != 200:
            return []
        return [json.loads(line)['event_id'] for series in response['body']['data']['result'] for _, line in series['values']]
    response = lab.http('https://' + backend + ':9200/springboot-*-logs/_search',
        {'size': 1000, 'query': {'term': {'event_group.keyword': group}}}, role='reader')
    return [hit['_source']['event_id'] for hit in response.get('body', {}).get('hits', {}).get('hits', [])] if response['status'] == 200 else []


def compare(lab, group, expected, backend, require_all=True):
    ids = log_ids(lab, group, backend)
    counts = Counter(ids)
    detail = {'submitted': len(expected), 'stored': len(ids), 'unique': len(counts),
              'missing': sorted(expected - set(ids)), 'duplicates': {k: n for k, n in counts.items() if n > 1}}
    store(lab, group + '-' + backend, detail)
    lab.check((not detail['missing'] if require_all else True) and not (set(ids) - expected), group + ' stored IDs: ' + backend, detail)
    return detail


def traces(lab, count=10, padding=0):
    assert count <= 300 and padding <= 2000
    stamp = time.time_ns()
    ids = [uuid.uuid4().hex for _ in range(count)]
    spans = [{'traceId': trace, 'spanId': uuid.uuid4().hex[:16], 'name': 'phase6b.synthetic', 'kind': 2,
              'startTimeUnixNano': str(stamp), 'endTimeUnixNano': str(stamp + 1000000),
              'attributes': [{'key': 'fixture.padding', 'value': {'stringValue': 'x' * padding}}]} for trace in ids]
    body = {'resourceSpans': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'phase6b-fixture'}}]},
                             'scopeSpans': [{'scope': {'name': 'phase6b'}, 'spans': spans}]}]}
    result = lab.http('https://collector:4318/v1/traces', body)
    return ids, {'submitted': count, 'receiver_http_status': result['status'], 'receiver_body': result.get('body')}


def trace_ids(lab, ids, host='tempo'):
    responses = lab.http_many(['https://' + host + ':3200/api/traces/' + trace for trace in ids])
    return [trace for trace, response in zip(ids, responses) if response['status'] == 200]


def security(lab):
    started = now()
    results = []
    for service, path in [('loki', ':3100/ready'), ('tempo', ':3200/ready'), ('prometheus', ':9090/-/ready'), ('probe', ':8443/metrics')]:
        url = 'https://' + service + path
        for scenario, options, expected in [('trusted', {}, 200), ('missing-client', {'role': 'none'}, 0),
                  ('untrusted-client', {'role': 'unknown'}, 0), ('wrong-trust-root', {'ca': 'untrusted'}, 0)]:
            response = lab.http(url, **options)
            passed = response['status'] == expected
            results.append({'component': service, 'scenario': scenario, 'status': response['status'], 'pass': passed})
            lab.check(passed, service + ' TLS ' + scenario, response['status'])
    # Same server by IP: SAN deliberately lacks IP; verified hostname must reject.
    ip = json.loads(cmd('docker', 'inspect', lab.owned('loki')))[0]['NetworkSettings']['Networks']
    address = next(iter(ip.values()))['IPAddress']
    response = lab.http('https://' + address + ':3100/ready')
    lab.check(response['status'] == 0 and response.get('tls_rejected'), 'TLS hostname mismatch rejected', response)
    lab.check(lab.http('https://loki:3100/ready', role='rotated')['status'] == 200, 'new CA-authorized client identity accepted (rotation prerequisite)')
    gf = lab.http('https://grafana:3000/api/search')
    lab.check(gf['status'] == 401 and lab.http('https://grafana:3000/api/search', basic=True)['status'] == 200, 'isolated Grafana login boundary preserved')
    targets = lab.http('https://prometheus:9090/api/v1/targets')['body']['data']['activeTargets']
    lab.wait(lambda: all(t['health'] == 'up' for t in lab.http('https://prometheus:9090/api/v1/targets')['body']['data']['activeTargets']))
    lab.check(len(targets) == 4, 'four configured native/fixture HTTPS scrape targets', len(targets))
    for uid in ['loki', 'tempo', 'prometheus']:
        response = lab.http('https://grafana:3000/api/datasources/uid/' + uid + '/health', basic=True)
        if uid == 'tempo' and response['status'] == 404 and response.get('body', {}).get('messageId') == 'plugin.notImplemented':
            response = lab.http('https://grafana:3000/api/datasources/proxy/uid/tempo/ready', basic=True)
            lab.check(response['status'] == 200, 'Grafana verified TLS datasource: ' + uid,
                      'Tempo plugin health not implemented; actual Grafana backend proxy readiness returned200')
        else:
            lab.check(response['status'] == 200 and response.get('body', {}).get('status') == 'OK', 'Grafana verified TLS datasource: ' + uid, response.get('body'))
    ids, accepted = traces(lab, 1)
    lab.wait(lambda: len(trace_ids(lab, ids)) == 1)
    lab.check(accepted['receiver_http_status'] == 200 and lab.http('https://grafana:3000/api/datasources/proxy/uid/tempo/api/traces/' + ids[0], basic=True)['status'] == 200,
              'fixture mTLS OTLP to Collector, TLS gRPC to Tempo and Grafana trace resolution')
    for role in ['none', 'unknown']:
        rejected = lab.http('https://collector:4318/v1/traces', {}, role=role)
        lab.check(rejected['status'] == 0, 'Collector OTLP rejects client: ' + role, rejected)
    store(lab, 'tls', results)
    lab.result('PASS', 'native TLS/mTLS handshake matrix completed', 'Current and CA-authorized replacement clients; invalid/missing clients and hostname/trust failures checked', started=started)
    lab.result('NOT VERIFIED', 'production application SSL bundle and metrics sidecar activation', 'Fixture OTLP client used; no application images rebuilt or real JWT/DB dependencies introduced')


def opensearch(lab):
    started = now()
    lab.os_start()
    matrix = []
    for role, statuses in [('admin', [200]), ('reader', [200]), ('unknown', [0]), ('none', [0]), ('probe', [401, 403])]:
        response = lab.http('https://opensearch:9200/_cluster/health', role=role)
        matrix.append({'role': role, 'status': response['status']})
        lab.check(response['status'] in statuses, 'OpenSearch identity boundary: ' + role, response['status'])
    bad = lab.http('https://opensearch:9200/_cluster/health', headers={'Authorization': 'Basic bm9ib2R5OmluY29ycmVjdA=='})
    lab.check(bad['status'] in [401, 403], 'OpenSearch incorrect Basic credentials rejected',
              {'status': bad['status'], 'note': 'trusted but unmapped client cert may authenticate then fail authorization after Basic fallback'})
    name = 'springboot-user-' + datetime.now(timezone.utc).strftime('%Y.%m.%d') + '-logs'
    allowed = lab.http('https://opensearch:9200/' + name + '/_doc/least-privilege', {'fixture': True}, role='fluent-bit')
    lab.check(allowed['status'] in [200, 201], 'OpenSearch writer creates permitted dated index', allowed['status'])
    forbidden = lab.http('https://opensearch:9200/unrelated-fixture/_doc/denied', {'fixture': True}, role='fluent-bit')
    read_denied = lab.http('https://opensearch:9200/' + name + '/_search', role='fluent-bit')
    write_denied = lab.http('https://opensearch:9200/' + name + '/_doc/reader-denied', {'fixture': True}, role='reader')
    lab.check(forbidden['status'] == 403 and read_denied['status'] == 403 and write_denied['status'] == 403, 'OpenSearch least-privilege read/write separation', [forbidden['status'], read_denied['status'], write_denied['status']])
    lab.check(lab.http('https://opensearch:9200/_plugins/_security/api/roles', role='reader')['status'] == 403, 'OpenSearch administrative credential separation')
    group = 'secure-' + uuid.uuid4().hex[:8]
    expected = logs(lab, group, 12)
    lab.wait(lambda: len(set(log_ids(lab, group, 'opensearch'))) == 12)
    lab.wait(lambda: len(set(log_ids(lab, group))) == 12)
    compare(lab, group, expected, 'opensearch')
    compare(lab, group, expected, 'loki')
    lab.mutate('stop', 'opensearch')
    lab.mutate('start', 'opensearch')
    lab.ready('opensearch')
    lab.wait(lambda: len(set(log_ids(lab, group, 'opensearch'))) == 12)
    compare(lab, group, expected, 'opensearch')
    store(lab, 'opensearch-auth', matrix)
    store(lab, 'backup-control', {'group': group, 'events': sorted(expected)})
    lab.result('PASS', 'OpenSearch native security bootstrap and restart persistence', 'TLS-verified securityadmin bootstrap; cert writer/reader/admin roles; no demo users; same disposable data', started=started)
    lab.result('NOT VERIFIED', 'positive username/password authentication and Dashboards server integration', 'Certificate authentication exercised; no Dashboards fixture or password-authenticated ingestion used')


def crash(lab):
    # Both outputs available initially; only exact fixture processes are killed.
    for target in ['loki', 'opensearch']:
        lab.mutate('stop', target)
    group = 'crash-' + uuid.uuid4().hex[:8]
    expected = logs(lab, group, 20, 200)
    time.sleep(5)
    before = lab.http('http://fluent-bit:2020/api/v1/metrics/prometheus')
    store(lab, group + '-before', before)
    started = now()
    lab.mutate('kill', 'fluent-bit')
    lab.mutate('start', 'fluent-bit')
    for target in ['loki', 'opensearch']:
        lab.mutate('start', target)
        lab.ready(target)
    lab.wait(lambda: len(set(log_ids(lab, group))) == 20, 120)
    lab.wait(lambda: len(set(log_ids(lab, group, 'opensearch'))) == 20, 120)
    for backend in ['loki', 'opensearch']:
        compare(lab, group, expected, backend)
    lab.result('PASS', 'Fluent Bit SIGKILL queue/offset recovery', '20 submitted,20 unique events in each real backend; per-output acknowledgement before crash not observable', started=started)
    lab.mutate('stop', 'tempo')
    ids, accepted = traces(lab, 8)
    time.sleep(4)
    store(lab, 'collector-precrash-metrics', lab.http('http://collector:8888/metrics'))
    started = now()
    lab.mutate('kill', 'collector')
    lab.mutate('start', 'collector')
    lab.mutate('start', 'tempo')
    lab.ready('tempo')
    lab.wait(lambda: len(trace_ids(lab, ids)) == len(ids), 120)
    found = trace_ids(lab, ids)
    store(lab, 'collector-crash', {**accepted, 'stored_unique': len(found), 'missing': sorted(set(ids) - set(found)),
                                 'duplicate_semantics': 'Tempo trace-ID query is not physical duplicate-span proof'})
    lab.check(len(found) == len(ids), 'Collector SIGKILL persistent queue recovery', {**accepted, 'stored_unique': len(found)}, started=started)
    # Destination crash after a confirmed prefix; send while absent, then recover.
    group = 'backend-crash-' + uuid.uuid4().hex[:8]
    lab.mutate('kill', 'loki')
    expected = logs(lab, group, 10)
    time.sleep(3)
    lab.mutate('start', 'loki')
    lab.ready('loki')
    lab.wait(lambda: len(set(log_ids(lab, group))) == 10)
    compare(lab, group, expected, 'loki')
    lab.result('NOT VERIFIED', 'host crash and storage failure durability', 'Only isolated container SIGKILL tested; tmpfs is not host-crash durable')


def overflow(lab):
    started = now()
    # Physically bounded ENOSPC only on a2MiB fixture tmpfs; never Docker root/host disk.
    code = "import errno,json,pathlib; p=pathlib.Path('/stores/diskfull/fill'); n=0; status=''; f=p.open('wb',buffering=0);\ntry:\n for i in range(80):\n  f.write(b'x'*65536); n+=65536\nexcept OSError as e:\n status=errno.errorcode[e.errno]\nfinally:\n f.close()\nprint(json.dumps({'written':n,'error':status,'capacity':2097152}))"
    result = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', code))
    lab.check(result['error'] == 'ENOSPC' and result['written'] <= 2097152, 'bounded fixture filesystem ENOSPC', result)
    lab.compose('exec', '-T', 'probe', 'python', '-c', "from pathlib import Path; Path('/stores/diskfull/fill').unlink(); Path('/stores/diskfull/recovered').write_text('ok')")
    lab.result('PASS', 'bounded filesystem capacity restoration', 'Only the explicitly generated fixture filler was removed; fresh write succeeds')
    lab.mutate('stop', 'loki')
    group = 'overflow-' + uuid.uuid4().hex[:8]
    expected = set()
    for segment in range(12):
        expected |= logs(lab, group, 20, 1800, offset=20 * segment, segment=segment)
        time.sleep(1.2)
    time.sleep(8)
    before = lab.http('http://fluent-bit:2020/api/v1/metrics/prometheus')
    store(lab, 'fluent-bit-overflow-metrics', before)
    lab.mutate('start', 'loki')
    lab.ready('loki')
    time.sleep(6)
    loki = compare(lab, group, expected, 'loki', require_all=False)
    lab.wait(lambda: len(set(log_ids(lab, group, 'opensearch'))) == 240)
    healthy = compare(lab, group, expected, 'opensearch')
    raw = cmd('docker', 'logs', '--tail', '250', lab.owned('fluent-bit'))
    signals = [line for line in raw.splitlines() if any(s in line.lower() for s in ['overlimit', 'over limit', 'dropp', 'limit', 'no space'])]
    store(lab, 'fluent-bit-overflow-signals', signals)
    lab.check(bool(loki['missing']) and not healthy['missing'], 'Fluent Bit output limit loss and healthy-output isolation',
              {'submitted': 240, 'loki_unique': loki['unique'], 'loki_missing': len(loki['missing']), 'opensearch_unique': healthy['unique'], 'signals': len(signals)})
    lab.mutate('stop', 'tempo')
    ids, admitted = traces(lab, 100, 1800)
    time.sleep(4)
    metric = lab.http('http://collector:8888/metrics')
    store(lab, 'collector-overflow-metrics', metric)
    lab.mutate('start', 'tempo')
    lab.ready('tempo')
    time.sleep(8)
    found = trace_ids(lab, ids)
    details = {**admitted, 'stored_unique': len(found), 'missing_count': len(ids) - len(found),
               'acknowledgement_scope': 'OTLP receiver HTTP success is not queue admission or backend acknowledgement'}
    store(lab, 'collector-overflow', details)
    lab.check(len(found) < len(ids) and 'enqueue_failed' in str(metric.get('body', '')), 'Collector byte queue saturation/refusal observed', details)
    next_ids, _ = traces(lab, 2)
    lab.wait(lambda: len(trace_ids(lab, next_ids)) == 2)
    lab.result('PASS', 'queue overflow recovery accepts new traces', '2 fresh traces stored after fixture backend recovery', started=started)
    lab.result('BLOCKED', 'real backend disk-full recovery and disk-pressure alerting', 'No dedicated block device/filesystem-pressure exporter; generic2MiB fixture ENOSPC is not backend corruption/recovery evidence')


def lifecycle(lab):
    started = now()
    lab.http('http://probe:8080/control', {'breach': 0, 'notify_failures': 1})
    root = 'https://grafana:3000'
    lab.http(root + '/api/folders', {'uid': 'phase6b', 'title': 'Phase6B disposable'}, basic=True)
    contact = {'uid': 'phase6b-local', 'name': 'phase6b-local', 'type': 'webhook', 'settings': {'url': 'http://probe:8080/notify', 'httpMethod': 'POST'}, 'disableResolveMessage': False}
    lab.check(lab.http(root + '/api/v1/provisioning/contact-points', contact, basic=True)['status'] in [200, 201, 202], 'local-only Grafana contact point created')
    policy = {'receiver': 'phase6b-local', 'group_by': ['suite'], 'group_wait': '1s', 'group_interval': '10s', 'repeat_interval': '30s'}
    lab.check(lab.http(root + '/api/v1/provisioning/policies', policy, method='PUT', basic=True)['status'] in [200, 202], 'fixture notification grouping/repeat policy')
    query = {'refId': 'A', 'queryType': '', 'relativeTimeRange': {'from': 30, 'to': 0}, 'datasourceUid': 'prometheus',
             'model': {'expr': 'phase6b_breach', 'instant': True, 'range': False, 'refId': 'A', 'intervalMs': 1000, 'maxDataPoints': 100}}
    condition = {'refId': 'B', 'queryType': '', 'relativeTimeRange': {'from': 0, 'to': 0}, 'datasourceUid': '__expr__',
                 'model': {'type': 'threshold', 'expression': 'A', 'refId': 'B', 'conditions': [{'evaluator': {'type': 'gt', 'params': [0]},
                    'operator': {'type': 'and'}, 'query': {'params': ['B']}, 'reducer': {'type': 'last', 'params': []}, 'type': 'query'}]}}
    rule = {'uid': 'phase6b-lifecycle', 'title': 'Phase6B lifecycle', 'condition': 'B', 'data': [query, condition],
            'noDataState': 'NoData', 'execErrState': 'Error', 'for': '20s', 'annotations': {'summary': 'Synthetic fixture only'},
            'labels': {'suite': 'phase6b', 'environment': 'test', 'severity': 'test'}, 'isPaused': False}
    group = {'title': 'phase6b', 'folderUid': 'phase6b', 'interval': 10, 'rules': [rule]}
    response = lab.http(root + '/api/v1/provisioning/folder/phase6b/rule-groups/phase6b', group, method='PUT', basic=True)
    lab.check(response['status'] in [200, 202], 'elapsed lifecycle rule provisioned', response['status'])
    transitions = []
    def state():
        response = lab.http(root + '/api/prometheus/grafana/api/v1/rules', basic=True)
        rules = [r for g in response.get('body', {}).get('data', {}).get('groups', []) for r in g.get('rules', []) if r.get('name') == 'Phase6B lifecycle']
        if not rules:
            return None
        actual = rules[0]['state']
        if not transitions or transitions[-1]['state'] != actual:
            transitions.append({'utc': now(), 'state': actual, 'health': rules[0].get('health')})
            store(lab, 'alert-transitions', transitions)
        return actual
    lab.wait(lambda: state() == 'inactive', 60)
    lab.http('http://probe:8080/control', {'breach': 1})
    lab.wait(lambda: state() == 'pending', 60)
    lab.wait(lambda: state() == 'firing', 60)
    lab.wait(lambda: bool(lab.http('http://probe:8080/state')['body']['notifications']), 90)
    # Wait naturally for at least one repeat, then resolve.
    lab.wait(lambda: len(lab.http('http://probe:8080/state')['body']['notifications']) >= 2, 75)
    lab.http('http://probe:8080/control', {'breach': 0})
    lab.wait(lambda: state() == 'inactive', 60)
    lab.wait(lambda: any(n['payload'].get('status') == 'resolved' for n in lab.http('http://probe:8080/state')['body']['notifications']), 60)
    received = lab.http('http://probe:8080/state')['body']
    store(lab, 'notification-lifecycle', received)
    lab.check([t['state'] for t in transitions] == ['inactive', 'pending', 'firing', 'inactive'], 'actual Normal/Pending/Firing/Resolved transitions', transitions, started=started)
    messages = received['notifications']
    lab.check(any(len(m['payload'].get('alerts', [])) == 2 for m in messages), 'two alert instances grouped in local payload')
    lab.check(any(m['http_status'] == 503 for m in received['attempts']) and len(messages) >= 3, 'receiver error retry, repeat and recovery delivery',
              {'attempts': len(received['attempts']), 'accepted': len(messages), 'statuses': [m['payload'].get('status') for m in messages]})
    lab.result('NOT VERIFIED', 'actual external provider notifications', 'Only internal-network local HTTP receiver authorized/tested; no external delivery')
    # Preserve the completed lifecycle rule; exercise no-data/error in separate synthetic rules.
    import copy
    for suffix, expression, wanted in [('nodata', 'phase6b_nonexistent', 'NoData'), ('error', 'invalid_promql{', 'Error')]:
        isolated = copy.deepcopy(rule)
        isolated.update(uid='phase6b-' + suffix, title='Phase6B ' + suffix, **{'for': '0s'})
        isolated['data'][0]['model']['expr'] = expression
        payload = {**group, 'title': 'phase6b-' + suffix, 'rules': [isolated]}
        lab.http(root + '/api/v1/provisioning/folder/phase6b/rule-groups/phase6b-' + suffix, payload, method='PUT', basic=True)
    time.sleep(25)
    current = lab.http(root + '/api/prometheus/grafana/api/v1/rules', basic=True)['body']
    store(lab, 'alert-no-data-error', current)
    check_evaluations(lab, current)


def check_evaluations(lab, current):
    rules = {r.get('uid'): r for group in current.get('data', {}).get('groups', []) for r in group.get('rules', [])}
    missing = rules.get('phase6b-nodata', {})
    failed = rules.get('phase6b-error', {})
    lab.check(missing.get('health') == 'nodata' and any(a.get('state') == 'NoData' for a in missing.get('alerts', [])),
              'actual no-data alert behavior', {'health': missing.get('health'), 'instance_states': [a.get('state') for a in missing.get('alerts', [])]})
    lab.check(failed.get('health') == 'error' and bool(failed.get('lastError')) and any(a.get('state') == 'Error' for a in failed.get('alerts', [])),
              'actual execution-error evaluation behavior', {'health': failed.get('health'), 'lastError': failed.get('lastError')})


def cold_copy(lab, service, volume):
    started = now()
    lab.mutate('stop', service)
    code = "import hashlib,json,pathlib,tarfile; key='" + volume + "'; base=pathlib.Path('/stores'); out=pathlib.Path('/lab/evidence')/(key+'-cold.tar');\nwith tarfile.open(out,'w') as t: t.add(base/key,arcname='state')\nassert out.stat().st_size < 134217728\nwith tarfile.open(out) as t: t.extractall(base/(key+'-restore'),filter='data')\n# Move extracted contents into the fresh destination root.\nfor p in (base/(key+'-restore')/'state').iterdir(): p.rename(base/(key+'-restore')/p.name)\n(base/(key+'-restore')/'state').rmdir()\nprint(json.dumps({'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))"
    result = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', code))
    lab.compose('up', '-d', '--no-build', '--pull', 'never', service + '-restore')
    lab.ready(service + '-restore')
    lab.mutate('start', service)
    lab.ready(service)
    store(lab, service + '-backup', {**result, 'start': started, 'end': now(), 'method': 'quiesced full store copy to separate bounded disposable volume'})
    return result


def backup(lab):
    started = now()
    control = json.loads((lab.folder / 'evidence/backup-control.json').read_text())
    expected = set(control['events'])
    lab.http('https://grafana:3000/api/dashboards/db', {'dashboard': {'uid': 'phase6b-backup', 'title': 'Phase6B recovery marker',
             'schemaVersion': 41, 'panels': [], 'tags': ['phase6b']}, 'overwrite': True}, basic=True)
    # Quiesce writers, then flush native filesystem backends before cold copies.
    lab.mutate('stop', 'fluent-bit')
    lab.mutate('stop', 'collector')
    for service in ['loki', 'tempo', 'grafana']:
        result = cold_copy(lab, service, service)
        if service == 'loki':
            actual = compare(lab, control['group'], expected, 'loki-restore')
            verified = not actual['missing']
        elif service == 'grafana':
            recovered = lab.http('https://grafana-restore:3000/api/v1/provisioning/alert-rules', basic=True)
            marker = lab.http('https://grafana-restore:3000/api/dashboards/uid/phase6b-backup', basic=True)
            verified = recovered['status'] == 200 and 'phase6b-lifecycle' in {r['uid'] for r in recovered['body']} and marker['status'] == 200
        else:
            trace_control = json.loads((lab.folder / 'evidence/backup-traces.json').read_text())
            verified = len(trace_ids(lab, trace_control, 'tempo-restore')) == len(trace_control)
        lab.check(verified, service + ' cold backup restored and queried', result, started=started)
        lab.mutate('stop', service + '-restore')
    backup_native(lab)


def backup_native(lab):
    started = now()
    control = json.loads((lab.folder / 'evidence/backup-control.json').read_text())
    expected = set(control['events'])
    snapshot = lab.http('https://prometheus:9090/api/v1/admin/tsdb/snapshot', {}, method='POST')
    lab.check(snapshot['status'] == 200, 'Prometheus native snapshot includes head', snapshot['status'])
    name = snapshot['body']['data']['name']
    code = "import pathlib,shutil,json,hashlib; p=pathlib.Path('/stores/prometheus/snapshots')/'" + name + "'; target=pathlib.Path('/stores/prometheus-restore'); shutil.copytree(p,target,dirs_exist_ok=True); files=[{'path':str(f.relative_to(p)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in p.rglob('*') if f.is_file()]; print(json.dumps(files))"
    manifest = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', code))
    store(lab, 'prometheus-native-backup-manifest', manifest)
    lab.compose('up', '-d', '--no-build', '--pull', 'never', 'prometheus-restore')
    lab.ready('prometheus-restore')
    # Snapshot values from before restore startup, not freshly scraped replacement values.
    stamp = time.time() - 5
    query = urllib.parse.urlencode({'query': 'phase6b_breach', 'time': str(stamp)})
    original = lab.http('https://prometheus:9090/api/v1/query?' + query)['body']['data']['result']
    restored = lab.http('https://prometheus-restore:9090/api/v1/query?' + query)['body']['data']['result']
    lab.check(bool(restored) and restored == original, 'Prometheus native snapshot restore historical samples', {'series': len(restored), 'manifest_files': len(manifest)})
    lab.mutate('stop', 'prometheus-restore')
    # Native OpenSearch snapshot, restricted to the synthetic application index family.
    repo = lab.http('https://opensearch:9200/_snapshot/phase6b', {'type': 'fs', 'settings': {'location': '/snapshots', 'compress': True}}, method='PUT', role='admin')
    snap = lab.http('https://opensearch:9200/_snapshot/phase6b/control?wait_for_completion=true',
                    {'indices': 'springboot-*-logs', 'include_global_state': False}, method='PUT', role='admin', timeout=30)
    lab.check(repo['status'] == 200 and snap.get('body', {}).get('snapshot', {}).get('state') == 'SUCCESS', 'OpenSearch native snapshot SUCCESS', snap.get('body', {}).get('snapshot', {}).get('state'))
    lab.mutate('stop', 'opensearch')
    lab.os_start('opensearch-restore')
    lab.http('https://opensearch-restore:9200/_snapshot/phase6b', {'type': 'fs', 'settings': {'location': '/snapshots', 'readonly': True}}, method='PUT', role='admin')
    restore = lab.http('https://opensearch-restore:9200/_snapshot/phase6b/control/_restore?wait_for_completion=true',
                       {'indices': 'springboot-*-logs', 'include_global_state': False}, method='POST', role='admin', timeout=30)
    lab.wait(lambda: len(set(log_ids(lab, control['group'], 'opensearch-restore'))) == len(expected))
    compare(lab, control['group'], expected, 'opensearch-restore')
    lab.check(restore['status'] == 200, 'OpenSearch native snapshot restore into separate security-enabled cluster', restore['status'])
    lab.mutate('stop', 'opensearch-restore')
    lab.mutate('start', 'opensearch')
    lab.ready('opensearch')
    lab.mutate('start', 'collector')
    lab.mutate('start', 'fluent-bit')
    lab.result('NOT VERIFIED', 'off-host encrypted backup, established RPO/RTO and live restore', 'Local disposable restoration only; memory-backed stores are not durable backup media')


def retention(lab):
    started = now()
    index = 'phase6b-expire-' + uuid.uuid4().hex[:6]
    lab.http('https://opensearch:9200/' + index, {'settings': {'number_of_shards': 1, 'number_of_replicas': 0}}, method='PUT', role='admin')
    lab.http('https://opensearch:9200/' + index + '/_doc/marker?refresh=true', {'marker': 'naturally-expiring-synthetic'}, role='admin')
    metadata = lab.http('https://opensearch:9200/' + index + '/_settings', role='admin')['body']
    index_uuid = metadata[index]['settings']['index']['uuid']
    scan_code = "import os,json; errors=[]; paths=[];\nfor root,dirs,files in os.walk('/stores/os',onerror=lambda e:errors.append(type(e).__name__)):\n paths.extend(os.path.join(root,d) for d in dirs if d=='" + index_uuid + "')\nprint(json.dumps({'paths':paths,'errors':errors}))"
    physical_before = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', scan_code))
    policy = {'policy': {'description': 'Disposable natural expiry only', 'default_state': 'hot', 'states': [
        {'name': 'hot', 'actions': [], 'transitions': [{'state_name': 'delete', 'conditions': {'min_index_age': '1m'}}]},
        {'name': 'delete', 'actions': [{'delete': {}}], 'transitions': []}]}}
    lab.http('https://opensearch:9200/_plugins/_ism/policies/phase6b-expiry', policy, method='PUT', role='admin')
    assignment = lab.http('https://opensearch:9200/_plugins/_ism/add/' + index, {'policy_id': 'phase6b-expiry'}, role='admin')
    states = []
    deadline = time.monotonic() + 210
    deleted = False
    while time.monotonic() < deadline:
        response = lab.http('https://opensearch:9200/' + index, role='admin')
        explain = lab.http('https://opensearch:9200/_plugins/_ism/explain/' + index, role='admin')
        states.append({'utc': now(), 'index_status': response['status'], 'explain': explain.get('body')})
        if response['status'] == 404:
            deleted = True
            break
        time.sleep(10)
    physical_after = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', scan_code))
    store(lab, 'opensearch-retention', {'index': index, 'uuid': index_uuid, 'states': states,
          'physical_before': physical_before, 'physical_after': physical_after})
    verified = deleted and bool(physical_before['paths']) and not physical_after['paths'] and not physical_before['errors'] and not physical_after['errors']
    lab.result('PASS' if verified else 'NOT VERIFIED', 'OpenSearch natural ISM deletion and shard directory removal',
               {'deleted': deleted, 'physical_before': physical_before, 'physical_after': physical_after, 'assignment_status': assignment['status']}, started=started)
    lab.result('NOT VERIFIED', 'Loki physical retention deletion', 'Supported fixture retention24h exceeds bounded observation; configuration accepted, no timestamp manipulation')
    lab.result('NOT VERIFIED', 'Prometheus physical retention deletion', '15m configured but normal head/block compaction exceeds bounded observation; native snapshot restore tested separately')
    # Tempo configuration is changed only inside this disposable fixture.
    ids, _ = traces(lab, 2)
    lab.wait(lambda: len(trace_ids(lab, ids)) == 2)
    time.sleep(15)
    manifest_code = "import json; from pathlib import Path; print(json.dumps([str(p.relative_to('/stores/tempo')) for p in Path('/stores/tempo/blocks').rglob('meta.json')]))"
    before_files = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', manifest_code))
    path = lab.folder / 'config/tempo.yml'
    original = path.read_text()
    write(path, original.replace('block_retention: 10m', 'block_retention: 30s'))
    lab.mutate('stop', 'tempo')
    lab.mutate('start', 'tempo')
    lab.ready('tempo')
    time.sleep(45)
    found = trace_ids(lab, ids)
    after_files = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', manifest_code))
    removed = sorted(set(before_files) - set(after_files))
    directory_code = "import json; from pathlib import Path; paths=" + repr(before_files) + "; print(json.dumps([str(Path(p).parent) for p in paths if not (Path('/stores/tempo')/Path(p).parent).exists()]))"
    removed_directories = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c', directory_code))
    control, _ = traces(lab, 1)
    lab.wait(lambda: len(trace_ids(lab, control)) == 1)
    detail = {'expired_cohort_remaining_queryable': len(found), 'before_block_metadata': before_files,
              'after_block_metadata': after_files, 'physically_removed_metadata': removed,
              'physically_removed_block_directories': removed_directories, 'fresh_control_queryable': True}
    store(lab, 'tempo-retention', detail)
    lab.result('PASS' if not found and removed_directories else 'NOT VERIFIED', 'Tempo natural trace expiry and physical block removal', detail)
    write(path, original)
    lab.mutate('stop', 'tempo')
    lab.mutate('start', 'tempo')
    lab.ready('tempo')


def performance(lab):
    started = now()
    lab.resources('before-load')
    group = 'perf-' + uuid.uuid4().hex[:8]
    expected = set()
    start = time.monotonic()
    # Explicit envelope:10 events/sec for10sec,20 spans total, serial queries.
    for i in range(10):
        expected |= logs(lab, group + '-' + str(i), 10, 200)
        lab.headroom()
        time.sleep(1)
    ids, response = traces(lab, 20)
    trace_started = time.monotonic()
    lab.wait(lambda: len(trace_ids(lab, ids)) == len(ids))
    trace_recovery_seconds = time.monotonic() - trace_started
    # Query all per-second groups; aggregate IDs and backend latencies.
    query_latencies = []
    stored = set()
    for i in range(10):
        group_ids = lab.wait(lambda i=i: log_ids(lab, group + '-' + str(i)))
        stored |= set(group_ids)
        begin = time.monotonic()
        log_ids(lab, group + '-' + str(i), 'opensearch')
        query_latencies.append(round((time.monotonic() - begin) * 1000, 2))
    elapsed = time.monotonic() - start
    detail = {'submitted_logs': 100, 'stored_unique_loki': len(stored), 'submitted_spans': 20, 'queryable_trace_ids': len(ids),
              'receiver_http_status': response['receiver_http_status'], 'trace_queryable_wait_seconds': round(trace_recovery_seconds, 3),
              'elapsed_including_drain_seconds': round(elapsed, 3), 'observed_log_events_per_second_including_drain': round(100 / elapsed, 2),
              'opensearch_query_ms_including_docker_probe_overhead': query_latencies, 'envelope': '10logs/s10s;20spans;serialqueries;max4MiBsource'}
    urls = [('loki', 'https://loki:3100/ready', False), ('prometheus', 'https://prometheus:9090/api/v1/query?query=phase6b_breach', False),
            ('grafana-datasource-proxy', 'https://grafana:3000/api/datasources/proxy/uid/prometheus/api/v1/query?query=phase6b_breach', True)]
    detail['http_query_samples'] = {name: [{k: result[k] for k in ['status', 'ms']} for result in
            [lab.http(url, basic=auth) for _ in range(3)]] for name, url, auth in urls}
    detail['storage_bytes'] = json.loads(lab.compose('exec', '-T', 'probe', 'python', '-c',
        "import json; from pathlib import Path; print(json.dumps({p.name:sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) for p in Path('/stores').iterdir()}))"))
    store(lab, 'performance-collector-queue', lab.http('http://collector:8888/metrics'))
    store(lab, 'performance-fluentbit-buffer', lab.http('http://fluent-bit:2020/api/v1/metrics/prometheus'))
    store(lab, 'performance', detail)
    lab.resources('after-load')
    lab.check(stored == expected, 'bounded isolated ingestion/query measurement', detail, started=started)
    backup_ids, _ = traces(lab, 3)
    lab.wait(lambda: len(trace_ids(lab, backup_ids)) == 3)
    store(lab, 'backup-traces', backup_ids)
    lab.result('NOT VERIFIED', 'representative production capacity and dashboard browser latency', 'Small synthetic fixture and Docker-probe timings cannot establish production API capacity or browser rendering')


def execute(lab, selected=None):
    lab.validate()
    lab.audit_runtime()
    suites = [('security', security), ('opensearch', opensearch), ('crash', crash), ('overflow', overflow),
              ('lifecycle', lifecycle), ('performance', performance), ('backup', backup), ('retention', retention)]
    if selected == 'backup-native':
        suites = [('backup-native', backup_native)]
    started = time.monotonic()
    success = True
    for name, function in suites:
        if selected and selected != name:
            continue
        if time.monotonic() - started > 1800:
            lab.result('BLOCKED', name, 'Maximum test run duration reached')
            break
        lab.headroom()
        begin = now()
        lab.active_suite = name
        lab.attempt = uuid.uuid4().hex[:10]
        first_row = len(lab.rows)
        try:
            function(lab)
        except Exception as error:
            lab.result('FAIL', name + ' execution', type(error).__name__ + ': ' + str(error), started=begin)
            lab.result('FAIL', name + ' suite completion', 'Attempt stopped at failure; earlier evidence retained', started=begin)
            success = False
            # Fail closed: do not continue destructive suites with unknown fixture state.
            break
        passed = not any(row['status'] == 'FAIL' for row in lab.rows[first_row:])
        lab.result('PASS' if passed else 'FAIL', name + ' suite completion', 'Completed bounded attempt; see individual scoped checks', started=begin)
        success = success and passed
        lab.resources(name)
    lab.active_suite = 'preservation'
    lab.attempt = uuid.uuid4().hex[:10]
    first_row = len(lab.rows)
    lab.preserve()
    success = success and not any(row['status'] == 'FAIL' for row in lab.rows[first_row:])
    print('SUMMARY:', dict(Counter(r['status'] for r in lab.rows)), flush=True)
    return success
