"""Bounded disposable native Logback/Fluent Bit protocol fixture. No live downtime.

Only newly created labelled fixture containers are stopped. Volumes are retained.
"""
from collections import Counter
from datetime import datetime,timezone
import importlib
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode=True
v=importlib.import_module('phase5-runtime')
ROOT=v.ROOT

def command(*args):
    p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=90)
    if p.returncode:
        raise RuntimeError('Fixture subprocess failed: '+args[0]+'; output withheld')
    return p.stdout

def main():
    run=uuid.uuid4().hex[:10]
    name='remediation-rotation-'+run
    volume='remediation_rotation_'+run
    network=name
    folder=ROOT/'data'/name
    folder.mkdir(parents=True)
    libs=folder/'lib'
    libs.mkdir()
    cache=Path.home()/'.m2/repository'
    paths=[cache/'ch/qos/logback/logback-classic/1.5.38/logback-classic-1.5.38.jar',
           cache/'ch/qos/logback/logback-core/1.5.38/logback-core-1.5.38.jar']
    paths += [sorted((cache/'org/slf4j/slf4j-api').glob('*/slf4j-api-*.jar'))[-1]]
    for file in paths:
        shutil.copy2(file,libs/file.name)
    command('javac','-cp',str(libs/'*'),'-d',str(folder),str(ROOT/'observability/fixtures/LogRotationWriter.java'))
    shutil.copy2(ROOT/'observability/fixtures/telemetry-sink.py',folder/'sink.py')
    shutil.copy2(ROOT/'observability/fluent-bit/parsers.conf',folder/'parsers.conf')
    command('docker','network','create','--internal','--label','observability.remediation.fixture='+run,network)
    command('docker','volume','create','--label','observability.remediation.fixture='+run,volume)
    def helper(shell,root=False):
        args=['docker','run','--rm','--pull','never','--network','none','--read-only','--cap-drop','ALL',
            '--memory','64m','--pids-limit','32','--user','0:0' if root else '10001:10001']
        if root:
            args += ['--cap-add','CHOWN']
        return command(*args,'-v',volume+':/lab','-v',str(folder)+':/fixture:ro','--entrypoint','/bin/sh','postgres:17.6','-ec',shell)
    helper('mkdir -p /lab/logs/spool /lab/logs/archive /lab/buffer && chown -R 10001:10001 /lab',True)
    def write_batch(start,end,legacy=False):
        rows=[]
        for i in range(start,end):
            rows.append({'@timestamp':datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),
                'service':'jwks-service','environment':'test','level':'INFO','event':'fixture.rotation',
                'correlationId':name+'-'+str(i),'traceId':'1234567890abcdef1234567890abcdef',
                'spanId':'1234567890abcdef','message':'synthetic '+('x'*1100)})
        (folder/'input.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        if legacy:
            helper('cat /fixture/input.jsonl > /lab/logs/app.log')
            return
        command('docker','run','--rm','--pull','never','--network','none','--read-only','--cap-drop','ALL',
            '--memory','192m','--cpus','0.5','--pids-limit','64','--user','10001:10001',
            '-v',volume+':/lab','-v',str(folder)+':/fixture:ro','--entrypoint','java','springboot_project-jwks-api',
            '-Xmx64m','-cp','/fixture:/fixture/lib/*','LogRotationWriter','/fixture/input.jsonl','/lab/logs')
    def config(archives):
        (folder/'tail.conf').write_text('''[SERVICE]
    Flush 1
    Grace 2
    Parsers_File /fixture/parsers.conf
    storage.path /lab/buffer
    storage.sync full
    storage.checksum on
[INPUT]
    Name tail
    Tag lab
    Path /lab/logs/app.log'''+(',/lab/logs/spool/app.*.log' if archives else '')+'''
    Exclude_Path /lab/logs/archive/*.gz
    Parser application_json
    DB /lab/tail.db
    DB.sync Full
    DB.journal_mode WAL
    DB.compare_filename Off
    Read_from_Head On
    Refresh_Interval 1
    Rotate_Wait 3
    Skip_Long_Lines On
    Buffer_Max_Size 256k
    storage.type filesystem
[OUTPUT]
    Name loki
    Match lab
    Host sink
    Port 9020
    Labels job=fixture,service=$service,environment=$environment
    Line_Format json
    Retry_Limit False
    storage.total_limit_size 1M
[OUTPUT]
    Name opensearch
    Match lab
    Host sink
    Port 9020
    Index fixture
    Suppress_Type_Name On
    Generate_ID On
    Retry_Limit False
    storage.total_limit_size 1M
''')
    def create(role,image,args):
        return command('docker','run','-d','--pull','never','--name',name+'-'+role,
            '--label','observability.remediation.fixture='+run,'--network',network,
            '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
            '--memory','64m','--cpus','0.5','--pids-limit','32','--user','10001:10001',
            '-v',volume+':/lab','-v',str(folder)+':/fixture:ro',*args,image,
            *(['/fixture/sink.py'] if role=='sink' else ['-c','/fixture/tail.conf'])).strip()
    ids=[]
    checks=[]
    def check(ok,label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)
        print('PASS:',label,flush=True)
    def stop(cid):
        obj=json.loads(command('docker','inspect',cid))[0]
        assert obj['Config']['Labels']['observability.remediation.fixture']==run
        command('docker','stop','--time','5',cid)
    def events():
        raw=helper('if [ -f /lab/sink-events.jsonl ]; then cat /lab/sink-events.jsonl; fi')
        return [json.loads(line) for line in raw.splitlines() if line]
    def wait_all(count):
        end=time.monotonic()+35
        while time.monotonic()<end:
            rows=events()
            if all(len({r['record']['correlationId'] for r in rows if r['backend']==sink})==count for sink in ['loki','opensearch']):
                time.sleep(1)
                return rows
            time.sleep(2)
        raise TimeoutError('Fixture delivery incomplete')
    try:
        sink=create('sink','python:3.14-alpine',['--network-alias','sink','--entrypoint','python'])
        ids.append(sink)
        write_batch(0,4,legacy=True)
        write_batch(4,12)
        archives=helper('find /lab/logs/spool -name "*.log" -type f').splitlines()
        check(len(archives)>1,'real Logback size rollover creates multiple stable uncompressed files')
        config(False)
        fb=create('fluent','cr.fluentbit.io/fluent/fluent-bit:3.2.10',['--entrypoint','/fluent-bit/bin/fluent-bit'])
        ids.append(fb)
        time.sleep(4)
        original=events()
        check(bool(original) and len({r['record']['correlationId'] for r in original})<12,'old current-only tail reads active file but leaves older archives unread')
        stop(fb)
        state_before=helper('stat -c "%i" /lab/tail.db').strip()
        config(True)
        command('docker','start',fb)
        wait_all(12)
        check(helper('stat -c "%i" /lab/tail.db').strip()==state_before,'migration reuses existing tail DB file without reset')
        check(True,'archive-aware discovery recovers existing uncompressed archives')
        (folder/'legacy.gz').write_bytes(gzip.compress((json.dumps({'service':'jwks-service',
            'correlationId':name+'-legacy-compressed'})+'\n').encode()))
        helper('cat /fixture/legacy.gz > /lab/logs/archive/app.legacy.log.gz')
        legacy_hash=helper('sha256sum /lab/logs/archive/app.legacy.log.gz').split()[0]
        write_batch(12,24)
        wait_all(24)
        check(True,'rotation while collector running delivers to both protocol outputs')
        stop(fb)
        write_batch(24,48)
        compressed=helper('find /lab/logs/spool -name "*.gz" -type f').strip()
        check(not compressed,'no automatic compression makes unread rotated files inaccessible')
        command('docker','start',fb)
        wait_all(48)
        check(True,'collector downtime across multiple real rotations recovers all retained records')
        stop(fb)
        command('docker','start',fb)
        write_batch(48,52)
        rows=wait_all(52)
        time.sleep(3)
        rows=events()
        for sinkname in ['loki','opensearch']:
            counts=Counter(r['record']['correlationId'] for r in rows if r['backend']==sinkname)
            check(len(counts)==52 and all(n==1 for n in counts.values()),'52 retained events observed once after restart: '+sinkname)
        check(not any(r['record']['correlationId']==name+'-legacy-compressed' for r in rows)
            and helper('sha256sum /lab/logs/archive/app.legacy.log.gz').split()[0]==legacy_hash,
            'legacy compressed archive remains untouched and excluded from ingestion')
        check(all(r['record']['traceId']=='1234567890abcdef1234567890abcdef' and r['record']['spanId']=='1234567890abcdef' for r in rows),'JSON trace fields retained through rotation and restart')
        used=int(helper('du -sb /lab/logs').split()[0])
        check(used<192*1024,'fixture source data stays within configured archive cap plus active-file allowance')
        output={'result':'PASS','run':run,'checks':checks,'events_per_sink':52,'source_bytes':used,
            'containers':ids,'volume':volume,'network':network,'scope':'native Logback + native Fluent Bit + protocol sinks; live storage tested separately'}
        (ROOT/'observability/remediation-rotation-evidence.log').write_text(json.dumps(output,indent=2))
    finally:
        for cid in reversed(ids):
            stop(cid)
        print('Fixture containers stopped; task-owned volume/network retained. No live collector was stopped.')

if __name__=='__main__':
    main()
