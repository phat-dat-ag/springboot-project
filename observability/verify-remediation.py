"""Run fresh Phase 6 regressions without overwriting historical Phase 6A reports."""
import argparse
import importlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
v=importlib.import_module('verify-phase6')

class Followup(v.Validation):
    def metrics(self):
        if self.details.get('linked_trace'):
            self.wait(lambda:self.query('http_client_requests_seconds_count{service="learning-api",uri="/internal/users/{id}",status="200"}'))
        super().metrics()

    def gaps(self):
        # Preserve the broad durability/paging gaps; verify the narrower fixed cause separately.
        super().gaps()
        fixture=json.loads((v.OBS/'remediation-rotation-evidence.log').read_text())
        self.check(fixture['result']=='PASS' and fixture['events_per_sink']==52,'isolated migration/rollover/downtime/restart evidence')
        for service,module in zip(v.APPS,v.MODULES):
            cid=self.ids[service]
            raw=self.cmd('docker','exec',cid,'cat','/etc/application/logback-spring.xml')
            self.check(raw==(v.ROOT/module/'src/main/resources/logback-spring.xml').read_text(), 'actual loaded external Logback source matches: '+service)
            self.check('/spool/' in raw and '<file>' not in raw and '.log.gz</fileNamePattern>' not in raw,
                'stable filename, no rename/compression in deployed rolling policy: '+service)
            files=self.cmd('docker','exec',cid,'find','/app/data/logs/spool','-type','f','-name','*.log')
            self.check(bool(files.strip()),'real application spool files created: '+service)
        self.result('PASS','compression-specific unread-file loss cause remediated','fixture plus live source-file delivery verified; retention/overflow/crash loss remain separate limitations')

if __name__=='__main__':
    args=argparse.Namespace(evidence_dir=v.OBS/'phase6-evidence/remediation-regression',compose_file=['docker-compose.yml'],
        endpoint=[],timeout=10,credentials=v.OBS/'local-test-credentials.json')
    sys.exit(Followup(args).run())
