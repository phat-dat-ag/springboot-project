"""Safety regressions for the Phase 6 verifier; no Docker or HTTP calls."""
import contextlib
import importlib
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

v=importlib.import_module('verify-phase6')

class ToolingSafetyTest(unittest.TestCase):
    def test_access_failure_is_derived_from_configuration(self):
        self.assertTrue(v.observed_access_gap({'opensearch':{'environment':{'DISABLE_SECURITY_PLUGIN':'true'}}},'', ''))
        self.assertFalse(v.observed_access_gap({'opensearch':{'environment':{'DISABLE_SECURITY_PLUGIN':'false'}}},'auth_enabled: true','auth_enabled: true'))

    def test_rotation_failure_requires_compressed_archive_and_current_only_tail(self):
        logback='<fileNamePattern>archive/app.%i.log.gz</fileNamePattern>'
        self.assertTrue(v.observed_rotation_gap([logback],'    Path /logs/app.log\n'))
        self.assertFalse(v.observed_rotation_gap([logback],'    Path /logs/archive/*.log\n'))

    def test_subprocess_failure_never_echoes_secret_payload(self):
        run=v.Validation.__new__(v.Validation)
        response=subprocess.CompletedProcess([],1,stdout='TOKEN_SENTINEL',stderr='PASSWORD_SENTINEL')
        with patch.object(v.subprocess,'run',return_value=response):
            with self.assertRaises(RuntimeError) as caught:
                run.cmd('docker','secret-argument-SENTINEL')
        self.assertNotIn('SENTINEL',str(caught.exception))

    def test_subprocess_has_bounded_timeout(self):
        run=v.Validation.__new__(v.Validation)
        with patch.object(v.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout='ok')) as command:
            self.assertEqual(run.cmd('docker','ps'),'ok')
            self.assertEqual(command.call_args.kwargs['timeout'],60)
            self.assertTrue(command.call_args.kwargs['capture_output'])

    def test_digest_is_order_independent(self):
        self.assertEqual(v.digest({'a':1,'b':2}),v.digest({'b':2,'a':1}))

    def test_inventory_excludes_environment_and_normalizes_mount_order(self):
        run=v.Validation.__new__(v.Validation)
        import json
        item={'Id':'id','Name':'/fixture','Image':'imageid','Config':{'Image':'image','Env':['PASSWORD=SECRET'],
            'Labels':{'com.docker.compose.project':'fixture'}},'State':{'StartedAt':'time','Status':'running'},
            'RestartCount':0,'Mounts':[{'Destination':'/z'},{'Destination':'/a'}],
            'HostConfig':{'PortBindings':{},'Memory':1,'NanoCpus':1,'LogConfig':{},'ReadonlyRootfs':True},
            'NetworkSettings':{'Networks':{'fixture':{}}}}
        with patch.object(run,'cmd',side_effect=['id',json.dumps([item])]):
            result=run.inventory()
        self.assertNotIn('SECRET',json.dumps(result))
        self.assertEqual([m['Destination'] for m in result[0]['mounts']],['/a','/z'])

    def test_readiness_gaps_do_not_become_green(self):
        run=v.Validation.__new__(v.Validation)
        run.rows=[]
        with patch.object(run,'save'),contextlib.redirect_stdout(io.StringIO()):
            run.result('NOT VERIFIED','external delivery')
            with self.assertRaises(AssertionError):
                run.check(False,'unsafe readiness')
        self.assertEqual([row['status'] for row in run.rows],['NOT VERIFIED','FAIL'])

if __name__=='__main__':
    unittest.main()
