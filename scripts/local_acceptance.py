"""Run with .venv/bin/python scripts/local_acceptance.py; synthetic data only."""
import os, socket, subprocess, sys, tempfile, time
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='klare-acceptance-') as temp:
    env={**os.environ,'KLARE_DB_PATH':str(Path(temp)/'test.sqlite')}
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    def start():
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if httpx.get(base+'/login').status_code==200: return proc
            except httpx.TransportError: pass
            time.sleep(.1)
        proc.terminate();proc.wait();raise RuntimeError('server failed to start')
    proc=start()
    try:
        with httpx.Client(base_url=base,follow_redirects=False) as c:
            def login(user,password):
                assert c.post('/login',data=dict(username=user,password=password)).status_code==303
            login('owner','owner123')
            for page in ['/dashboard','/call','/customers','/menu','/confirmer','/kitchen','/dispatch']:
                assert c.get(page).status_code==200,page
            p=dict(phone='+493099990099',name='Synthetic Acceptance',address=dict(street='Testweg',house_number='1',plz='10115',city='Berlin'),items=[dict(menu_item_id=1,qty=2)])
            result=c.post('/call/submit',json=p).json();oid=result['order_id']
            assert c.post('/call/lookup',data={'phone':p['phone']}).json()['matched']
            assert c.post(f'/confirmer/{oid}/approve').status_code==303
            login('kitchen','kitchen123')
            assert f'#{oid}' in c.get('/kitchen').text
            assert c.post(f'/kitchen/{oid}/ready').status_code==303
            login('owner','owner123')
            import sqlite3
            with sqlite3.connect(env['KLARE_DB_PATH']) as db:
                courier=db.execute("SELECT id FROM users WHERE username='courier1'").fetchone()[0]
            assert c.post(f'/dispatch/{oid}/assign',data={'courier_id':courier}).status_code==303
            login('courier1','courier123')
            page=c.get(f'/courier/{oid}');assert page.status_code==200 and 'destination=Testweg' in page.text
            assert c.post(f'/courier/{oid}/start').status_code==303
            assert c.post(f'/courier/{oid}/delivered').status_code==303
            proc.terminate();proc.wait();proc=start()
            login('owner','owner123')
            assert c.get('/dashboard').status_code==200
            with sqlite3.connect(env['KLARE_DB_PATH']) as db:
                status,total=db.execute('SELECT status,total_cents FROM orders WHERE id=?',(oid,)).fetchone()
                assert status=='closed' and total==result['total_cents']
                assert db.execute("SELECT COUNT(*) FROM order_events WHERE order_id=? AND event='status.closed'",(oid,)).fetchone()[0]==1
            print('PASS: manager pages, new/returning lookup, approval, kitchen, dispatch, courier navigation URL, delivery/closed, process restart and persisted cents/events')
    finally:
        proc.terminate();proc.wait()
