#!/usr/bin/env python3
"""Three bounded, tool-free real requests. Never opens or resumes an old mission."""
import argparse
import json
from pathlib import Path
import tempfile
import time
import sys
import runner


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--recovery',action='store_true',help='Real timeout, checkpoint checks, Codex continuation and Claude review')
    args=parser.parse_args()
    root=Path(args.directory).resolve()
    root.mkdir(mode=0o700)  # refuse reusing previous evidence
    work=root/'fixture';work.mkdir()
    runner.git(work,'init')
    runner.git(work,'-c','user.name=Runner Demo','-c','user.email=runner@example.invalid','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','--allow-empty','-m','Isolated synthetic timeout fixture')
    if args.recovery:
        app=work/'app';app.mkdir();(app/'fixture.py').write_text('value = 1\n')
        (work/'.gitignore').write_text('__pycache__/\n*.pyc\n')
        runner.git(work,'add','app/fixture.py','.gitignore')
        runner.git(work,'-c','user.name=Runner Demo','-c','user.email=runner@example.invalid','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','-m','Synthetic syntax-check fixture')
        class TimeoutOnce(runner.CLIProvider):
            calls=0
            def execute(self,provider,worktree,prompt,timeout,scratch,probe=False):
                self.calls+=1
                # Real process/deadline fault injection; no fabricated result or quota event.
                return super().execute(provider,worktree,prompt,min(timeout,.5) if self.calls==1 else timeout,scratch,probe=True)
        definition=root/'mission.json'
        definition.write_text(json.dumps(dict(name='Bounded synthetic timeout recovery',source='HEAD',
            prompt='Synthetic read-only verification. Do not inspect files, run commands, edit or use tools. Return status done, summary synthetic verification answered, findings empty.',
            provider='claude',fallback=True,checks=['compile'],checkpoint_checks=['compile'],
            python=sys.executable,timeout_recovery='checkpoint',invocation_seconds=120,
            max_seconds=300,max_invocations=3,max_retries=1,max_failures=3)))
        store=runner.Store(root/'state.sqlite');engine=runner.Engine(store,TimeoutOnce())
        with store.lock():mission=engine.start(definition,work)
        engine.drive(mission)
        attempts=[dict(row) for row in store.c.execute('SELECT * FROM attempts')]
        summary=dict(mission=mission,state=store.c.execute('SELECT state FROM missions').fetchone()[0],
            attempts=[{k:a[k] for k in ('id','provider','state','duration','exit_code','error')} for a in attempts],
            checks=[dict(row) for row in store.c.execute('SELECT name,passed FROM tests')],
            checkpoints=[dict(row) for row in store.c.execute('SELECT phase,classification FROM checkpoints')],
            files_unchanged=runner.git(work,'status','--porcelain')=='')
        before=len(attempts);engine.drive(mission)
        summary['duplicate_drive_added_attempts']=store.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]-before
        (root/'results.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
        raise SystemExit(0 if summary['state']=='COMPLETED' and summary['duplicate_drive_added_attempts']==0 else 1)
    provider=runner.CLIProvider();provider.mission_deadline=time.time()+420
    results=[]
    for name,backend,seconds in [('claude-timeout','claude',.5),('claude-answer','claude',210),('codex-answer','codex',120)]:
        provider.artifact_dir=root/name
        provider.heartbeat=lambda data:print(json.dumps({'activity':data}),flush=True)
        before=runner.git(work,'status','--porcelain')
        try:
            with tempfile.TemporaryDirectory(prefix='runner-timeout-demo-') as scratch:
                runner.isolation_probe(work,scratch)
                result=provider.probe(backend,work,seconds,scratch)
            result['name']=name
            result['files_unchanged']=before==runner.git(work,'status','--porcelain')==''
        except Exception as exc:
            result={'name':name,'error':str(exc),'verified':False}
        results.append(result)
        (root/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(result),flush=True)
    expected=(results[0].get('timed_out') and results[0].get('terminated') and
              all(x.get('exit_code')==0 and x.get('result') and not x.get('limited') for x in results[1:]) and
              all(x.get('files_unchanged') for x in results))
    raise SystemExit(0 if expected else 1)


if __name__=='__main__':main()
