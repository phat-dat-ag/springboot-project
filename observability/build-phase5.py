"""Deterministic Phase 5 artifacts; standard library only. No network or secrets."""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / 'observability'
DS = {k: {'type': k, 'uid': k} for k in ('prometheus', 'loki', 'tempo')}
FILTER = 'service=~"$service",environment=~"$environment"'
GROUP = 'service,environment'
HTTP = 'http_server_requests_seconds'
SELECT = '{' + FILTER + '}'
LOG = '{job="springboot",' + FILTER + '}'
BOUNDED = 'uri!~"/actuator/.*"'

def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')

def variable(name, values=None):
    v = {'name': name, 'label': name.title(), 'type': 'custom', 'multi': True,
         'includeAll': True, 'allValue': '.*', 'current': {'text': 'All', 'value': '$__all'},
         'query': ','.join(values or []), 'options': []}
    if values is None:
        q = 'label_values(app_build_info, environment)'
        v.update(type='query', datasource=DS['prometheus'], query=q, definition=q, refresh=1)
    return v

def panel(title, expr, unit='short', description='', ds='prometheus', kind='timeseries', legend=None):
    p = {'title': title, 'type': kind, 'description': description or title,
         'datasource': DS[ds], 'fieldConfig': {'defaults': {'unit': unit, 'noValue': 'No telemetry',
          'custom': {'spanNulls': False}}, 'overrides': []},
         'options': {'legend': {'displayMode': 'table', 'placement': 'bottom', 'calcs': ['lastNotNull']},
                     'tooltip': {'mode': 'multi', 'sort': 'desc'}},
         'targets': [{'refId': 'A', 'datasource': DS[ds], 'expr': expr,
                      'legendFormat': legend or '{{service}}', 'editorMode': 'code'}]}
    if ds == 'loki':
        p['targets'][0].update(queryType='range', maxLines=100)
    if kind == 'logs':
        p['options'] = {'showTime': True, 'showLabels': False, 'wrapLogMessage': True,
                         'sortOrder': 'Descending', 'enableLogDetails': True, 'dedupStrategy': 'none'}
    if kind == 'heatmap':
        p['targets'][0].update(format='heatmap', legendFormat='{{le}}')
        p['options'] = {'calculate': False, 'yAxis': {'unit': 's'}, 'cellGap': 1,
                        'color': {'mode': 'scheme', 'scheme': 'Oranges'}, 'legend': {'show': True}}
    return p

def text(title, body):
    return {'title': title, 'type': 'text', 'description': title,
            'options': {'mode': 'markdown', 'content': body}}

def dashboard(slug, title, panels, database=False, logs=False, infrastructure=False):
    services = ['user-learning', 'learning-api'] + ([] if database else ['jwks-service'])
    if infrastructure:
        services += ['prometheus', 'loki', 'tempo', 'otel-collector', 'fluent-bit', 'grafana']
    variables = [variable('environment'), variable('service', services)]
    if logs:
        for name, label in [('correlation', 'Correlation ID regex (.* = all)'), ('trace', 'Trace ID regex (.* = all)')]:
            variables.append({'name': name, 'label': label, 'type': 'textbox', 'query': '.*',
                              'current': {'text': '.*', 'value': '.*'}})
    for i, p in enumerate(panels):
        p.update(id=i+1, gridPos={'x': (i % 2)*12, 'y': (i//2)*9, 'w': 12, 'h': 9})
    d = {'uid': 'sb5-' + slug, 'title': 'Spring Boot / ' + title, 'schemaVersion': 41,
         'version': 1, 'editable': False, 'timezone': 'browser', 'tags': ['springboot', 'phase5'],
         'description': title + '. Missing series remain gaps; idle percentiles have no value. See observability/dashboards.md.',
         'time': {'from': 'now-1h', 'to': 'now'}, 'refresh': '30s', 'panels': panels,
         'templating': {'list': variables}, 'links': [
             {'title': 'All Spring Boot dashboards', 'type': 'dashboards', 'tags': ['phase5'],
              'asDropdown': True, 'includeVars': True, 'keepTime': True},
             {'title': 'Alert rules', 'type': 'link', 'url': '/alerting/list'}]}
    write(OBS / 'grafana/dashboards' / (slug + '.json'), d)
    return d

def rate(metric, extra='', group=GROUP, window='$__rate_interval'):
    sel = '{' + FILTER + (',' + extra if extra else '') + '}'
    return f'sum by ({group}) (rate({metric}{sel}[{window}]))'

def quantile(q, route=False, client=False):
    metric = 'http_client_requests_seconds_bucket' if client else HTTP + '_bucket'
    return f'histogram_quantile({q}, {rate(metric, BOUNDED, GROUP + (",uri" if route else "") + ",le")})'

def recording(name):
    return name + SELECT

def generate(environment):
    targets = [('user-api:9091', 'user-learning'), ('learning-api:9091', 'learning-api'), ('jwks-api:9091', 'jwks-service')]
    write(OBS / 'prometheus/targets/applications.json', [
        {'targets': [host], 'labels': {'service': service, 'environment': environment}} for host, service in targets])
    write(OBS / 'prometheus/targets/infrastructure.json', [
        {'targets': [host], 'labels': {'service': service, 'environment': environment}} for host, service in
        [('prometheus:9090', 'prometheus'), ('loki:3100', 'loki'), ('tempo:3200', 'tempo'),
         ('fluent-bit:2020', 'fluent-bit'), ('otel-collector:8888', 'otel-collector'), ('grafana:3000', 'grafana')]])
    # Service-level reuse only; route panels retain raw bounded uri dimensions.
    rawbase = f'sum by ({GROUP}) (rate({HTTP}_count{{{BOUNDED}}}[5m]))'
    base = f'({rawbase} or on ({GROUP}) (0 * max by ({GROUP}) (up{{job="springboot"}} == 1)))'
    zero = f'(0 * {base})'
    errors = lambda code: f'(sum by ({GROUP}) (rate({HTTP}_count{{{BOUNDED},status=~"{code}"}}[5m])) or on ({GROUP}) {zero})'
    rules = [
        ('sb:http_requests:rate5m', base),
        ('sb:http_5xx:rate5m', errors('5..')),
        ('sb:http_errors:ratio5m', f'{errors("4..|5..")} / on ({GROUP}) ({base} > 0)'),
        ('sb:http_p95:seconds5m', f'histogram_quantile(0.95, sum by ({GROUP},le) (rate({HTTP}_bucket{{{BOUNDED}}}[5m])))'),
        ('sb:http_p99:seconds5m', f'histogram_quantile(0.99, sum by ({GROUP},le) (rate({HTTP}_bucket{{{BOUNDED}}}[5m])))')]
    write(OBS / 'prometheus/rules/phase5.json', {'groups': [{'name': 'springboot-phase5', 'interval': '30s',
        'rules': [{'record': name, 'expr': expr} for name, expr in rules]}]})
    overview = [
        text('Reading this dashboard', 'Availability is the scrape result, not a business transaction. Zero throughput means a successful scrape with no requests. Missing telemetry remains a gap. HTTP panels exclude Actuator routes; quiet latency panels are expected.'),
        panel('Service availability', 'up{job="springboot",' + FILTER + '}', 'bool', '1 = private metrics target reachable; 0 = scrape failed. Missing targets require MissingMetrics alert.'),
        panel('HTTP requests per second', recording('sb:http_requests:rate5m'), 'reqps'),
        panel('HTTP 4xx per second', rate(HTTP+'_count', BOUNDED+',status=~"4.."') + ' or on (service,environment) (0 * ' + recording('sb:http_requests:rate5m') + ')', 'reqps'),
        panel('HTTP 5xx per second', recording('sb:http_5xx:rate5m'), 'reqps'),
        panel('HTTP error percentage', recording('sb:http_errors:ratio5m'), 'percentunit', '4xx + 5xx / requests. No ratio when idle; includes expected client rejections.'),
        *[panel(f'HTTP p{int(q*100)} latency', quantile(q) if q == .5 else recording('sb:http_p'+str(int(q*100))+':seconds5m'), 's', 'Histogram interpolation; no observation when no requests occurred.') for q in (.5,.95,.99)],
        panel('Request volume over selected range', f'sum by ({GROUP}) (increase({HTTP}_count{{{FILTER},{BOUNDED}}}[$__range]))', 'req'),
        panel('Recent application errors', LOG+' | json | __error__="" | level="ERROR"', ds='loki', kind='logs'),
        panel('JVM memory used', 'sum by (service,environment,area) (jvm_memory_used_bytes'+SELECT+')', 'bytes', legend='{{service}} {{area}}'),
        panel('Process CPU', 'process_cpu_usage'+SELECT, 'percentunit'),
        panel('Application uptime', 'process_uptime_seconds'+SELECT, 's')]
    dashboards = [dashboard('overview','Microservices Overview',overview)]
    http = [panel('Throughput by service',recording('sb:http_requests:rate5m'),'reqps'),
        panel('Top routes by throughput','topk(15, '+rate(HTTP+'_count',BOUNDED,GROUP+',uri')+')','reqps',legend='{{service}} {{uri}}'),
        panel('HTTP method breakdown',rate(HTTP+'_count',BOUNDED,GROUP+',method'),'reqps',legend='{{service}} {{method}}'),
        panel('Status distribution',rate(HTTP+'_count',BOUNDED,GROUP+',status'),'reqps',legend='{{service}} {{status}}'),
        panel('4xx trend',rate(HTTP+'_count',BOUNDED+',status=~"4.."'),'reqps'),
        panel('5xx trend',recording('sb:http_5xx:rate5m'),'reqps'),
        panel('HTTP error ratio',recording('sb:http_errors:ratio5m'),'percentunit'),
        *[panel(f'p{int(q*100)} latency',quantile(q),'s') for q in (.5,.95,.99)],
        panel('Slow endpoints by p95','topk(10, '+quantile(.95,route=True)+')','s', 'Bounded route templates; widen time window for quiet routes.',legend='{{service}} {{uri}}'),
        panel('Request duration distribution',rate(HTTP+'_bucket',BOUNDED,'le'),'s','Cumulative Prometheus buckets; Grafana heatmap format converts buckets to noncumulative counts. Aggregated across selected services.',kind='heatmap'),
        panel('Internal HTTP client throughput',rate('http_client_requests_seconds_count',group=GROUP+',uri'),'reqps','Appears only after observed managed HTTP client requests.',legend='{{service}} {{uri}}'),
        panel('Internal HTTP client p95',quantile(.95,client=True),'s')]
    dashboards.append(dashboard('http','HTTP Performance',http))
    heap_used = 'sum by (service,environment) (jvm_memory_used_bytes{'+FILTER+',area="heap"})'
    heap_max = 'sum by (service,environment) (jvm_memory_max_bytes{'+FILTER+',area="heap"} > 0)'
    runtime = [panel('Heap used',heap_used,'bytes'),panel('Heap maximum',heap_max,'bytes'),
        panel('Heap utilization',heap_used+' / ('+heap_max+' > 0)','percentunit','Only positive known pool maxima contribute.'),
        panel('Non-heap memory','sum by (service,environment) (jvm_memory_used_bytes{'+FILTER+',area="nonheap"})','bytes'),
        panel('GC frequency',rate('jvm_gc_pause_seconds_count'),'ops'),
        panel('GC pause time per second',rate('jvm_gc_pause_seconds_sum'),'s','Total GC pause seconds / wall-clock second; not a percentile.'),
        panel('Mean GC pause',rate('jvm_gc_pause_seconds_sum')+' / ('+rate('jvm_gc_pause_seconds_count')+' > 0)','s'),
        panel('Live threads','jvm_threads_live_threads'+SELECT),panel('Daemon threads','jvm_threads_daemon_threads'+SELECT),
        panel('Process CPU','process_cpu_usage'+SELECT,'percentunit'),panel('System CPU','system_cpu_usage'+SELECT,'percentunit'),
        panel('Process uptime','process_uptime_seconds'+SELECT,'s'),
        panel('Executor active threads','executor_active_threads'+SELECT,legend='{{service}} {{name}}'),
        panel('Executor maximum threads','executor_pool_max_threads'+SELECT,description='Configured maximum; very large defaults are not practical capacity guarantees.',legend='{{service}} {{name}}'),
        panel('Executor pool size','executor_pool_size_threads'+SELECT,legend='{{service}} {{name}}'),
        panel('Executor queued tasks','executor_queued_tasks'+SELECT,legend='{{service}} {{name}}'),
        panel('Open file descriptors','process_files_open_files'+SELECT),
        panel('JVM direct/mapped buffer memory','jvm_buffer_memory_used_bytes'+SELECT,'bytes',legend='{{service}} {{id}}')]
    dashboards.append(dashboard('jvm','JVM & Runtime',runtime))
    pool = '{'+FILTER+',service=~"user-learning|learning-api"}'
    db = [panel(name,'hikaricp_connections_'+suffix+pool,legend='{{service}} {{pool}}') for name,suffix in
          [('Active connections','active'),('Idle connections','idle'),('Pending connections','pending'),('Maximum connections','max')]]
    db += [panel('Pool utilization','hikaricp_connections_active'+pool+' / (hikaricp_connections_max'+pool+' > 0)','percentunit','Unknown/zero maximum excluded.',legend='{{service}} {{pool}}'),
        panel('Mean connection acquisition latency',rate('hikaricp_connections_acquire_seconds_sum',group=GROUP+',pool')+' / ('+rate('hikaricp_connections_acquire_seconds_count',group=GROUP+',pool')+' > 0)','s',legend='{{service}} {{pool}}'),
        panel('Connection timeouts',rate('hikaricp_connections_timeout_total',group=GROUP+',pool'),'ops',legend='{{service}} {{pool}}'),
        panel('Pool acquisition maximum','hikaricp_connections_acquire_seconds_max'+pool,'s','Micrometer time-window maximum, not lifetime maximum.',legend='{{service}} {{pool}}')]
    dashboards.append(dashboard('database','Database & Connection Pools',db,database=True))
    sec = [text('Security event meaning','Counters classify terminal HTTP results. Login/refresh failure includes invalid input and server errors; 401 alone is not proof of an attack. No separately instrumented cryptographic token-validation counter exists.'),
        panel('Authentication failures',rate('app_security_events_total','operation=~"authentication|internal_authentication|login|refresh",result="failure"'),'ops'),
        panel('Authorization denials',rate('app_security_events_total','operation="authorization",result="failure"'),'ops'),
        panel('Security event trends',rate('app_security_events_total',group=GROUP+',operation,result'),'ops',legend='{{service}} {{operation}} {{result}}'),
        panel('Security events over selected range','sum by (service,environment,operation,result) (increase(app_security_events_total'+SELECT+'[$__range]))',legend='{{service}} {{operation}} {{result}}'),
        panel('HTTP 401 trend',rate(HTTP+'_count','status="401"'),'reqps'),panel('HTTP 403 trend',rate(HTTP+'_count','status="403"'),'reqps'),
        panel('Authentication and authorization logs',LOG+' | json category=`["error.category"]` | __error__="" | category=~"authentication|authorization"',ds='loki',kind='logs')]
    dashboards.append(dashboard('security','Security & Authentication',sec))
    logfilter = LOG+' | json | __error__="" | correlationId=~"${correlation:regex}" | traceId=~"${trace:regex}"'
    logging = [text('Log investigation','Use an exact correlation ID or trace ID; default .* includes records with absent optional fields. Expand JSON details and choose TraceID → View trace. Sampling means some log trace IDs have no stored trace.'),
        panel('Log volume by service','sum by (service) (rate('+LOG+'[$__interval]))','logs','Stream labels only; no request IDs become labels.',ds='loki'),
        panel('Log volume by severity','sum by (service,level) (rate(('+LOG+' | json | __error__="")[$__interval]))','logs',ds='loki',legend='{{service}} {{level}}'),
        panel('ERROR trend','sum by (service) (rate(('+LOG+' | json | __error__="" | level="ERROR")[$__interval]))','logs',ds='loki'),
        panel('WARN trend','sum by (service) (rate(('+LOG+' | json | __error__="" | level="WARN")[$__interval]))','logs',ds='loki'),
        panel('Recent errors',logfilter+' | level="ERROR"',ds='loki',kind='logs'),
        panel('Recent warnings',logfilter+' | level="WARN"',ds='loki',kind='logs'),
        panel('HTTP request failures',logfilter+' | event="http.request.completed" | outcome=~"client_error|server_error"',ds='loki',kind='logs'),
        panel('Correlated logs',logfilter,ds='loki',kind='logs')]
    dashboards.append(dashboard('logging','Centralized Logging',logging,logs=True))
    def explore(query):
        # Literal Grafana macros remain in URL; variable values are bounded custom options.
        from urllib.parse import quote
        panes = {'trace': {'datasource': 'tempo', 'queries': [{'refId': 'A', 'datasource': DS['tempo'],
                    'queryType': 'traceql', 'query': query}], 'range': {'from': 'now-1h', 'to': 'now'}}}
        encoded = quote(json.dumps(panes, separators=(',',':')), safe='')
        encoded = encoded.replace('%24service', '${service:regex}').replace('%24environment', '${environment:regex}')
        return '/explore?schemaVersion=1&panes=' + encoded + '&orgId=1'
    tracebase = 'resource.service.name =~ "$service" && resource.deployment.environment.name =~ "$environment"'
    workflow = '1. Select service/environment and inspect HTTP latency.\n2. Open a Tempo search below, narrow time range and inspect a SERVER span.\n3. Use its trace-to-logs action; expand a log and use TraceID → View trace for the reverse direction.\n\n'
    for name, query in [('Search selected services','{ '+tracebase+' }'),('Slow requests (>1 second)','{ '+tracebase+' && duration > 1s }'),('Error traces','{ '+tracebase+' && status = error }')]:
        workflow += '['+name+']('+explore(query)+')\n\n'
    workflow += '10% root sampling remains unchanged. No service graph, span-metrics pipeline or TraceQL metrics generator is enabled. HTTP 4xx need not set span status=error. Search and waterfall UI interactions require manual browser verification.'
    tracing = [text('Trace investigation workflow',workflow),panel('Service p95',recording('sb:http_p95:seconds5m'),'s'),
        panel('Service p99',recording('sb:http_p99:seconds5m'),'s'),panel('Request throughput',recording('sb:http_requests:rate5m'),'reqps'),
        panel('Recent errors with trace navigation',LOG+' | json | __error__="" | level="ERROR"',ds='loki',kind='logs')]
    dashboards.append(dashboard('tracing','Distributed Tracing',tracing))
    infra = [text('Coverage and limitations','UP means metrics endpoint reachable, not a full ingest/query transaction. OpenSearch has no Prometheus exporter: use the existing protected local cluster-health check; no cluster-health gauge is fabricated. Backend disk capacity and Fluent Bit output-buffer saturation are unavailable as reliable collected metrics. App disk_* gauges describe their mounted filesystem only and do not monitor backend volumes.'),
        panel('All scrape target health','up{'+FILTER+'}','bool',legend='{{service}} {{instance}}'),
        panel('Scrape duration','scrape_duration_seconds'+SELECT,'s'),
        panel('Collector queue utilization','otelcol_exporter_queue_size'+SELECT+' / (otelcol_exporter_queue_capacity'+SELECT+' > 0)','percentunit','Configured byte queue; size/capacity ratio is dimensionless despite generic upstream HELP text.',legend='{{service}} {{exporter}}'),
        panel('Collector failed span export attempts',rate('otelcol_exporter_send_failed_spans'),'ops','Failed attempts may recover through retries; not proof of lost spans.'),
        panel('Collector refused spans',rate('otelcol_receiver_refused_spans'),'ops','Spans refused at receiver; this does not quantify queue-disk saturation.'),
        panel('Fluent Bit output errors',rate('fluentbit_output_errors_total',group=GROUP+',name'),'ops',legend='{{service}} {{name}}'),
        panel('Fluent Bit dropped records',rate('fluentbit_output_dropped_records_total',group=GROUP+',name'),'ops',legend='{{service}} {{name}}'),
        panel('Fluent Bit failed retries',rate('fluentbit_output_retries_failed_total',group=GROUP+',name'),'ops',legend='{{service}} {{name}}'),
        panel('Loki received lines',rate('loki_distributor_lines_received_total'),'logs'),
        panel('Loki flush failures',rate('loki_ingester_chunks_flush_failures_total'),'ops'),
        panel('Loki WAL bytes','loki_ingester_wal_bytes_in_use'+SELECT,'bytes','Usage gauge only; filesystem capacity is unavailable.'),
        panel('Tempo received spans',rate('tempo_distributor_spans_received_total'),'ops'),
        panel('Tempo failed flushes',rate('tempo_ingester_failed_flushes_total'),'ops'),
        panel('Grafana alert instances','grafana_alerting_alerts'+SELECT,legend='{{service}} {{state}}'),
        panel('Prometheus resident memory','process_resident_memory_bytes{'+FILTER+',service="prometheus"}','bytes')]
    dashboards.append(dashboard('infrastructure','Observability Infrastructure',infra,infrastructure=True))
    build_alerts(environment)
    write(OBS/'grafana/phase5-inventory.json', [{'uid':d['uid'],'title':d['title'],
        'panels':[p['title'] for p in d['panels']], 'variables':[v['name'] for v in d['templating']['list']],
        'datasources':sorted({p['datasource']['uid'] for p in d['panels'] if 'datasource' in p})} for d in dashboards])
    inventory = '# Phase 5 dashboard inventory\n\nGenerated by `build-phase5.py`. All dashboards live in **Observability**, default to one hour and refresh every 30 seconds.\n\n'
    for d in dashboards:
        sources = sorted({p['datasource']['uid'] for p in d['panels'] if 'datasource' in p})
        inventory += '## '+d['title']+'\n\nUID: `'+d['uid']+'`. Datasources: '+', '.join(sources)+'. Variables: '+', '.join(x['name'] for x in d['templating']['list'])+'.\n\n'
        inventory += '\n'.join('- '+p['title'] for p in d['panels'])+'\n\n'
    (OBS/'dashboard-inventory.md').write_text(inventory,encoding='utf-8')
    print('Generated 8 dashboards, 5 recording rules, application/infrastructure targets and alert provisioning for',environment)

def build_alerts(environment):
    rows=[]
    def add(name, expr, threshold, pending, severity, why, investigate, no_data='OK', comparator='gt', service=None):
        uid='sb5-'+''.join('-'+c.lower() if c.isupper() else c for c in name).lstrip('-')
        labels={'severity':severity,'environment':environment,'phase':'5','service':service or '{{ $labels.service }}'}
        # Service comes from PromQL result; do not overwrite it with a template label.
        if service is None:
            del labels['service']
        rows.append({'uid':uid,'title':name,'condition':'B','for':pending,'noDataState':no_data,
            'execErrState':'Error','keepFiringFor':'1m','isPaused':False,'labels':labels,
            'annotations':{'summary':name,'description':why,'runbook':investigate},
            'notification_settings':{'receiver':'$PHASE5_ALERT_RECEIVER',
                'group_by':['service','environment','severity'],'group_wait':'1m','group_interval':'5m',
                'repeat_interval':'4h','mute_time_intervals':['phase5-delivery-disabled']},
            'data':[{'refId':'A','relativeTimeRange':{'from':600,'to':0},'datasourceUid':'prometheus',
                'model':{'refId':'A','datasource':DS['prometheus'],'expr':expr,'instant':True,'range':False,
                    'intervalMs':15000,'maxDataPoints':43200}},
                {'refId':'B','relativeTimeRange':{'from':0,'to':0},'datasourceUid':'__expr__',
                 'model':{'refId':'B','datasource':{'type':'__expr__','uid':'__expr__'},'type':'threshold',
                     'expression':'A','conditions':[{'type':'query','query':{'params':['B']},
                        'reducer':{'type':'last','params':[]},'evaluator':{'type':comparator,'params':[threshold]},
                        'operator':{'type':'and'}}]}}]})
    add('ServiceDown','up{job="springboot"}',1,'2m','critical','Private scrape endpoint failed continuously for 2m; not proof the public API is down.','Check target lastError, API readiness, private port 9091 and container health.',comparator='lt',no_data='NoData')
    for host,service in [('user-api:9091','user-learning'),('learning-api:9091','learning-api'),('jwks-api:9091','jwks-service')]:
        add('MissingMetrics'+('User' if service=='user-learning' else 'Learning' if service=='learning-api' else 'JWKS'),
            f'absent_over_time(up{{job="springboot",instance="{host}"}}[5m])',0,'2m','warning',
            'Expected scrape target disappeared for 5m plus pending period.','Check Prometheus target discovery and targets/applications.json.',service=service)
    request='sb:http_requests:rate5m'
    volume=f'sum by ({GROUP}) (increase({HTTP}_count{{{BOUNDED}}}[5m]))'
    add('High5xxErrorRate',f'(sb:http_5xx:rate5m / ({request} > 0)) and on ({GROUP}) ({volume} >= 100)',.05,'5m','critical',
        '>5% server errors with at least 100 requests/5m; excludes Actuator.','Open HTTP Performance, compare routes/status, then errors and sampled traces.')
    add('HighHTTPErrorRatio',f'sb:http_errors:ratio5m and on ({GROUP}) ({volume} >= 100)',.20,'10m','warning',
        '>20% 4xx+5xx for sustained traffic; client rejections may be expected.','Compare 4xx vs 5xx, routes, release changes and expected rejected requests.')
    add('HighP95Latency',f'sb:http_p95:seconds5m and on ({GROUP}) ({volume} >= 100)',1,'10m','warning',
        'p95 >1 second with >=100 requests/5m; initial development threshold, not a contractual SLO.','Inspect slow bounded routes, pool waits, GC and Tempo slow search.')
    add('HighP99Latency',f'sb:http_p99:seconds5m and on ({GROUP}) ({volume} >= 1000)',2.5,'15m','warning',
        'p99 >2.5 seconds with >=1000 requests/5m to limit tail noise.','Inspect HTTP histogram and sampled slow traces; tune from a real SLO.')
    used=f'sum by ({GROUP}) (jvm_memory_used_bytes{{area="heap"}})'
    maximum=f'sum by ({GROUP}) (jvm_memory_max_bytes{{area="heap"}} > 0)'
    add('HighHeapUsage',f'{used} / ({maximum} > 0)',.85,'15m','warning','Heap >85% of positive configured maximum for 15m.','Check JVM heap, allocation and GC; compare trends before changing limits.')
    add('HighCPUUsage',f'max by ({GROUP}) (process_cpu_usage)',.85,'15m','warning','Process CPU fraction >85% for 15m; JVM/container CPU interpretation varies.','Inspect traffic, GC, thread/executor load and configured CPU limits.')
    add('ExcessiveGCPause',f'sum by ({GROUP}) (rate(jvm_gc_pause_seconds_sum[5m]))',.10,'10m','warning',
        'GC pause time exceeds 0.10 seconds per wall-clock second for 10m; no GC percentile fabricated.','Inspect heap occupancy/allocation and GC causes in JVM dashboard.')
    add('HikariPoolSaturation','max by (service,environment,pool) (hikaricp_connections_active / (hikaricp_connections_max > 0))',.90,'10m','warning',
        'Active / known positive maximum >90% for 10m.','Check pending connections, acquisition latency, slow queries and DB availability.')
    add('HikariPendingConnections','max by (service,environment,pool) (hikaricp_connections_pending)',0,'5m','warning',
        'At least one pending connection remains for 5m.','Check saturation, connection leaks, transaction duration and database health.')
    add('CollectorExportFailures',f'sum by ({GROUP}) (rate(otelcol_exporter_send_failed_spans[5m]))',0,'5m','warning',
        'Sustained failed span export attempts; retries may recover, this is not a loss count.','Check Tempo readiness, Collector exporter logs and queue utilization.')
    add('CollectorQueueSaturation',f'max by ({GROUP}) (otelcol_exporter_queue_size / (otelcol_exporter_queue_capacity > 0))',.80,'5m','critical',
        'Persistent trace queue >80% for 5m; capacity is configured in bytes.','Restore Tempo/connectivity, inspect exporter failures; do not erase the queue.')
    add('FluentBitDeliveryFailures',f'sum by ({GROUP}) (rate(fluentbit_output_errors_total[5m]) + rate(fluentbit_output_retries_failed_total[5m]) + rate(fluentbit_output_dropped_records_total[5m]))',0,'5m','warning',
        'Sustained output errors, exhausted retries or dropped records; one underlying problem can increment multiple counters.','Inspect output name on infrastructure dashboard, readiness, filesystem backlog and destination logs.')
    add('LokiIngestionFailures',f'sum by ({GROUP}) (rate(loki_ingester_chunks_flush_failures_total[5m]) or rate(loki_request_duration_seconds_count{{route="loki_api_v1_push",status_code=~"4..|5.."}}[5m]))',0,'5m','warning',
        'Loki HTTP push rejections/server errors or chunk flush failures persist; not a complete per-reason discard count.','Inspect Loki push status, logs/WAL/free space and Fluent Bit Loki output; no complete discard coverage claimed.')
    add('TempoUnavailable','up{job="observability",service="tempo"}',1,'2m','critical',
        'Tempo metrics endpoint unreachable for 2m; query readiness is checked separately.','Check internal /ready, Tempo logs, storage and Collector queue.',comparator='lt',no_data='NoData')
    add('PrometheusTargetDown','up{job="observability",service!="tempo"}',1,'3m','warning',
        'Infrastructure metrics endpoint unreachable for 3m; Tempo has its own alert.','Inspect Prometheus target lastError, endpoint and container state.',comparator='lt',no_data='NoData')
    add('ElevatedAuthenticationFailures',f'sum by ({GROUP}) (increase(app_security_events_total{{operation=~"authentication|internal_authentication|login|refresh",result="failure"}}[10m]))',50,'5m','warning',
        '>50 failed terminal authentication HTTP operations/10m for 5m; an investigation signal, not proof of an attack.','Compare operation trends, deployments and expected negative tests using safe logs only.')
    add('ElevatedAuthorizationDenials',f'sum by ({GROUP}) (increase(app_security_events_total{{operation="authorization",result="failure"}}[10m]))',100,'10m','warning',
        '>100 terminal authorization denials/10m for 10m; higher threshold accounts for expected rejections.','Inspect aggregate 403 routes and configuration; never add user identifiers to labels.')
    write(OBS/'grafana/provisioning/alerting/phase5.json', {'apiVersion':1,
        'muteTimes':[{'orgId':1,'name':'phase5-delivery-disabled',
            'time_intervals':[{'times':[{'start_time':'00:00','end_time':'24:00'}]}]}],
        'groups':[{'orgId':1,'name':'springboot-phase5','folder':'Observability', 'interval':'1m','rules':rows}]})
    reference = '# Phase 5 alert reference\n\nGenerated by `build-phase5.py`. All rules evaluate every minute, recover after a one-minute keep-firing period, and have execution-error behavior `Error`. External delivery is muted.\n\n'
    for r in rows:
        condition=r['data'][1]['model']['conditions'][0]['evaluator']
        reference += '## '+r['title']+'\n\nUID: `'+r['uid']+'`; severity **'+r['labels']['severity']+'**; pending **'+r['for']+'**; no-data **'+r['noDataState']+'**. Condition: `'+condition['type']+' '+str(condition['params'][0])+'`.\n\n'
        reference += '```promql\n'+r['data'][0]['model']['expr']+'\n```\n\n'+r['annotations']['description']+'\n\nInvestigate: '+r['annotations']['runbook']+'\n\n'
    (OBS/'alert-rules.md').write_text(reference,encoding='utf-8')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--environment',default=os.environ.get('DEPLOYMENT_ENVIRONMENT','development'),
                        choices=['development','test','staging','production'])
    generate(parser.parse_args().environment)
