"""Isolated Fluent Bit tail tests. Writes only task-owned synthetic files under data/."""
from collections import Counter
import datetime
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pipeline', ROOT / 'observability/verify-pipeline.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def main():
    run = uuid.uuid4().hex[:10]
    folder = ROOT / 'data' / ('phase4-tail-' + run)
    folder.mkdir(parents=True)
    logfile = folder / 'app.log'
    name = 'springboot_project-phase4-tail-' + run
    volume = 'springboot_project_phase4_tail_' + run
    config = folder / 'tail.conf'
    config.write_text('''[SERVICE]
    Flush 1
    Grace 2
    Log_Level info
    Parsers_File /test/parsers.conf
    storage.path /state/buffer
    storage.sync full
    storage.checksum on
    storage.max_chunks_up 4
[INPUT]
    Name tail
    Tag lab
    Path /state/logs/app.log
    Parser application_json
    DB /state/tail.db
    DB.sync Full
    DB.journal_mode WAL
    Read_from_Head On
    Refresh_Interval 1
    Rotate_Wait 5
    Skip_Long_Lines On
    Buffer_Max_Size 256k
    storage.type filesystem
[OUTPUT]
    Name stdout
    Match lab
    Format json_lines
    storage.total_limit_size 1M
''')
    (folder / 'parsers.conf').write_text((ROOT / 'observability/fluent-bit/parsers.conf').read_text())
    expected = []

    def event(label, message='synthetic event'):
        correlation = 'phase4-tail-' + run + '-' + label
        return {'@timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                'service': 'jwks-service', 'environment': 'test', 'message': message, 'event': 'fixture.test',
                'correlationId': correlation, 'traceId': '1234567890abcdef1234567890abcdef',
                'spanId': '1234567890abcdef'}

    def helper(command):
        return p.v.docker('run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                          '--user', '10001:10001', '-v', volume + ':/state', '-v', str(folder) + ':/test:ro',
                          '--entrypoint', '/bin/sh', 'postgres:17.6', '-ec', command)

    def write(path, record, mode='a'):
        payload = folder / ('event-' + uuid.uuid4().hex + '.json')
        payload.write_text(json.dumps(record) + '\n', encoding='utf-8')
        redirect = ' >> ' if mode == 'a' else ' > '
        helper('cat /test/' + payload.name + redirect + '/state/logs/' + path.name)

    def flatten(obj):
        if isinstance(obj, dict):
            return [obj] if 'correlationId' in obj else []
        if isinstance(obj, list):
            return [record for item in obj for record in flatten(item)]
        return []

    def records():
        result = []
        for line in p.v.docker('logs', name).splitlines():
            try:
                result.extend(flatten(json.loads(line)))
            except ValueError:
                pass
        return result

    def expect(label, record):
        expected.append(record['correlationId'])
        p.wait_for(lambda: record['correlationId'] in [r['correlationId'] for r in records()], label, attempts=15)
        p.check(True, label)

    first = event('initial', 'x' * 2000)
    p.v.docker('run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--cap-add', 'CHOWN',
               '--user', '0:0', '-v', volume + ':/state', '--entrypoint', '/bin/sh', 'postgres:17.6',
               '-ec', 'mkdir -p /state/logs && chown 10001:10001 /state /state/logs')
    write(logfile, first)
    try:
        p.v.docker('run', '-d', '--name', name, '--label', 'phase4.lab=tail', '--network', 'none',
                   '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                   '--memory', '64m', '--pids-limit', '32', '--user', '10001:10001',
                   '-v', str(folder) + ':/test:ro', '-v', volume + ':/state',
                   '--entrypoint', '/fluent-bit/bin/fluent-bit', 'cr.fluentbit.io/fluent/fluent-bit:3.2.10',
                   '-c', '/test/tail.conf')
        expect('initial tail read', first)
        rotated = folder / 'app.log.1'
        helper('mv /state/logs/app.log /state/logs/app.log.1')
        late = event('renamed-late')
        write(rotated, late)
        fresh = event('new-file', 'x' * 2000)
        write(logfile, fresh, 'w')
        expect('renamed inode late write retained during Rotate_Wait', late)
        expect('new current file after rename discovered', fresh)
        helper(': > /state/logs/app.log')
        time.sleep(2)
        truncated = event('truncated')
        write(logfile, truncated)
        expect('copy-truncate resumes with new content', truncated)
        compressed = event('compressed-must-not-read')
        with gzip.open(folder / 'app.log.2.gz', 'wt', encoding='utf-8') as output:
            output.write(json.dumps(compressed) + '\n')
        helper('cat /test/app.log.2.gz > /state/logs/app.log.2.gz')
        p.v.docker('stop', '--time', '5', name)
        stopped = event('written-while-stopped')
        write(logfile, stopped)
        p.v.docker('start', name)
        expect('persisted DB resumes new content written during stop', stopped)
        time.sleep(3)
        observed = records()
        counts = Counter(record['correlationId'] for record in observed)
        p.check(all(counts[value] == 1 for value in expected), 'no old records reread after normal restart')
        p.check(compressed['correlationId'] not in counts, 'compressed historical file excluded')
        p.check(all(r.get('traceId') == first['traceId'] and r.get('spanId') == first['spanId'] for r in observed),
                'synthetic JSON tracing fields preserved')
        p.record('tailLab', {'result': 'PASS', 'events': len(expected), 'exactlyOnceObserved': True,
                            'container': name, 'volume': volume, 'scope': 'isolated synthetic fixture, not app log rotation'})
    finally:
        p.v.docker('stop', '--time', '5', name)
    print('PASS: isolated fixture complete; stopped container/volume retained, no volume deletion')


if __name__ == '__main__':
    main()
