"""Reuse authenticated Phase 4 probe without overwriting historical evidence."""
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import urllib.parse

sys.dont_write_bytecode=True
p=importlib.import_module('verify-pipeline')
v=importlib.import_module('phase5-runtime')
OBS=Path(__file__).resolve().parent
p.EVIDENCE=OBS/'phase5-regression-evidence.log'
p.authenticated()
p.health()
for path,digest in p.BASE['protected'].items():
    p.check(hashlib.sha256((v.ROOT/path).read_bytes()).hexdigest()==digest,'protected environment/key/test credential unchanged: '+path)
for path,body in p.BASE['jwks'].items():
    p.check(p.request('jwks-api',path)[2]==body,'JWKS public response unchanged: '+path)
for file,strings in [
    ('fluent-bit/fluent-bit.conf',['storage.sync      full','storage.checksum  on','storage.type      filesystem','DB.sync           Full','DB.journal_mode   WAL']),
    ('otel-collector/config.yml',['sizer: bytes','storage: file_storage/queue','fsync: true','max_elapsed_time: 0s']),
    ('loki/loki-config.yml',['retention_period: 720h','retention_enabled: true']),
    ('tempo/tempo.yml',['block_retention: 72h'])]:
    raw=(OBS/file).read_text()
    p.check(all(s in raw for s in strings),'persistent buffering/retention contract: '+file)
for name in ['user-api','learning-api','jwks-api','fluent-bit','otel-collector','grafana','prometheus','loki','tempo','opensearch','opensearch-dashboards']:
    current=next(c for c in v.inventory() if c['project']=='springboot_project' and c['service']==name)
    p.check(current['logging']['Config'].get('max-size')=='10m' and current['logging']['Config'].get('max-file')=='3',
            'effective Docker log rotation: '+name)
state=json.loads(p.EVIDENCE.read_text())
tid=state['authenticated']['traceId']
for expression in [
    '{ resource.service.name =~ "learning-api|user-learning" && resource.deployment.environment.name = "development" }',
    '{ resource.service.name =~ ".*" && resource.deployment.environment.name =~ ".*" && duration > 1s }',
    '{ resource.service.name =~ ".*" && resource.deployment.environment.name =~ ".*" && status = error }']:
    result=v.api('/api/datasources/proxy/uid/tempo/api/search?'+urllib.parse.urlencode({'q':expression}))
    p.check('traces' in result,'actual Tempo TraceQL search accepted')
query='{service=~"learning-api|user-learning"} | json | traceId="'+tid+'"'
result=v.api('/loki/api/v1/query_range?'+urllib.parse.urlencode({'query':query,'limit':100}),'loki')
p.check(bool(result['data']['result']),'trace-to-log query returns actual correlated logs')
ds=v.api('/api/datasources/uid/loki')['jsonData']['derivedFields'][0]
p.check(ds['datasourceUid']=='tempo' and ds['url']=='${__value.raw}', 'log-to-trace derived-field target and interpolation retained')
for stream in result['data']['result']:
    for _,line in stream['values']:
        match=re.search(ds['matcherRegex'],line)
        if match:
            p.check(match.group(1)==tid,'derived field extracts actual stored trace')
            p.check(bool(v.api('/api/datasources/proxy/uid/tempo/api/traces/'+tid)),'derived trace resolves through Tempo proxy')
            break
print('Phase 5 authenticated, pipeline, retention, navigation and privacy regression complete.')
