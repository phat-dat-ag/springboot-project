"""Immutable baseline, read-only preservation check and explicit logging-only rollout."""
import argparse
import importlib
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.dont_write_bytecode=True
v=importlib.import_module('verify-phase6')
STATE=v.OBS/'phase6a-remediation-state.log'

def create():
    if STATE.exists():
        raise RuntimeError('Original remediation baseline already exists; refusing overwrite')
    args=argparse.Namespace(evidence_dir=v.OBS/'phase6-evidence/remediation',compose_file=None,
        endpoint=[],timeout=10,credentials=v.OBS/'local-test-credentials.json')
    x=v.Validation(args)
    x.snapshot()
    before=x.baseline
    now=time.time()
    query=urllib.parse.urlencode({'query':'http_server_requests_seconds_count{service="jwks-service"}','time':str(now)})
    before['historical_prometheus']={'params':query,'rows':x.api('prometheus','/api/v1/query?'+query)['data']['result']}
    traces=x.api('grafana','/api/datasources/proxy/uid/tempo/api/search?limit=3')['traces']
    before['historical_traces']=[row['traceID'] for row in traces]
    before['initial_logback']={m:(v.ROOT/m/'src/main/resources/logback-spring.xml').read_text() for m in v.MODULES}
    before['initial_fluentbit']=(v.OBS/'fluent-bit/fluent-bit.conf').read_text()
    (x.out/'baseline.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    STATE.write_text(json.dumps({'baseline':str((x.out/'baseline.json').relative_to(v.ROOT))}),encoding='utf-8')
    print('Immutable remediation baseline saved:',x.out.relative_to(v.ROOT))

def verify():
    base=json.loads((v.ROOT/json.loads(STATE.read_text())['baseline']).read_text())
    x=v.Validation.__new__(v.Validation)
    current={c['name']:c for c in x.inventory()}
    allowed={'user-api','learning-api','jwks-api','fluent-bit'}
    changed=[]
    for c in base['containers']:
        a=current[c['name']]
        if any(a[k]!=c[k] for k in ['id','started','restarts']):
            assert c['project']=='springboot_project' and c['service'] in allowed
            changed.append(c['service'])
        for k in ['ports','networks']:
            assert a[k]==c[k]
        assert {m['Destination']:m.get('Name') for m in a['mounts'] if m['Type']=='volume'}=={m['Destination']:m.get('Name') for m in c['mounts'] if m['Type']=='volume'}
    p=importlib.import_module('phase5-runtime')
    assert set(base['volumes'])<=set(x.cmd('docker','volume','ls','-q').split())
    for file,wanted in base['protected'].items():
        assert v.digest((v.ROOT/file).read_bytes())==wanted
    for key,path in [('contacts','contact-points'),('policies','policies'),('alerts','alert-rules')]:
        assert v.digest(p.api('/api/v1/provisioning/'+path))==base[key+'_digest']
    for uid,wanted in base['dashboards'].items():
        assert v.digest(p.api('/api/dashboards/uid/'+uid)['dashboard'])==wanted
    assert v.digest(p.api('/api/datasources'))==base['datasources_digest']
    for path,wanted in base['jwks'].items():
        port=next(item['published'] for item in p.model()['services']['jwks-api']['ports'] if item['target']==8080)
        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+path,timeout=10) as r:
            assert v.digest(json.load(r))==wanted
    original={r['index']:r for r in base['opensearch_indices']}
    actual={r['index']:r for r in p.api('/_cat/indices/springboot-*-logs?format=json&bytes=b','opensearch')}
    assert all(name in actual and actual[name]['uuid']==row['uuid'] and int(actual[name]['docs.count'])>=int(row['docs.count']) for name,row in original.items())
    saved=base['historical_prometheus']
    canonical=lambda rows:sorted((json.dumps(r['metric'],sort_keys=True),r['value']) for r in rows)
    assert canonical(p.api('/api/v1/query?'+saved['params'],'prometheus')['data']['result'])==canonical(saved['rows'])
    for tid in base['historical_traces']:
        assert p.api('/api/datasources/proxy/uid/tempo/api/traces/'+tid)
    historical=json.loads((v.OBS/'phase6-measurements.json').read_text())
    tid=historical['linked_trace']
    assert isinstance(tid,str) and len(tid)==32 and all(c in '0123456789abcdef' for c in tid)
    params=urllib.parse.urlencode({'query':'{job="springboot"} |= "'+tid+'"',
        'start':str(int((time.time()-86400*2)*1e9)),'end':str(time.time_ns()),'limit':'20'})
    assert p.api('/loki/api/v1/query_range?'+params,'loki')['data']['result']
    print('PASS: all original volumes, database mounts, keys/env, Grafana resources, JWKS, index UUID/counts, historical Loki logs, Prometheus samples and traces preserved')
    print('PASS: all unrelated containers unchanged; affected target services:',sorted(set(changed)))

def deploy():
    base=json.loads((v.ROOT/json.loads(STATE.read_text())['baseline']).read_text())
    x=v.Validation.__new__(v.Validation)
    for module in v.MODULES:
        suites=[ET.parse(p).getroot() for p in (v.ROOT/module/'target/surefire-reports').glob('TEST-*.xml')]
        assert suites and all(int(s.get('failures',0))==0 and int(s.get('errors',0))==0 for s in suites)
    fixture=json.loads((v.OBS/'remediation-rotation-evidence.log').read_text())
    assert fixture['result']=='PASS' and fixture['events_per_sink']==52
    services={c['service']:c for c in base['containers'] if c['project']=='springboot_project'}
    before={c['name']:c for c in x.inventory()}
    for service in ['user-api','learning-api','jwks-api','fluent-bit']:
        assert before[services[service]['name']]['id']==services[service]['id']
    # Preserve the actual per-service override set. Current APIs were started base-only.
    x.cmd('docker','restart','--time','40',services['fluent-bit']['id'])
    p=importlib.import_module('phase5-runtime')
    model=p.model()['services']
    for service in ['user-api','learning-api','jwks-api']:
        files=services[service]['config_files'].split(',')
        assert all(Path(file).resolve().parent==v.ROOT for file in files)
        compose=['docker','compose','-p','springboot_project','--env-file','.env']
        for file in files:
            compose += ['-f',file]
        x.cmd(*compose,'config','--quiet')
        x.cmd(*compose,'up','-d','--no-deps','--no-build','--pull','never',service)
        port=next(item['published'] for item in model[service]['ports'] if item['target']==8080)
        deadline=time.monotonic()+120
        import urllib.request
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/actuator/health/readiness',timeout=5) as r:
                    if json.load(r)['status']=='UP':
                        break
            except (OSError,ValueError):
                pass
            if time.monotonic()>deadline:
                raise TimeoutError(service+' readiness; halted remaining rollout')
            time.sleep(2)
        cid=next(c['id'] for c in x.inventory() if c['project']=='springboot_project' and c['service']==service)
        loaded=x.cmd('docker','exec',cid,'cat','/etc/application/logback-spring.xml')
        assert '/spool/' in loaded and '.log.gz</fileNamePattern>' not in loaded and '<file>' not in loaded
        files=x.cmd('docker','exec',cid,'find','/app/data/logs/spool','-type','f','-name','*.log')
        assert files.strip()
        print('PASS: sequential logging rollout ready with stable spool files:',service,flush=True)
    verify()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['snapshot','verify','deploy'])
    mode=parser.parse_args().mode
    globals()['create' if mode=='snapshot' else mode]()
