import uuid
import pytest
from .conftest import login
from .test_e2e_flow import _sample_items, _submit_call


def payload():
    return dict(phone='+493099990004', name='Synthetic Test', address=dict(street='Testweg', house_number='1', plz='10115', city='Berlin'), items=[dict(menu_item_id=1, qty=2)])


@pytest.mark.parametrize('items', [[{'menu_item_id':99999,'qty':1}], [{'menu_item_id':1,'qty':-1}], [{'menu_item_id':1,'qty':'oops'}], [{'menu_item_id':1,'qty':True}], []])
def test_bad_items_atomic(client, items):
    from app import db
    login(client,'owner','owner123')
    p=payload();p['items']=items
    assert client.post('/call/submit',json=p).status_code==400
    with db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]==0
        assert not c.execute('SELECT 1 FROM customers WHERE phone=?',(p['phone'],)).fetchone()


def test_idempotency_and_snapshot(client):
    from app import db, orders
    login(client,'owner','owner123')
    p=payload();headers={'Idempotency-Key':str(uuid.uuid4())}
    first=client.post('/call/submit',json=p,headers=headers).json()
    assert client.post('/call/submit',json=p,headers=headers).json()==first
    p['address']['street']='Different Testweg'
    assert client.post('/call/submit',json=p,headers=headers).status_code==409
    assert client.post('/call/submit',json=p).status_code==200
    assert orders.fetch_order(first['order_id'])['customer']['street']=='Testweg'
    with db.connect() as c:
        c.execute('UPDATE menu_items SET price_cents=99999 WHERE id=1')
    assert orders.fetch_order(first['order_id'])['order']['total_cents']==first['total_cents']


def test_empty_approval_and_duplicate_transition(client):
    from app import db
    login(client,'owner','owner123')
    oid=client.post('/call/submit',json=payload()).json()['order_id']
    assert client.post(f'/confirmer/{oid}/approve').status_code==200 # redirect to queue
    assert client.post(f'/confirmer/{oid}/approve').status_code==409
    assert client.post(f'/kitchen/{oid}/ready').status_code==200
    assert client.post(f'/kitchen/{oid}/ready').status_code==409
    oid=client.post('/call/submit',json=payload()).json()['order_id']
    with db.connect() as c: c.execute('DELETE FROM order_items WHERE order_id=?',(oid,))
    assert client.post(f'/confirmer/{oid}/approve').status_code==400


def test_cross_origin_and_bad_json(client):
    assert client.post('/login',data=dict(username='owner',password='owner123'),headers={'Origin':'https://attacker.invalid'}).status_code==403
    login(client,'owner','owner123')
    assert client.post('/call/submit',content='not json').status_code==400
    assert client.post('/call/submit',json=[]).status_code==400


@pytest.mark.parametrize('path', ['/confirmer/1/approve','/kitchen/1/ready','/dispatch/1/assign','/courier/1/start','/courier/1/delivered','/courier/1/reveal_phone'])
def test_anonymous_actions(client,path):
    assert client.post(path,data={'courier_id':4}).status_code==401


def test_other_courier_denied(client):
    from app import db
    login(client,'owner','owner123')
    oid=client.post('/call/submit',json=payload()).json()['order_id']
    client.post(f'/confirmer/{oid}/approve');client.post(f'/kitchen/{oid}/ready')
    with db.connect() as c: cid=c.execute("SELECT id FROM users WHERE username='courier1'").fetchone()[0]
    client.post(f'/dispatch/{oid}/assign',data={'courier_id':cid})
    login(client,'courier2','courier123')
    assert client.get(f'/courier/{oid}').status_code==403
    for action in ['start','delivered','reveal_phone','failed']:
        assert client.post(f'/courier/{oid}/{action}',data={'reason':'test'}).status_code==403


def test_delivery_report_uses_delivery_day(client,monkeypatch):
    import app.main as main
    from app import db
    monkeypatch.setattr(main,'report_window',lambda days:('2026-01-02 23:00:00','2026-01-03 23:00:00'))
    login(client,'owner','owner123')
    oid=client.post('/call/submit',json=payload()).json()['order_id']
    with db.connect() as c:
        c.execute("UPDATE orders SET status='closed',created_at='2026-01-01 10:00:00',delivered_at='2026-01-03 01:00:00' WHERE id=?",(oid,))
    r=client.get('/dashboard')
    from app.main import _format_cents
    with db.connect() as c: total=c.execute('SELECT total_cents FROM orders WHERE id=?',(oid,)).fetchone()[0]
    assert _format_cents(total) in r.text


def test_old_public_key_no_longer_signs_sessions(client):
    import base64,json
    from itsdangerous import TimestampSigner
    token=TimestampSigner('dev-only-secret-change-me-in-every-non-local-environment').sign(base64.b64encode(json.dumps({'uid':1}).encode())).decode()
    client.cookies.set('session',token)
    assert client.get('/dashboard').status_code==401
