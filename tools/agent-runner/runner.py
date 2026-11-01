#!/usr/bin/env python3
"""Local, fail-closed sequential agent orchestration (Python standard library)."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

SCHEMA = {'type':'object','properties':{'status':{'type':'string','enum':['done','repair','approval','limited']},'summary':{'type':'string'},'findings':{'type':'array','items':{'type':'string'}}},'required':['status','summary','findings'],'additionalProperties':False}
STATES = {'QUEUED','RUNNING','VALIDATING','COMPLETED','RETRYABLE_FAILURE','PROVIDER_LIMITED','WAITING_APPROVAL','FAILED','CANCELLED'}
CHECKS = {'compile': ['{python}','-m','compileall','-q','app'], 'pytest':['{python}','-m','pytest','-q'], 'acceptance':['{python}','scripts/local_acceptance.py']}
DDL = '''
CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,state TEXT,definition TEXT,worktree TEXT,started REAL,paused INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,mission TEXT,provider TEXT,state TEXT,kind TEXT,prompt TEXT,retries INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,task INTEGER,provider TEXT,state TEXT,started REAL,duration REAL,exit_code INTEGER,result TEXT,usage TEXT,error TEXT,pid INTEGER);
CREATE TABLE IF NOT EXISTS availability(provider TEXT PRIMARY KEY,available INTEGER,reason TEXT,retry_at REAL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,mission TEXT,at REAL,event TEXT,detail TEXT);
CREATE TABLE IF NOT EXISTS tests(id INTEGER PRIMARY KEY,mission TEXT,attempt INTEGER,name TEXT,passed INTEGER,exit_code INTEGER,output TEXT);
CREATE TABLE IF NOT EXISTS handoffs(id INTEGER PRIMARY KEY,mission TEXT,from_attempt INTEGER,to_task INTEGER,payload TEXT);
CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY,mission TEXT,reason TEXT,approved INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS commits(id INTEGER PRIMARY KEY,mission TEXT,sha TEXT,attempt INTEGER);
'''

def run(args, cwd=None, **kwargs):
    return subprocess.run(args,cwd=cwd,text=True,capture_output=True,**kwargs)

def git(root,*args):
    r=run(['git',*args],root)
    if r.returncode: raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()

class Hold(Exception): pass

class Store:
    def __init__(self,path):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.c=sqlite3.connect(self.path,timeout=10,isolation_level=None);self.c.row_factory=sqlite3.Row
        self.c.execute('PRAGMA journal_mode=WAL');self.c.executescript(DDL)
    def event(self,m,event,detail=''):
        self.c.execute('INSERT INTO events(mission,at,event,detail) VALUES(?,?,?,?)',(m,time.time(),event,str(detail)))
    def state(self,m,state):
        assert state in STATES
        self.c.execute('UPDATE missions SET state=? WHERE id=?',(state,m));self.event(m,state)
    def hold(self,m,why):
        self.c.execute('INSERT INTO approvals(mission,reason) VALUES(?,?)',(m,why));self.state(m,'WAITING_APPROVAL');self.event(m,'approval_required',why)
    @contextlib.contextmanager
    def lock(self):
        with open(str(self.path)+'.lock','a') as f:
            try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise Hold('another runner owns this state/worktree')
            try: yield
            finally: fcntl.flock(f,fcntl.LOCK_UN)


def profile(worktree,scratch,network=True):
    if sys.platform!='darwin' or not shutil.which('sandbox-exec'): raise Hold('macOS sandbox-exec required; no unrestricted fallback')
    def q(p): return json.dumps(str(Path(p).resolve()))
    paths={Path(sys.executable).resolve().parent.parent,Path(shutil.which('node') or '/usr/bin').resolve().parent.parent}
    for cli in ('claude','codex'):
        found=shutil.which(cli)
        if found: paths.add(Path(found).resolve().parent.parent)
    # Deny all user-home reads; explicitly open only this task and installed runtime.
    text='(version 1)(allow default)(deny file-read*)(allow file-read* (literal "/"))(allow file-read-metadata)(deny file-write*)'
    for system in ('/usr','/bin','/sbin','/System','/Library','/opt/homebrew','/private/etc','/private/var/db','/dev'):
        text+=f'(allow file-read* (subpath {q(system)}))'
    for flag in ('--git-dir','--git-common-dir'):
        path=Path(git(worktree,'rev-parse',flag))
        paths.add(path if path.is_absolute() else Path(worktree)/path)
    for path in paths|{Path(worktree),Path(scratch)}: text+=f'(allow file-read* (subpath {q(path)}))'
    for path in (worktree,scratch): text+=f'(allow file-write* (subpath {q(path)}))'
    text+='(allow file-write* (literal "/dev/null") (literal "/dev/tty"))'
    if not network: text+='(deny network*)'
    return text


def isolation_probe(worktree,scratch):
    # Verify positive execution AND negative access, not just CLI availability.
    forbidden=Path.home()/('.agent-runner-probe-'+uuid.uuid4().hex)
    forbidden.write_text('canary')
    try:
        script='import pathlib,sys; p=pathlib.Path(sys.argv[1]);\ntry: p.read_text()\nexcept PermissionError: pass\nelse: sys.exit(7)\ntry: p.write_text("bad")\nexcept PermissionError: pass\nelse: sys.exit(8)\nprint("isolated")'
        r=run(['sandbox-exec','-p',profile(worktree,scratch),sys.executable,'-c',script,str(forbidden)])
        if r.returncode or 'isolated' not in r.stdout: raise Hold('OS isolation probe failed: '+r.stderr[-500:])
    finally: forbidden.unlink(missing_ok=True)


class CLIProvider:
    def execute(self,provider,worktree,prompt,timeout,scratch):
        scratch=Path(scratch);home=scratch/'home';home.mkdir(exist_ok=True)
        (home/'.codex').mkdir(exist_ok=True);(home/'.claude').mkdir(exist_ok=True)
        # Provider authentication only. Never inherit shell tokens or production credentials.
        auth=Path.home()/'.codex/auth.json'
        if auth.exists():
            shutil.copyfile(auth,home/'.codex/auth.json');os.chmod(home/'.codex/auth.json',0o600)
        env={k:os.environ[k] for k in ('PATH','LANG','TERM','TMPDIR') if k in os.environ}
        env.update(HOME=str(home),CODEX_HOME=str(home/'.codex'),CLAUDE_CONFIG_DIR=str(home/'.claude'),DISABLE_AUTOUPDATER='1')
        schema=scratch/'schema.json';schema.write_text(json.dumps(SCHEMA));output=scratch/'result.json'
        empty=scratch/'mcp.json';empty.write_text('{"mcpServers":{}}')
        if provider=='claude':
            credential=run(['security','find-generic-password','-s','Claude Code-credentials','-w'])
            if credential.returncode==0:
                try:
                    token=json.loads(credential.stdout).get('claudeAiOauth',{}).get('accessToken')
                    if token: env['CLAUDE_CODE_OAUTH_TOKEN']=token
                except ValueError: pass
            args=['claude','-p','--output-format','json','--json-schema',json.dumps(SCHEMA),'--setting-sources','project','--strict-mcp-config','--mcp-config',str(empty),'--permission-mode','dontAsk','--tools','Read,Grep,Glob,Edit,Write,Agent','--allowedTools','Read,Grep,Glob,Edit,Write,Agent','--no-session-persistence','--max-budget-usd','1',prompt]
        else:
            args=['codex','exec','--ignore-user-config','--ignore-rules','-c','approval_policy="never"','-c','shell_environment_policy.inherit="none"','--sandbox','workspace-write','--ephemeral','--json','--output-schema',str(schema),'--output-last-message',str(output),'-C',str(worktree),prompt]
        args=['sandbox-exec','-p',profile(worktree,scratch),*args]
        start=time.monotonic()
        proc=subprocess.Popen(args,cwd=worktree,env=env,text=True,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        if getattr(self,'on_start',None): self.on_start(proc.pid)
        deadline=time.monotonic()+timeout
        try:
            while True:
                if getattr(self,'control',lambda:False)(): raise Hold('operator pause/stop requested')
                remaining=deadline-time.monotonic()
                if remaining<=0: raise subprocess.TimeoutExpired(args,timeout)
                try:
                    stdout,stderr=proc.communicate(timeout=min(.5,remaining));break
                except subprocess.TimeoutExpired: pass
        except BaseException:
            os.killpg(proc.pid,signal.SIGTERM)
            try: proc.communicate(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(proc.pid,signal.SIGKILL);proc.communicate()
            raise
        usage={};result=None;limited=False;error=stderr[-2000:]
        try:
            if provider=='claude':
                envelope=json.loads(stdout);usage={k:envelope[k] for k in ('usage','total_cost_usd') if k in envelope}
                result=envelope.get('structured_output')
                # Only documented machine error codes; unknown nonzero exits are not limits.
                limited=envelope.get('error')=='rate_limit_error'
                if envelope.get('is_error'): error=str(envelope.get('result','provider error'))[-2000:]
            else:
                for line in stdout.splitlines():
                    e=json.loads(line)
                    if e.get('type')=='turn.completed': usage=e.get('usage',{})
                    err=e.get('error',{})
                    if isinstance(err,dict) and err.get('code') in ('usage_limit_reached','rate_limit_exceeded'): limited=True
                if output.exists(): result=json.loads(output.read_text())
        except (ValueError,TypeError): error='malformed provider JSON'
        valid=isinstance(result,dict) and set(result)=={'status','summary','findings'} and result['status'] in ('done','repair','approval','limited') and isinstance(result['summary'],str) and isinstance(result['findings'],list) and all(isinstance(x,str) for x in result['findings'])
        if not valid: error+='; structured output missing/invalid; events: '+stdout[-4000:]
        return dict(exit_code=proc.returncode,result=result if valid else None,usage=usage,error=error,duration=time.monotonic()-start,limited=limited)

class Engine:
    def __init__(self,store,provider=None,validator=None):
        self.s=store;self.c=store.c;self.provider=provider or CLIProvider();self.validator=validator
    def task(self,m,p,kind,prompt,retries=0):
        return self.c.execute('INSERT INTO tasks(mission,provider,state,kind,prompt,retries) VALUES(?,?,\'QUEUED\',?,?,?)',(m,p,kind,prompt,retries)).lastrowid
    def start(self,definition,repo):
        d=json.loads(Path(definition).read_text())
        allowed={'name','source','prompt','checks','max_invocations','max_retries','max_failures','max_seconds','max_concurrent','provider','fallback','approval_required','python','max_cost_usd'}
        if set(d)-allowed: raise Hold('unknown mission options')
        if not all(x in CHECKS for x in d.get('checks',[])): raise Hold('validation command outside allowlist')
        if d.get('max_concurrent',1)!=1: raise Hold('single-writer implementation supports max_concurrent=1 only')
        if d.get('max_cost_usd') is not None: raise Hold('cross-provider hard monetary cap cannot be verified; use invocation/time limits')
        if d.get('provider','claude') not in ('claude','codex'): raise Hold('invalid provider')
        if git(repo,'status','--porcelain'): raise Hold('dirty source worktree: commit or isolate before starting')
        m=uuid.uuid4().hex[:12];work=self.s.path.parent/'worktrees'/m;work.parent.mkdir(exist_ok=True)
        git(repo,'worktree','add','-b','runner/'+m,str(work),d['source'])
        self.c.execute('INSERT INTO missions(id,state,definition,worktree,started) VALUES(?,\'QUEUED\',?,?,?)',(m,json.dumps(d),str(work),time.time()))
        self.task(m,d.get('provider','claude'),'implement',d['prompt']);self.s.event(m,'created',d['name'])
        return m
    def recover(self,m):
        # Unknown child state is never automatically re-executed. Operator must inspect preserved worktree.
        running=self.c.execute("SELECT id FROM attempts WHERE task IN (SELECT id FROM tasks WHERE mission=?) AND state='RUNNING'",(m,)).fetchall()
        if running:
            for a in running: self.c.execute("UPDATE attempts SET state='FAILED',error='interrupted; execution outcome unknown' WHERE id=?",(a['id'],))
            self.s.hold(m,'interrupted attempt; inspect preserved worktree and terminate orphan CLI before approval')
            return False
        return True
    def validate(self,m,a,work,d):
        ok=True
        for name in d.get('checks',[]):
            if self.validator: r=self.validator(name,work)
            else:
                # No arbitrary shell commands. Reviewed repository code still executes in OS sandbox, offline.
                python=Path(d.get('python',sys.executable)).resolve()
                if not python.is_file(): raise Hold('validation Python unavailable')
                with tempfile.TemporaryDirectory(prefix='runner-check-') as tmp:
                    args=[x.replace('{python}',str(python)) for x in CHECKS[name]]
                    remaining=d.get('max_seconds',600)-(time.time()-self.c.execute('SELECT started FROM missions WHERE id=?',(m,)).fetchone()[0])
                    if remaining<=0: raise Hold('mission duration exhausted')
                    r=run(['sandbox-exec','-p',profile(work,tmp,False),*args],work,timeout=min(120,remaining))
            self.c.execute('INSERT INTO tests(mission,attempt,name,passed,exit_code,output) VALUES(?,?,?,?,?,?)',(m,a,name,int(r.returncode==0),r.returncode,(r.stdout+r.stderr)[-12000:]));ok &= r.returncode==0
        return ok and bool(d.get('checks'))
    def step(self,m):
        row=self.c.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone();d=json.loads(row['definition']);work=Path(row['worktree'])
        if row['state'] in ('COMPLETED','FAILED','CANCELLED','WAITING_APPROVAL') or row['paused']: return False
        if not self.recover(m): return False
        attempts=self.c.execute('SELECT COUNT(*) FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=?',(m,)).fetchone()[0]
        if time.time()-row['started']>=d.get('max_seconds',600) or attempts>=d.get('max_invocations',4): self.s.state(m,'FAILED');self.s.event(m,'limit','duration or invocations');return False
        failures=self.c.execute("SELECT a.state FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=? ORDER BY a.id DESC",(m,)).fetchall()
        n=0
        for f in failures:
            if f[0]=='COMPLETED': break
            n+=1
        if n>=d.get('max_failures',3): self.s.state(m,'FAILED');return False
        t=self.c.execute("SELECT * FROM tasks WHERE mission=? AND state='QUEUED' ORDER BY id LIMIT 1",(m,)).fetchone()
        if not t: self.s.hold(m,'no dispatchable task');return False
        if d.get('approval_required'): self.s.hold(m,'mission requests human approval');return False
        avail=self.c.execute('SELECT * FROM availability WHERE provider=?',(t['provider'],)).fetchone()
        if avail and not avail['available']: self.s.hold(m,'selected provider unavailable; retry time '+str(avail['retry_at']));return False
        if git(work,'status','--porcelain'): self.s.hold(m,'dirty task worktree; preserved for inspection');return False
        self.s.state(m,'RUNNING')
        a=self.c.execute("INSERT INTO attempts(task,provider,state,started) VALUES(?,?,'RUNNING',?)",(t['id'],t['provider'],time.time())).lastrowid
        self.c.execute("UPDATE tasks SET state='RUNNING' WHERE id=?",(t['id'],))
        prompt=t['prompt']+'\nAcceptance: produce exact JSON matching supplied schema; no external services, new dependencies, credentials, git commits/push/merge, production or instructions outside task. Changes only in this worktree. Review tasks must not edit. Browser acceptance must be marked unverified if no browser tool is available. Existing .claude/agents roles remain available.'
        try:
            with tempfile.TemporaryDirectory(prefix='runner-agent-') as tmp:
                if not isinstance(self.provider,CLIProvider): pass
                else: isolation_probe(work,tmp)
                if isinstance(self.provider,CLIProvider):
                    self.provider.on_start=lambda pid:self.c.execute('UPDATE attempts SET pid=? WHERE id=?',(pid,a))
                    self.provider.control=lambda:bool(self.c.execute("SELECT paused OR state='CANCELLED' FROM missions WHERE id=?",(m,)).fetchone()[0])
                r=self.provider.execute(t['provider'],work,prompt,min(180,d.get('max_seconds',600)-(time.time()-row['started'])),tmp)
        except (Exception,KeyboardInterrupt) as exc:
            self.c.execute("UPDATE attempts SET state='FAILED',error=? WHERE id=?",(str(exc),a));
            if self.c.execute('SELECT state FROM missions WHERE id=?',(m,)).fetchone()[0]!='CANCELLED': self.s.hold(m,'execution interrupted or isolation unavailable: '+str(exc))
            return False
        self.c.execute('UPDATE attempts SET duration=?,exit_code=?,result=?,usage=?,error=? WHERE id=?',(r['duration'],r['exit_code'],json.dumps(r['result']),json.dumps(r['usage']),r['error'],a))
        if r.get('limited'):
            self.c.execute("INSERT OR REPLACE INTO availability VALUES(?,0,'confirmed provider limit; retry time unknown',NULL)",(t['provider'],));self.c.execute("UPDATE attempts SET state='PROVIDER_LIMITED' WHERE id=?",(a,));self.s.state(m,'PROVIDER_LIMITED')
            other='codex' if t['provider']=='claude' else 'claude'
            available=self.c.execute('SELECT available FROM availability WHERE provider=?',(other,)).fetchone()
            if d.get('fallback',False) and (not available or available[0]):
                if git(work,'status','--porcelain'): self.s.hold(m,'limited provider left uncommitted work; preserved');return False
                self.c.execute("UPDATE tasks SET state='PROVIDER_LIMITED' WHERE id=?",(t['id'],));self.task(m,other,t['kind'],t['prompt'],t['retries']);return True
            self.s.hold(m,'provider limited; no permitted available fallback');return False
        control=self.c.execute('SELECT state,paused FROM missions WHERE id=?',(m,)).fetchone()
        if control['state']=='CANCELLED' or control['paused']:
            self.c.execute("UPDATE attempts SET state='FAILED',error='operator stopped or paused after bounded invocation' WHERE id=?",(a,))
            if control['state']!='CANCELLED': self.s.hold(m,'paused invocation outcome preserved; inspect before continuing')
            return False
        if r['exit_code'] and ('Not logged in' in r.get('error','') or 'authentication' in r.get('error','').lower()):
            self.c.execute("UPDATE attempts SET state='FAILED' WHERE id=?",(a,))
            self.c.execute("UPDATE tasks SET state='WAITING_APPROVAL' WHERE id=?",(t['id'],))
            self.s.hold(m,'provider authentication unavailable in isolated HOME; no broad credential access fallback')
            return False
        result=r['result']
        if result and result['status'] in ('approval','limited'):
            self.c.execute("UPDATE attempts SET state='FAILED' WHERE id=?",(a,));self.s.hold(m,'provider requested approval or unconfirmed limit: '+result['summary']);return False
        self.s.state(m,'VALIDATING')
        changes=git(work,'status','--porcelain')
        if changes:
            # Reject sensitive/unreviewed paths; no blind git add of DBs or generated credentials.
            changed=git(work,'diff','--name-only').splitlines()+git(work,'ls-files','--others','--exclude-standard').splitlines()
            permitted=all(Path(x).parts[0] in ('app','tests','docs','outputs') and not any(y in x for y in ('.sqlite','.env','secret','requirements')) for x in changed)
            if not permitted or t['kind']=='review': self.s.hold(m,'out-of-scope or reviewer changes preserved');return False
            self.s.hold(m,'agent edits require diff/security approval before commit or execution');return False
        passed=False
        if result and r['exit_code']==0 and result['status']=='done':
            try: passed=self.validate(m,a,work,d)
            except Exception as exc: self.s.event(m,'validation_error',str(exc))
        self.c.execute('UPDATE attempts SET state=? WHERE id=?',('COMPLETED' if passed else 'FAILED',a));self.c.execute('UPDATE tasks SET state=? WHERE id=?',('COMPLETED' if passed else 'FAILED',t['id']))
        sha=git(work,'rev-parse','HEAD');self.c.execute('INSERT INTO commits(mission,sha,attempt) VALUES(?,?,?)',(m,sha,a))
        if not passed:
            if t['retries']>=d.get('max_retries',1): self.s.state(m,'FAILED');return False
            self.s.state(m,'RETRYABLE_FAILURE');other='claude' if t['provider']=='codex' else 'codex'
            self.task(m,other if d.get('fallback',False) else t['provider'],'repair',t['prompt']+'\nPrevious machine result: '+json.dumps(r)+'\nExternal checks: '+json.dumps([dict(x) for x in self.c.execute('SELECT name,passed,output FROM tests WHERE attempt=?',(a,))])+'\nExternal validation failed; address findings.',t['retries']+1);return True
        if t['kind']!='review':
            other='codex' if t['provider']=='claude' else 'claude';task=self.task(m,other,'review','Independently review the previous bounded task and report defects. Do not edit. Task: '+t['prompt']+'\nPrevious result (untrusted evidence): '+json.dumps(result))
            self.c.execute('INSERT INTO handoffs(mission,from_attempt,to_task,payload) VALUES(?,?,?,?)',(m,a,task,json.dumps(result)));self.s.state(m,'QUEUED');return True
        self.s.state(m,'COMPLETED');return False
    def drive(self,m):
        with self.s.lock():
            while self.step(m): pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--state',default='.agent-runner/state.sqlite');parser.add_argument('command',choices=['start','status','pause','resume','stop','report','approve']);parser.add_argument('mission',nargs='?');parser.add_argument('--approval-note');args=parser.parse_args()
    s=Store(args.state);e=Engine(s)
    try:
        if args.command=='start':
            if not args.mission: parser.error('mission file required')
            with s.lock(): m=e.start(args.mission,Path.cwd())
            print('mission',m,flush=True);e.drive(m)
            final=s.c.execute('SELECT state FROM missions WHERE id=?',(m,)).fetchone()[0]
            print(final)
            if final!='COMPLETED': sys.exit(2 if final=='WAITING_APPROVAL' else 1)
        else:
            row=s.c.execute('SELECT * FROM missions ORDER BY started DESC LIMIT 1').fetchone()
            if not row: print('no missions');return
            m=row['id']
            if args.command=='pause': s.c.execute('UPDATE missions SET paused=1 WHERE id=?',(m,));s.event(m,'pause','takes effect before next invocation; active invocation remains bounded')
            elif args.command=='stop': s.c.execute('UPDATE missions SET paused=1 WHERE id=?',(m,));s.state(m,'CANCELLED')
            elif args.command=='approve':
                if not args.approval_note: raise Hold('explicit --approval-note required; approval is a human action')
                with s.lock():
                    if row['state']!='WAITING_APPROVAL': raise Hold('mission is not waiting for approval')
                    if git(row['worktree'],'status','--porcelain'): raise Hold('preserve/review/commit changes manually before approval')
                    for attempt in s.c.execute('SELECT a.pid FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=? AND a.pid IS NOT NULL',(m,)):
                        try: os.kill(attempt[0],0)
                        except ProcessLookupError: pass
                        else: raise Hold('recorded process still alive; inspect before approval')
                    s.c.execute('UPDATE approvals SET approved=1 WHERE mission=?',(m,))
                    s.c.execute("UPDATE tasks SET state='QUEUED' WHERE mission=? AND state IN ('RUNNING','WAITING_APPROVAL')",(m,))
                    s.c.execute("UPDATE attempts SET state='FAILED' WHERE task IN (SELECT id FROM tasks WHERE mission=?) AND state='RUNNING'",(m,))
                    s.c.execute('UPDATE missions SET paused=0 WHERE id=?',(m,));s.state(m,'QUEUED');s.event(m,'human_approval',args.approval_note)
            elif args.command=='resume':
                if row['state']=='WAITING_APPROVAL': raise Hold('approval boundary: inspect worktree and records; resume does not grant approval')
                s.c.execute('UPDATE missions SET paused=0 WHERE id=?',(m,));e.drive(m)
            print(json.dumps(dict(s.c.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone()),indent=2))
            if args.command=='report':
                print('attempts',json.dumps([dict(x) for x in s.c.execute('SELECT a.* FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=?',(m,))],indent=2))
                for table in ('tasks','events','tests','handoffs','approvals','commits'):
                    print(table,json.dumps([dict(x) for x in s.c.execute(f'SELECT * FROM {table} WHERE mission=?',(m,))],indent=2))
    except Hold as exc: print('WAITING_APPROVAL:',exc,file=sys.stderr);sys.exit(2)

if __name__=='__main__': main()
