"""Authorized time-based queue. Scheduling is not evidence of provider quota exhaustion."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import time
import quota

DDL='''CREATE TABLE IF NOT EXISTS scheduled_missions(mission TEXT PRIMARY KEY,not_before REAL,phase TEXT,source_sha TEXT,digest TEXT,task INTEGER,task_scope TEXT,branch TEXT);'''

def parse_time(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('not-before requires an explicit timezone')
    return parsed.timestamp()

def task_scope(task):
    return hashlib.sha256(json.dumps([task['prompt'],task['kind'],task['retries']]).encode()).hexdigest()

def enqueue(engine,definition,repo,not_before):
    due=parse_time(not_before)
    if due<=time.time(): raise engine.Hold('enqueue requires a future not-before time')
    d=json.loads(Path(definition).read_text())
    if not d.get('auto_resume_quota'): raise engine.Hold('unattended mission must authorize auto_resume_quota')
    if due-time.time()>=d.get('max_seconds',600): raise engine.Hold('scheduled time is outside original duration budget')
    d['not_before']=datetime.fromtimestamp(due,timezone.utc).isoformat()
    engine.c.executescript(DDL)
    path=engine.s.path.parent/'scheduled-definitions'/f'{hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()}.json'
    path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(d,indent=2))
    # Idempotent registration; no second worktree or mission for the same definition/time.
    for old in engine.c.execute('SELECT id,definition FROM missions'):
        if json.loads(old['definition'])==d:
            if not engine.c.execute('SELECT 1 FROM scheduled_missions WHERE mission=?',(old['id'],)).fetchone():raise engine.Hold('incomplete enqueue registration; inspect preserved mission')
            return old['id']
    m=engine.start(path,repo)
    row=engine.c.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone()
    if row['state']!='QUEUED': return m
    work=Path(row['worktree']);task=engine.c.execute('SELECT * FROM tasks WHERE mission=?',(m,)).fetchone()
    engine.c.execute('INSERT INTO scheduled_missions VALUES(?,?,?,?,?,?,?,?)',(m,due,'PENDING',engine.git_head(work),engine.fingerprint(work),task['id'],task_scope(task),engine.git_branch(work)))
    engine.s.event(m,'mission_enqueued',json.dumps({'not_before':d['not_before'],'reason':'operator-authorized schedule, NOT a quota reset claim','AI_calls':0}))
    return m

def tick(engine):
    engine.c.executescript(DDL)
    rows=engine.c.execute("SELECT m.*,s.not_before,s.phase,s.source_sha,s.digest,s.task,s.task_scope,s.branch FROM scheduled_missions s JOIN missions m ON m.id=s.mission WHERE m.state IN ('QUEUED','VALIDATING','RETRYABLE_FAILURE','PROVIDER_LIMITED') AND NOT EXISTS(SELECT 1 FROM quota_waits q WHERE q.mission=m.id) ORDER BY s.not_before").fetchall()
    for row in rows:
        if row['paused'] or time.time()<row['not_before']: continue
        m=row['id'];d=json.loads(row['definition']);auth=engine.c.execute('SELECT * FROM quota_authorizations WHERE mission=?',(m,)).fetchone()
        if not auth or auth['scope']!=quota.scope_hash(d,row['started']) or auth['code']!=quota.code_hash() or parse_time(d['not_before'])!=row['not_before']:
            engine.s.hold(m,'scheduled authorization, code or time changed');continue
        if time.time()-row['started']>=d.get('max_seconds',600): engine.s.state(m,'FAILED');continue
        task=engine.c.execute('SELECT * FROM tasks WHERE id=?',(row['task'],)).fetchone()
        if task_scope(task)!=row['task_scope']: engine.s.hold(m,'scheduled task scope changed');continue
        work=Path(row['worktree']);sha=engine.git_head(work);digest=engine.fingerprint(work)
        if engine.git_branch(work)!=row['branch']:engine.s.hold(m,'scheduled worktree branch changed');continue
        baseline=not engine.git_status(work) and sha==row['source_sha'] and digest==row['digest']
        receipt=engine.c.execute('SELECT 1 FROM receipts r JOIN attempts a ON a.id=r.attempt JOIN tasks t ON t.id=a.task WHERE t.mission=? AND r.commit_sha=? AND r.digest=?',(m,sha,digest)).fetchone() if row['phase']=='RELEASED' else None
        checkpoint=engine.c.execute("SELECT 1 FROM checkpoints WHERE mission=? AND digest=? AND commit_sha=? AND phase IN ('COMMITTED','HANDED_OFF')",(m,digest,sha)).fetchone() if row['phase']=='RELEASED' else None
        if not baseline and not receipt and not checkpoint:engine.s.hold(m,'scheduled worktree is changed or unvalidated');continue
        if row['phase']=='PENDING':
            engine.c.execute("UPDATE scheduled_missions SET phase='RELEASED' WHERE mission=?",(m,));engine.s.event(m,'scheduled_time_reached','existing provider/quota policy will select capacity; no quota is assumed')
        if engine.recover(m):
            while engine.step(m): pass
        return True
    return False

def pending(engine):
    engine.c.executescript(DDL)
    return [dict(x) for x in engine.c.execute("SELECT m.id,m.state,m.paused,s.not_before,s.phase FROM scheduled_missions s JOIN missions m ON m.id=s.mission WHERE m.state NOT IN ('COMPLETED','FAILED','CANCELLED','STOPPED') ORDER BY s.not_before")]
