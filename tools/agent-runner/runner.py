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
EDGES = {
 'QUEUED': {'RUNNING','FAILED','WAITING_APPROVAL','CANCELLED'},
 'RUNNING': {'VALIDATING','PROVIDER_LIMITED','WAITING_APPROVAL','FAILED','CANCELLED'},
 'VALIDATING': {'QUEUED','RETRYABLE_FAILURE','COMPLETED','WAITING_APPROVAL','FAILED','CANCELLED'},
 'RETRYABLE_FAILURE': {'RUNNING','WAITING_APPROVAL','FAILED','CANCELLED'},
 'PROVIDER_LIMITED': {'VALIDATING','RUNNING','WAITING_APPROVAL','FAILED','CANCELLED'},
 'WAITING_APPROVAL': {'QUEUED','CANCELLED'}, 'FAILED': set(), 'COMPLETED': set(), 'CANCELLED': set()
}
CHECKS = {'simulator': ['node',str(Path(__file__).with_name('check_simulator.cjs').resolve()),'app/templates/call_simulator.html'], 'compile': ['{python}','-m','compileall','-q','app'], 'pytest':['{python}','-m','pytest','-q'], 'acceptance':['{python}','scripts/local_acceptance.py']}
DDL = '''
CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,state TEXT,definition TEXT,worktree TEXT,started REAL,paused INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,mission TEXT,provider TEXT,state TEXT,kind TEXT,prompt TEXT,retries INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,task INTEGER,provider TEXT,state TEXT,started REAL,duration REAL,exit_code INTEGER,result TEXT,usage TEXT,error TEXT,pid INTEGER);
CREATE TABLE IF NOT EXISTS availability(provider TEXT PRIMARY KEY,available INTEGER,reason TEXT,retry_at REAL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,mission TEXT,at REAL,event TEXT,detail TEXT);
CREATE TABLE IF NOT EXISTS tests(id INTEGER PRIMARY KEY,mission TEXT,attempt INTEGER,name TEXT,passed INTEGER,exit_code INTEGER,output TEXT);
CREATE TABLE IF NOT EXISTS handoffs(id INTEGER PRIMARY KEY,mission TEXT,from_attempt INTEGER,to_task INTEGER,payload TEXT);
CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY,mission TEXT,reason TEXT,approved INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS receipts(attempt INTEGER PRIMARY KEY,digest TEXT,commit_sha TEXT);
CREATE TABLE IF NOT EXISTS deliveries(mission TEXT PRIMARY KEY,commit_sha TEXT,digest TEXT,review_attempt INTEGER,classification TEXT);
CREATE TABLE IF NOT EXISTS imports(source_key TEXT PRIMARY KEY,mission TEXT NOT NULL,digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outcomes(attempt INTEGER PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkpoints(id INTEGER PRIMARY KEY,mission TEXT,attempt INTEGER UNIQUE,task INTEGER,phase TEXT,base_sha TEXT,digest TEXT,snapshot TEXT,commit_sha TEXT,classification TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_handoff_per_attempt ON handoffs(from_attempt);
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
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.c=sqlite3.connect(self.path,timeout=10,isolation_level=None);self.c.row_factory=sqlite3.Row
        os.chmod(self.path,0o600)
        self.c.execute('PRAGMA journal_mode=WAL');self.c.executescript(DDL)
        # Recover machine evidence from early runner versions without clearing approval holds.
        for row in self.c.execute("SELECT id,provider,error FROM attempts WHERE error LIKE '%; events: %'").fetchall():
            try: envelope=json.loads(row['error'].split('; events: ',1)[1])
            except (ValueError,IndexError): continue
            if envelope.get('is_error') is True and envelope.get('api_error_status')==429:
                self.c.execute("INSERT OR IGNORE INTO availability VALUES(?,0,'confirmed API 429; retry time unknown',NULL)",(row['provider'],))
                self.c.execute("UPDATE attempts SET state='PROVIDER_LIMITED' WHERE id=?",(row['id'],))

    def event(self,m,event,detail=''):
        self.c.execute('INSERT INTO events(mission,at,event,detail) VALUES(?,?,?,?)',(m,time.time(),event,str(detail)))
    def state(self,m,state):
        assert state in STATES
        previous=self.c.execute('SELECT state FROM missions WHERE id=?',(m,)).fetchone()[0]
        if state!=previous and state not in EDGES[previous]: raise Hold(f'invalid or concurrent transition {previous} -> {state}')
        changed=self.c.execute('UPDATE missions SET state=? WHERE id=? AND state=?',(state,m,previous)).rowcount
        if not changed: raise Hold('concurrent operator state change')
        self.event(m,state)
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
    if not network: text+='(deny network*)(allow network-outbound (remote ip "localhost:*"))(allow network-bind (local ip "localhost:*"))(allow network-inbound (local ip "localhost:*"))'
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


def codex_options(worktree,scratch):
    roots={'/':'deny', ':minimal':'read', str(Path(worktree).resolve()):'write', str(Path(scratch).resolve()):'write', '/opt/homebrew':'read'}
    for flag in ('--git-dir','--git-common-dir'):
        value=Path(git(worktree,'rev-parse',flag));roots[str(value.resolve() if value.is_absolute() else (Path(worktree)/value).resolve())]='read'
    for command in ('node','codex'):
        found=shutil.which(command)
        if found: roots[str(Path(found).resolve().parent.parent)]='read'
    table='{'+','.join(json.dumps(k)+'='+json.dumps(v) for k,v in roots.items())+'}'
    return ['-c','default_permissions="runner"','-c','permissions.runner.filesystem='+table,'-c','permissions.runner.network.enabled=false']


def codex_probe(worktree,scratch,env):
    forbidden=Path.home()/('.agent-runner-probe-'+uuid.uuid4().hex);forbidden.write_text('canary')
    try:
        script='import pathlib,sys; p=pathlib.Path(sys.argv[1]);\ntry: p.read_text()\nexcept PermissionError: pass\nelse: sys.exit(7)\ntry: p.write_text("bad")\nexcept PermissionError: pass\nelse: sys.exit(8)\nprint("isolated")'
        result=run(['codex','sandbox',*codex_options(worktree,scratch),'-P','runner','-C',str(worktree),sys.executable,'-c',script,str(forbidden)],env=env,timeout=20)
        if result.returncode or 'isolated' not in result.stdout: raise Hold('native Codex read/write isolation probe failed: '+result.stderr[-1000:])
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
            args=['codex','exec','--ignore-user-config','--ignore-rules','--disable','apps','--disable','browser_use','--disable','computer_use','-c','approval_policy="never"','-c','shell_environment_policy.inherit="none"','--ephemeral','--json','--output-schema',str(schema),'--output-last-message',str(output),'-C',str(worktree),prompt]
        if provider=='claude': args=['sandbox-exec','-p',profile(worktree,scratch),*args]
        else:
            codex_probe(worktree,scratch,env)
            args=args[:2]+codex_options(worktree,scratch)+args[2:]
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
                limited=envelope.get('error')=='rate_limit_error' or (envelope.get('is_error') is True and envelope.get('api_error_status')==429)
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
    def start(self,definition,repo,mission_id=None):
        d=json.loads(Path(definition).read_text())
        allowed={'name','source','prompt','checks','max_invocations','max_retries','max_failures','max_seconds','max_concurrent','provider','fallback','approval_required','python','max_cost_usd','allow_edits','review_fallback','checkpoint_checks'}
        if set(d)-allowed: raise Hold('unknown mission options')
        if not all(x in CHECKS for x in d.get('checkpoint_checks',d.get('checks',[]))): raise Hold('checkpoint command outside allowlist')
        if not all(x in CHECKS for x in d.get('checks',[])): raise Hold('validation command outside allowlist')
        if d.get('max_concurrent',1)!=1: raise Hold('single-writer implementation supports max_concurrent=1 only')
        if d.get('max_cost_usd') is not None: raise Hold('cross-provider hard monetary cap cannot be verified; use invocation/time limits')
        if d.get('provider','claude') not in ('claude','codex'): raise Hold('invalid provider')
        if git(repo,'status','--porcelain'): raise Hold('dirty source worktree: commit or isolate before starting')
        m=mission_id or uuid.uuid4().hex[:12];work=self.s.path.parent/'worktrees'/m;work.parent.mkdir(exist_ok=True)
        git(repo,'worktree','add','-b','runner/'+m,str(work),d['source'])
        self.c.execute('INSERT INTO missions(id,state,definition,worktree,started) VALUES(?,\'QUEUED\',?,?,?)',(m,json.dumps(d),str(work),time.time()))
        for unsafe in ('.mcp.json','.claude/settings.json','.claude/settings.local.json','.codex/config.toml'):
            if (work/unsafe).exists():
                self.s.hold(m,'project execution configuration requires review: '+unsafe)
                return m
        self.task(m,d.get('provider','claude'),'implement',d['prompt']);self.s.event(m,'created',d['name'])
        return m
    def checkpoint_files(self,work,d):
        changed=sorted(set(git(work,'diff','--name-only','HEAD').splitlines()+git(work,'ls-files','--others','--exclude-standard').splitlines()))
        if changed and not d.get('allow_edits'): raise Hold('checkpoint edits not authorized')
        import re
        for name in changed:
            path=work/name
            if Path(name).parts[0]!='app' or not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(work.resolve()):
                raise Hold('uncertain/out-of-scope checkpoint file: '+name)
            if any(part.is_symlink() for part in [path,*path.parents] if part!=work.parent):
                raise Hold('symlink in checkpoint path')
            text=path.read_text(errors='replace')
            if re.search(r'-----BEGIN .*PRIVATE KEY|(?:ghp_|sk-live-|sk-proj-)[A-Za-z0-9_-]{16,}',text): raise Hold('possible credential in checkpoint')
        return changed

    def fingerprint(self,work):
        names=set(git(work,'ls-files').splitlines()+git(work,'ls-files','--others','--exclude-standard').splitlines())
        manifest={}
        for name in sorted(names):
            path=work/name
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(work.resolve()): raise Hold('uncertain tracked file: '+name)
            manifest[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        return hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()

    def checkpoint(self,m,a,t,work,d):
        existing=self.c.execute('SELECT * FROM checkpoints WHERE attempt=?',(a,)).fetchone()
        if not existing:
            changed=self.checkpoint_files(work,d);digest=self.fingerprint(work)
            snapshot=self.s.path.parent/'checkpoints'/str(a);snapshot.mkdir(parents=True,exist_ok=True,mode=0o700)
            for name in changed:
                target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((work/name).read_bytes())
            (snapshot/'working.diff').write_text(git(work,'diff','--binary','HEAD'))
            self.c.execute("INSERT INTO checkpoints(mission,attempt,task,phase,base_sha,digest,snapshot,classification) VALUES(?,?,?,'PRESERVED',?,?,?,'incomplete-unverified')",(m,a,t['id'],git(work,'rev-parse','HEAD'),digest,str(snapshot)))
            self.s.event(m,'checkpoint_preserved',digest)
            self.checkpoint_hook('PRESERVED')
        return self.continue_checkpoint(m,a,work,d)

    def checkpoint_hook(self,phase):
        # Fault injection is an in-process test seam, never a mission-defined command.
        pass

    def continue_checkpoint(self,m,a,work,d):
        cp=self.c.execute('SELECT * FROM checkpoints WHERE attempt=?',(a,)).fetchone()
        if cp['phase']=='HANDED_OFF': return True
        if self.fingerprint(work)!=cp['digest']: raise Hold('checkpoint contents changed since preservation/validation')
        task=self.c.execute('SELECT * FROM tasks WHERE id=?',(cp['task'],)).fetchone()
        other='codex' if task['provider']=='claude' else 'claude'
        available=self.c.execute('SELECT available FROM availability WHERE provider=?',(other,)).fetchone()
        if not d.get('fallback') or (available and not available[0]): raise Hold('checkpoint preserved; no permitted available continuation provider')
        if cp['phase']=='PRESERVED':
            if git(work,'rev-parse','HEAD')!=cp['base_sha']: raise Hold('checkpoint base changed before validation')
            self.s.state(m,'VALIDATING')
            checkpoint_policy={**d,'checks':d.get('checkpoint_checks',d.get('checks',[]))}
            self.s.event(m,'checkpoint_validation_policy',json.dumps({'safety_checks':checkpoint_policy['checks'],'completion_checks':d.get('checks',[])}))
            if not self.validate(m,a,work,checkpoint_policy): raise Hold('incomplete checkpoint failed external checks; no commit or handoff')
            if self.fingerprint(work)!=cp['digest']: raise Hold('external checks changed checkpoint contents')
            self.c.execute("UPDATE checkpoints SET phase='VALIDATED',classification='incomplete-checks-passed' WHERE id=?",(cp['id'],));self.checkpoint_hook('VALIDATED')
        cp=self.c.execute('SELECT * FROM checkpoints WHERE attempt=?',(a,)).fetchone()
        if cp['phase']=='VALIDATED':
            if self.fingerprint(work)!=cp['digest']: raise Hold('validated checkpoint changed before commit')
            head=git(work,'rev-parse','HEAD');changed=self.checkpoint_files(work,d)
            if head!=cp['base_sha']:
                if git(work,'log','-1','--format=%s')!=f'Runner validated checkpoint {cp["id"]}' or git(work,'rev-parse','HEAD^')!=cp['base_sha'] or changed:
                    raise Hold('unrecognized Git commit during checkpoint recovery')
            elif changed:
                git(work,'add','--',*changed)
                git(work,'-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','-c','user.name=Local Agent Runner','-c','user.email=runner@example.invalid','commit','-m',f'Runner validated checkpoint {cp["id"]}')
            head=git(work,'rev-parse','HEAD')
            self.checkpoint_hook('GIT_COMMITTED')
            self.c.execute("UPDATE checkpoints SET phase='COMMITTED',commit_sha=? WHERE id=?",(head,cp['id']))
            self.c.execute('INSERT INTO commits(mission,sha,attempt) VALUES(?,?,?)',(m,head,a));self.checkpoint_hook('COMMITTED')
        cp=self.c.execute('SELECT * FROM checkpoints WHERE attempt=?',(a,)).fetchone()
        committed_names=git(work,'ls-tree','-r','--name-only','HEAD').splitlines()
        committed_manifest={name:hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+name],cwd=work)).hexdigest() for name in committed_names}
        committed_digest=hashlib.sha256(json.dumps(committed_manifest,sort_keys=True).encode()).hexdigest()
        if committed_digest!=cp['digest']: raise Hold('committed tree differs from validated checkpoint')
        if git(work,'rev-parse','HEAD')!=cp['commit_sha'] or git(work,'status','--porcelain'): raise Hold('checkpoint commit no longer matches clean worktree')
        self.c.execute('BEGIN IMMEDIATE')
        try:
            payload={'checkpoint':cp['id'],'commit':cp['commit_sha'],'classification':'incomplete-checks-passed','completion_checks_pending':d.get('checks',[]),'retry_at':None}
            next_task=self.task(m,other,task['kind'],task['prompt']+'\nContinue validated but INCOMPLETE checkpoint '+json.dumps(payload)+'. Inspect the saved changes; finish remaining work and report only task-scoped results.',task['retries'])
            self.c.execute("UPDATE tasks SET state='PROVIDER_LIMITED' WHERE id=?",(task['id'],))
            self.c.execute('INSERT INTO handoffs(mission,from_attempt,to_task,payload) VALUES(?,?,?,?)',(m,a,next_task,json.dumps(payload)))
            self.c.execute("UPDATE checkpoints SET phase='HANDED_OFF' WHERE id=?",(cp['id'],));self.s.state(m,'QUEUED')
            self.c.execute('COMMIT')
        except BaseException: self.c.execute('ROLLBACK');raise
        self.checkpoint_hook('HANDED_OFF');return True

    def import_held(self,source_db,source_mission,note,python,repo=None):
        if not note: raise Hold('explicit recovery authorization note required; existing holds are not auto-approved')
        original=sqlite3.connect('file:'+str(Path(source_db).resolve())+'?mode=ro',uri=True);original.row_factory=sqlite3.Row
        try:
            old=original.execute('SELECT * FROM missions WHERE id=?',(source_mission,)).fetchone()
            if not old or old['state']!='WAITING_APPROVAL': raise Hold('source is not a held mission')
            previous=original.execute('SELECT a.*,t.prompt,t.kind FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=? ORDER BY a.id DESC LIMIT 1',(source_mission,)).fetchone()
            try: envelope=json.loads(previous['error'].split('; events: ',1)[1])
            except (ValueError,IndexError,TypeError): raise Hold('no recoverable machine limit evidence')
            if previous['provider']!='claude' or envelope.get('is_error') is not True or envelope.get('api_error_status')!=429: raise Hold('source limit evidence not confirmed API429')
            if previous['pid']:
                try: os.kill(previous['pid'],0)
                except ProcessLookupError: pass
                else: raise Hold('source CLI PID still exists; ownership uncertain')
            origin=Path(old['worktree']);definition=json.loads(old['definition'])
            def common(path):
                value=Path(git(path,'rev-parse','--git-common-dir'));return (value if value.is_absolute() else Path(path)/value).resolve()
            if common(origin)!=common(repo or Path.cwd()): raise Hold('source worktree belongs to a different repository')
            if definition.get('max_concurrent',1)!=1 or definition.get('max_cost_usd') is not None: raise Hold('source resource/isolation policy cannot be honored')
            changed=self.checkpoint_files(origin,definition);digest=self.fingerprint(origin)
            source_key=str(Path(source_db).resolve())+'#'+source_mission
            imported=self.c.execute('SELECT * FROM imports WHERE source_key=?',(source_key,)).fetchone()
            if imported:
                if imported['digest']!=digest: raise Hold('source contents changed since prior recovery import')
                if not self.c.execute('SELECT 1 FROM missions WHERE id=?',(imported['mission'],)).fetchone(): raise Hold('interrupted import construction; source archive preserved, inspect before continuing')
                return imported['mission']
            m=uuid.uuid4().hex[:12]
            self.c.execute('INSERT INTO imports VALUES(?,?,?)',(source_key,m,digest))
            archive=self.s.path.parent/'imports'/m;archive.mkdir(parents=True,mode=0o700)
            backup=sqlite3.connect(archive/'source.sqlite');original.backup(backup);backup.close()
            for name in changed:
                target=archive/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((origin/name).read_bytes())
            head=git(origin,'rev-parse','HEAD');(archive/'working.diff').write_text(git(origin,'diff','--binary','HEAD'))
            definition.update(source=head,python=str(Path(python).absolute()),review_fallback=True,checks=['pytest','acceptance','simulator'],checkpoint_checks=['pytest','acceptance'])
            definition['prompt']+='\nAdditional deterministic completion requirement: uncertain retries must keep BOTH the exact serialized request body and key even if editable fields change; explicit new order after success resets both. Runner independently tests this behavior. Safety-passed checkpoint is incomplete, not feature acceptance.'
            work=self.s.path.parent/'worktrees'/m;work.parent.mkdir(exist_ok=True)
            git(origin,'worktree','add','-b','runner/'+m,str(work),head)
            for name in changed:
                target=work/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((archive/name).read_bytes())
            if self.fingerprint(origin)!=digest or self.fingerprint(work)!=digest: raise Hold('source changed during recovery copy; original preserved')
            self.c.execute("INSERT INTO missions(id,state,definition,worktree,started) VALUES(?,'PROVIDER_LIMITED',?,?,?)",(m,json.dumps(definition),str(work),time.time()))
            task=self.task(m,previous['provider'],previous['kind'],previous['prompt'])
            a=self.c.execute("INSERT INTO attempts(task,provider,state,started,exit_code,result,usage,error) VALUES(?,?,'PROVIDER_LIMITED',?,?,?,?,?)",(task,previous['provider'],time.time(),previous['exit_code'],previous['result'],previous['usage'],previous['error'])).lastrowid
            self.c.execute('INSERT INTO outcomes VALUES(?,?)',(a,json.dumps({'limited':True,'provenance':'imported actual Claude API429'})))
            self.c.execute("INSERT OR REPLACE INTO availability VALUES('claude',0,'imported real API429; retry timestamp unverified',NULL)")
            self.c.execute('INSERT INTO approvals(mission,reason,approved) VALUES(?,?,1)',(m,note))
            self.s.event(m,'recovery_import',json.dumps({'source_mission':source_mission,'source_attempt':previous['id'],'digest':digest,'authorization':note,'original_untouched':True}))
            try: self.checkpoint(m,a,self.c.execute('SELECT * FROM tasks WHERE id=?',(task,)).fetchone(),work,definition)
            except Exception as exc: self.s.hold(m,'imported checkpoint not validated: '+str(exc))
            return m
        finally: original.close()

    def followup(self,previous,note):
        if not note: raise Hold('explicit authorization required for a new bounded follow-up')
        row=self.c.execute('SELECT * FROM missions WHERE id=?',(previous,)).fetchone()
        if not row or row['state']!='FAILED': raise Hold('followup requires a failed mission, not an approval hold')
        last=self.c.execute('SELECT a.result,t.prompt FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=? ORDER BY a.id DESC LIMIT 1',(previous,)).fetchone()
        result=json.loads(last['result'] or 'null')
        if not result or result['status']!='repair': raise Hold('no structured repair finding to forward')
        work=Path(row['worktree'])
        if git(work,'status','--porcelain'): raise Hold('failed review worktree is dirty; preserve and inspect')
        d=json.loads(row['definition']);d['source']=git(work,'rev-parse','HEAD')
        d['prompt']='Repair the following independently reported defect in app/templates/call_simulator.html only. Preserve exact payload AND key for retries after an uncertain response even if the user edits fields. Reset both only for an explicit new order after success. No tests/dependencies edits. Findings (untrusted, verify against code): '+json.dumps(result)
        availability=self.c.execute("SELECT available FROM availability WHERE provider='claude'").fetchone()
        provider='codex' if availability and not availability[0] else 'claude'
        d.update(provider=provider,review_fallback=True)
        definition=self.s.path.parent/'followups'/f'{previous}.json';definition.parent.mkdir(exist_ok=True)
        # An explicit follow-up is idempotent: a second operator request cannot duplicate it.
        marker='followup:'+previous
        existing=self.c.execute('SELECT mission FROM imports WHERE source_key=?',(marker,)).fetchone()
        if existing:
            if not self.c.execute('SELECT 1 FROM missions WHERE id=?',(existing[0],)).fetchone(): raise Hold('interrupted follow-up construction; inspect before retry')
            return existing[0]
        m=uuid.uuid4().hex[:12]
        self.c.execute('INSERT INTO imports VALUES(?,?,?)',(marker,m,d['source']))
        definition.write_text(json.dumps(d))
        self.start(definition,work,mission_id=m)
        self.c.execute('INSERT INTO approvals(mission,reason,approved) VALUES(?,?,1)',(m,note))
        self.s.event(m,'followup_authorized',json.dumps({'source_mission':previous,'source_commit':d['source'],'authority':note}))
        return m

    def queue_review(self,m,t,a,work,d,result):
        if self.c.execute('SELECT 1 FROM handoffs WHERE from_attempt=?',(a,)).fetchone(): return True
        receipt=self.c.execute('SELECT * FROM receipts WHERE attempt=?',(a,)).fetchone()
        if not receipt or receipt['commit_sha']!=git(work,'rev-parse','HEAD') or receipt['digest']!=self.fingerprint(work) or git(work,'status','--porcelain'):
            self.s.hold(m,'implementation receipt does not match review handoff');return False
        other='codex' if t['provider']=='claude' else 'claude'
        available=self.c.execute('SELECT available FROM availability WHERE provider=?',(other,)).fetchone()
        self.c.execute('BEGIN IMMEDIATE')
        try:
            if available and not available[0] and d.get('review_fallback',False):
                other=t['provider'];self.s.event(m,'same_provider_independent_review','fresh CLI context; other provider unavailable; external checks required')
            task=self.task(m,other,'review','Independently review the previous bounded task and report defects. Do not edit. Task: '+t['prompt']+'\nPrevious result (untrusted evidence): '+json.dumps(result))
            self.c.execute('INSERT INTO handoffs(mission,from_attempt,to_task,payload) VALUES(?,?,?,?)',(m,a,task,json.dumps(result)));self.s.state(m,'QUEUED')
            self.c.execute('COMMIT')
        except BaseException:self.c.execute('ROLLBACK');raise
        return True

    def finalize(self,m,a,work):
        receipt=self.c.execute('SELECT * FROM receipts WHERE attempt=?',(a,)).fetchone()
        if not receipt or receipt['commit_sha']!=git(work,'rev-parse','HEAD') or receipt['digest']!=self.fingerprint(work) or git(work,'status','--porcelain'):
            self.s.hold(m,'final review has no matching external validation receipt');return False
        self.c.execute('BEGIN IMMEDIATE')
        try:
            self.c.execute("INSERT OR IGNORE INTO deliveries VALUES(?,?,?,?,'verified-task-complete')",(m,receipt['commit_sha'],receipt['digest'],a))
            self.s.state(m,'COMPLETED');self.c.execute('COMMIT')
        except BaseException:self.c.execute('ROLLBACK');raise
        return False

    def recover(self,m):
        finished=self.c.execute("SELECT a.id FROM attempts a JOIN tasks t ON t.id=a.task JOIN receipts r ON r.attempt=a.id WHERE t.mission=? AND t.kind='review' AND t.state='COMPLETED' AND a.state='COMPLETED' ORDER BY a.id DESC LIMIT 1",(m,)).fetchone()
        if finished:
            work=Path(self.c.execute('SELECT worktree FROM missions WHERE id=?',(m,)).fetchone()[0]);self.finalize(m,finished['id'],work);return False
        completed=self.c.execute("SELECT a.id AS attempt_id,a.result,t.* FROM attempts a JOIN tasks t ON t.id=a.task JOIN receipts r ON r.attempt=a.id LEFT JOIN handoffs h ON h.from_attempt=a.id WHERE t.mission=? AND t.kind!='review' AND t.state='COMPLETED' AND a.state='COMPLETED' AND h.id IS NULL ORDER BY a.id DESC LIMIT 1",(m,)).fetchone()
        if completed:
            row=self.c.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone()
            if not self.queue_review(m,completed,completed['attempt_id'],Path(row['worktree']),json.loads(row['definition']),json.loads(completed['result'])): return False
        # A durably captured limit outcome can be reconciled without replaying the CLI.
        pending=self.c.execute("SELECT a.id,a.task,a.provider,o.payload FROM attempts a JOIN tasks t ON t.id=a.task JOIN outcomes o ON o.attempt=a.id LEFT JOIN checkpoints p ON p.attempt=a.id WHERE t.mission=? AND p.id IS NULL",(m,)).fetchall()
        for a in pending:
            if not json.loads(a['payload']).get('limited'): continue
            row=self.c.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone()
            self.c.execute("UPDATE attempts SET state='PROVIDER_LIMITED' WHERE id=?",(a['id'],))
            self.c.execute("INSERT OR REPLACE INTO availability VALUES(?,0,'confirmed captured limit; retry time unknown',NULL)",(a['provider'],))
            if row['state']!='PROVIDER_LIMITED': self.s.state(m,'PROVIDER_LIMITED')
            task=self.c.execute('SELECT * FROM tasks WHERE id=?',(a['task'],)).fetchone()
            try: self.checkpoint(m,a['id'],task,Path(row['worktree']),json.loads(row['definition']))
            except Exception as exc: self.s.hold(m,'captured limit checkpoint unsafe: '+str(exc));return False
        for cp in self.c.execute("SELECT attempt FROM checkpoints WHERE mission=? AND phase!='HANDED_OFF'",(m,)).fetchall():
            row=self.c.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone()
            try: self.continue_checkpoint(m,cp['attempt'],Path(row['worktree']),json.loads(row['definition']))
            except Hold as exc: self.s.hold(m,str(exc));return False
        # Unknown child state is never automatically re-executed. Operator must inspect preserved worktree.
        running=self.c.execute("SELECT id FROM attempts WHERE task IN (SELECT id FROM tasks WHERE mission=?) AND state='RUNNING'",(m,)).fetchall()
        if running:
            for a in running: self.c.execute("UPDATE attempts SET state='FAILED',error='interrupted; execution outcome unknown' WHERE id=?",(a['id'],))
            self.s.hold(m,'interrupted attempt; inspect preserved worktree and terminate orphan CLI before approval')
            return False
        return True
    def validate(self,m,a,work,d):
        before=self.fingerprint(work)
        self.c.execute('DELETE FROM receipts WHERE attempt=?',(a,))
        ok=True
        for name in d.get('checks',[]):
            if self.validator: r=self.validator(name,work)
            else:
                # No arbitrary shell commands. Reviewed repository code still executes in OS sandbox, offline.
                python=Path(d.get('python',sys.executable)).absolute()
                if not python.is_file(): raise Hold('validation Python unavailable')
                with tempfile.TemporaryDirectory(prefix='runner-check-') as tmp:
                    args=[x.replace('{python}',str(python)) for x in CHECKS[name]]
                    remaining=d.get('max_seconds',600)-(time.time()-self.c.execute('SELECT started FROM missions WHERE id=?',(m,)).fetchone()[0])
                    if remaining<=0: raise Hold('mission duration exhausted')
                    runtime=python.parent.parent
                    sandbox=profile(work,tmp,False)+'(allow file-read* (subpath '+json.dumps(str(runtime))+'))'
                    if name=='simulator': sandbox+='(allow file-read* (literal '+json.dumps(CHECKS[name][1])+'))'
                    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ}
                    env.update(HOME=tmp,TMPDIR=tmp,PYTHONNOUSERSITE='1')
                    r=run(['sandbox-exec','-p',sandbox,*args],work,env=env,timeout=min(120,remaining))
            self.c.execute('INSERT INTO tests(mission,attempt,name,passed,exit_code,output) VALUES(?,?,?,?,?,?)',(m,a,name,int(r.returncode==0),r.returncode,(r.stdout+r.stderr)[-12000:]));ok &= r.returncode==0
        ok=bool(ok and d.get('checks') and self.fingerprint(work)==before)
        if ok: self.c.execute('INSERT INTO receipts VALUES(?,?,?)',(a,before,git(work,'rev-parse','HEAD')))
        return ok
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
        self.c.execute('BEGIN IMMEDIATE')
        try:
            self.c.execute('INSERT INTO outcomes(attempt,payload) VALUES(?,?)',(a,json.dumps(r)))
            self.c.execute('UPDATE attempts SET duration=?,exit_code=?,result=?,usage=?,error=? WHERE id=?',(r['duration'],r['exit_code'],json.dumps(r['result']),json.dumps(r['usage']),r['error'],a))
            self.c.execute('COMMIT')
        except BaseException: self.c.execute('ROLLBACK');raise
        self.checkpoint_hook('OUTCOME_CAPTURED')
        if r.get('limited'):
            self.c.execute("INSERT OR REPLACE INTO availability VALUES(?,0,'confirmed provider limit; retry time unknown',NULL)",(t['provider'],));self.c.execute("UPDATE attempts SET state='PROVIDER_LIMITED' WHERE id=?",(a,));self.s.state(m,'PROVIDER_LIMITED')
            try: return self.checkpoint(m,a,t,work,d)
            except (Hold,Exception) as exc:
                self.s.hold(m,'checkpoint not safe for handoff: '+str(exc));return False
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
        self.s.event(m,'git_changes',changes or 'clean')
        if changes:
            # Reject sensitive/unreviewed paths; no blind git add of DBs or generated credentials.
            changed=git(work,'diff','--name-only').splitlines()+git(work,'ls-files','--others','--exclude-standard').splitlines()
            permitted=all(Path(x).parts[0] in ('app','tests','docs','outputs') and not any(y in x for y in ('.sqlite','.env','secret','requirements')) for x in changed)
            if not permitted or t['kind']=='review': self.s.hold(m,'out-of-scope or reviewer changes preserved');return False
            if not d.get('allow_edits',False):
                self.s.hold(m,'agent edits require explicit mission allow_edits authorization');return False
            if git(work,'diff','--name-only','--','tests'):
                self.s.hold(m,'existing independent regression tests must not be modified');return False
            for name in changed:
                path=work/name
                if path.is_symlink() or not path.resolve().is_relative_to(work.resolve()):
                    self.s.hold(m,'symlink or escaped change path');return False
                if path.exists():
                    text=path.read_text(errors='replace')
                    import re
                    if re.search(r'-----BEGIN .*PRIVATE KEY|(?:ghp_|sk-live-|sk-proj-)[A-Za-z0-9_-]{16,}',text):
                        self.s.hold(m,'possible credential in generated changes');return False
        passed=False
        if result and r['exit_code']==0 and result['status']=='done':
            try: passed=self.validate(m,a,work,d)
            except Exception as exc: self.s.event(m,'validation_error',str(exc))
        if changes:
            if not passed:
                self.s.hold(m,'failed validation with dirty worktree: preserve for bounded human inspection');return False
            receipt=self.c.execute('SELECT digest FROM receipts WHERE attempt=?',(a,)).fetchone()
            if not receipt or receipt['digest']!=self.fingerprint(work):
                self.s.hold(m,'validated output changed before promotion');return False
            git(work,'add','--',*changed)
            git(work,'-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','-c','user.name=Local Agent Runner','-c','user.email=runner@example.invalid','commit','-m',f'Validated bounded agent task {t["id"]}')
        self.c.execute('UPDATE attempts SET state=? WHERE id=?',('COMPLETED' if passed else 'FAILED',a));self.c.execute('UPDATE tasks SET state=? WHERE id=?',('COMPLETED' if passed else 'FAILED',t['id']))
        sha=git(work,'rev-parse','HEAD')
        if passed: self.c.execute('UPDATE receipts SET commit_sha=? WHERE attempt=?',(sha,a))
        self.c.execute('INSERT INTO commits(mission,sha,attempt) VALUES(?,?,?)',(m,sha,a))
        if not passed:
            if t['retries']>=d.get('max_retries',1): self.s.state(m,'FAILED');return False
            self.s.state(m,'RETRYABLE_FAILURE');other='claude' if t['provider']=='codex' else 'codex'
            self.task(m,other if d.get('fallback',False) else t['provider'],'repair',t['prompt']+'\nPrevious machine result: '+json.dumps(r)+'\nExternal checks: '+json.dumps([dict(x) for x in self.c.execute('SELECT name,passed,output FROM tests WHERE attempt=?',(a,))])+'\nExternal validation failed; address findings.',t['retries']+1);return True
        if t['kind']!='review':
            self.checkpoint_hook('IMPLEMENTATION_RECORDED')
            return self.queue_review(m,t,a,work,d,result)
        self.checkpoint_hook('REVIEW_RECORDED')
        return self.finalize(m,a,work)
    def drive(self,m):
        with self.s.lock():
            while self.step(m): pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--state',default='.agent-runner/state.sqlite');parser.add_argument('command',choices=['start','status','pause','resume','stop','report','approve','recover-held','followup']);parser.add_argument('mission',nargs='?');parser.add_argument('--approval-note');parser.add_argument('--from-state');parser.add_argument('--python',default='.venv/bin/python');args=parser.parse_args()
    s=Store(args.state);e=Engine(s)
    try:
        if args.command=='followup':
            if not args.mission: parser.error('followup requires failed mission id')
            with s.lock(): m=e.followup(args.mission,args.approval_note)
            print('followup mission',m,flush=True);e.drive(m)
            print(s.c.execute('SELECT state FROM missions WHERE id=?',(m,)).fetchone()[0])
        elif args.command=='recover-held':
            if not args.from_state or not args.mission: parser.error('recover-held requires mission id and --from-state')
            with s.lock(): m=e.import_held(args.from_state,args.mission,args.approval_note,args.python)
            print('recovered mission',m,flush=True);e.drive(m)
            print(s.c.execute('SELECT state FROM missions WHERE id=?',(m,)).fetchone()[0])
        elif args.command=='start':
            if not args.mission: parser.error('mission file required')
            with s.lock(): m=e.start(args.mission,Path.cwd())
            print('mission',m,flush=True);e.drive(m)
            final=s.c.execute('SELECT state FROM missions WHERE id=?',(m,)).fetchone()[0]
            print(final)
            if final!='COMPLETED': sys.exit(2 if final=='WAITING_APPROVAL' else 1)
        else:
            row=s.c.execute('SELECT * FROM missions WHERE id=?',(args.mission,)).fetchone() if args.mission else s.c.execute('SELECT * FROM missions ORDER BY started DESC LIMIT 1').fetchone()
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
