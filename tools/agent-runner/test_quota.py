import json
from pathlib import Path
import plistlib
import subprocess
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import test_runner as baseline
Fake=baseline.Fake
response=baseline.response
r=baseline.r
import quota
import scheduler

class Provider(Fake):
    def __init__(self,*results,probe_result=None):
        super().__init__(*results);self.probe_calls=[];self.probe_result=probe_result or response()
    def probe(self,provider,*args):
        self.probe_calls.append(provider);return self.probe_result

class QuotaTests(unittest.TestCase):
    setUp=baseline.RunnerTests.setUp
    tearDown=baseline.RunnerTests.tearDown
    setup_engine=baseline.RunnerTests.setup_engine
    state=baseline.RunnerTests.state
    def waiting(self,**options):
        provider=Provider(response(limited=True),response(),response())
        settings=dict(auto_resume_quota=True,quota_probe_authorized=True,fallback=False,max_seconds=7200,max_invocations=6)
        settings.update(options);engine,m=self.setup_engine(provider,**settings);engine.drive(m)
        self.assertEqual(self.state(m),'WAITING_QUOTA')
        due=self.store.c.execute('SELECT next_check FROM quota_waits WHERE mission=?',(m,)).fetchone()[0]
        return engine,m,provider,due
    def test_both_exhausted_waits_with_checkpoint(self):
        provider=Provider(response(limited=True),response(limited=True));e,m=self.setup_engine(provider,auto_resume_quota=True,max_seconds=7200)
        e.drive(m);self.assertEqual(self.state(m),'WAITING_QUOTA')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM quota_waits WHERE mission=?',(m,)).fetchone()[0],2)
        self.assertTrue(self.store.c.execute("SELECT 1 FROM checkpoints WHERE mission=? AND phase='COMMITTED'",(m,)).fetchone())
    def test_probe_recovered_resumes_existing_mission(self):
        e,m,p,due=self.waiting();scheduler.tick(e,due+1)
        self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(len(p.probe_calls),1)
        self.assertEqual(len(p.calls),3)
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM missions').fetchone()[0],1)
    def test_no_authentication_signal_misclassified(self):
        p=Provider(response(exit_code=1));p.responses[0]['error']='authentication failed'
        e,m=self.setup_engine(p,auto_resume_quota=True,max_retries=0);e.drive(m)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM quota_signals').fetchone()[0],0)
    def test_network_error_not_quota(self):
        p=Provider(response(exit_code=1));p.responses[0]['error']='connection reset'
        e,m=self.setup_engine(p,auto_resume_quota=True,max_retries=0);e.drive(m)
        self.assertEqual(self.state(m),'FAILED');self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM quota_waits').fetchone()[0],0)
    def test_explicit_reset_and_http_retry_after(self):
        now=time.time()
        self.assertEqual(quota.retry_time({'headers':{'Retry-After':'3600'}},now),now+3600)
        self.assertEqual(quota.retry_time({'reset_at':'2030-01-01T00:00:00Z'},now),1893456000)
        self.assertIsNone(quota.retry_time({'result':'resets 1am'},now))
        self.assertIsNone(quota.retry_time({'reset_at':'2030-01-01T00:00:00'},now))
        value=response(limited=True);value['retry_at']=now+3600
        e,m=self.setup_engine(Provider(value),fallback=False,auto_resume_quota=True,max_seconds=7200)
        e.drive(m);self.assertGreaterEqual(self.store.c.execute('SELECT next_check FROM quota_waits').fetchone()[0],now+3600)
    def test_unknown_reset_backoff_and_no_busy_poll(self):
        e,m,p,due=self.waiting();p.probe_result=response(exit_code=1)
        scheduler.tick(e,due-1);self.assertFalse(p.probe_calls)
        scheduler.tick(e,due+1);self.assertEqual(len(p.probe_calls),1)
        next_time=self.store.c.execute('SELECT next_check FROM quota_signals').fetchone()[0]
        self.assertGreaterEqual(next_time,due+1+2*quota.MIN_INTERVAL)
        scheduler.tick(e,due+2);self.assertEqual(len(p.probe_calls),1)
    def test_probe_requires_prior_authorization(self):
        e,m,p,due=self.waiting(quota_probe_authorized=False);scheduler.tick(e,due+1)
        self.assertFalse(p.probe_calls);self.assertEqual(self.state(m),'WAITING_QUOTA')
    def test_existing_real_success_avoids_probe(self):
        e,m,p,due=self.waiting();quota.recovered(e,'claude');scheduler.tick(e,due-100)
        self.assertEqual(self.state(m),'COMPLETED');self.assertFalse(p.probe_calls)
    def test_sleep_wake_coalesces_checks(self):
        e,m,p,due=self.waiting();scheduler.tick(e,due+8*3600)
        self.assertEqual(len(p.probe_calls),1);self.assertEqual(self.state(m),'COMPLETED')
    def test_reopen_store_no_repeat_call_or_commit(self):
        e,m,p,due=self.waiting();self.store.c.close();self.store=r.Store(self.root/'state/state.sqlite')
        reopened=r.Engine(self.store,p,lambda *a:subprocess.CompletedProcess([],0,'',''));scheduler.tick(reopened,due+1)
        before=self.store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0];scheduler.tick(reopened,due+10000)
        self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],before)
    def test_unknown_inflight_probe_requires_approval(self):
        e,m,p,due=self.waiting();task=self.store.c.execute('SELECT task FROM quota_waits').fetchone()[0]
        self.store.c.execute("INSERT INTO attempts(task,provider,state) VALUES(?,'claude','RUNNING')",(task,))
        scheduler.tick(e,due+1);self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(p.probe_calls)
    def test_duplicate_scheduler_writer_lock(self):
        e,m,p,due=self.waiting()
        with self.store.lock():self.assertFalse(scheduler.tick(e,due+1))
        self.assertFalse(p.probe_calls);self.assertEqual(self.state(m),'WAITING_QUOTA')
    def test_active_other_provider_not_interrupted(self):
        e,m,p,due=self.waiting();self.store.c.execute("UPDATE missions SET state='RUNNING' WHERE id=?",(m,))
        quota.recovered(e,'claude');scheduler.tick(e,due+1)
        self.assertEqual(self.state(m),'RUNNING');self.assertFalse(p.probe_calls)
    def test_expired_original_duration(self):
        e,m,p,due=self.waiting();started=self.store.c.execute('SELECT started FROM missions').fetchone()[0]
        with patch.object(quota.time,'time',return_value=started+7201):scheduler.tick(e,due+7201)
        self.assertEqual(self.state(m),'FAILED');self.assertFalse(p.probe_calls)
    def test_scope_changed_requires_approval(self):
        e,m,p,due=self.waiting();d=json.loads(self.store.c.execute('SELECT definition FROM missions').fetchone()[0]);d['prompt']='different authorized work?'
        self.store.c.execute('UPDATE missions SET definition=?',(json.dumps(d),));scheduler.tick(e,due+1)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(p.probe_calls)
    def test_task_changed_requires_approval(self):
        e,m,p,due=self.waiting();self.store.c.execute("UPDATE tasks SET prompt='changed'");scheduler.tick(e,due+1)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(p.probe_calls)
    def test_dirty_anchor_requires_approval(self):
        e,m,p,due=self.waiting();work=Path(self.store.c.execute('SELECT worktree FROM missions').fetchone()[0]);(work/'dirty').write_text('unknown')
        scheduler.tick(e,due+1);self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(p.probe_calls)
    def test_human_approval_and_terminal_states_never_resume(self):
        for state in ['WAITING_APPROVAL','CANCELLED','STOPPED']:
            e,m,p,due=self.waiting();self.store.c.execute('UPDATE missions SET state=? WHERE id=?',(state,m))
            scheduler.tick(e,due+1);self.assertEqual(self.state(m),state);self.assertFalse(p.probe_calls)
            self.store.c.execute('DELETE FROM availability');self.store.c.execute('DELETE FROM quota_signals')
    def test_invocation_budget_includes_probe(self):
        e,m,p,due=self.waiting(max_invocations=2);scheduler.tick(e,due+1)
        self.assertEqual(self.state(m),'FAILED');self.assertFalse(p.probe_calls)
    def test_check_count_bounded(self):
        e,m,p,due=self.waiting();self.store.c.execute('UPDATE quota_signals SET checks=?',(quota.MAX_CHECKS,));scheduler.tick(e,due+1)
        self.assertFalse(p.probe_calls)
    def test_probe_success_crash_does_not_repeat_billable_probe(self):
        e,m,p,due=self.waiting()
        def crash(phase):
            if phase=='PROBE_RESULT_CAPTURED':raise SystemExit('controlled worker crash')
        e.checkpoint_hook=crash
        with self.assertRaises(SystemExit):scheduler.tick(e,due+1)
        self.assertEqual(len(p.probe_calls),1)
        self.store.c.close();self.store=r.Store(self.root/'state/state.sqlite')
        reopened=r.Engine(self.store,p,lambda *a:subprocess.CompletedProcess([],0,'',''));scheduler.tick(reopened,due+2)
        self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(len(p.probe_calls),1)
    def test_failed_probes_respect_consecutive_failure_limit(self):
        e,m,p,due=self.waiting(max_failures=2);p.probe_result=response(exit_code=1)
        scheduler.tick(e,due+1);self.assertEqual(self.state(m),'FAILED')
        self.assertEqual(len(p.probe_calls),1)
    def test_probe_authentication_failure_requires_human(self):
        e,m,p,due=self.waiting();p.probe_result=response(exit_code=1);p.probe_result['error']='authentication failed'
        scheduler.tick(e,due+1);self.assertEqual(self.state(m),'WAITING_APPROVAL')

    def test_scheduler_restart_after_resume_selection(self):
        e,m,p,due=self.waiting()
        def crash(phase):
            if phase=='QUOTA_RESUME_SELECTED':raise SystemExit('controlled handoff crash')
        e.checkpoint_hook=crash
        with self.assertRaises(SystemExit):scheduler.tick(e,due+1)
        self.assertEqual(self.state(m),'VALIDATING')
        self.store.c.close();self.store=r.Store(self.root/'state/state.sqlite')
        resumed=r.Engine(self.store,p,lambda *a:subprocess.CompletedProcess([],0,'',''));scheduler.tick(resumed,due+2)
        self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(len(p.probe_calls),1);self.assertEqual(len(p.calls),3)

    def test_launchagent_roundtrip_and_activation_guard(self):
        e,m,p,due=self.waiting();script=Path(r.__file__).resolve();args=SimpleNamespace(command='scheduler',mission='generate',output=str(self.root/'generated.plist'),authorize_activation=None)
        scheduler.command(e,args,script);config=plistlib.loads(Path(args.output).read_bytes())
        self.assertEqual(config['StartInterval'],300);self.assertTrue(config['RunAtLoad']);self.assertNotIn('KeepAlive',config)
        self.assertNotIn('shell',config['ProgramArguments']);args.mission='install'
        with self.assertRaises(r.Hold):scheduler.command(e,args,script)

    def test_install_enable_disable_uninstall_use_fake_home_only(self):
        e,m,p,due=self.waiting();home=self.root/'fake-home';(home/'Library').mkdir(parents=True)
        args=SimpleNamespace(command='scheduler',mission='generate',output=str(self.root/'reviewed.plist'),authorize_activation=None)
        with patch.object(Path,'home',return_value=home):
            scheduler.command(e,args,Path(r.__file__).resolve())
            args.authorize_activation='TEST authorization only; fake HOME and mocked launchctl'
            with patch.object(scheduler.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')) as launch:
                for action in ('install','enable','disable','uninstall'):
                    args.mission=action;scheduler.command(e,args,Path(r.__file__).resolve())
                self.assertFalse((home/'Library/LaunchAgents'/f'{scheduler.LABEL}.plist').exists())
                self.assertTrue(launch.called)

if __name__=='__main__': unittest.main()
