import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('runner',Path(__file__).with_name('runner.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def response(status='done',exit_code=0,limited=False):
    return dict(result=None if status=='malformed' else dict(status=status,summary='synthetic',findings=[]),exit_code=exit_code,limited=limited,usage={},error='',duration=.01)
class Fake:
    def __init__(self,*responses): self.responses=list(responses);self.calls=[]
    def execute(self,provider,*args): self.calls.append(provider);return self.responses.pop(0)

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
        for args in (['init'],['config','user.name','Runner Test'],['config','user.email','runner@example.invalid']): r.git(self.repo,*args)
        (self.repo/'file.txt').write_text('test');r.git(self.repo,'add','.');r.git(self.repo,'commit','-m','fixture')
        self.store=r.Store(self.root/'state/state.sqlite');self.definition=self.root/'mission.json'
    def tearDown(self): self.store.c.close();self.tmp.cleanup()
    def setup_engine(self,adapter,validation=True,**options):
        d=dict(name='test',source='HEAD',prompt='review',checks=['compile'],fallback=True,max_failures=10);d.update(options);self.definition.write_text(json.dumps(d))
        engine=r.Engine(self.store,adapter,lambda *a:subprocess.CompletedProcess([],0 if validation else 1,'checked',''))
        m=engine.start(self.definition,self.repo);return engine,m
    def state(self,m): return self.store.c.execute('SELECT state FROM missions WHERE id=?',(m,)).fetchone()[0]
    def test_claude_success_codex_review(self):
        fake=Fake(response(),response());e,m=self.setup_engine(fake);e.drive(m);self.assertEqual(fake.calls,['claude','codex']);self.assertEqual(self.state(m),'COMPLETED');self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM handoffs').fetchone()[0],1)
    def test_codex_failure_claude_repair(self):
        fake=Fake(response(exit_code=1),response(),response());e,m=self.setup_engine(fake,provider='codex');e.drive(m);self.assertEqual(fake.calls,['codex','claude','codex']);self.assertEqual(self.state(m),'COMPLETED')
    def test_claude_limit_takeover(self):
        fake=Fake(response(limited=True),response(),response());e,m=self.setup_engine(fake);e.drive(m);self.assertEqual(fake.calls[:2],['claude','codex']);self.assertEqual(self.state(m),'WAITING_APPROVAL') # unavailable Claude cannot review
    def test_codex_limit_safe_hold(self):
        e,m=self.setup_engine(Fake(response(limited=True)),provider='codex',fallback=False);e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
    def test_crash_recovery(self):
        e,m=self.setup_engine(Fake());task=self.store.c.execute('SELECT id FROM tasks').fetchone()[0];self.store.c.execute("INSERT INTO attempts(task,provider,state) VALUES(?,'claude','RUNNING')",(task,));e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
    def test_restart_without_duplication(self):
        fake=Fake(response(),response());e,m=self.setup_engine(fake);self.assertTrue(e.step(m));self.store.c.close();self.store=r.Store(self.root/'state/state.sqlite');r.Engine(self.store,fake,lambda *a:subprocess.CompletedProcess([],0,'','')).drive(m);self.assertEqual(fake.calls,['claude','codex']);self.assertEqual(self.state(m),'COMPLETED')
    def test_dirty_worktree_hold(self):
        fake=Fake();e,m=self.setup_engine(fake);work=Path(self.store.c.execute('SELECT worktree FROM missions').fetchone()[0]);(work/'dirty').write_text('x');e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertFalse(fake.calls)
    def test_failed_validation_bounded(self):
        fake=Fake(response(),response());e,m=self.setup_engine(fake,False,max_retries=1);e.drive(m);self.assertEqual(len(fake.calls),2);self.assertEqual(self.state(m),'FAILED')
    def test_both_unavailable(self):
        e,m=self.setup_engine(Fake());self.store.c.executemany('INSERT INTO availability VALUES(?,0,?,NULL)',[('claude','limit'),('codex','limit')]);e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
    def test_approval(self):
        fake=Fake();e,m=self.setup_engine(fake,approval_required=True);e.drive(m);self.assertFalse(fake.calls);self.assertEqual(self.state(m),'WAITING_APPROVAL')
    def test_malformed(self):
        fake=Fake(response('malformed'));e,m=self.setup_engine(fake,max_retries=0);e.drive(m);self.assertEqual(self.state(m),'FAILED')
    def test_max_attempts(self):
        fake=Fake(response());e,m=self.setup_engine(fake,max_invocations=1);e.drive(m);self.assertEqual(self.state(m),'FAILED');self.assertEqual(len(fake.calls),1)
    def test_validated_edits_committed(self):
        class Edit(Fake):
            def execute(self,provider,*args):
                if not self.calls:
                    path=Path(args[0])/'app';path.mkdir();(path/'safe.py').write_text('value = 1\n')
                return super().execute(provider,*args)
        fake=Edit(response(),response());e,m=self.setup_engine(fake,allow_edits=True);e.drive(m)
        self.assertEqual(self.state(m),'COMPLETED')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM commits').fetchone()[0],2)
    def test_limited_dirty_checkpoint_takeover(self):
        class LimitedEdit(Fake):
            def execute(self,provider,*args):
                if not self.calls:
                    path=Path(args[0])/'app';path.mkdir();(path/'partial.py').write_text('value = 1\n')
                return super().execute(provider,*args)
        fake=LimitedEdit(response(limited=True),response());e,m=self.setup_engine(fake,allow_edits=True);e.drive(m)
        self.assertEqual(fake.calls,['claude','codex']);self.assertEqual(self.state(m),'WAITING_APPROVAL')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM handoffs').fetchone()[0],2)
    def limited_edit(self,provider='claude',validation=True):
        class LimitedEdit(Fake):
            def execute(self,p,*args):
                if not self.calls:
                    path=Path(args[0])/'app';path.mkdir();(path/'partial.py').write_text('value = 1\n')
                return super().execute(p,*args)
        fake=LimitedEdit(response(limited=True),response(),response())
        e,m=self.setup_engine(fake,validation,provider=provider,allow_edits=True,review_fallback=True)
        return e,m,fake
    def test_failed_checkpoint_no_commit_or_handoff(self):
        e,m,fake=self.limited_edit(validation=False);e.drive(m)
        self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(len(fake.calls),1)
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM commits').fetchone()[0],0)
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM handoffs').fetchone()[0],0)
        self.assertEqual(self.store.c.execute('SELECT phase FROM checkpoints').fetchone()[0],'PRESERVED')
    def test_reverse_validated_checkpoint(self):
        e,m,fake=self.limited_edit('codex');e.drive(m)
        self.assertEqual(fake.calls,['codex','claude','claude']);self.assertEqual(self.state(m),'COMPLETED')
    def test_restart_at_each_checkpoint_boundary(self):
        for phase in ['PRESERVED','VALIDATED','GIT_COMMITTED','COMMITTED','HANDED_OFF']:
            with self.subTest(phase=phase):
                self.store.c.execute('DELETE FROM availability')
                e,m,fake=self.limited_edit()
                def crash(at):
                    if at==phase: raise SystemExit('synthetic process death')
                e.checkpoint_hook=crash
                with self.assertRaises(SystemExit): e.step(m)
                self.store.c.close();self.store=r.Store(self.root/'state/state.sqlite')
                resumed=r.Engine(self.store,fake,lambda *a:subprocess.CompletedProcess([],0,'checked',''))
                resumed.drive(m);self.assertEqual(self.state(m),'COMPLETED')
                self.assertEqual(fake.calls,['claude','codex','codex'])
                work=Path(self.store.c.execute('SELECT worktree FROM missions WHERE id=?',(m,)).fetchone()[0])
                self.assertEqual((work/'app/partial.py').read_text(),'value = 1\n')
                self.assertEqual(len(r.git(work,'log','--format=%s','--grep=Runner validated checkpoint').splitlines()),1)
    def test_changed_preserved_checkpoint_holds(self):
        e,m,fake=self.limited_edit()
        def crash(phase): raise SystemExit('crash')
        e.checkpoint_hook=crash
        with self.assertRaises(SystemExit):e.step(m)
        work=Path(self.store.c.execute('SELECT worktree FROM missions WHERE id=?',(m,)).fetchone()[0]);(work/'app/partial.py').write_text('unexpected change')
        r.Engine(self.store,fake).drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL');self.assertEqual(len(fake.calls),1)
    def test_validation_mutating_checkpoint_holds(self):
        e,m,fake=self.limited_edit()
        def mutate(name,work):
            (work/'app/partial.py').write_text('changed during checks')
            return subprocess.CompletedProcess([],0,'','')
        e.validator=mutate;e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
        self.assertEqual(self.store.c.execute('SELECT COUNT(*) FROM handoffs').fetchone()[0],0)

    def test_recorded_api429_recovery(self):
        e,m=self.setup_engine(Fake());task=self.store.c.execute('SELECT id FROM tasks').fetchone()[0]
        error='; events: '+json.dumps({'is_error':True,'api_error_status':429})
        self.store.c.execute("INSERT INTO attempts(task,provider,state,error) VALUES(?,'claude','FAILED',?)",(task,error))
        self.store.c.close();self.store=r.Store(self.root/'state/state.sqlite')
        self.assertEqual(self.store.c.execute("SELECT available FROM availability WHERE provider='claude'").fetchone()[0],0)
    def test_invalid_terminal_transition(self):
        e,m=self.setup_engine(Fake(response(),response()));e.drive(m)
        with self.assertRaises(r.Hold):self.store.state(m,'RUNNING')
    def test_execution_crash_holds(self):
        class Crash(Fake):
            def execute(self,*args): raise RuntimeError('synthetic process crash')
        e,m=self.setup_engine(Crash());e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
    def test_duration_limit(self):
        fake=Fake();e,m=self.setup_engine(fake,max_seconds=0);e.drive(m);self.assertEqual(self.state(m),'FAILED');self.assertFalse(fake.calls)
    def test_authentication_boundary(self):
        value=response(exit_code=1);value['error']='Not logged in'
        e,m=self.setup_engine(Fake(value));e.drive(m);self.assertEqual(self.state(m),'WAITING_APPROVAL')
    def test_writer_lock(self):
        with self.store.lock():
            with self.assertRaises(r.Hold):
                with self.store.lock(): pass
    def test_dirty_source_refused(self):
        self.definition.write_text(json.dumps(dict(name='x',source='HEAD',prompt='x',checks=['compile'])));(self.repo/'dirty').write_text('x')
        with self.assertRaises(r.Hold):r.Engine(self.store).start(self.definition,self.repo)
    def test_arbitrary_check_refused(self):
        self.definition.write_text(json.dumps(dict(name='x',source='HEAD',prompt='x',checks=['curl evil'])))
        with self.assertRaises(r.Hold):r.Engine(self.store).start(self.definition,self.repo)
    def test_monetary_cap_refused(self):
        self.definition.write_text(json.dumps(dict(name='x',source='HEAD',prompt='x',checks=['compile'],max_cost_usd=2)))
        with self.assertRaises(r.Hold):r.Engine(self.store).start(self.definition,self.repo)

if __name__=='__main__': unittest.main()
