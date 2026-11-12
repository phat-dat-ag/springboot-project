"""Read listening sockets through disposable network-namespace inspectors; no probes/writes."""
import importlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode=True
v=importlib.import_module('verify-phase6')

def main():
    x=v.Validation.__new__(v.Validation)
    rows=[r for r in x.inventory() if r['project']=='springboot_project' and r['status']=='running']
    code='''import json,socket
rows=[]
for file,family in [("/proc/net/tcp",4),("/proc/net/tcp6",6)]:
 for line in open(file).read().splitlines()[1:]:
  fields=line.split()
  if fields[3]!="0A": continue
  addr,port=fields[1].split(":")
  data=bytes.fromhex(addr)
  if family==4: addr=socket.inet_ntop(socket.AF_INET,data[::-1])
  else: addr=socket.inet_ntop(socket.AF_INET6,b"".join(data[i:i+4][::-1] for i in range(0,16,4)))
  rows.append({"address":addr,"port":int(port,16)})
print(json.dumps(rows))'''
    inventory=[]
    for r in rows:
        if r['service'] in ['mysql','postgres','opensearch-dashboards']:
            continue
        p=subprocess.run(['docker','run','--rm','--pull','never','--network','container:'+r['id'],
            '--read-only','--cap-drop','ALL','--memory','32m','--pids-limit','16','--user','10001:10001',
            'python:3.14-alpine','python','-c',code],capture_output=True,text=True,timeout=30)
        if p.returncode:
            raise RuntimeError('Socket inventory failed; payload withheld')
        inventory.append({'service':r['service'],'listening':json.loads(p.stdout),'published':r['ports'],'networks':r['networks']})
    (v.OBS/'remediation-endpoints.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print('PASS: current socket/exposure inventory captured for',len(inventory),'target services; no existing process changed')

if __name__=='__main__':
    main()
