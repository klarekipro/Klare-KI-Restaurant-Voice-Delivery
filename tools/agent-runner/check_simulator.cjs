// Behavior test of the actual template JavaScript with a minimal DOM, not a browser test.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[2], 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/const menu = .*?;/, 'const menu = [];');
function element(id) {
  return { value: '', disabled: false, textContent: '', innerHTML: '', dataset: {}, callbacks: {},
    addEventListener(event, fn) { this.callbacks[event] = fn; } };
}
const ids = Object.fromEntries(['phone','name','street','house_number','plz','city','notes','total','lookup-btn','lookup-result','submit-btn','submit-result','new-order-btn'].map(id => [id, element(id)]));
const qty = element('qty'); qty.value='1'; qty.dataset={ menuId:'1', price:'100' };
let calls=[], sequence=0, mode='success';
const ctx={document:{getElementById:id=>ids[id],querySelectorAll:()=>[qty]},crypto:{randomUUID:()=>`test-key-${++sequence}`},fetch: async (url,opts)=>{
  calls.push(opts);
  if (mode==='offline') throw Error('offline');
  await new Promise(resolve=>setTimeout(resolve,10));
  return {ok:true,json:async()=>({order_id:1,crm_match_status:'unmatched',call_id:'synthetic'})};
}};
vm.createContext(ctx);vm.runInContext(code,ctx);
(async()=>{
  const submit=ids['submit-btn'].callbacks.click;
  mode='offline';await submit();assert.equal(ids['submit-btn'].disabled,false);assert.match(ids['submit-result'].textContent,/offline/);
  mode='success';let first=submit();await submit();await first;
  assert.equal(calls.length,2,'double click must not add a request');
  assert.equal(calls[0].headers['Idempotency-Key'],calls[1].headers['Idempotency-Key'],'uncertain retry must retain key');
  assert.equal(ids['submit-btn'].disabled,true);
  ids['new-order-btn'].callbacks.click();assert.equal(qty.value,'0');assert.equal(ids['submit-btn'].disabled,false);
  qty.value='1';await submit();assert.equal(calls.length,3);
  assert.notEqual(calls[1].headers['Idempotency-Key'],calls[2].headers['Idempotency-Key'],'explicit new order must rotate key');
  console.log('PASS: actual template JS retry, duplicate click, reset, and new-order key rotation (DOM stub; no browser)');
})().catch(e=>{console.error(e);process.exitCode=1;});
