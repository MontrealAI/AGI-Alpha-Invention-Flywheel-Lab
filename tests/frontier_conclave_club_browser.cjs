'use strict';
// Staged site, simulated ENS and deterministic test signers. For signature
// validation the fixture independently recovers with eth_keys in Python.
// Usage: CONCLAVE_URL=http://127.0.0.1:18731/frontier-conclave.html node this-file
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright-core');
const url=process.env.CONCLAVE_URL??'http://127.0.0.1:18731/frontier-conclave.html';
const helper=`
import sys
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import Signature
mode=sys.argv[1]
if mode=='account':
    print(Account.from_key(bytes.fromhex('01'.zfill(64))).address.lower())
elif mode=='sign':
    print('0x'+bytes(Account.sign_message(encode_defunct(hexstr=sys.argv[2]),bytes.fromhex(sys.argv[3].zfill(64))).signature).hex())
else:
    data=bytes.fromhex(sys.argv[2][2:])
    assert len(data)==128
    v=int.from_bytes(data[32:64],'big')-27
    r=int.from_bytes(data[64:96],'big')
    s=int.from_bytes(data[96:128],'big')
    signer=Signature(vrs=(v,r,s)).recover_public_key_from_msg_hash(data[:32]).to_address()
    print('0x'+signer[2:].zfill(64))
`;
const independent=(...args)=>execFileSync('python3',['-c',helper,...args],{encoding:'utf8'}).trim();
const owner=independent('account');
async function wallet(page,mode){
  await page.exposeFunction('signFixture',(payload,key)=>independent('sign',payload,key));
  await page.exposeFunction('recoverFixture',data=>independent('recover',data));
  await page.addInitScript(({owner,mode})=>{
    const methods=[],listeners={};
    let wrong=mode==='token-only';
    const word=n=>BigInt(n).toString(16).padStart(64,'0');
    const other='0x'+'12'.repeat(20);
    const address=a=>'0x'+a.slice(2).padStart(64,'0');
    const s=window.conclaveFixture={methods,signed:[],tick:event=>listeners[event]?.(event==='accountsChanged'?[other]:null),withdraw:()=>wrong=true};
    const block=()=>({hash:'0x'+'11'.repeat(32),number:'0x16',timestamp:'0x'+Math.floor(Date.now()/1000).toString(16)});
    window.ethereum={
      isMetaMask:true,on(event,fn){listeners[event]=fn;},removeListener(event){delete listeners[event];},
      async request({method,params}){
        methods.push(method);
        if(method==='eth_chainId')return mode==='wrong-network'?'0x89':'0x1';
        if(method==='eth_getBlockByNumber')return block();
        if(method==='eth_requestAccounts'){listeners.accountsChanged?.([owner]);return[owner];}
        if(method==='eth_accounts')return[owner];
        if(method==='personal_sign'){
          if(mode==='cancel')throw {code:4001};
          s.signed.push(params[0]);
          return signFixture(params[0],mode==='wrong-signer'?'2':'1');
        }
        if(method!=='eth_call')throw Error('Unexpected wallet method');
        const {data,to}=params[0];
        if(to==='0x'+'0'.repeat(39)+'1')return recoverFixture(data);
        if(params[1]!==block().number)throw Error('Wrong block');
        if(data.startsWith('0x02571be3'))return address(wrong?other:owner);
        if(to.toLowerCase()==='0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85')return '0x'+word(data.length===10?0:mode==='expired'?1:Math.floor(Date.now()/1000)+86400);
        if(data.startsWith('0x70a08231'))return '0x'+word(1_000_000n*10n**18n);
        throw Error('Unexpected selector');
      }
    };
  },{owner,mode});
}
(async()=>{
  const b=await chromium.launch({executablePath:process.env.FRONTIER_CHROME??'/usr/bin/google-chrome'});
  const testcases=[
    ['qualifies',/membership verified/i],['french',/adhésion à l’AGI CLUB vérifiée/i],['token-only',/does not own/],['expired',/does not own/],
    ['wrong-network',/Ethereum Mainnet/],['cancel',/canceled/],['wrong-signer',/Could not verify or open/],
    ['no-wallet',/Open this page with MetaMask/],['hash-dossier',/Open this page with MetaMask/],
    ['hash-demo',/Open this page with MetaMask/],['expires',/membership verified/i],['disconnect',/membership verified/i],['network-change',/membership verified/i]
  ];
  try{
    let nonce;
    for(const [mode,expected] of testcases){
      const page=await b.newPage({viewport:{width:390,height:844}});const errors=[];
      page.on('pageerror', e=>errors.push(e.message));
      try{
        if(mode!=='no-wallet'&&!mode.startsWith('hash-'))await wallet(page,mode);
        if(mode==='expires')await page.clock.install();
        const direct=mode==='hash-dossier'?'#dossier':mode==='hash-demo'?'#double-flywheel':'';
        const response=await page.goto(url+direct);
        assert.equal(response.status(),200);
        assert.ok(await page.locator('#dossier a[download]').count());
        assert.equal(await page.locator('#dossier').isVisible(),false);
        const csp=await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content');
        assert.match(csp,/script-src 'self';/);
        const form=page.locator('#conclave-club-form'), panel=page.locator('#member');
        assert.equal(await panel.isVisible(),false);
        assert.equal(await page.locator('#double-flywheel').count(),0,'demo templates must stay inert');
        assert.equal(await page.locator('[data-connect="token"]').count(),0);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        const open=async()=>{
          await page.locator('#conclave-club-label').fill('member-example');
          await page.locator('#conclave-club-enter').click();
          await page.waitForFunction(({source,flags})=>new RegExp(source,flags).test(document.querySelector('#conclave-club-status').textContent),
            {source:expected.source,flags:expected.flags});
        };
        if(mode==='french')await page.locator('[data-club-lang="fr"]').click();
        await open();
        if(mode==='qualifies'||mode==='french'||mode==='expires'||mode==='network-change'||mode==='disconnect'){
          if(mode==='french'){
            assert.equal(await panel.getAttribute('lang'),'fr');
            assert.match(await panel.locator('#df-title').innerText(),/Première Lumière/i);
          }
          if(mode!=='qualifies'){
            assert.equal(await panel.isVisible(),true);
            if(mode==='french'){
              await panel.locator('#conclave-club-lock').click();
              assert.equal(await panel.isVisible(),false);
            }else if(mode==='expires'){
              await page.clock.fastForward(5*60*1000+5);
              assert.equal(await panel.isVisible(),false);
            }else{
              await page.evaluate(e=>window.conclaveFixture.tick(e),mode==='disconnect'?'disconnect':'chainChanged');
              assert.equal(await panel.isVisible(),false);
            }
            assert.equal(await page.locator('#double-flywheel').count(),0);
            assert.deepEqual(errors,[]);
            console.log('PASS',mode);
            continue;
          }
          assert.equal(await panel.isVisible(),true);
          assert.equal(await page.locator('#dossier').isVisible(),true);
          assert.equal(await form.isVisible(),false);
          let calls=await page.evaluate(()=>window.conclaveFixture);
          const signed=Buffer.from(calls.signed[0].slice(2),'hex').toString('utf8');
          assert.match(signed,/frontier-conclave\.html/);assert.match(signed,/ENSv1 name: member-example\.club\.agi\.eth/);
          nonce=signed.match(/Nonce: ([a-f0-9]{32})/)[1];
          assert.ok(!calls.methods.some(m=>/sendTransaction|switchEthereumChain/.test(m)));
          const start=panel.locator('[data-df="start"]');
          assert.equal(await start.isEnabled(),true);
          const stage=panel.locator('[data-df="stage"]');
          for(const phase of ['0','1','2','payoff']){
            await start.click();
            assert.equal(await stage.isVisible(),true);
            assert.equal(await stage.getAttribute('data-df-state'),phase);
          }
          assert.equal(await panel.locator('[data-df="finale"]').isVisible(),true);
          assert.equal((await page.evaluate(()=>window.conclaveFixture.signed)).length,1,'single signature for entry and complete demo');
          await page.evaluate(()=>window.conclaveFixture.tick('accountsChanged'));
          assert.equal(await panel.isVisible(),false);
          assert.equal(await page.locator('#dossier').isVisible(),false);
          await open();assert.equal(await panel.isVisible(),true);
          const second=await page.evaluate(()=>window.conclaveFixture.signed[1]);
          assert.ok(!Buffer.from(second.slice(2),'hex').toString('utf8').includes(nonce));
          await page.evaluate(()=>{
            window.conclaveFixture.withdraw();
            document.dispatchEvent(new Event('visibilitychange'));
          });
          await page.waitForFunction(()=>document.querySelector('#member').hidden);
          assert.equal(await page.locator('#double-flywheel').count(),0);
          assert.equal(page.url(),url,'demo must stay on the exact Conclave page');
          await page.reload();
          assert.equal(await panel.isVisible(),false,'reload must not retain session');
        }else{
          assert.equal(await panel.isVisible(),false);
          if(['token-only','expired','wrong-network'].includes(mode)){
            const methods=await page.evaluate(()=>window.conclaveFixture.methods);
            assert.ok(!methods.includes('personal_sign'));
          }
        }
        assert.deepEqual(errors,[]);
        console.log('PASS',mode);
      }finally{await page.close();}
    }
  }finally{await b.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
