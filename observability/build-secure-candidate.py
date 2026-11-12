"""Render inactive secure-production configuration. Never generates credentials.

No containers are started. This candidate requires PKI, isolated verification and
an approved migration before use with existing persistent data.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OBS=ROOT/'observability'
OUT=OBS/'secure-production'
PROXY='nginx@sha256:73c75df4075c918f91017fdda46ad81e55e5af77ba3a64ca3d5014bd9244fe7f'

def write(name,value):
    p=OUT/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2)+'\n' if isinstance(value,(dict,list)) else value,encoding='utf-8')

def bind(source,target):
    return {'type':'bind','source':source,'target':target,'read_only':True,'bind':{'create_host_path':False}}

def main():
    tlsroot='${OBS_TLS_DIR:?Supply existing authorized per-service certificates; no generation is performed}'
    services={}
    roles=['user-api','learning-api','jwks-api','fluent-bit','otel-collector','loki','tempo','prometheus','grafana','opensearch','opensearch-dashboards']
    for name in roles:
        services[name]={'volumes':[bind(tlsroot+'/'+name,'/run/tls')]}
    for app in ['user-api','learning-api','jwks-api']:
        services[app]['environment']={
            'DEPLOYMENT_ENVIRONMENT':'production',
            'APP_METRICS_LISTENER_ADDRESS':'127.0.0.1',
            'MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_ENDPOINT':'https://otel-collector:4318/v1/traces',
            'MANAGEMENT_OPENTELEMETRY_TRACING_EXPORT_OTLP_SSL_BUNDLE':'telemetry',
            'SPRING_SSL_BUNDLE_PEM_TELEMETRY_TRUSTSTORE_CERTIFICATE':'file:/run/tls/ca.pem',
            'SPRING_SSL_BUNDLE_PEM_TELEMETRY_KEYSTORE_CERTIFICATE':'file:/run/tls/client.crt',
            'SPRING_SSL_BUNDLE_PEM_TELEMETRY_KEYSTORE_PRIVATE_KEY':'file:/run/tls/client.key'}
    # Only local namespace plaintext remains; remote scrapers must use the mTLS proxy.
    for name,upstream,port,path in [(a,9091,9092,'/actuator/prometheus') for a in ['user-api','learning-api','jwks-api']]+[
            ('fluent-bit',2020,2021,'/api/v1/metrics/prometheus'),('otel-collector',8888,8889,'/metrics')]:
        proxy=name+'-metrics-tls'
        services[proxy]={'image':PROXY,'user':'10001:10001','network_mode':'service:'+name,
            'depends_on':{name:{'condition':'service_started'}},'restart':'unless-stopped',
            'read_only':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
            'mem_limit':'32m','cpus':0.25,'pids_limit':32,
            'tmpfs':['/tmp:rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001'],
            'entrypoint':['nginx'],'command':['-c','/etc/nginx/nginx.conf','-g','daemon off;'],
            'volumes':[bind(tlsroot+'/'+name,'/run/tls'),bind('./observability/secure-production/'+proxy+'.conf','/etc/nginx/nginx.conf')]}
        write(proxy+'.conf','''pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 128; }
http {
  access_log off;
  client_body_temp_path /tmp/client;
  proxy_temp_path /tmp/proxy;
  server {
    listen '''+str(port)+''' ssl;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_certificate /run/tls/server.crt;
    ssl_certificate_key /run/tls/server.key;
    ssl_client_certificate /run/tls/ca.pem;
    ssl_verify_client on;
    location = '''+path+''' {
      limit_except GET { deny all; }
      proxy_pass http://127.0.0.1:'''+str(upstream)+''';
    }
    location / { return 403; }
  }
}
''')
    fb=(OBS/'fluent-bit/fluent-bit.conf').read_text().replace('HTTP_Listen       0.0.0.0','HTTP_Listen       127.0.0.1')
    fb=fb.replace('    Name              loki\n','    Name              loki\n    tls On\n    tls.verify On\n    tls.verify_hostname On\n    tls.ca_file /run/tls/ca.pem\n    tls.crt_file /run/tls/client.crt\n    tls.key_file /run/tls/client.key\n')
    fb=fb.replace('    Name                opensearch\n','    Name                opensearch\n    tls On\n    tls.verify On\n    tls.verify_hostname On\n    tls.ca_file /run/tls/ca.pem\n    tls.crt_file /run/tls/client.crt\n    tls.key_file /run/tls/client.key\n')
    write('fluent-bit.conf',fb)
    services['fluent-bit']['volumes'] += [bind('./observability/secure-production/fluent-bit.conf','/fluent-bit/etc/fluent-bit.conf')]
    services['fluent-bit']['environment']={'DEPLOYMENT_ENVIRONMENT':'production'}
    collector=(OBS/'otel-collector/config.yml').read_text()
    collector=collector.replace('        endpoint: 0.0.0.0:4318','''        endpoint: 0.0.0.0:4318
        tls:
          cert_file: /run/tls/server.crt
          key_file: /run/tls/server.key
          client_ca_file: /run/tls/ca.pem''')
    collector=collector.replace('      insecure: true','''      insecure: false
      ca_file: /run/tls/ca.pem
      cert_file: /run/tls/client.crt
      key_file: /run/tls/client.key''')
    collector=collector.replace('host: 0.0.0.0','host: 127.0.0.1').replace('endpoint: 0.0.0.0:13133','endpoint: 127.0.0.1:13133')
    write('collector.yml',collector)
    services['otel-collector']['volumes'] += [bind('./observability/secure-production/collector.yml','/etc/otelcol/config.yml')]
    server_tls='''  http_tls_config:
    cert_file: /run/tls/server.crt
    key_file: /run/tls/server.key
    client_ca_file: /run/tls/ca.pem
    client_auth_type: RequireAndVerifyClientCert
  grpc_listen_address: 127.0.0.1
'''
    for name,source,target in [('loki','loki/loki-config.yml','/etc/loki/loki-config.yml'),('tempo','tempo/tempo.yml','/etc/tempo/tempo.yml')]:
        raw=(OBS/source).read_text().replace('server:\n','server:\n'+server_tls,1)
        if name=='tempo':
            raw=raw.replace('ingester:\n','ingester:\n  lifecycler:\n    address: 127.0.0.1\n',1)
            raw+='\nmemberlist:\n  bind_addr: [127.0.0.1]\n  advertise_addr: 127.0.0.1\n'
            raw=raw.replace('          endpoint: 0.0.0.0:4317','''          endpoint: 0.0.0.0:4317
          tls:
            cert_file: /run/tls/server.crt
            key_file: /run/tls/server.key
            client_ca_file: /run/tls/ca.pem''')
        write(name+'.yml',raw)
        services[name]['volumes'] += [bind('./observability/secure-production/'+name+'.yml',target)]
    client_tls={'ca_file':'/run/tls/ca.pem','cert_file':'/run/tls/client.crt','key_file':'/run/tls/client.key','insecure_skip_verify':False}
    jobs=[]
    for job,file in [('springboot','applications.json'),('observability','infrastructure.json')]:
        cfg={'job_name':job,'scheme':'https','scrape_interval':'15s','scrape_timeout':'5s','sample_limit':20000,
            'tls_config':client_tls,'file_sd_configs':[{'files':['/etc/prometheus/targets/'+file]}],
            'relabel_configs':[{'source_labels':['__address__'],'target_label':'instance'},
                {'source_labels':['__address__'],'regex':'(.+):9091','target_label':'__address__','replacement':'${1}:9092'},
                {'source_labels':['__address__'],'regex':'fluent-bit:2020','target_label':'__address__','replacement':'fluent-bit:2021'},
                {'source_labels':['__address__'],'regex':'otel-collector:8888','target_label':'__address__','replacement':'otel-collector:8889'},
                {'source_labels':['service'],'regex':'fluent-bit','target_label':'__metrics_path__','replacement':'/api/v1/metrics/prometheus'}]}
        if job=='springboot':
            cfg.update(metrics_path='/actuator/prometheus',honor_labels=True,label_limit=20)
        else:
            cfg['relabel_configs'].insert(0,{'source_labels':['service'],'regex':'grafana','action':'drop'})
        jobs.append(cfg)
    grafana_job={'job_name':'grafana-secure','scheme':'https','tls_config':client_tls,
        'static_configs':[{'targets':['grafana:3000'],'labels':{'service':'grafana','environment':'${DEPLOYMENT_ENVIRONMENT:-development}'}}],
        'basic_auth':{'username':'prometheus','password_file':'/run/tls/grafana-metrics-password'},
        'relabel_configs':[{'target_label':'job','replacement':'observability'}]}
    # Prometheus does not interpolate environment variables in files: operator must render environment before activation.
    grafana_job['static_configs'][0]['labels']['environment']='production'
    jobs.append(grafana_job)
    write('prometheus.json',{'global':{'scrape_interval':'15s','evaluation_interval':'15s'},
        'rule_files':['/etc/prometheus/rules/phase5.json'],'scrape_configs':jobs})
    write('prometheus-web.json',{'tls_server_config':{'cert_file':'/run/tls/server.crt','key_file':'/run/tls/server.key',
        'client_auth_type':'RequireAndVerifyClientCert','client_ca_file':'/run/tls/ca.pem','min_version':'TLS12'}})
    write('prometheus-client.json',{'tls_config':client_tls})
    services['prometheus'].update(command=['--config.file=/etc/prometheus/prometheus.yml','--storage.tsdb.path=/prometheus',
        '--storage.tsdb.retention.time=15d','--storage.tsdb.retention.size=2GB','--web.listen-address=0.0.0.0:9090',
        '--web.config.file=/etc/prometheus/web.json'],
        healthcheck={'test':['CMD','promtool','check','ready','--url=https://prometheus:9090',
            '--http.config.file=/etc/prometheus/client.json']})
    services['prometheus']['volumes'] += [bind('./observability/secure-production/prometheus.json','/etc/prometheus/prometheus.yml'),
        bind('./observability/secure-production/prometheus-web.json','/etc/prometheus/web.json'),
        bind('./observability/secure-production/prometheus-client.json','/etc/prometheus/client.json'),
        bind('./observability/secure-production/targets','/etc/prometheus/targets')]
    for file in ['applications.json','infrastructure.json']:
        rows=json.loads((OBS/'prometheus/targets'/file).read_text())
        for row in rows:
            row['labels']['environment']='production'
        write('targets/'+file,rows)
    for name in ['loki','prometheus','tempo']:
        # Keep the original UID and log/trace integration. YAML env interpolation remains Grafana-owned.
        raw=(OBS/'grafana/provisioning/datasources'/ (name+'.yml')).read_text().replace('url: http:','url: https:')
        raw=raw.replace('    jsonData:\n','''    secureJsonData:
      tlsCACert: $GRAFANA_TLS_CA_PEM
      tlsClientCert: $GRAFANA_TLS_CLIENT_CERT_PEM
      tlsClientKey: $GRAFANA_TLS_CLIENT_KEY_PEM
    jsonData:
      tlsAuth: true
      tlsAuthWithCACert: true
      tlsSkipVerify: false
''')
        write('datasources/'+name+'.yml',raw)
        services['grafana']['volumes'] += [bind('./observability/secure-production/datasources/'+name+'.yml','/etc/grafana/provisioning/datasources/'+name+'.yml')]
    services['grafana']['environment']={'GF_SERVER_PROTOCOL':'https','GF_SERVER_CERT_FILE':'/run/tls/server.crt',
        'GF_SERVER_CERT_KEY':'/run/tls/server.key','GF_SECURITY_COOKIE_SECURE':'true','GF_METRICS_BASIC_AUTH_USERNAME':'prometheus',
        'GF_SERVER_ROOT_URL':'${OBS_GRAFANA_ROOT_URL:?Supply approved HTTPS Grafana URL}',
        'GF_METRICS_BASIC_AUTH_PASSWORD':'${GRAFANA_METRICS_PASSWORD:?Supply authorized metrics password}',
        **{k:'${'+k+':?Supply authorized PEM through ignored environment}' for k in ['GRAFANA_TLS_CA_PEM','GRAFANA_TLS_CLIENT_CERT_PEM','GRAFANA_TLS_CLIENT_KEY_PEM']}}
    alerting=json.loads((OBS/'grafana/provisioning/alerting/phase5.json').read_text())
    for group in alerting['groups']:
        for rule in group['rules']:
            rule['labels']['environment']='production'
    write('alerting.json',alerting)
    services['grafana']['volumes'] += [bind('./observability/secure-production/alerting.json','/etc/grafana/provisioning/alerting/phase5.json')]
    write('opensearch.yml','''cluster.name: springboot-observability-secure
network.host: 0.0.0.0
discovery.type: single-node
plugins.security.disabled: false
plugins.security.allow_default_init_securityindex: false
plugins.security.ssl.transport.pemcert_filepath: telemetry-tls/server.crt
plugins.security.ssl.transport.pemkey_filepath: telemetry-tls/server.key
plugins.security.ssl.transport.pemtrustedcas_filepath: telemetry-tls/ca.pem
plugins.security.ssl.transport.enforce_hostname_verification: true
plugins.security.ssl.http.enabled: true
plugins.security.ssl.http.pemcert_filepath: telemetry-tls/server.crt
plugins.security.ssl.http.pemkey_filepath: telemetry-tls/server.key
plugins.security.ssl.http.pemtrustedcas_filepath: telemetry-tls/ca.pem
plugins.security.ssl.http.clientauth_mode: REQUIRE
plugins.security.authcz.admin_dn:
  - ${OS_ADMIN_DN}
plugins.security.nodes_dn:
  - ${OS_NODE_DN}
''')
    services['opensearch']['environment']={'DISABLE_SECURITY_PLUGIN':'false','DISABLE_INSTALL_DEMO_CONFIG':'true',
        'OS_ADMIN_DN':'${OS_ADMIN_DN:?Supply approved admin certificate DN}',
        'OS_NODE_DN':'${OS_NODE_DN:?Supply approved node certificate DN}'}
    services['opensearch']['volumes'] += [bind(tlsroot+'/opensearch','/usr/share/opensearch/config/telemetry-tls'),
        bind('./observability/secure-production/opensearch.yml','/usr/share/opensearch/config/opensearch.yml'),
        bind('${OS_SECURITY_CONFIG_DIR:?Supply reviewed externally rendered security YAML files}','/usr/share/opensearch/config/opensearch-security')]
    services['opensearch']['healthcheck']={'test':['CMD-SHELL',
        "curl --fail --silent --cacert /run/tls/ca.pem --cert /run/tls/client.crt --key /run/tls/client.key 'https://opensearch:9200/_cluster/health?wait_for_status=yellow&timeout=5s' >/dev/null"]}
    write('opensearch_dashboards.yml','''server.host: 0.0.0.0
server.ssl.enabled: true
server.ssl.certificate: /run/tls/server.crt
server.ssl.key: /run/tls/server.key
opensearch.hosts: ["https://opensearch:9200"]
opensearch.ssl.verificationMode: full
opensearch.ssl.certificateAuthorities: ["/run/tls/ca.pem"]
opensearch.ssl.certificate: /run/tls/client.crt
opensearch.ssl.key: /run/tls/client.key
opensearch.username: dashboards_svc
opensearch.password: ${OS_DASHBOARDS_PASSWORD}
opensearch_security.cookie.secure: true
''')
    services['opensearch-dashboards']['environment']={'OPENSEARCH_HOSTS':'["https://opensearch:9200"]',
        'DISABLE_SECURITY_DASHBOARDS_PLUGIN':'false','OS_DASHBOARDS_PASSWORD':'${OS_DASHBOARDS_PASSWORD:?Supply existing authorized server credential}'}
    services['opensearch-dashboards']['volumes'] += [bind('./observability/secure-production/opensearch_dashboards.yml','/usr/share/opensearch-dashboards/config/opensearch_dashboards.yml')]
    services['opensearch-dashboards']['healthcheck']={'test':['CMD-SHELL',
        'curl --fail --silent --max-time 5 --cacert /run/tls/ca.pem https://opensearch-dashboards:5601/ >/dev/null']}
    # These tags don't activate anything; loading this explicit override still requires every secret prerequisite.
    write('compose.json',{'services':services})
    write('security-config.example/config.yml',{'_meta':{'type':'config','config_version':2},'config':{'dynamic':{
        'http':{'anonymous_auth_enabled':False},'authc':{
            'basic_internal':{'http_enabled':True,'transport_enabled':False,'order':0,
                'http_authenticator':{'type':'basic','challenge':False},'authentication_backend':{'type':'intern'}},
            'client_certificate':{'http_enabled':True,'transport_enabled':False,'order':1,
                'http_authenticator':{'type':'clientcert','config':{'username_attribute':'cn'},'challenge':False},
                'authentication_backend':{'type':'noop'}}}}}})
    write('security-config.example/roles.yml',{'_meta':{'type':'roles','config_version':2},
        'telemetry_writer':{'cluster_permissions':['cluster_composite_ops'],
            'index_permissions':[{'index_patterns':['springboot-user-20*-logs','springboot-learning-20*-logs','springboot-jwks-20*-logs'],
                'allowed_actions':['indices:data/write/bulk*','indices:data/write/index*','indices:data/write/create*','indices:admin/create','indices:admin/mapping/put']}]},
        'telemetry_health':{'cluster_permissions':['cluster:monitor/health'],'index_permissions':[]}})
    write('security-config.example/roles_mapping.yml',{'_meta':{'type':'rolesmapping','config_version':2},
        'telemetry_writer':{'users':['fluent-bit']},'telemetry_health':{'users':['opensearch-health']},
        'kibana_server':{'users':['dashboards_svc']},'all_access':{'users':['observability_operator']},
        'security_rest_api_access':{'users':['observability_operator']}})
    write('security-config.example/internal_users.yml',{'_meta':{'type':'internalusers','config_version':2},
        'dashboards_svc':{'hash':'REPLACE_WITH_OPERATOR_SUPPLIED_BCRYPT_HASH'},
        'observability_operator':{'hash':'REPLACE_WITH_OPERATOR_SUPPLIED_BCRYPT_HASH'}})
    for name,kind in [('action_groups.yml','actiongroups'),('tenants.yml','tenants'),('nodes_dn.yml','nodesdn'),('allowlist.yml','allowlist'),('audit.yml','audit')]:
        write('security-config.example/'+name,{'_meta':{'type':kind,'config_version':2}})
    print('Rendered inactive secure candidate; no certificates, passwords, hashes or containers generated.')

if __name__=='__main__':
    main()
