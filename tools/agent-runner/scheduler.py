"""One-shot launchd worker and explicitly authorized per-user installation controls."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time
import quota

LABEL='com.klareki.agent-runner'
INTERVAL=300

def spec(script,state):
    state=Path(state).resolve();logs=state.parent/'logs'
    return {'Label':LABEL,'ProgramArguments':[sys.executable,str(script),'--state',str(state),'scheduler','tick'],
            'WorkingDirectory':str(script.parents[2]),'RunAtLoad':True,'StartInterval':INTERVAL,
            'ThrottleInterval':INTERVAL,'ProcessType':'Background','ExitTimeOut':15,
            'StandardOutPath':str(logs/'scheduler.out.log'),'StandardErrorPath':str(logs/'scheduler.err.log'),
            'EnvironmentVariables':{'PATH':os.environ.get('PATH','/usr/bin:/bin')}}

def tick(engine,now=None):
    try:
        with engine.s.lock():
            engine.s.event(None,'scheduler_tick','single-instance acquired')
            inflight=engine.c.execute("SELECT a.id,t.mission,m.state FROM attempts a JOIN tasks t ON t.id=a.task JOIN missions m ON m.id=t.mission WHERE a.state='RUNNING' LIMIT 1").fetchone()
            if inflight:
                if inflight['state'] not in ('WAITING_APPROVAL','CANCELLED','STOPPED','COMPLETED','FAILED'):
                    engine.s.hold(inflight['mission'],'unknown in-flight execution after worker restart; inspect before scheduling')
                engine.s.event(None,'scheduler_unknown_inflight',str(inflight['id']));return False
            quota.tick(engine,now)
            engine.s.event(None,'scheduler_idle','tick completed')
    except engine.Hold as exc:
        engine.s.event(None,'scheduler_busy_or_hold',str(exc));return False
    return True

def command(engine,args,script):
    action=args.mission or 'status';state=engine.s.path;root=state.parent
    if args.command=='quota':
        if action not in ('status','next-check'): raise engine.Hold('quota command must be status or next-check')
        waits=[dict(x) for x in engine.c.execute("SELECT q.* FROM quota_waits q JOIN missions m ON m.id=q.mission WHERE m.state='WAITING_QUOTA' ORDER BY q.next_check")]
        for wait in waits:
            signal=engine.c.execute('SELECT next_check FROM quota_signals WHERE provider=?',(wait['provider'],)).fetchone()
            if signal:wait['next_check']=max(wait['next_check'],signal[0])
        if action=='next-check':
            waits=[{k:x[k] for k in ('mission','task','provider','next_check','checks','provider_state')} for x in waits]
        print(json.dumps({'waiting':waits,'providers':[dict(x) for x in engine.c.execute('SELECT * FROM quota_signals')],'missions':[dict(x) for x in engine.c.execute("SELECT id,state,paused,EXISTS(SELECT 1 FROM quota_authorizations a WHERE a.mission=missions.id) AS auto_resume_authorized FROM missions")]},indent=2));return
    if action=='tick':
        tick(engine);return
    generated=root/'launchagent.plist';target=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
    expected=plistlib.dumps(spec(script,state),sort_keys=True)
    if action=='generate':
        output=Path(args.output).absolute() if args.output else generated
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_bytes(expected);os.chmod(output,0o600)
        if output!=generated: generated.write_bytes(expected);os.chmod(generated,0o600)
        (root/'logs').mkdir(exist_ok=True,mode=0o700)
        for name in ('scheduler.out.log','scheduler.err.log'):
            path=root/'logs'/name;path.touch(exist_ok=True);os.chmod(path,0o600)
        print('Generated only; NOT installed or enabled:',output);return
    if action=='logs':
        for row in engine.c.execute('SELECT at,mission,event,detail FROM events ORDER BY id DESC LIMIT 80'):
            print(json.dumps(dict(row)))
        for name in ('scheduler.out.log','scheduler.err.log'):
            path=root/'logs'/name
            if path.exists(): print(name,path.read_bytes()[-65536:].decode(errors='replace'))
        return
    domain=f'gui/{os.getuid()}';job=f'{domain}/{LABEL}'
    if action=='status':
        result=subprocess.run(['launchctl','print',job],capture_output=True,text=True) if sys.platform=='darwin' else None
        print(json.dumps({'installed':target.exists(),'loaded':bool(result and result.returncode==0),'label':LABEL,'state':str(state),'generated':str(generated),'logs':str(root/'logs'),'waiting_missions':engine.c.execute("SELECT COUNT(*) FROM missions WHERE state='WAITING_QUOTA'").fetchone()[0]},indent=2));return
    if action not in ('install','enable','disable','uninstall'): raise engine.Hold('unknown scheduler command')
    if sys.platform!='darwin' or os.getuid()==0: raise engine.Hold('scheduler activation requires a non-root macOS user')
    if not args.authorize_activation: raise engine.Hold('separate explicit --authorize-activation NOTE required; development does not authorize persistence')
    if not generated.exists(): raise engine.Hold('reviewed configuration is missing')
    approved=generated.read_bytes()
    try: reviewed=plistlib.loads(approved)
    except Exception: raise engine.Hold('reviewed configuration is invalid')
    if reviewed.get('Label')!=LABEL: raise engine.Hold('reviewed configuration has another label')
    if action in ('install','enable') and approved!=expected: raise engine.Hold('generate and review the exact current configuration first')
    if target.exists() and target.read_bytes()!=approved: raise engine.Hold('existing LaunchAgent differs; refusing to overwrite/remove it')
    def launch(*argv,allow_failure=False):
        result=subprocess.run(['launchctl',*argv],capture_output=True,text=True)
        if result.returncode and not allow_failure: raise engine.Hold('launchctl failed: '+result.stderr.strip())
    if action=='install':
        target.parent.mkdir(exist_ok=True)
        # Exclusive creation; never replace another process's LaunchAgent.
        if not target.exists():
            with open(target,'xb') as f:f.write(expected)
            os.chmod(target,0o600)
    elif action=='enable':
        if not target.exists(): raise engine.Hold('install reviewed configuration first')
        launch('enable',job)
        active=subprocess.run(['launchctl','print',job],capture_output=True).returncode==0
        if not active: launch('bootstrap',domain,str(target))
    else:
        launch('bootout',job,allow_failure=True);launch('disable',job)
        if subprocess.run(['launchctl','print',job],capture_output=True).returncode==0: raise engine.Hold('job remains loaded; refusing to remove its configuration')
        if action=='uninstall' and target.exists(): target.unlink()
    engine.s.event(None,'scheduler_'+action,args.authorize_activation);print(action,'completed')
