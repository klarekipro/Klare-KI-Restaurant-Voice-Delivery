import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import test_runner as fixtures
from test_runner import Fake, response, r
import execution


def timeout_response(terminated=True):
    return dict(response('malformed',exit_code=-15),timed_out=True,terminated=terminated)


class ProcessTests(unittest.TestCase):
    def launch(self,code,timeout=2,**kwargs):
        return execution.execute([sys.executable,'-u','-c',code],self.root,os.environ.copy(),timeout,self.root/'logs',**kwargs)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_long_call_stream_and_activity(self):
        beats=[]
        result=self.launch("import time; print('started'); time.sleep(.4); print('finished')",heartbeat=beats.append,interval=.05)
        self.assertFalse(result['timed_out']);self.assertTrue(result['terminated'])
        self.assertGreater(len(beats),2);self.assertTrue(any(b['stdout_bytes']>0 for b in beats))
        self.assertIn('finished',result['stdout'])

    def test_virtual_long_process_exceeds_old_180_second_limit(self):
        clock=[0.0]
        class Process:
            pid=123456789
            returncode=0
            def poll(self):return 0 if clock[0]>=182 else None
        with patch.object(execution.subprocess,'Popen',return_value=Process()), \
             patch.object(execution.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(execution.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)), \
             patch.object(execution,'terminate',return_value=True):
            result=self.launch('virtual process',timeout=240)
        self.assertFalse(result['timed_out']);self.assertGreaterEqual(result['duration'],182)

    def test_hang_kill_and_preserve(self):
        result=self.launch("import time; print('partial'); time.sleep(60)",timeout=.25)
        self.assertTrue(result['timed_out']);self.assertTrue(result['terminated'])
        self.assertIn('partial',result['stdout'])
        metadata=json.loads((self.root/'logs/process.json').read_text())
        self.assertFalse(execution.alive(metadata['pid'],True))

    def test_ignores_term(self):
        with patch.object(execution,'terminate',side_effect=lambda p: original_terminate(p,.1)):
            result=self.launch("import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready'); time.sleep(60)",timeout=.25)
        self.assertTrue(result['terminated']);self.assertEqual(result['exit_code'],-9)

    def test_operator_interrupt_preserves_output(self):
        start=time.monotonic()
        with self.assertRaises(InterruptedError):
            self.launch("import time; print('partial'); time.sleep(60)",control=lambda:time.monotonic()-start>.3)
        metadata=json.loads((self.root/'logs/process.json').read_text())
        self.assertTrue(metadata['terminated']);self.assertIn('partial',(self.root/'logs/stdout.jsonl').read_text())

    def test_start_callback_failure_still_terminates(self):
        def fail(pid): raise RuntimeError('db unavailable')
        with self.assertRaises(RuntimeError):self.launch('import time; time.sleep(60)',on_start=fail)
        metadata=json.loads((self.root/'logs/process.json').read_text())
        self.assertTrue(metadata['terminated'])

    def test_leader_exit_does_not_leave_child(self):
        # Parent reaps its child on TERM to avoid platform-specific orphan zombies.
        code="""import subprocess,signal,time
child=subprocess.Popen(['sleep','60'])
def stop(*args):
 child.terminate(); child.wait(); raise SystemExit(0)
signal.signal(signal.SIGTERM,stop)
print(child.pid,flush=True)
time.sleep(60)
"""
        result=self.launch(code,timeout=.3)
        self.assertTrue(result['terminated']);self.assertFalse(execution.alive(int(result['stdout'].strip())))


original_terminate=execution.terminate


class TimeoutTests(unittest.TestCase):
    setUp=fixtures.RunnerTests.setUp
    tearDown=fixtures.RunnerTests.tearDown
    setup_engine=fixtures.RunnerTests.setup_engine
    state=fixtures.RunnerTests.state

    def edited_timeout(self,**options):
        class Edit(Fake):
            def execute(self,p,*args):
                if not self.calls:
                    path=Path(args[0])/'app';path.mkdir();(path/'partial.py').write_text('value = 1\n')
                return super().execute(p,*args)
        fake=Edit(timeout_response(),response(),response())
        e,m=self.setup_engine(fake,allow_edits=True,**options)
        return e,m,fake

    def test_separate_call_and_mission_limits(self):
        class Capture(Fake):
            def execute(self,p,*args):self.timeout=args[2];return super().execute(p,*args)
        fake=Capture(response());e,m=self.setup_engine(fake,max_seconds=900,invocation_seconds=240)
        e.step(m);self.assertEqual(fake.timeout,240)

    def test_call_clipped_by_mission_budget(self):
        class Capture(Fake):
            def execute(self,p,*args):self.timeout=args[2];return super().execute(p,*args)
        fake=Capture(response());e,m=self.setup_engine(fake,max_seconds=30,invocation_seconds=240)
        e.step(m);self.assertGreater(fake.timeout,0);self.assertLessEqual(fake.timeout,30)

    def test_default_hold_preserves_and_validates_no_quota(self):
        e,m,fake=self.edited_timeout();e.drive(m)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(fake.calls,['claude'])
        cp=self.store.c.execute('SELECT * FROM checkpoints').fetchone()
        self.assertEqual(cp['phase'],'VALIDATED');self.assertEqual((Path(cp['snapshot'])/'app/partial.py').read_text(),'value = 1\n')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM quota_signals').fetchone()[0],0)
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM commits').fetchone()[0],0)
        e.drive(m);self.assertEqual(fake.calls,['claude'])

    def test_authorized_handoff_and_review(self):
        e,m,fake=self.edited_timeout(timeout_recovery='checkpoint');e.drive(m)
        self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(fake.calls,['claude','codex','claude'])
        self.assertEqual(self.store.c.execute('SELECT phase FROM checkpoints').fetchone()[0],'HANDED_OFF')
        self.assertEqual(self.store.c.execute('SELECT retries FROM tasks WHERE id=2').fetchone()[0],1)

    def test_failed_checks_hold(self):
        e,m,fake=self.edited_timeout(timeout_recovery='checkpoint');e.validator=lambda *a:subprocess.CompletedProcess([],1,'failed','')
        e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(len(fake.calls),1)
        self.assertEqual(self.store.c.execute('SELECT phase FROM checkpoints').fetchone()[0],'PRESERVED')

    def test_unconfirmed_termination_no_validation(self):
        e,m=self.setup_engine(Fake(timeout_response(False)),timeout_recovery='checkpoint')
        e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM checkpoints').fetchone()[0],0)

    def test_live_group_blocks_checkpoint(self):
        e,m=self.setup_engine(Fake(timeout_response()),timeout_recovery='checkpoint')
        original=e.timeout_checkpoint
        def live(m,a,*args):
            self.store.c.execute('UPDATE attempts SET pid=? WHERE id=?',(os.getpid(),a))
            return original(m,a,*args)
        e.timeout_checkpoint=live;e.drive(m)
        self.assertEqual(self.state(m),'WAITING_APPROVAL')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM tests').fetchone()[0],0)

    def test_retry_budget_is_not_reset(self):
        e,m,fake=self.edited_timeout(timeout_recovery='checkpoint',max_retries=0)
        e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(len(fake.calls),1)

    def test_restart_after_captured_timeout_no_repeat(self):
        e,m,fake=self.edited_timeout(timeout_recovery='checkpoint')
        def crash(phase):
            if phase=='OUTCOME_CAPTURED':raise SystemExit('crash')
        e.checkpoint_hook=crash
        with self.assertRaises(SystemExit):e.step(m)
        e=r.Engine(self.store,fake,lambda *a:subprocess.CompletedProcess([],0,'checked',''));e.drive(m)
        self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(fake.calls,['claude','codex','claude'])

    def test_restart_at_timeout_checkpoint_boundaries(self):
        for phase in ['PRESERVED','VALIDATED','GIT_COMMITTED','COMMITTED','HANDED_OFF']:
            with self.subTest(phase=phase):
                e,m,fake=self.edited_timeout(timeout_recovery='checkpoint')
                def crash(at):
                    if at==phase:raise SystemExit('simulated crash')
                e.checkpoint_hook=crash
                with self.assertRaises(SystemExit):e.step(m)
                resumed=r.Engine(self.store,fake,lambda *a:subprocess.CompletedProcess([],0,'checked',''))
                resumed.drive(m)
                self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(fake.calls,['claude','codex','claude'])
                self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM checkpoints WHERE mission=?',(m,)).fetchone()[0],1)

    def test_repeat_timeouts_stop_at_original_retry_limit(self):
        e,m=self.setup_engine(Fake(timeout_response(),timeout_response()),timeout_recovery='checkpoint',max_retries=1)
        e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],2)
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM handoffs').fetchone()[0],1)

    def test_mutated_validated_timeout_checkpoint_holds(self):
        e,m,fake=self.edited_timeout(timeout_recovery='checkpoint')
        def crash(phase):
            if phase=='VALIDATED':raise SystemExit('crash')
        e.checkpoint_hook=crash
        with self.assertRaises(SystemExit):e.step(m)
        work=Path(self.store.c.execute('SELECT worktree FROM missions WHERE id=?',(m,)).fetchone()[0])
        (work/'app/partial.py').write_text('value = 2')
        r.Engine(self.store,fake).drive(m)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(fake.calls,['claude'])

    def test_unknown_interruption_never_replays(self):
        class Interrupted(Fake):
            def execute(self,*args):self.calls.append('claude');raise KeyboardInterrupt()
        fake=Interrupted();e,m=self.setup_engine(fake,timeout_recovery='checkpoint')
        e.drive(m);e.drive(m)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(len(fake.calls),1)

    def test_bad_time_settings_rejected(self):
        for option in [dict(invocation_seconds=0),dict(invocation_seconds=True),dict(invocation_seconds=float('nan')),dict(max_seconds=float('inf'))]:
            with self.subTest(option=option),self.assertRaises(r.Hold):self.setup_engine(Fake(),**option)

    def test_no_checks_cannot_authorize_resume(self):
        with self.assertRaises(r.Hold):self.setup_engine(Fake(),checks=[],timeout_recovery='checkpoint')


if __name__=='__main__':unittest.main()
