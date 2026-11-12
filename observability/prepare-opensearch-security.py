"""Prepare ignored security bootstrap files from pinned vendor defaults + supplied hashes.

Never starts OpenSearch, writes an index, generates credentials or prints hashes.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/'observability/secure-production/security-config.example'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--dashboards-hash-file',type=Path,required=True)
    parser.add_argument('--operator-hash-file',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists():
        raise RuntimeError('Output must be a new directory; refusing overwrite')
    if not output.is_relative_to(ROOT/'data'):
        raise RuntimeError('Output must be under ignored workspace data directory')
    hashes=[p.read_text().strip() for p in [args.dashboards_hash_file,args.operator_hash_file]]
    if not all(re.fullmatch(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}',h) for h in hashes):
        raise RuntimeError('Operator-supplied bcrypt hash format invalid')
    def read_vendor(name):
        p=subprocess.run(['docker','run','--rm','--pull','never','--network','none','--read-only',
            '--memory','64m','--pids-limit','32','--entrypoint','cat','opensearchproject/opensearch:3.9.0',
            '/usr/share/opensearch/config/opensearch-security/'+name],cwd=ROOT,capture_output=True,text=True,timeout=30)
        if p.returncode:
            raise RuntimeError('Cannot read pinned vendor security defaults; output withheld')
        return p.stdout
    # Keep vendor reserved role/action definitions. Never copy vendor default users/passwords.
    names=['roles.yml','action_groups.yml','tenants.yml','nodes_dn.yml','allowlist.yml','audit.yml']
    stock={name:read_vendor(name) for name in names}
    if 'telemetry_writer:' in stock['roles.yml']:
        raise RuntimeError('Unexpected existing role; review rather than overwrite')
    custom='''
telemetry_writer:
  cluster_permissions: [cluster_composite_ops]
  index_permissions:
    - index_patterns: ["springboot-user-20*-logs", "springboot-learning-20*-logs", "springboot-jwks-20*-logs"]
      allowed_actions: ["indices:data/write/bulk*", "indices:data/write/index*", "indices:data/write/create*", "indices:admin/create", "indices:admin/mapping/put"]
telemetry_health:
  cluster_permissions: ["cluster:monitor/health"]
  index_permissions: []
'''
    output.mkdir(parents=True)
    for name,text in stock.items():
        (output/name).write_text(text+custom if name=='roles.yml' else text)
    for name in ['config.yml','roles_mapping.yml']:
        (output/name).write_text((EXAMPLES/name).read_text())
    users=json.loads((EXAMPLES/'internal_users.yml').read_text())
    users['dashboards_svc']['hash']=hashes[0]
    users['observability_operator']['hash']=hashes[1]
    (output/'internal_users.yml').write_text(json.dumps(users,indent=2))
    print('Prepared protected bootstrap files with vendor reserved roles and supplied hashes; no security API called.')

if __name__=='__main__':
    main()
