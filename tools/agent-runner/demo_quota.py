#!/usr/bin/env python3
"""Controlled quota injection + REAL read-only Codex probe/work/review, no launchd activation."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import runner as r
import quota
import scheduler

class ControlledClaudeLimit(r.CLIProvider):
    def execute(self,provider,*args,**kwargs):
        if provider=='claude':
            return dict(result=None,exit_code=1,usage={},error='CONTROLLED TEST: simulated API429; no Claude request made',duration=0,limited=True,retry_at=time.time()+3600,quota_code=429,simulated=True)
        return super().execute(provider,*args,**kwargs)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['run','tick']);parser.add_argument('--state',required=True);parser.add_argument('--python');args=parser.parse_args()
    store=r.Store(args.state);meta=store.path.parent/'demo.json'
    if args.mode=='run':
        if not args.python:parser.error('--python reviewed project interpreter required')
        if store.c.execute('SELECT 1 FROM missions').fetchone():raise r.Hold('demo requires a new empty private state store')
        d=dict(name='Mission06 controlled quota / real CLI recovery',source='8471c4d5215b80cb260a546d339291afe727630e',prompt='Read-only bounded review of the existing simulator retry behavior and docs/agents/CURRENT_STATE.md. Do not edit or run commands; use available file reads if needed. Return done when review is complete, list limitations, and do not claim browser verification or product readiness.',checks=['pytest','acceptance','simulator'],python=str(Path(args.python).absolute()),max_seconds=7200,max_invocations=6,max_retries=0,max_failures=4,max_concurrent=1,provider='claude',fallback=True,review_fallback=True,auto_resume_quota=True,quota_probe_authorized=True)
        definition=store.path.parent/'mission.json';definition.write_text(json.dumps(d,indent=2))
        engine=r.Engine(store,ControlledClaudeLimit())
        with store.lock():
            quota.confirm(engine,'codex',dict(limited=True,quota_code=429,retry_at=time.time()+900,simulated=True))
            mission=engine.start(definition,Path.cwd())
        engine.drive(mission)
        row=store.c.execute('SELECT state FROM missions WHERE id=?',(mission,)).fetchone();assert row[0]=='WAITING_QUOTA'
        due=store.c.execute("SELECT next_check FROM quota_signals WHERE provider='codex'").fetchone()[0]
        meta.write_text(json.dumps({'mission':mission,'simulated_check_time':due+1,'quota_errors_simulated':True,'real_reset_observed':False,'no_Claude_request':True}))
        print('Persisted WAITING_QUOTA; starting a separate one-shot worker process (no LaunchAgent).',flush=True)
        child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'tick','--state',str(store.path)])
        if child.returncode:sys.exit(child.returncode)
        before=store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'tick','--state',str(store.path)],check=True)
        assert store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==before
        print('Duplicate worker did not repeat calls; final state:',store.c.execute('SELECT state FROM missions WHERE id=?',(mission,)).fetchone()[0])
    else:
        data=json.loads(meta.read_text());engine=r.Engine(store)
        # Test clock affects eligibility only; real mission budgets and process deadlines remain unchanged.
        scheduler.tick(engine,now=data['simulated_check_time'])
        state=store.c.execute('SELECT state FROM missions WHERE id=?',(data['mission'],)).fetchone()[0]
        print('One-shot recovery worker:',state,flush=True)
        if state!='COMPLETED':sys.exit(2)

if __name__=='__main__':main()
