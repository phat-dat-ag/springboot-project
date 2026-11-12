"""Validate inactive candidate structure or report missing PKI; never deploys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'observability/secure-production'
REQUIRED=['OBS_TLS_DIR','OS_SECURITY_CONFIG_DIR','OS_ADMIN_DN','OS_NODE_DN','OS_DASHBOARDS_PASSWORD',
          'OBS_GRAFANA_ROOT_URL','GRAFANA_METRICS_PASSWORD','GRAFANA_TLS_CA_PEM','GRAFANA_TLS_CLIENT_CERT_PEM','GRAFANA_TLS_CLIENT_KEY_PEM']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structure',action='store_true',help='Use synthetic interpolation values; does NOT verify TLS')
    args=parser.parse_args()
    env=os.environ.copy()
    if args.structure:
        env.update({k:'STRUCTURE_VALIDATION_ONLY' for k in REQUIRED})
        env.update(OBS_TLS_DIR=str(FOLDER),OS_SECURITY_CONFIG_DIR=str(FOLDER/'security-config.example'),OBS_GRAFANA_ROOT_URL='https://grafana.invalid')
    else:
        missing=[k for k in REQUIRED if not env.get(k)]
        if missing:
            print('NOT VERIFIED: missing authorized prerequisites:',', '.join(missing))
            return 2
        print('NOT VERIFIED: supplied PKI still requires isolated native startup, negative auth and TLS handshake tests; no activation performed')
    cmd=['docker','compose','-p','springboot_project','--env-file','.env','-f','docker-compose.yml',
         '-f','observability/secure-production/compose.json','config','--format','json']
    result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
    if result.returncode:
        print('FAIL: candidate Compose validation; expanded output withheld')
        return 1
    model=json.loads(result.stdout)
    for name,service in model['services'].items():
        assert all(p.get('host_ip')=='127.0.0.1' for p in service.get('ports',[]))
    for app in ['user-api','learning-api','jwks-api']:
        cfg=model['services'][app]['environment']
        assert cfg['APP_METRICS_LISTENER_ADDRESS']=='127.0.0.1'
        assert cfg['MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_ENDPOINT'].startswith('https://')
        assert cfg['MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_SSL_BUNDLE']=='telemetry'
    assert model['services']['opensearch']['environment']['DISABLE_SECURITY_PLUGIN']=='false'
    proxies=[n for n in model['services'] if n.endswith('-metrics-tls')]
    assert len(proxies)==5 and all(not model['services'][n].get('ports') for n in proxies)
    for file in FOLDER.glob('*metrics-tls.conf'):
        raw=file.read_text()
        assert 'ssl_verify_client on;' in raw and 'return 403' in raw
    collector=(FOLDER/'collector.yml').read_text()
    assert 'insecure: false' in collector and 'client_ca_file:' in collector
    fb=(FOLDER/'fluent-bit.conf').read_text()
    assert fb.count('tls.verify On')==4 and fb.count('tls.verify_hostname On')==4
    for file in (FOLDER/'datasources').glob('*.yml'):
        assert 'tlsSkipVerify: false' in file.read_text()
    rules=json.loads((FOLDER/'alerting.json').read_text())['groups'][0]['rules']
    assert len(rules)==21 and all(r['notification_settings']['mute_time_intervals']==['phase5-delivery-disabled'] for r in rules)
    print('PASS: secure candidate Compose, loopback exposure, native TLS references, metrics proxies, datasource UIDs and 21 muted rules structurally validate')
    print('NOT VERIFIED: runtime TLS/authentication/authorization, certificate validity, OpenSearch bootstrap, isolated migration and restore')
    return 0 if args.structure else 2

if __name__=='__main__':
    sys.exit(main())
