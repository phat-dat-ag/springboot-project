"""Publish allowlisted Phase 6 results; never copies raw contacts, keys or tokens."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OBS=ROOT/'observability'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,help='Ignored run directory; defaults to latest completed run')
    args=parser.parse_args()
    folder=args.run or sorted((OBS/'phase6-evidence').glob('phase6-*/results.json'))[-1].parent
    result=json.loads((folder/'results.json').read_text())
    baseline=json.loads((folder/'baseline.json').read_text())
    counts=dict(Counter(row['status'] for row in result['checks']))
    suites={}
    for name in ['springboot-user-api','springboot-learning-api','springboot-jwks-api']:
        files=list((ROOT/name/'target/surefire-reports').glob('TEST-*.xml'))
        suites[name]={k:sum(int(ET.parse(p).getroot().attrib.get(k,0)) for p in files)
                      for k in ['tests','failures','errors','skipped']}
        suites[name]['report_files']=len(files)
    details=result['details']
    panels=details.get('panel_queries',[])
    times=sorted(row['ms'] for row in panels)
    report={'run_id':result['run_id'],'utc':result['utc'],'counts':counts,'maven':suites,
        'container_count':len(baseline['containers']),'volume_count':len(baseline['volumes']),
        'project_container_count':sum(c['project']=='springboot_project' for c in baseline['containers']),
        'jp_dev_count':sum(c['project']=='jp_dev' for c in baseline['containers']),
        'protected_file_count':len(baseline['protected']),
        'versions':details['baseline']['versions'],'git':details['baseline']['git'],
        'events':details.get('events',[]),'linked_trace':details.get('linked_trace'),
        'panel_query_count':len(panels),'panel_query_latency_ms':{
            'min':times[0] if times else None,'max':times[-1] if times else None,
            'median':times[len(times)//2] if times else None},
        'alert_states':details.get('alert_states'),
        'docker_stats':details.get('docker_stats'),'opensearch_capacity':details.get('opensearch_capacity'),
        'capacity_queries':details.get('capacity_queries'),'retention':details.get('retention'),
        'gaps':[r for r in result['checks'] if r['status']!='PASS']}
    (OBS/'phase6-measurements.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    checklist='# Consolidated Phase 6 verification checklist\n\n'
    checklist+='Current evidence: `'+result['run_id']+'`. Counts: `'+json.dumps(counts)+'`. A PASS applies to its stated scope; prior passes are not used as substitutes for current tests.\n\n'
    checklist+='## Current executed checks and explicit gaps\n\n| Status | Check | Detail |\n| --- | --- | --- |\n'
    for row in result['checks']:
        checklist+='| '+row['status']+' | '+row['check'].replace('|','\\|')+' | '+row['detail'].replace('|','\\|')+' |\n'
    checklist+='\n## Historical acceptance inventory\n\nThese rows are transcribed from prior reports, including superseded/history rows. They are historical claims, not new Phase 6 evidence. Phase 3 later authenticated checks supersede its earlier credential gaps; Phase 4 persistent queues supersede Phase 3 RAM-only configuration. Current criteria above determine this assessment.\n\n| Report | Historical status | Criterion |\n| --- | --- | --- |\n'
    for filename in ['phase0-baseline.md','phase0-runtime-verification.md','phase1-verification.md','phase2-verification.md','phase3-verification.md','phase4-verification.md','phase5-verification.md']:
        file=OBS/filename
        if not file.exists():
            continue
        for line in file.read_text(encoding='utf-8').splitlines():
            if line.startswith('|'):
                cells=[c.strip() for c in line.strip('|').split('|')]
                status=next((c for c in cells if c in ['PASS','FAIL','NOT VERIFIED','NOT APPLICABLE']),None)
                if status:
                    checklist+='| ['+filename+']('+filename+') | '+status+' | '+cells[0]+' |\n'
    (OBS/'phase6-checklist.md').write_text(checklist,encoding='utf-8')
    print('Published sanitized checklist/measurements:',json.dumps(counts))
    print('Maven:',json.dumps(suites))
    print('Panel queries:',len(panels),'latency ms:',report['panel_query_latency_ms'])
    print('OpenSearch capacity:',json.dumps(report['opensearch_capacity']))

if __name__=='__main__':
    main()
