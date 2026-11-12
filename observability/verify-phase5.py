"""Phase 5 validation. static/native/runtime/preflight do not deploy or notify."""
import argparse
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import sys
import time
import urllib.parse

sys.dont_write_bytecode = True
v = importlib.import_module('phase5-runtime')
ROOT, OBS = v.ROOT, v.ROOT / 'observability'
ART = OBS/'grafana/provisioning/alerting/phase5.json'

def check(ok, label):
    if not ok:
        raise AssertionError(label)
    print('PASS:', label, flush=True)

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def dashboards():
    return [load(p) for p in sorted((OBS/'grafana/dashboards').glob('*.json'))]

def alerts():
    return load(ART)['groups'][0]['rules']

def substitute(expr):
    for key, value in {'${correlation:regex}':'.*','${trace:regex}':'.*',
        '${service:regex}':'.*','${level:regex}':'.*',
        '$__rate_interval':'5m','$__interval':'1m','$__range':'1h',
        '$service':'.*','$environment':'.*','$level':'.*'}.items():
        expr=expr.replace(key,value)
    return expr

def static():
    ds= {'prometheus','loki','tempo'}
    all_dash=dashboards()
    check(len(all_dash)==9,'eight Phase 5 dashboards plus preserved application logs')
    check(len({d['uid'] for d in all_dash})==len(all_dash),'unique dashboard UIDs')
    for d in all_dash:
        check(d['schemaVersion']==41 and bool(d.get('time')),'dashboard schema/time: '+d['title'])
        ids=[p['id'] for p in d['panels']]
        check(len(ids)==len(set(ids)),'unique panel IDs: '+d['title'])
        if d['uid'].startswith('sb5-'):
            check({'environment','service'} <= {x['name'] for x in d['templating']['list']},'service/environment filters: '+d['title'])
        for p in d['panels']:
            if d['uid'].startswith('sb5-'):
                check(bool(p.get('description')),'panel description: '+p['title'])
            for t in p.get('targets',[]):
                check(t.get('datasource',p.get('datasource',{})).get('uid') in ds,'datasource: '+p['title'])
                expr=t.get('expr','')
                if 'histogram_quantile' in expr:
                    check('le' in expr and '_bucket' in expr,'histogram aggregation: '+p['title'])
    config=load(ART)
    rules=alerts()
    check(len({r['uid'] for r in rules})==len(rules),'unique alert UIDs')
    check(not any(k in config for k in ['deleteRules','deleteContactPoints','resetPolicies','policies']),
          'no resource deletion or policy tree replacement')
    check(config['muteTimes'][0]['time_intervals']==[{'times':[{'start_time':'00:00','end_time':'24:00'}]}],
          'all-day delivery mute')
    for r in rules:
        check(bool(re.fullmatch(r'[1-9][0-9]*m',r['for'])) and r['noDataState'] in ['OK','NoData']
              and r['execErrState']=='Error' and r['keepFiringFor']=='1m','pending/no-data/error/recovery: '+r['title'])
        check(r['labels']['severity'] in ['warning','critical'] and r['labels']['environment'] in ['development','test','staging','production'],
              'severity/environment: '+r['title'])
        ns=r['notification_settings']
        check(ns['mute_time_intervals']==['phase5-delivery-disabled'] and ns['group_by']==['service','environment','severity']
              and ns['repeat_interval']=='4h','safe grouped routing: '+r['title'])
        check(r['data'][1]['model']['conditions'][0]['evaluator']['params'][0]>=0,'threshold: '+r['title'])
    provider=(OBS/'grafana/provisioning/dashboards/application-logs.yml').read_text()
    check('disableDeletion: true' in provider and 'folderUid: observability' in provider and 'path: /etc/grafana/dashboards' in provider,
          'existing nondeleting provider/folder preserved')
    raw='\n'.join(p.read_text() for p in (OBS/'grafana/dashboards').glob('*.json'))+ART.read_text()
    check(not re.search(r'-----BEGIN .*PRIVATE KEY|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.|https?://[^/\s"]+:[^/\s"]+@',raw),
          'no private keys, JWT-shaped values or URL credentials in artifacts')
    check(not re.search(r'(username|email|userId|Authorization)\s*(?:=|:)',raw,re.I),
          'no sensitive query dimensions')
    recorded=load(OBS/'prometheus/rules/phase5.json')['groups'][0]['rules']
    check(len({r['record'] for r in recorded})==5,'five unique recording rules')

def native():
    check(v.command(*v.COMPOSE,'config','--quiet')=='','Compose syntax (base + existing debug override)')
    output=v.command(*v.COMPOSE,'run','--rm','--no-deps','--entrypoint','promtool','prometheus',
                     'check','config','/etc/prometheus/prometheus.yml')
    check('SUCCESS' in output,'installed Prometheus promtool config/recording rules')
    output=v.command('docker','run','--rm','--network','none','--read-only','--tmpfs',
                     '/tmp:rw,noexec,nosuid,nodev,size=32m','-v',str(OBS/'prometheus/rules')+':/rules:ro',
                     '--entrypoint','promtool','prom/prometheus:v3.13.5','test','rules','/rules/tests.json')
    check('SUCCESS' in output,'recording-rule synthetic tests: traffic, absent errors and zero traffic')

def preflight():
    base=load(OBS/'phase5-baseline.log')
    check(base['grafana_health']['version']=='12.2.0' and base['prometheus_version']['data']['version']=='3.13.5',
          'actual baseline Grafana/Prometheus versions')
    check({x['uid'] for x in base['datasources']}=={'prometheus','loki','tempo'},'baseline datasource UIDs')
    new_uids={d['uid'] for d in dashboards() if d['uid'].startswith('sb5-')}
    check(not new_uids.intersection(d['uid'] for d in base['dashboards']),'no new dashboard UID collision in baseline')
    check(not {r['uid'] for r in alerts()}.intersection(r['uid'] for r in base['alerts']),'no alert UID collision in baseline')
    m=v.model()['services']
    for service,cfg in m.items():
        for p in cfg.get('ports',[]):
            check(p.get('host_ip')=='127.0.0.1','loopback-only published port: '+service)
    for name in ['otel-collector','tempo','fluent-bit']:
        check(not m[name].get('ports'),'internal-only endpoints: '+name)
    for name in ['user-api','learning-api','jwks-api']:
        check(not any(p['target']==9091 for p in m[name]['ports']),'private Actuator scrape listener: '+name)
        check(str(m[name]['environment']['MANAGEMENT_TRACING_SAMPLING_PROBABILITY'])=='0.1','10% tracing sampling: '+name)
    env=m['grafana']['environment']
    check(env['PHASE5_ALERT_RECEIVER'] in {x['name'] for x in base['contacts']} | {base['policies']['receiver']},'rule-local receiver exists')
    targets=load(OBS/'prometheus/targets/applications.json')
    check({t['labels']['environment'] for t in targets}=={m['user-api']['environment']['DEPLOYMENT_ENVIRONMENT']},
          'target environment agrees with actual Compose environment')
    actual={c['service']:c for c in v.inventory() if c['project']=='springboot_project'}
    for name in ['grafana','prometheus','otel-collector']:
        expected={x['target']:x.get('source') for x in m[name].get('volumes',[]) if x['type']=='volume'}
        for dest,source in expected.items():
            check(any(x['Destination']==dest and x.get('Name')=='springboot_project_'+source for x in actual[name]['mounts']),
                  'existing persistent volume preserved: '+name+' '+dest)

def runtime():
    evidence={}
    check(v.api('/api/health')['database']=='ok','Grafana database/readiness')
    check('Ready' in v.api('/-/ready','prometheus'),'Prometheus readiness')
    check('ready' in v.api('/ready','loki'),'Loki readiness')
    check('ready' in v.api('/api/datasources/proxy/uid/tempo/ready'),'Tempo readiness')
    base=load(OBS/'phase5-baseline.log')
    current=v.api('/api/datasources')
    check({(d['uid'],d['type'],d['url']) for d in current}=={(d['uid'],d['type'],d['url']) for d in base['datasources']},'all existing datasource identities/URLs retained')
    for d in current:
        if d['uid']=='tempo':
            check('ready' in v.api('/api/datasources/proxy/uid/tempo/ready'),'Tempo readiness through datasource proxy (health API not implemented)')
        else:
            check(v.api('/api/datasources/uid/'+d['uid']+'/health')['status']=='OK','datasource health: '+d['uid'])
    check(v.api('/api/v1/provisioning/policies')==base['policies'],'existing notification policy unchanged')
    check(v.api('/api/v1/provisioning/contact-points')==base['contacts'],'existing contact points unchanged')
    mute=next(x for x in v.api('/api/v1/provisioning/mute-timings') if x['name']=='phase5-delivery-disabled')
    check(mute['time_intervals']==[{'times':[{'start_time':'00:00','end_time':'24:00'}]}],
          'all-day notification mute loaded by Grafana')
    search=v.api('/api/search?type=dash-db&limit=5000')
    expected={d['uid'] for d in dashboards()}
    check(expected <= {d['uid'] for d in search} and len(search)==len(expected),'nine dashboards visible without duplicates')
    results=[]
    empty=[]
    for d in dashboards():
        actual=v.api('/api/dashboards/uid/'+d['uid'])
        check(actual['meta']['provisioned'],'file provisioning active: '+d['title'])
        intended=[t.get('expr') for p in d['panels'] for t in p.get('targets',[])]
        deployed=[t.get('expr') for p in actual['dashboard']['panels'] for t in p.get('targets',[])]
        check(intended==deployed,'loaded panel expressions match files: '+d['title'])
        for p in d['panels']:
            for t in p.get('targets',[]):
                uid=t.get('datasource',p.get('datasource',{})).get('uid')
                check(uid in {x['uid'] for x in current},'live panel datasource: '+p['title'])
                if 'expr' not in t:
                    continue
                expr=substitute(t['expr'])
                try:
                    if uid=='prometheus':
                        result=v.query(expr)
                    else:
                        qs=urllib.parse.urlencode({'query':expr,'start':str(time.time_ns()-3600*10**9),
                                'end':str(time.time_ns()),'step':'60','limit':'20'})
                        result=v.api('/loki/api/v1/query_range?'+qs,'loki')['data']['result']
                except Exception as e:
                    print('FAILED expression:',d['title'],p['title'],expr,flush=True)
                    if hasattr(e,'read'):
                        print(e.read().decode()[:1200])
                    raise
                results.append({'dashboard':d['uid'],'panel':p['title'],'series':len(result)})
                if not result:
                    empty.append(p['title'])
    targets=v.api('/api/v1/targets','prometheus')['data']['activeTargets']
    check(len(targets)==9 and all(t['health']=='up' for t in targets),'all three APIs and six infrastructure targets UP')
    evidence['targets']=[{'service':t['labels']['service'],'health':t['health']} for t in targets]
    metric_names={x['metric']['__name__'] for x in v.query('count by (__name__) ({job=~"springboot|observability"})')}
    for r in alerts():
        expr=r['data'][0]['model']['expr']
        v.query(expr)
        check(True,'live alert PromQL accepted: '+r['title'])
    loaded=v.api('/api/v1/provisioning/alert-rules')
    check({r['uid'] for r in alerts()}=={r['uid'] for r in loaded},'all alert rules loaded without duplicates')
    intended_rules={r['uid']:r for r in alerts()}
    for r in loaded:
        check(r['notification_settings']['mute_time_intervals']==['phase5-delivery-disabled'],'runtime notification mute: '+r['title'])
        source=intended_rules[r['uid']]
        check(r['data'][0]['model']['expr']==source['data'][0]['model']['expr']
              and r['for']==source['for'] and r['noDataState']==source['noDataState']
              and r['execErrState']==source['execErrState'], 'loaded alert expression and behavior match files: '+r['title'])
    prom_rules=v.api('/api/v1/rules','prometheus')['data']['groups']
    check(sum(len(g['rules']) for g in prom_rules)==5 and all(r['health']=='ok' for g in prom_rules for r in g['rules']),
          'five recording rules loaded and healthy')
    evaluation=v.api('/api/prometheus/grafana/api/v1/rules')
    live_rules=[r for g in evaluation['data']['groups'] for r in g['rules'] if r['name'] in {r['title'] for r in alerts()}]
    check(len(live_rules)==len(alerts()) and all(r.get('health')=='ok' for r in live_rules),'all Grafana alerts evaluated with healthy queries')
    evidence['alert_states']=[{'name':r['name'],'state':r['state'],'health':r['health']} for r in live_rules]
    before={c['name']:c for c in base['containers']}
    after={c['name']:c for c in v.inventory()}
    for name,c in before.items():
        check(name in after,'baseline container still present: '+name)
        if c['project']!='springboot_project' or c['service'] not in ['grafana','prometheus','otel-collector']:
            check(c['id']==after[name]['id'] and c['started']==after[name]['started'], 'container identity/start unchanged: '+name)
        if c['project']=='springboot_project':
            oldvol={x['Name'] for x in c['mounts'] if x['Type']=='volume'}
            newvol={x['Name'] for x in after[name]['mounts'] if x['Type']=='volume'}
            check(oldvol==newvol,'persistent mounts retained: '+name)
    check(set(base['volumes']) <= set(v.command('docker','volume','ls','-q').split()),'all baseline volumes retained')
    evidence.update(panel_queries=results,empty_panels=empty,metric_names=sorted(metric_names))
    (OBS/'phase5-runtime-evidence.log').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print('Validated',len(results),'panel queries;',len(empty),'empty results (documented in local evidence).')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['static','native','preflight','runtime'])
    args=parser.parse_args()
    globals()[args.mode]()
