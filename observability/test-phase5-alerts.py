"""Read-only preview evaluation: never persists rules or sends notifications."""
import copy
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import urllib.error

v=importlib.import_module('phase5-runtime')
rule=json.loads((Path(__file__).parent/'grafana/provisioning/alerting/phase5.json').read_text())['groups'][0]['rules'][4]
for label,expr in [('breach','vector(1)'),('normal','vector(0)'),('no-data','vector(0) > 1')]:
    data=copy.deepcopy(rule['data'])
    data[0]['model']['expr']=expr
    data[1]['model']['conditions'][0]['evaluator']['params']=[.5]
    body={'condition':'B','data':data,'now':datetime.now(timezone.utc).isoformat()}
    try:
        result=v.api('/api/v1/eval',body=body)
    except urllib.error.HTTPError as e:
        print('Preview API status:',e.code,e.read().decode()[:1000])
        raise
    (Path(__file__).parent/('phase5-alert-preview-'+label+'.log')).write_text(json.dumps(result,indent=2))
    condition=result['results']['B']
    assert condition['status']==200
    values=[value for frame in condition['frames'] for column in frame['data']['values'] for value in column]
    assert values==({'breach':[1],'normal':[0],'no-data':[]}[label])
    print('PASS: isolated Grafana threshold preview:',label,values)
data[0]['model']['expr']='invalid_promql{'
try:
    result=v.api('/api/v1/eval',body={'condition':'B','data':data})
    assert result['results']['A'].get('error') or result['results']['A'].get('status',200)>=400
except urllib.error.HTTPError as e:
    assert e.code in [400,422]
print('PASS: isolated Grafana execution-error preview (no persistent test rule)')
