import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
import test_runner as baseline
import deferred
import scheduler
r=baseline.r

class DeferredTests(unittest.TestCase):
    setUp=baseline.RunnerTests.setUp
    tearDown=baseline.RunnerTests.tearDown
    state=baseline.RunnerTests.state
    def queued(self):
        provider=baseline.Fake(baseline.response(),baseline.response())
        engine=r.Engine(self.store,provider,lambda *a:subprocess.CompletedProcess([],0,'checked',''))
        due=time.time()+3600
        stamp=datetime.fromtimestamp(due,timezone.utc).isoformat()
        d=dict(name='deferred test',source='HEAD',prompt='bounded test',checks=['compile'],provider='claude',auto_resume_quota=True,quota_probe_authorized=True,max_seconds=86400,max_invocations=6,max_retries=1,max_failures=4)
        self.definition.write_text(json.dumps(d))
        with self.store.lock():m=deferred.enqueue(engine,self.definition,self.repo,stamp)
        return engine,m,provider,due,stamp
    def test_registration_and_early_ticks_never_call_AI(self):
        e,m,p,due,stamp=self.queued();self.assertEqual(self.state(m),'QUEUED')
        scheduler.tick(e);e.step(m)
        self.assertFalse(p.calls);self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM quota_signals').fetchone()[0],0)
    def test_due_tick_dispatches_existing_mission(self):
        e,m,p,due,stamp=self.queued()
        with patch.object(deferred.time,'time',return_value=due+1):scheduler.tick(e)
        self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(p.calls,['claude','codex'])
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM missions').fetchone()[0],1)
    def test_restart_and_duplicate_enqueue_do_not_duplicate(self):
        e,m,p,due,stamp=self.queued();self.assertEqual(deferred.enqueue(e,self.definition,self.repo,stamp),m)
        self.store.c.close();self.store=r.Store(self.root/'state/state.sqlite');e=r.Engine(self.store,p,lambda *a:subprocess.CompletedProcess([],0,'',''))
        with patch.object(deferred.time,'time',return_value=due+1):scheduler.tick(e);scheduler.tick(e)
        self.assertEqual(p.calls,['claude','codex']);self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],2)
    def test_modified_schedule_holds(self):
        e,m,p,due,stamp=self.queued();self.store.c.execute('UPDATE scheduled_missions SET not_before=?',(due-1,))
        with patch.object(deferred.time,'time',return_value=due+1):scheduler.tick(e)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(p.calls)
    def test_pause_and_human_hold_are_never_cleared(self):
        e,m,p,due,stamp=self.queued();self.store.c.execute('UPDATE missions SET paused=1 WHERE id=?',(m,))
        with patch.object(deferred.time,'time',return_value=due+1):scheduler.tick(e)
        self.assertFalse(p.calls);self.store.hold(m,'human boundary')
        self.store.c.execute('UPDATE missions SET paused=0 WHERE id=?',(m,))
        with patch.object(deferred.time,'time',return_value=due+1):scheduler.tick(e)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(p.calls)
    def test_expired_original_budget_no_call(self):
        e,m,p,due,stamp=self.queued()
        with patch.object(deferred.time,'time',return_value=due+86400):scheduler.tick(e)
        self.assertEqual(self.state(m),'FAILED');self.assertFalse(p.calls)
    def test_unknown_dirty_worktree_no_call(self):
        e,m,p,due,stamp=self.queued();work=Path(self.store.c.execute('SELECT worktree FROM missions').fetchone()[0]);(work/'unknown').write_text('changed')
        with patch.object(deferred.time,'time',return_value=due+1):scheduler.tick(e)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(p.calls)

if __name__=='__main__':unittest.main()
