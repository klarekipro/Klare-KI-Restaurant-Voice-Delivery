"""Persistent quota gates. No authentication/status prose is treated as quota evidence."""
import hashlib
import json
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import tempfile
import time

MIN_INTERVAL = 900  # at most four availability requests/hour/provider, across missions
MAX_INTERVAL = 21600
MAX_CHECKS = 8
DDL = '''
CREATE TABLE IF NOT EXISTS quota_signals(provider TEXT PRIMARY KEY,status TEXT,evidence TEXT,last_attempt REAL,next_check REAL,checks INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS quota_waits(mission TEXT,task INTEGER,provider TEXT,evidence TEXT,last_attempt REAL,next_check REAL,checks INTEGER DEFAULT 0,anchor TEXT,provider_state TEXT,PRIMARY KEY(mission,task,provider));
CREATE TABLE IF NOT EXISTS quota_authorizations(mission TEXT PRIMARY KEY,scope TEXT,code TEXT);
CREATE TABLE IF NOT EXISTS probe_attempts(attempt INTEGER PRIMARY KEY);
'''

def retry_time(data, now):
    """Only explicit machine fields/HTTP headers; never parse natural-language reset claims."""
    if not isinstance(data,dict): return None
    for key in ('reset_at','retry_at'):
        value=data.get(key)
        try:
            if isinstance(value,(int,float)) and not isinstance(value,bool): stamp=float(value)
            elif isinstance(value,str):
                parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
                if parsed.tzinfo is None: continue
                stamp=parsed.timestamp()
            else: continue
            if math.isfinite(stamp) and stamp>now: return stamp
        except (ValueError,OverflowError): pass
    value=data.get('retry_after_seconds',data.get('retry_after'))
    if isinstance(value,str):
        try:value=float(value)
        except ValueError:value=None
    if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0: return now+value
    headers=data.get('headers',{})
    if isinstance(headers,dict):
        value=next((v for k,v in headers.items() if k.lower()=='retry-after'),None)
        if value is not None:
            try:
                seconds=float(value)
                if math.isfinite(seconds) and seconds>=0: return now+seconds
            except (ValueError,TypeError):
                try:
                    parsed=parsedate_to_datetime(str(value))
                    if parsed.tzinfo and parsed.timestamp()>now: return parsed.timestamp()
                except (ValueError,TypeError,OverflowError): pass
    return None

def code_hash():
    root=Path(__file__).parent
    return hashlib.sha256(b''.join((root/name).read_bytes() for name in ('runner.py','quota.py','scheduler.py','check_simulator.cjs','deferred.py','execution.py'))).hexdigest()

def scope_hash(d,started):
    return hashlib.sha256(json.dumps({'definition':d,'started':started},sort_keys=True,separators=(',',':')).encode()).hexdigest()

def authorize(engine,m,d):
    if d.get('auto_resume_quota'):
        engine.c.execute('INSERT INTO quota_authorizations VALUES(?,?,?)',(m,scope_hash(d,engine.c.execute('SELECT started FROM missions WHERE id=?',(m,)).fetchone()[0]),code_hash()))

def confirm(engine,provider,result,now=None):
    now=time.time() if now is None else now
    reset=result.get('retry_at')
    if not isinstance(reset,(int,float)) or isinstance(reset,bool) or not math.isfinite(reset) or reset<=now: reset=None
    evidence=json.dumps({'confirmed':True,'code':result.get('quota_code','confirmed adapter limit'),'reset_at':reset,'simulated':result.get('simulated',False)})
    previous=engine.c.execute('SELECT * FROM quota_signals WHERE provider=?',(provider,)).fetchone()
    # Never move a check earlier because another mission sees the same limit.
    next_check=max(now+MIN_INTERVAL, reset or now+MIN_INTERVAL, previous['next_check'] if previous else 0)
    engine.c.execute('INSERT OR REPLACE INTO quota_signals VALUES(?,?,?,?,?,?)',(provider,'limited',evidence,now,next_check,previous['checks'] if previous else 0))
    engine.c.execute('INSERT OR REPLACE INTO availability VALUES(?,0,?,?)',(provider,'confirmed quota/rate limit; exact type may be unknown',reset))

def recovered(engine,provider,now=None):
    now=time.time() if now is None else now
    engine.c.execute("UPDATE quota_signals SET status='recovered' WHERE provider=?",(provider,))
    engine.c.execute('INSERT OR REPLACE INTO availability VALUES(?,1,?,NULL)',(provider,'successful structured provider response'))
    engine.c.execute("UPDATE quota_waits SET provider_state='recovered' WHERE provider=?",(provider,))

def anchor(engine,m,task,work,d):
    if engine.git_status(work): raise engine.Hold('quota checkpoint is dirty; no unattended resume')
    digest=engine.fingerprint(work);sha=engine.git_head(work)
    receipt=engine.c.execute('SELECT attempt FROM receipts WHERE digest=? AND commit_sha=? ORDER BY attempt DESC LIMIT 1',(digest,sha)).fetchone()
    if not receipt:
        if not engine.validate(m,None,work,{**d,'checks':d.get('checkpoint_checks',d.get('checks',[]))},record_receipt=False):
            raise engine.Hold('quota baseline failed external safety checks')
    cp=engine.c.execute("SELECT id FROM checkpoints WHERE mission=? AND commit_sha=? AND digest=? AND phase IN ('COMMITTED','HANDED_OFF') ORDER BY id DESC LIMIT 1",(m,sha,digest)).fetchone()
    task_scope=hashlib.sha256(json.dumps([task['prompt'],task['kind'],task['retries']]).encode()).hexdigest()
    return json.dumps({'sha':sha,'digest':digest,'checkpoint':cp[0] if cp else None,'task_scope':task_scope})

def enter(engine,m,task,work,d):
    saved=anchor(engine,m,task,work,d)
    providers=[task['provider']]
    if d.get('fallback'): providers.append('codex' if task['provider']=='claude' else 'claude')
    count=0
    for provider in providers:
        signal=engine.c.execute("SELECT * FROM quota_signals WHERE provider=? AND status='limited'",(provider,)).fetchone()
        if not signal: continue
        engine.c.execute('INSERT OR IGNORE INTO quota_waits VALUES(?,?,?,?,?,?,0,?,?)',(m,task['id'],provider,signal['evidence'],signal['last_attempt'],signal['next_check'],saved,'limited'))
        count+=1
    if not count: raise engine.Hold('unavailable provider has no confirmed quota evidence')
    engine.c.execute("UPDATE tasks SET state='WAITING_QUOTA' WHERE id=?",(task['id'],))
    engine.s.state(m,'WAITING_QUOTA');engine.s.event(m,'waiting_quota','validated anchor preserved; budgets and approvals unchanged')
    return False

def safe(engine,row,d,intermediate=False):
    """Return False for expired/paused work; hold changed or uncertain scope."""
    m=row['id']
    allowed=('WAITING_QUOTA','QUEUED','VALIDATING','PROVIDER_LIMITED','RETRYABLE_FAILURE') if intermediate else ('WAITING_QUOTA',)
    if row['state'] not in allowed or row['paused']: return False
    auth=engine.c.execute('SELECT * FROM quota_authorizations WHERE mission=?',(m,)).fetchone()
    if not auth: return False  # enrollment must predate the quota wait
    if auth['scope']!=scope_hash(d,row['started']) or auth['code']!=code_hash():
        engine.s.hold(m,'quota authorization or runner safety scope changed');return False
    if time.time()-row['started']>=d.get('max_seconds',600):
        engine.s.state(m,'FAILED');engine.s.event(m,'quota_budget_expired','original wall-clock duration exhausted');return False
    attempts=engine.c.execute('SELECT COUNT(*) FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=?',(m,)).fetchone()[0]
    if attempts>=d.get('max_invocations',4):
        engine.s.state(m,'FAILED');engine.s.event(m,'quota_budget_expired','original invocation budget exhausted');return False
    failures=0
    for attempt in engine.c.execute('SELECT a.state FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=? ORDER BY a.id DESC',(m,)):
        if attempt[0]=='COMPLETED': break
        failures+=1
    if failures>=d.get('max_failures',3):
        engine.s.state(m,'FAILED');engine.s.event(m,'quota_budget_expired','original consecutive-failure limit exhausted');return False
    work=Path(row['worktree'])
    if engine.c.execute("SELECT 1 FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=? AND a.state='RUNNING'",(m,)).fetchone():
        engine.s.hold(m,'unknown in-flight execution during quota recovery');return False
    for wait in engine.c.execute('SELECT anchor,task FROM quota_waits WHERE mission=?',(m,)):
        expected=json.loads(wait[0])
        task=engine.c.execute('SELECT * FROM tasks WHERE id=?',(wait['task'],)).fetchone()
        task_scope=hashlib.sha256(json.dumps([task['prompt'],task['kind'],task['retries']]).encode()).hexdigest()
        if expected['task_scope']!=task_scope:
            engine.s.hold(m,'waiting task authorization scope changed');return False
        current_digest=engine.fingerprint(work);current_sha=engine.git_head(work)
        exact=not engine.git_status(work) and current_sha==expected['sha'] and current_digest==expected['digest']
        receipt=engine.c.execute('SELECT 1 FROM receipts r JOIN attempts a ON a.id=r.attempt JOIN tasks t ON t.id=a.task WHERE t.mission=? AND r.digest=? AND r.commit_sha=?',(m,current_digest,current_sha)).fetchone() if intermediate else None
        if not exact and not receipt:
            engine.s.hold(m,'quota checkpoint no longer matches validated anchor/receipt');return False
    return True

def defer(engine,wait,provider,now,reason):
    signal=engine.c.execute('SELECT * FROM quota_signals WHERE provider=?',(provider,)).fetchone()
    checks=signal['checks']+1
    reset=json.loads(signal['evidence']).get('reset_at')
    interval=min(MAX_INTERVAL,MIN_INTERVAL*(2**min(checks,8)))
    due=max(now+interval,reset or 0)
    engine.c.execute('UPDATE quota_signals SET checks=?,last_attempt=?,next_check=? WHERE provider=?',(checks,now,due,provider))
    engine.c.execute('UPDATE quota_waits SET checks=checks+1,last_attempt=?,next_check=?,provider_state=? WHERE mission=? AND task=? AND provider=?',(now,due,reason,wait['mission'],wait['task'],provider))
    engine.s.event(wait['mission'],'quota_check_deferred',json.dumps({'provider':provider,'reason':reason,'next_check':due,'checks':checks}))

def tick(engine, now=None):
    """Caller holds the same writer lock as ordinary execution. No backlog replay."""
    now=time.time() if now is None else now
    # Reconcile already-validated handoff/finalization phases after a worker crash.
    interrupted=engine.c.execute("SELECT * FROM missions m WHERE state IN ('QUEUED','VALIDATING','PROVIDER_LIMITED','RETRYABLE_FAILURE') AND EXISTS(SELECT 1 FROM quota_waits q WHERE q.mission=m.id) ORDER BY started").fetchall()
    for row in interrupted:
        if not safe(engine,row,json.loads(row['definition']),intermediate=True):continue
        if engine.recover(row['id']):
            while engine.step(row['id']):pass
        return
    rows=engine.c.execute("SELECT * FROM missions WHERE state='WAITING_QUOTA' ORDER BY started").fetchall()
    for row in rows:
        d=json.loads(row['definition']);m=row['id']
        if not safe(engine,row,d): continue
        waits=engine.c.execute('SELECT * FROM quota_waits WHERE mission=? ORDER BY next_check,provider',(m,)).fetchall()
        chosen=None
        for wait in waits:
            provider=wait['provider'];availability=engine.c.execute('SELECT * FROM availability WHERE provider=?',(provider,)).fetchone()
            signal=engine.c.execute('SELECT * FROM quota_signals WHERE provider=?',(provider,)).fetchone()
            if availability and availability['available'] and signal and signal['status']=='recovered': chosen=provider;break
            if not signal or now<max(wait['next_check'],signal['next_check']): continue
            if signal['checks']>=MAX_CHECKS:
                engine.c.execute("UPDATE quota_waits SET provider_state='check_limit_reached' WHERE mission=? AND task=? AND provider=?",(m,wait['task'],provider));continue
            if not d.get('quota_probe_authorized'):
                defer(engine,wait,provider,now,'probe_not_authorized');continue
            attempts=engine.c.execute('SELECT COUNT(*) FROM attempts a JOIN tasks t ON t.id=a.task WHERE t.mission=?',(m,)).fetchone()[0]
            if attempts+1>=d.get('max_invocations',4):
                engine.s.state(m,'FAILED');engine.s.event(m,'quota_budget_expired','no budget for probe plus useful continuation');return
            a=engine.c.execute("INSERT INTO attempts(task,provider,state,started) VALUES(?,?,'RUNNING',?)",(wait['task'],provider,time.time())).lastrowid
            engine.c.execute('INSERT INTO probe_attempts VALUES(?)',(a,))
            try:
                with tempfile.TemporaryDirectory(prefix='runner-quota-probe-') as tmp:
                    engine.provider.mission_deadline=row['started']+d.get('max_seconds',600)
                    engine.provider.artifact_dir=engine.s.path.parent/'attempts'/str(a)
                    engine.provider.heartbeat=lambda data:engine.s.event(m,'process_activity',json.dumps(dict(attempt=a,**data)))
                    engine.provider.on_start=lambda pid:engine.c.execute('UPDATE attempts SET pid=? WHERE id=?',(pid,a))
                    engine.provider.control=lambda:bool(engine.c.execute("SELECT paused OR state IN ('CANCELLED','STOPPED') FROM missions WHERE id=?",(m,)).fetchone()[0])
                    remaining=d.get('max_seconds',600)-(time.time()-row['started'])
                    result=engine.provider.probe(provider,Path(row['worktree']),min(45,remaining),tmp)
            except BaseException as exc:
                engine.c.execute("UPDATE attempts SET state='FAILED',error=? WHERE id=?",(str(exc),a))
                engine.s.hold(m,'availability probe interrupted/unknown; do not repeat automatically');return
            good=result['exit_code']==0 and isinstance(result['result'],dict) and result['result'].get('status')=='done'
            engine.c.execute('BEGIN IMMEDIATE')
            try:
                engine.c.execute('UPDATE attempts SET state=?,duration=?,exit_code=?,result=?,usage=?,error=? WHERE id=?',('COMPLETED' if good else 'FAILED',result['duration'],result['exit_code'],json.dumps(result['result']),json.dumps(result['usage']),result['error'],a))
                engine.s.event(m,'quota_probe_result',json.dumps({'attempt':a,'provider':provider,'simulated':result.get('simulated',False)}))
                if result.get('limited'):
                    confirm(engine,provider,result,now);defer(engine,wait,provider,now,'limited')
                elif good:
                    engine.c.execute('UPDATE quota_signals SET checks=checks+1,last_attempt=?,next_check=? WHERE provider=?',(now,now+MIN_INTERVAL,provider))
                    engine.c.execute('UPDATE quota_waits SET checks=checks+1,last_attempt=? WHERE mission=? AND task=? AND provider=?',(now,m,wait['task'],provider))
                    recovered(engine,provider,now);engine.s.event(m,'provider_recovered',provider)
                else: defer(engine,wait,provider,now,'unknown_failure')
                engine.c.execute('COMMIT')
            except BaseException:engine.c.execute('ROLLBACK');raise
            engine.checkpoint_hook('PROBE_RESULT_CAPTURED')
            fresh=engine.c.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone()
            if not safe(engine,fresh,d): return
            if result.get('limited'): continue
            if good:chosen=provider;break
            if 'Not logged in' in result.get('error','') or 'authentication' in result.get('error','').lower() or (result.get('result') or {}).get('status')=='approval':
                engine.s.hold(m,'availability check requires authentication or human approval; not a quota signal');return
        if not chosen: continue
        task=engine.c.execute("SELECT * FROM tasks WHERE mission=? AND state='WAITING_QUOTA' ORDER BY id LIMIT 1",(m,)).fetchone()
        if not task: engine.s.hold(m,'quota wait has no pending task');continue
        pending=engine.c.execute("SELECT * FROM checkpoints WHERE task=? AND phase='COMMITTED'",(task['id'],)).fetchone()
        if pending:
            engine.s.state(m,'VALIDATING')
            engine.checkpoint_hook('QUOTA_RESUME_SELECTED')
            engine.continue_checkpoint(m,pending['attempt'],Path(row['worktree']),d)
        else:
            engine.c.execute('BEGIN IMMEDIATE')
            try:
                engine.c.execute("UPDATE tasks SET state='QUEUED',provider=? WHERE id=?",(chosen,task['id']))
                engine.s.state(m,'QUEUED');engine.c.execute('COMMIT')
            except BaseException: engine.c.execute('ROLLBACK');raise
        engine.s.event(m,'mission_resumed',chosen)
        while engine.step(m): pass
        return  # one mission per tick, no unbounded drain loop
