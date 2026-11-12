"""Non-destructive Phase 6A checks. No deployment, restarts, external sends or installs.

Exit 0: executed checks passed, 1: a verified failure, 2: required evidence missing.
Each run has an immutable snapshot and separate local evidence directory.
"""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / 'observability'
APPS = {'user-api':'user-learning','learning-api':'learning-api','jwks-api':'jwks-service'}
MODULES = ['springboot-user-api','springboot-learning-api','springboot-jwks-api']

def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()

def observed_access_gap(services, loki, tempo):
    disabled=str(services.get('opensearch',{}).get('environment',{}).get('DISABLE_SECURITY_PLUGIN','')).lower()=='true'
    return disabled or any(re.search(r'^auth_enabled:\s*false\s*$',text,re.M) for text in [loki,tempo])

def observed_rotation_gap(logbacks, fluent):
    paths=re.findall(r'^\s*Path\s+(\S+)\s*$',fluent,re.M)
    return any('.log.gz</fileNamePattern>' in text for text in logbacks) and bool(paths) and all(
        path.endswith('.log') and '*' not in path and '/archive/' not in path for path in paths)

class Validation:
    def __init__(self, args):
        self.args = args
        self.rows = []
        self.details = {}
        self.secrets = []
        self.probes = []
        self.started = time.time()
        self.run_id = 'phase6-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        self.out = args.evidence_dir.resolve() / self.run_id
        self.out.mkdir(parents=True, exist_ok=False)
        # Evidence can contain topology; insist it is ignored before collecting it.
        if subprocess.run(['git','check-ignore','--quiet',str(self.out/'results.json')],cwd=ROOT).returncode:
            raise RuntimeError('Evidence directory must be Git-ignored')
        self.compose = ['docker','compose','-p','springboot_project','--env-file','.env']
        for file in args.compose_file or ['docker-compose.yml','docker-compose.debug.yml']:
            self.compose += ['-f',file]
        self.model = json.loads(self.cmd(*self.compose,'config','--format','json'))
        self.services = self.model['services']
        self.endpoints = {}
        for service, target in {**{a:8080 for a in APPS}, 'grafana':3000,'prometheus':9090,'loki':3100,'opensearch':9200}.items():
            port = next(p['published'] for p in self.services[service]['ports'] if int(p['target'])==target)
            self.endpoints[service] = 'http://127.0.0.1:' + str(port)
        for entry in args.endpoint:
            name, url = entry.split('=',1)
            parsed = urllib.parse.urlparse(url)
            if name not in self.endpoints or parsed.scheme not in ['http','https'] or parsed.hostname not in ['localhost','127.0.0.1','::1'] or parsed.username or parsed.password:
                raise ValueError('Endpoint overrides must be recognized loopback URLs without credentials')
            self.endpoints[name] = url.rstrip('/')
        e = self.services['grafana']['environment']
        self.auth = base64.b64encode((e['GF_SECURITY_ADMIN_USER']+':'+e['GF_SECURITY_ADMIN_PASSWORD']).encode()).decode()
        self.secrets += [e['GF_SECURITY_ADMIN_PASSWORD']]

    def cmd(self, *args, timeout=60):
        p = subprocess.run(args,cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=timeout)
        if p.returncode:
            # Never echo command arguments, expanded Compose, bodies or stderr.
            raise RuntimeError('Subprocess failed (exit '+str(p.returncode)+')')
        return p.stdout

    def result(self, status, name, detail=''):
        self.rows.append({'status':status,'check':name,'detail':detail})
        print(status+': '+name+(' - '+detail if detail else ''),flush=True)
        self.save()

    def check(self, ok, name, detail=''):
        self.result('PASS' if ok else 'FAIL',name,detail)
        if not ok:
            raise AssertionError(name)

    def save(self):
        (self.out/'results.json').write_text(json.dumps({'run_id':self.run_id,'utc':datetime.now(timezone.utc).isoformat(),
            'checks':self.rows,'details':self.details},indent=2),encoding='utf-8')

    def request(self, service, path, method='GET', body=None, headers=None, auth=True):
        h = {'Content-Type':'application/json',**(headers or {})}
        if service=='grafana' and auth:
            h['Authorization']='Basic '+self.auth
        req=urllib.request.Request(self.endpoints[service]+path,method=method,headers=h,
            data=None if body is None else json.dumps(body).encode())
        try:
            response=urllib.request.urlopen(req,timeout=self.args.timeout)
        except urllib.error.HTTPError as error:
            response=error
        with response:
            raw=response.read().decode()
            try:
                value=json.loads(raw)
            except ValueError:
                value=raw
            return response.status,dict(response.headers),value

    def api(self, service, path, body=None):
        status,_,value=self.request(service,path,'GET' if body is None else 'POST',body)
        if status!=200:
            raise RuntimeError('API '+service+' returned HTTP '+str(status))
        return value

    def query(self, expression):
        return self.api('prometheus','/api/v1/query?'+urllib.parse.urlencode({'query':expression}))['data']['result']

    def internal(self, url):
        return self.cmd('docker','exec',self.ids['prometheus'],'wget','-T',str(int(self.args.timeout)),'-q','-O','-',url)

    def inventory(self):
        ids=self.cmd('docker','ps','-aq').split()
        rows=json.loads(self.cmd('docker','inspect',*ids))
        safe=[]
        for r in rows:
            labels=r['Config'].get('Labels') or {}
            safe.append({'id':r['Id'],'name':r['Name'],'image':r['Config']['Image'],'image_id':r['Image'],
                'project':labels.get('com.docker.compose.project'),'service':labels.get('com.docker.compose.service'),
                'config_files':labels.get('com.docker.compose.project.config_files'),
                'started':r['State']['StartedAt'],'status':r['State']['Status'],
                'health':r['State'].get('Health',{}).get('Status'),'restarts':r['RestartCount'],
                'mounts':sorted(r['Mounts'],key=lambda m:m['Destination']),'ports':r['HostConfig']['PortBindings'],'networks':sorted(r['NetworkSettings']['Networks']),
                'memory_limit':r['HostConfig']['Memory'],'nano_cpus':r['HostConfig']['NanoCpus'],
                'logging':r['HostConfig']['LogConfig'],'readonly':r['HostConfig']['ReadonlyRootfs']})
        return safe

    def git(self):
        data={}
        for name in ['.']+MODULES:
            data[name]={'head':self.cmd('git','-C',name,'rev-parse','HEAD').strip(),
                'branch':self.cmd('git','-C',name,'branch','--show-current').strip(),
                'status':self.cmd('git','-C',name,'status','--porcelain=v1')}
        return data

    def fingerprints(self):
        files=list(ROOT.glob('.env*'))+list((ROOT/'key').glob('*.pem'))+list((ROOT/'data/keys/learning').glob('*.pem'))
        files += [ROOT/m/'.env' for m in MODULES]+[self.args.credentials]
        return {str(p.resolve().relative_to(ROOT)):digest(p.read_bytes()) for p in files if p.is_file() and not p.name.endswith('.example')}

    def snapshot(self):
        containers=self.inventory()
        target=[c for c in containers if c['project']=='springboot_project']
        self.ids={c['service']:c['id'] for c in target}
        self.images={c['service']:c['image_id'] for c in target}
        self.check(len([c for c in containers if c['project']=='jp_dev'])==16,'baseline has exactly 16 jp_dev containers')
        self.check(all(str(ROOT).lower() in (c['config_files'] or '').lower() for c in target),'target containers belong to this checkout')
        self.check(all(self.ids.get(s) for s in list(APPS)+['grafana','prometheus','loki','tempo','otel-collector','fluent-bit','opensearch']), 'required target containers identified')
        dashboards=self.api('grafana','/api/search?type=dash-db&limit=5000')
        contacts=self.api('grafana','/api/v1/provisioning/contact-points')
        self.baseline={'utc':datetime.now(timezone.utc).isoformat(),'containers':containers,
            'volumes':self.cmd('docker','volume','ls','-q').split(),'git':self.git(),'protected':self.fingerprints(),
            'compose_digest':digest(self.model),'datasources_digest':digest(self.api('grafana','/api/datasources')),
            'contacts_digest':digest(contacts),'contact_types':[c['type'] for c in contacts],
            'policies_digest':digest(self.api('grafana','/api/v1/provisioning/policies')),
            'dashboards':{d['uid']:digest(self.api('grafana','/api/dashboards/uid/'+d['uid'])['dashboard']) for d in dashboards},
            'alerts_digest':digest(self.api('grafana','/api/v1/provisioning/alert-rules')),
            'targets':self.api('prometheus','/api/v1/targets')['data']['activeTargets'],
            'grafana_version':self.api('grafana','/api/health')['version'],
            'prometheus_version':self.api('prometheus','/api/v1/status/buildinfo')['data']['version'],
            'jwks':{path:digest(self.api('jwks-api',path)) for path in ['/api/v1/jwks/user','/api/v1/jwks/learning']},
            'opensearch_indices':self.api('opensearch','/_cat/indices/springboot-*-logs?format=json&bytes=b'),
            'loki_stream_count':len(self.loki('{job="springboot"}',limit=1)),
            'tempo_trace_count':len(self.api('grafana','/api/datasources/proxy/uid/tempo/api/search?limit=1')['traces'])}
        self.baseline['config_files']={str(p.relative_to(ROOT)):digest(p.read_bytes())
            for p in list(OBS.rglob('*.yml'))+list(OBS.rglob('*.conf'))+list((OBS/'grafana').rglob('*.json'))
            if 'phase6-evidence' not in p.parts}
        (self.out/'baseline.json').write_text(json.dumps(self.baseline,indent=2),encoding='utf-8')
        self.details['baseline']={'containers':len(containers),'running':sum(c['status']=='running' for c in containers),
            'project_containers':len(target),'volumes':len(self.baseline['volumes']),
            'versions':{c['service']:c['image'] for c in target},'git':self.baseline['git']}
        self.result('PASS','fresh immutable baseline captured','container IDs/start times, volumes, protected fingerprints, Grafana state and existing backend availability')

    def loki(self, expr, limit=100):
        params={'query':expr,'start':str(int((self.started-300)*1e9)),'end':str(time.time_ns()),'limit':limit,'step':'60'}
        return self.api('loki','/loki/api/v1/query_range?'+urllib.parse.urlencode(params))['data']['result']

    def configuration(self):
        self.cmd(*self.compose,'config','--quiet')
        self.check(True,'Docker Compose base/selected overrides validate')
        for name,cfg in self.services.items():
            self.check(all(p.get('host_ip')=='127.0.0.1' for p in cfg.get('ports',[])), 'published ports loopback-only: '+name)
        for name in ['otel-collector','tempo','fluent-bit']:
            self.check(not self.services[name].get('ports'),'internal telemetry endpoints unpublished: '+name)
        for name in APPS:
            env=self.services[name]['environment']
            self.check(str(env['MANAGEMENT_TRACING_SAMPLING_PROBABILITY'])=='0.1','10% sampling: '+name)
            self.check(not any(p['target']==9091 for p in self.services[name]['ports']),'private metrics listener: '+name)
            keymounts=[m for m in self.services[name].get('volumes',[]) if '/run/keys/' in m['target']]
            self.check(all(m.get('read_only') for m in keymounts),'read-only key mounts: '+name)
        def fixture(service, mounts, command, env=None, tmp=True):
            args=['docker','run','--rm','--pull','never','--network','none','--read-only','--memory','256m','--cpus','0.5','--pids-limit','64']
            if tmp:
                args += ['--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=64m']
            for host,container in mounts:
                if not host.exists():
                    raise RuntimeError('Fixture mount missing')
                args += ['-v',str(host.resolve())+':'+container+':ro']
            for key,value in (env or {}).items():
                args += ['-e',key+'='+str(value)]
            if service=='prometheus':
                args += ['--entrypoint','promtool']
            return self.cmd(*args,self.images[service],*command)
        native=[
            ('Prometheus configuration and recording rules',lambda: fixture('prometheus',[(OBS/'prometheus','/etc/prometheus')],['check','config','/etc/prometheus/prometheus.yml'])),
            ('Prometheus idle/missing/histogram fixtures',lambda: fixture('prometheus',[(OBS/'prometheus/rules','/rules')],['test','rules','/rules/tests.json'])),
            ('Collector native configuration',lambda: fixture('otel-collector',[(OBS/'otel-collector/config.yml','/config.yml')],['validate','--config=/config.yml'],{'OTEL_QUEUE_CAPACITY_BYTES':self.services['otel-collector']['environment']['OTEL_QUEUE_CAPACITY_BYTES']})),
            ('Loki native configuration',lambda: fixture('loki',[(OBS/'loki/loki-config.yml','/config.yml')],['-config.file=/config.yml','-verify-config=true'])),
            ('Fluent Bit native dry-run',lambda: fixture('fluent-bit',[
                (OBS/'fluent-bit/fluent-bit.conf','/fluent-bit/etc/fluent-bit.conf'),
                (OBS/'fluent-bit/parsers.conf','/fluent-bit/etc/application-parsers.conf')],
                ['--dry-run','-c','/fluent-bit/etc/fluent-bit.conf'],{k:self.services['fluent-bit']['environment'][k]
                for k in ['DEPLOYMENT_ENVIRONMENT','FLUENT_BIT_LOKI_BUFFER_LIMIT','FLUENT_BIT_OPENSEARCH_BUFFER_LIMIT']}))]
        for label,fn in native:
            self.attempt(label,lambda fn=fn,label=label: (fn(),self.result('PASS',label)))
        tempo=self.api('grafana','/api/datasources/proxy/uid/tempo/status/config')
        self.check(isinstance(tempo,str) and 'block_retention: 72h' in tempo and '/var/tempo/blocks' in tempo,'Tempo loaded config and 72h retention via supported status API')

    def attempt(self,label,fn):
        try:
            fn()
        except Exception as error:
            if not isinstance(error,AssertionError):
                self.result('FAIL',label,type(error).__name__+'; payload/arguments withheld')

    def probe(self,service,path,expected,headers=None,body=None,method='GET',supplied=True):
        cid=self.run_id+'-'+str(len(self.probes))
        tid=uuid.uuid4().hex
        parent=uuid.uuid4().hex[:16]
        h={'traceparent':'00-'+tid+'-'+parent+'-01',**(headers or {})}
        if supplied:
            h['X-Correlation-ID']=cid
        status,response_headers,value=self.request(service,path,method,body,h)
        self.check(status==expected,'HTTP behavior: '+service+' probe '+str(len(self.probes)),'expected '+str(expected)+', observed '+str(status))
        effective=next((v for k,v in response_headers.items() if k.lower()=='x-correlation-id'),'')
        self.check(effective==cid if supplied else bool(re.fullmatch(r'[0-9a-f-]{36}',effective)),'correlation preserved/generated: '+service)
        self.probes.append({'service':service,'cid':effective,'trace':tid,'parent':parent,'status':expected})
        return value

    def telemetry(self):
        for name in APPS:
            self.check(self.api(name,'/actuator/health/readiness')['status']=='UP','service readiness: '+name)
            self.check(self.request(name,'/actuator/prometheus')[0]==403,'public metrics endpoint denied: '+name)
            self.check(self.request(name,'/actuator/env')[0] in [401,403,404], 'sensitive actuator endpoint protected: '+name)
            path={'user-api':'/internal/users/'+str(uuid.uuid4()),'learning-api':'/api/v1/learning/me','jwks-api':'/api/v1/jwks/user'}[name]
            self.probe(name,path,200 if name=='jwks-api' else 401,supplied=False)
            self.probe(name,path,200 if name=='jwks-api' else 401)
        self.authenticated()
        independent=[p for p in self.probes if not p.get('linked')]
        self.check(len({p['cid'] for p in independent})==len(independent)
            and len({p['trace'] for p in independent})==len(independent), 'request context isolation across independent live probes')
        # Poll for batched export and the log flush. No outages or configuration change.
        for probe in self.probes:
            self.attempt('stored logs/trace: '+probe['service'],lambda p=probe:self.verify_probe(p))

    def authenticated(self):
        file=self.args.credentials.resolve()
        if not file.is_file():
            self.result('NOT VERIFIED','authenticated regression','existing ignored credentials unavailable')
            return
        self.cmd('git','check-ignore','--quiet',str(file))
        account=json.loads(file.read_text(encoding='utf-8-sig'))
        account={k:account[k] for k in ['usernameOrEmail','password']}
        self.secrets += list(account.values())
        token=refresh=None
        try:
            body=self.probe('user-api','/auth/login',200,body=account,method='POST')
            token,refresh=body['data']['accessToken'],body['data']['refreshToken']
            self.secrets += [token,refresh]
            claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
            header=json.loads(base64.urlsafe_b64decode(token.split('.')[0]+'==='))
            self.secrets.append(claims['sub'])
            keys=self.api('jwks-api','/api/v1/jwks/user')['keys']
            self.check(header['kid'] in {k['kid'] for k in keys} and header['alg']=='RS256','access-token kid matches published RSA JWKS')
            self.check(claims['iss']==self.services['user-api']['environment']['JWT_ISSUER'],'access-token issuer matches configured contract')
            auth={'Authorization':'Bearer '+token}
            self.probe('learning-api','/api/v1/learning/me',200,headers=auth)
            userpath='/admin/users/'+claims['sub']
            roles=claims.get('roles') or claims.get('role') or []
            roles=roles if isinstance(roles,list) else [roles]
            if any(str(role) in ['2','ADMIN','ROLE_ADMIN'] for role in roles):
                self.probe('user-api',userpath,200,headers=auth)
                self.result('NOT VERIFIED','non-admin business authorization 403','existing account is admin; no account/role changes')
            else:
                self.probe('user-api',userpath,403,headers=auth)
                self.result('NOT VERIFIED','positive administrative User access','existing account lacks admin role; internal positive access is tested')
            self.probe('user-api','/internal/users/'+claims['sub'],401,headers=auth)
            self.probe('user-api','/actuator/prometheus',403,headers=auth)
            self.probe('learning-api','/api/v1/learning/me',401,headers={'Authorization':'Bearer invalid.phase6.signature'})
            linked=self.probe('learning-api','/api/v1/learning/internal-test/users/'+claims['sub'],200,headers=auth)
            self.check(linked.get('user',{}).get('id')==claims['sub'],'Learning to User actual internal JWT communication')
            for key in ['username','email']:
                value=linked.get('user',{}).get(key)
                if isinstance(value,str):
                    self.secrets.append(value)
            source=self.probes[-1]
            self.probes.append({**source,'service':'user-api','status':200,'linked':True})
            self.details['linked_trace']=source['trace']
            old=refresh
            status,_,body=self.request('user-api','/auth/refresh','POST',{'refreshToken':refresh})
            if status==200:
                token,refresh=body['data']['accessToken'],body['data']['refreshToken']
                self.secrets += [token,refresh]
            self.check(status==200 and refresh!=old,'refresh rotates this verification session')
            self.probe('learning-api','/api/v1/learning/me',200,headers={'Authorization':'Bearer '+token})
        finally:
            if refresh:
                status,_,_=self.request('user-api','/auth/logout','POST',{'refreshToken':refresh},{'Authorization':'Bearer '+token})
                self.check(status==200,'verification session logout cleanup')

    def wait(self,fn):
        end=time.monotonic()+45
        while True:
            value=fn()
            if value:
                return value
            if time.monotonic()>=end:
                raise TimeoutError('Bounded delivery deadline exceeded')
            time.sleep(2)

    def verify_probe(self,p):
        identity=APPS[p['service']]
        def logs():
            streams=self.loki('{job="springboot",service="'+identity+'"} | json | correlationId="'+p['cid']+'"')
            return [json.loads(line) for stream in streams for _,line in stream['values']
                    if json.loads(line).get('event')=='http.request.completed']
        rows=self.wait(logs)
        self.check(len(rows)==1,'one observed Loki HTTP completion: '+p['service'])
        r=rows[0]
        required=['@timestamp','level','service','environment','serviceVersion','event','correlationId','traceId','spanId',
                  'http.request.method','http.route','http.response.status_code','durationMs','error.category','outcome']
        self.check(all(key in r for key in required),'JSON schema fields: '+p['service'])
        self.check(datetime.fromisoformat(r['@timestamp'].replace('Z','+00:00')).tzinfo is not None,'UTC timestamp parses: '+p['service'])
        self.check(r['service']==identity and r['environment']==self.services[p['service']]['environment']['DEPLOYMENT_ENVIRONMENT']
                   and bool(r['serviceVersion']),'canonical log metadata: '+p['service'])
        self.check(type(r['http.response.status_code']) is int and r['http.response.status_code']==p['status']
            and type(r['durationMs']) in [int,float] and math.isfinite(r['durationMs']) and r['durationMs']>=0,'numeric final HTTP fields: '+p['service'])
        self.check(r['traceId']==p['trace'] and bool(re.fullmatch('[0-9a-f]{16}',r['spanId']))
            and p['cid']!=p['trace'],'independent correlation and W3C IDs: '+p['service'])
        self.check('?' not in r['http.route'] and not re.search(r'[0-9a-f]{8}-[0-9a-f-]{27}',r['http.route']), 'bounded route in logs: '+p['service'])
        query={'size':20,'query':{'bool':{'filter':[{'term':{'correlationId.keyword':p['cid']}},
            {'term':{'service.keyword':identity}},{'term':{'event.keyword':'http.request.completed'}}]}}}
        hits=self.wait(lambda:self.api('opensearch','/springboot-*-logs/_search',query)['hits']['hits'])
        self.check(len(hits)==1 and all(hits[0]['_source'].get(k)==r.get(k) for k in required),'same event identity/fields in Loki and OpenSearch: '+p['service'])
        path='/api/datasources/proxy/uid/tempo/api/traces/'+p['trace']
        def get_trace():
            status,_,data=self.request('grafana',path)
            return data if status==200 else None
        trace=self.wait(get_trace)
        spans=[]
        for batch in trace.get('batches',trace.get('resourceSpans',[])):
            attrs={a['key']:a['value'].get('stringValue') for a in batch['resource']['attributes']}
            self.check(attrs.get('deployment.environment.name')==r['environment'],'trace environment resource')
            for scope in batch.get('scopeSpans',batch.get('instrumentationLibrarySpans',[])):
                spans += [(attrs.get('service.name'),s) for s in scope['spans']]
        def hexid(value):
            return value if re.fullmatch('[0-9a-f]{16,32}',value) else base64.b64decode(value).hex()
        servers=[s for service,s in spans if service==identity and s['kind'] in [2,'SPAN_KIND_SERVER']]
        self.check(len(servers)==1 and hexid(servers[0]['spanId'])==r['spanId']
            and int(servers[0]['endTimeUnixNano'])>int(servers[0]['startTimeUnixNano']),'stored server span timing/log identity: '+p['service'])
        if p['trace']==self.details.get('linked_trace'):
            learning=next(s for service,s in spans if service=='learning-api' and s['kind'] in [2,'SPAN_KIND_SERVER'])
            user=next(s for service,s in spans if service=='user-learning' and s['kind'] in [2,'SPAN_KIND_SERVER'])
            client=next(s for service,s in spans if service=='learning-api' and s['kind'] in [3,'SPAN_KIND_CLIENT']
                and any(a['key']=='client.name' and a['value'].get('stringValue')=='user-api' for a in s.get('attributes',[])))
            self.check(hexid(learning['parentSpanId'])==p['parent'] and hexid(client['parentSpanId'])==hexid(learning['spanId'])
                and hexid(user['parentSpanId'])==hexid(client['spanId']),'Learning server to HTTP client to User parent chain')
        else:
            self.check(hexid(servers[0]['parentSpanId'])==p['parent'],'remote W3C parent continued: '+p['service'])
        raw=json.dumps(trace)+json.dumps(r)+json.dumps(hits)
        self.check(not any(s in raw for s in self.secrets if s) and not re.search(r'eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{16,}',raw),'tested credentials/tokens/identity absent from stored telemetry: '+p['service'])
        self.check(not any(key in json.dumps(trace).lower() for key in ['authorization','exception.message','exception.stacktrace','url.full','http.url']), 'sensitive span attribute names absent')
        self.details.setdefault('events',[]).append({'service':identity,'correlation':p['cid'],'trace':p['trace'],'span':r['spanId'],'status':p['status']})

    def metrics(self):
        targets=self.api('prometheus','/api/v1/targets')['data']['activeTargets']
        self.check(len(targets)==9 and all(t['health']=='up' and not t['lastError'] for t in targets),'all nine Prometheus targets UP without scrape errors')
        for service in APPS:
            raw=self.internal('http://'+service+':9091/actuator/prometheus')
            self.check(not any(secret in raw for secret in self.secrets if secret)
                and not re.search(r'(traceId|spanId|correlationId|username|email|userId|Authorization)=',raw),
                'no tested secrets or sensitive labels in live exposition: '+service)
        names=['http_server_requests_seconds_count','http_server_requests_seconds_bucket','jvm_memory_used_bytes',
            'jvm_gc_pause_seconds_count','jvm_threads_live_threads','process_cpu_usage','app_security_events_total']
        for name in names:
            values=self.query(name+'{job="springboot"}')
            self.check({x['metric']['service'] for x in values}==set(APPS.values()),'actual metric across three services: '+name)
        for q in [.5,.95,.99]:
            rows=self.query('histogram_quantile('+str(q)+',sum by (service,environment,le) (rate(http_server_requests_seconds_bucket[5m])))')
            self.check({x['metric']['service'] for x in rows if math.isfinite(float(x['value'][1]))}==set(APPS.values()),'finite HTTP histogram percentile '+str(q))
        for name in ['hikaricp_connections_active','hikaricp_connections_pending','hikaricp_connections_max','hikaricp_connections_acquire_seconds_count','hikaricp_connections_timeout_total']:
            self.check({x['metric']['service'] for x in self.query(name)}=={'learning-api','user-learning'},'database-only metric: '+name)
        for name in ['otelcol_exporter_queue_size','otelcol_exporter_queue_capacity','otelcol_exporter_send_failed_spans',
                     'fluentbit_output_errors_total','fluentbit_output_dropped_records_total']:
            self.check(bool(self.query(name)),'collected infrastructure metric: '+name)
        if self.details.get('linked_trace'):
            self.check(bool(self.query('http_client_requests_seconds_count{service="learning-api",uri="/internal/users/{id}",status="200"}')),'actual internal HTTP client metric')
        groups=self.api('prometheus','/api/v1/rules')['data']['groups']
        self.check(sum(len(g['rules']) for g in groups)==5 and all(r['health']=='ok' for g in groups for r in g['rules']),'five recording rules loaded and healthy')

    def grafana(self):
        expected=json.loads((OBS/'grafana/phase5-inventory.json').read_text())
        data_sources={d['uid'] for d in self.api('grafana','/api/datasources')}
        panel_results=[]
        for entry in expected:
            obj=self.api('grafana','/api/dashboards/uid/'+entry['uid'])
            d=obj['dashboard']
            source=json.loads(next(p for p in (OBS/'grafana/dashboards').glob('*.json') if json.loads(p.read_text())['uid']==entry['uid']).read_text())
            self.check(obj['meta']['provisioned'] and obj['meta']['folderUid']=='observability' and d['uid']==entry['uid'],'provisioned stable UID/folder: '+entry['uid'])
            self.check(d['templating']==source['templating'] and d['time']==source['time'] and d['refresh']=='30s','variables/time range: '+entry['uid'])
            self.check({x['name'] for x in d['templating']['list']} >= {'service','environment'},'service/environment variables: '+entry['uid'])
            for actual,p in zip(d['panels'],source['panels']):
                self.check(actual.get('fieldConfig')==p.get('fieldConfig') and actual.get('options')==p.get('options'), 'units/legends/no-data/options: '+entry['uid']+'/'+p['title'])
                for t in p.get('targets',[]):
                    uid=t.get('datasource',p.get('datasource',{})).get('uid')
                    self.check(uid in data_sources,'datasource resolves: '+p['title'])
                    expr=t['expr']
                    variants=[('all','.*','.*'),('filtered','learning-api',self.services['learning-api']['environment']['DEPLOYMENT_ENVIRONMENT'])]
                    for mode,service,env in variants:
                        q=expr
                        for key,value in {'${correlation:regex}':'.*','${trace:regex}':'.*','$__rate_interval':'5m',
                            '$__interval':'1m','$__range':'1h','$service':service,'$environment':env}.items():
                            q=q.replace(key,value)
                        start=time.perf_counter()
                        rows=self.query(q) if uid=='prometheus' else self.loki(q,limit=20)
                        if mode=='filtered':
                            self.check(all(x.get('metric',x.get('stream',{})).get('service','learning-api')=='learning-api' for x in rows),'service filter output: '+p['title'])
                        panel_results.append({'dashboard':entry['uid'],'panel':p['title'],'mode':mode,'series':len(rows),'ms':round((time.perf_counter()-start)*1000,2)})
        self.details['panel_queries']=panel_results
        source=json.loads((OBS/'grafana/provisioning/alerting/phase5.json').read_text())
        loaded=self.api('grafana','/api/v1/provisioning/alert-rules')
        expected_rules={r['uid']:r for r in source['groups'][0]['rules']}
        self.check(len(loaded)==21 and {r['uid'] for r in loaded}==set(expected_rules),'21 unique Grafana alert rules loaded')
        for r in loaded:
            wanted=expected_rules[r['uid']]
            exported=self.api('grafana','/api/v1/provisioning/alert-rules/'+r['uid']+'/export?format=json')['groups'][0]['rules'][0]
            queries_match=len(r['data'])==len(wanted['data']) and all(
                all(actual.get(k)==value for k,value in desired.items() if k!='model')
                and all(actual['model'].get(k)==value for k,value in desired['model'].items())
                for actual,desired in zip(r['data'],wanted['data']))
            self.check(all(r[k]==wanted[k] for k in ['for','noDataState','execErrState','labels'])
                and exported['keepFiringFor']==wanted['keepFiringFor'] and queries_match,'alert thresholds/labels/evaluation behavior: '+r['title'])
            ns=r['notification_settings']
            self.check(ns['mute_time_intervals']==['phase5-delivery-disabled'] and ns['group_by']==['service','environment','severity']
                and ns['repeat_interval']=='4h' and ns['group_wait']=='1m' and ns['group_interval']=='5m','muted grouped routing: '+r['title'])
        mute=self.api('grafana','/api/v1/provisioning/mute-timings')
        self.check(any(x['name']=='phase5-delivery-disabled' and x['time_intervals']==source['muteTimes'][0]['time_intervals'] for x in mute),'all-day notification mute remains active')
        groups=self.api('grafana','/api/prometheus/grafana/api/v1/rules')['data']['groups']
        rules=[r for g in groups for r in g['rules']]
        self.check(len(rules)==21 and all(r.get('health')=='ok' for r in rules),'all 21 Grafana rules evaluated successfully')
        self.details['alert_states']=[{'name':r['name'],'state':r['state'],'health':r['health']} for r in rules]
        template=copy.deepcopy(source['groups'][0]['rules'][4]['data'])
        for label,expr,wanted in [('normal','vector(0)',[0]),('breach','vector(1)',[1]),('no-data','vector(0)>1',[])]:
            template[0]['model']['expr']=expr
            template[1]['model']['conditions'][0]['evaluator']['params']=[.5]
            result=self.api('grafana','/api/v1/eval',{'condition':'B','data':template})
            values=[v for f in result['results']['B']['frames'] for col in f['data']['values'] for v in col]
            self.check(values==wanted,'non-persisted Grafana alert preview: '+label)
        template[0]['model']['expr']='invalid_phase6_promql{'
        status,_,body=self.request('grafana','/api/v1/eval','POST',{'condition':'B','data':template})
        self.check(status in [400,422] or bool(body.get('results',{}).get('A',{}).get('error')),'non-persisted execution-error preview')
        ds=self.api('grafana','/api/datasources/uid/loki')['jsonData']['derivedFields'][0]
        self.check(ds['datasourceUid']=='tempo' and ds['url']=='${__value.raw}','existing log-to-trace derived field retained')
        if self.details.get('linked_trace'):
            tid=self.details['linked_trace']
            rows=self.loki('{service=~"learning-api|user-learning"} | json | traceId="'+tid+'"')
            self.check(bool(rows),'trace-to-log query returns actual events')
            self.check(any(re.search(ds['matcherRegex'],line).group(1)==tid for s in rows for _,line in s['values'] if re.search(ds['matcherRegex'],line)),'derived log trace link extracts actual trace')
        for query in ['{ resource.service.name = "learning-api" }','{ duration > 1s }','{ status = error }']:
            self.check('traces' in self.api('grafana','/api/datasources/proxy/uid/tempo/api/search?'+urllib.parse.urlencode({'q':query,'limit':10})),'Tempo TraceQL exploration query accepted')
        self.check(self.request('grafana','/api/search',auth=False)[0]==401,'Grafana authentication required')

    def operations(self):
        for name,url in [('Collector','http://otel-collector:13133/'),('Tempo','http://tempo:3200/ready'),('Loki','http://loki:3100/ready')]:
            self.check(bool(self.internal(url)),name+' internal readiness')
        fb=json.loads(self.internal('http://fluent-bit:2020/api/v1/storage'))
        self.details['fluentbit_storage']=fb
        outputs=json.loads(self.internal('http://fluent-bit:2020/api/v1/metrics'))['output']
        self.check(all(v.get('retries_failed',0)==0 and v.get('dropped_records',0)==0 for v in outputs.values()),'Fluent Bit current-process exhausted retries/dropped records zero')
        self.details['fluentbit_outputs']=outputs
        for file,required in [('fluent-bit/fluent-bit.conf',['storage.sync      full','DB.sync           Full','DB.journal_mode   WAL','storage.type      filesystem','Retry_Limit       False']),
            ('otel-collector/config.yml',['storage: file_storage/queue','sizer: bytes','fsync: true','max_elapsed_time: 0s']),
            ('loki/loki-config.yml',['retention_period: 720h','retention_enabled: true','retention_delete_delay: 2h']),
            ('tempo/tempo.yml',['block_retention: 72h'])]:
            self.check(all(x in (OBS/file).read_text() for x in required),'persistent buffering/retention contract: '+file)
        indices=self.api('opensearch','/_cat/indices/springboot-*-logs?format=json&bytes=b')
        self.check(all(r['health']=='green' for r in indices),'OpenSearch application indices healthy')
        policy=self.api('opensearch','/_plugins/_ism/policies/springboot-dated-logs-retention')['policy']
        self.check(any(t.get('conditions',{}).get('min_index_age')=='30d' for state in policy['states'] for t in state.get('transitions',[])), 'OpenSearch 30-day lifecycle configured')
        managed=self.api('opensearch','/_plugins/_ism/explain/springboot-*-logs')
        dated=[r['index'] for r in indices if re.fullmatch(r'springboot-(user|learning|jwks)-\d{4}\.\d{2}\.\d{2}-logs',r['index'])]
        self.check(bool(dated) and all(managed[n].get('policy_id')=='springboot-dated-logs-retention' for n in dated),'dated OpenSearch indices actively assigned lifecycle')
        self.details['ism_states']={n:{k:managed[n].get(k) for k in ['policy_id','enabled','state','action','step','retry_info']} for n in dated}
        self.details['retention']={'dated_indices':len(dated),'legacy_unmanaged':[r['index'] for r in indices if r['index'] not in dated],
            'prometheus_flags':{k:v for k,v in self.api('prometheus','/api/v1/status/flags')['data'].items() if k in ['storage.tsdb.retention.time','storage.tsdb.retention.size','web.enable-admin-api']},
            'opensearch_repositories':list(self.api('opensearch','/_snapshot').keys())}
        stats=self.cmd('docker','stats','--no-stream','--format','{{json .}}',*[c['id'] for c in self.baseline['containers'] if c['project']=='springboot_project' and c['status']=='running'])
        self.details['docker_stats']=[json.loads(line) for line in stats.splitlines() if line]
        storage=self.api('opensearch','/_nodes/stats/fs,jvm,process')['nodes']
        self.details['opensearch_capacity']=[{'available_bytes':n['fs']['total']['available_in_bytes'],'total_bytes':n['fs']['total']['total_in_bytes'],
            'heap_used_percent':n['jvm']['mem']['heap_used_percent'],'cpu_percent':n['process']['cpu']['percent']} for n in storage.values()]
        expressions=['sum by (service) (jvm_memory_used_bytes{area="heap"}) / sum by (service) (jvm_memory_max_bytes{area="heap"}>0)',
            'process_cpu_usage{job="springboot"}','hikaricp_connections_active / (hikaricp_connections_max>0)',
            'hikaricp_connections_pending','otelcol_exporter_queue_size / (otelcol_exporter_queue_capacity>0)',
            'sum by (service) (rate(loki_distributor_bytes_received_total[5m]))','sum by (service) (rate(tempo_distributor_spans_received_total[5m]))']
        self.details['capacity_queries']={expr:self.query(expr) for expr in expressions}
        self.result('PASS','bounded resource/queue/ingestion snapshot captured','development observation only; no representative production load')
        self.check(all(c['logging']['Config'].get('max-size')=='10m' and c['logging']['Config'].get('max-file')=='3'
            for c in self.inventory() if c['project']=='springboot_project' and c['service'] in list(APPS)+['grafana','prometheus','loki','tempo','fluent-bit','otel-collector','opensearch','opensearch-dashboards']), 'effective 10m/3 Docker log rotation on 11 services')
        if observed_access_gap(self.services,(OBS/'loki/loki-config.yml').read_text(),(OBS/'tempo/tempo.yml').read_text()):
            self.result('FAIL','production telemetry access-control readiness','OpenSearch security disabled; Loki/Tempo/Collector/Prometheus trust internal plaintext network; loopback exposure is not production authentication')
        else:
            self.result('NOT VERIFIED','production telemetry access-control readiness','configuration changed; verify actual TLS/authentication/network enforcement before claiming readiness')

    def preservation(self):
        after={c['name']:c for c in self.inventory()}
        for c in self.baseline['containers']:
            self.check(c['name'] in after and all(after[c['name']][k]==c[k] for k in ['id','started','mounts','ports','networks','restarts']), 'container identity/start/mounts/ports unchanged: '+c['name'])
        self.check(set(self.baseline['volumes'])==set(self.cmd('docker','volume','ls','-q').split()), 'all original volumes retained, no new persistent volumes')
        self.check(self.fingerprints()==self.baseline['protected'],'environment/key/credential fingerprints unchanged')
        self.check(digest(json.loads(self.cmd(*self.compose,'config','--format','json')))==self.baseline['compose_digest'],'effective Compose configuration unchanged')
        for file,expected in self.baseline['config_files'].items():
            self.check(digest((ROOT/file).read_bytes())==expected,'deployed config file unchanged: '+file)
        for key,path in [('contacts','contact-points'),('policies','policies'),('alerts','alert-rules')]:
            self.check(digest(self.api('grafana','/api/v1/provisioning/'+path))==self.baseline[key+'_digest'],'Grafana '+key+' unchanged')
        self.check(digest(self.api('grafana','/api/datasources'))==self.baseline['datasources_digest'],'Grafana datasources unchanged')
        for uid,expected in self.baseline['dashboards'].items():
            self.check(digest(self.api('grafana','/api/dashboards/uid/'+uid)['dashboard'])==expected,'Grafana dashboard unchanged: '+uid)
        for path,expected in self.baseline['jwks'].items():
            self.check(digest(self.api('jwks-api',path))==expected,'public JWKS body unchanged: '+path)
        now=self.git()
        for name,old in self.baseline['git'].items():
            self.check(now[name]['head']==old['head'] and now[name]['branch']==old['branch'],'Git HEAD/branch unchanged: '+name)
            if name!='.':
                self.check(now[name]['status']==old['status'],'submodule worktree unchanged: '+name)
        self.details['final_git']=now

    def gaps(self):
        for label,why in [
            ('browser rendering and navigation','no browser automation available; API coverage only'),
            ('elapsed Pending/Firing/Resolved lifecycle','preview-only; isolated timed rule plan is in Phase 6B'),
            ('external notification delivery/recovery','forbidden in Phase 6A; mute remains active'),
            ('crash durability and queue/buffer overflow','no live failure injection; historical restart evidence is not crash proof'),
            ('physical retention deletion','policy/configuration checked, no expiration forced or deletion observed'),
            ('backup integrity and restore','no restore rehearsal performed; repository state inspected'),
            ('production load capacity','single bounded development snapshot, not representative load'),
            ('runtime async endpoints','no public production async fixture; Maven integration tests provide isolated coverage'),
            ('backend storage pressure alerting','reliable collected capacity metric/alert source absent')]:
            self.result('NOT VERIFIED',label,why)
        if observed_rotation_gap([(ROOT/m/'src/main/resources/logback-spring.xml').read_text() for m in MODULES],
                (OBS/'fluent-bit/fluent-bit.conf').read_text()):
            self.result('FAIL','lossless compressed-rollover collection','immediate gzip archive + exact-current-file tails can lose unread history while Fluent Bit is stopped; mitigation/test plan documented')
        else:
            self.result('NOT VERIFIED','lossless compressed-rollover collection','collection contract changed; require isolated rotation/restart evidence before claiming lossless behavior')
        self.result('NOT APPLICABLE','JWKS database pool','JWKS has no datasource')
        self.result('NOT APPLICABLE','Tempo service graphs/span-derived metrics','not enabled; no second metrics pipeline required')

    def run(self):
        self.snapshot()
        for label,fn in [('configuration',self.configuration),('telemetry',self.telemetry),('metrics',self.metrics),('Grafana',self.grafana),('operations',self.operations)]:
            self.attempt(label,fn)
        self.gaps()
        self.attempt('preservation',self.preservation)
        self.save()
        counts={s:sum(r['status']==s for r in self.rows) for s in ['PASS','FAIL','NOT VERIFIED','NOT APPLICABLE']}
        print('SUMMARY:',json.dumps(counts),'Evidence:',self.out.relative_to(ROOT),flush=True)
        return 1 if counts['FAIL'] else 2 if counts['NOT VERIFIED'] else 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose-file',action='append',help='Repeat for base/override files; project is fixed')
    parser.add_argument('--endpoint',action='append',default=[],metavar='SERVICE=URL',help='Loopback endpoint override')
    parser.add_argument('--timeout',type=int,default=10,choices=range(1,31))
    parser.add_argument('--credentials',type=Path,default=OBS/'local-test-credentials.json')
    parser.add_argument('--evidence-dir',type=Path,default=OBS/'phase6-evidence')
    args=parser.parse_args()
    try:
        return Validation(args).run()
    except Exception as error:
        print('FAIL: Phase 6A could not complete - '+type(error).__name__+'; details withheld to protect secrets',flush=True)
        return 1

if __name__=='__main__':
    sys.exit(main())
