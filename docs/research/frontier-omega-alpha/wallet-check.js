// Keccak and namehash ported from MONTREAL.AI's GoalOS Singularity Office access.js.
const enc = new TextEncoder();
const MASK64=(1n<<64n)-1n,ROT=[0,1,62,28,27,36,44,6,55,20,3,10,43,25,39,41,45,15,21,8,18,2,61,56,14],RC=[0x1n,0x8082n,0x800000000000808an,0x8000000080008000n,0x808bn,0x80000001n,0x8000000080008081n,0x8000000000008009n,0x8an,0x88n,0x80008009n,0x8000000an,0x8000808bn,0x800000000000008bn,0x8000000000008089n,0x8000000000008003n,0x8000000000008002n,0x8000000000000080n,0x800an,0x800000008000000an,0x8000000080008081n,0x8000000000008080n,0x80000001n,0x8000000080008008n];
function rotl(x,n){n=BigInt(n);return n===0n?x&MASK64:((x<<n)|(x>>(64n-n)))&MASK64}function kF(s){for(let r=0;r<24;r++){const C=Array(5),D=Array(5),B=Array(25);for(let x=0;x<5;x++)C[x]=s[x]^s[x+5]^s[x+10]^s[x+15]^s[x+20];for(let x=0;x<5;x++)D[x]=C[(x+4)%5]^rotl(C[(x+1)%5],1);for(let x=0;x<5;x++)for(let y=0;y<5;y++)s[x+5*y]=(s[x+5*y]^D[x])&MASK64;for(let x=0;x<5;x++)for(let y=0;y<5;y++)B[y+5*((2*x+3*y)%5)]=rotl(s[x+5*y],ROT[x+5*y]);for(let x=0;x<5;x++)for(let y=0;y<5;y++)s[x+5*y]=(B[x+5*y]^((~B[(x+1)%5+5*y])&B[(x+2)%5+5*y]))&MASK64;s[0]=(s[0]^RC[r])&MASK64}}
function k256(input){const bytes=typeof input==='string'?enc.encode(input):input,rate=136,n=Math.ceil((bytes.length+1)/rate)*rate,p=new Uint8Array(n);p.set(bytes);p[bytes.length]^=1;p[n-1]^=128;const s=Array(25).fill(0n);for(let o=0;o<p.length;o+=rate){for(let i=0;i<rate;i++)s[Math.floor(i/8)]^=BigInt(p[o+i])<<BigInt(8*(i%8));kF(s)}const out=new Uint8Array(32);for(let i=0;i<32;i++)out[i]=Number((s[Math.floor(i/8)]>>BigInt(8*(i%8)))&255n);return out}
function hx(b){return[...b].map(x=>x.toString(16).padStart(2,'0')).join('')}function cat(a,b){const o=new Uint8Array(a.length+b.length);o.set(a);o.set(b,a.length);return o}function namehash(name){let node=new Uint8Array(32);for(const label of name.toLowerCase().split('.').reverse())node=k256(cat(node,k256(label)));return'0x'+hx(node)}

const registry='0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e';
const wrapper='0xD4416b13d2b3a9aBae7AcD5D6C2BbDBE25686401';
const registrar='0x57f1887a8BF19b14fC0dF6Fd9B2acc9Af147eA85';
const token='0xA61a3B3a130a9c20768EEBF97E21515A6046a1fA';
const zero='0x'+'0'.repeat(40);
const min=1000000n*10n**18n;
const sessionLifetime = 5 * 60 * 1000;
const isAddr=x=>typeof x==='string'&&/^0x[0-9a-f]{40}$/i.test(x);
const quantity=x=>typeof x==='string'&&/^0x(?:0|[1-9a-f][0-9a-f]{0,63})$/i.test(x);
const hash32=x=>typeof x==='string'&&/^0x[0-9a-f]{64}$/i.test(x);
const same=(a,b)=>typeof a==='string'&&typeof b==='string'&&a.toLowerCase()===b.toLowerCase();
const selector=s=>hx(k256(s)).slice(0,8);
const word=x=>x.toString(16).padStart(64,'0');
function words(raw,count){
  if(typeof raw!=='string'||raw.length!==2+64*count||!/^0x[0-9a-f]+$/i.test(raw))throw Error('unavailable');
  return raw.slice(2).toLowerCase().match(/.{64}/g);
}
function addr(w){if(!/^0{24}[0-9a-f]{40}$/.test(w))throw Error('unavailable');return '0x'+w.slice(24);}
function normalized(value){
  const label=String(value).trim().toLowerCase();
  if(!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)||label.slice(2,4)==='--')throw Error('label');
  return label;
}
export async function eligible(wallet,account,path,label,now=Date.now()){
  if(!isAddr(account)||!['club','token'].includes(path))throw Error('unavailable');
  if(await wallet.request({method:'eth_chainId'})!=='0x1')throw Error('network');
  const ask=(method,...params)=>wallet.request({method,params});
  const block=await ask('eth_getBlockByNumber','latest',false);
  if(!hash32(block?.hash)||!quantity(block.number)||!quantity(block.timestamp))throw Error('unavailable');
  const stamp=Number(BigInt(block.timestamp));
  const age=Math.floor(now/1000)-stamp;
  if(age>90||age< -12)throw Error('unavailable');
  const call=(to,s,arg='')=>ask('eth_call',{to,data:'0x'+selector(s)+arg},block.number);
  const owner=async node=>{
    const off=node.slice(2);
    const [o]=words(await call(registry,'owner(bytes32)',off),1);
    const direct=addr(o);
    if(!same(direct,wrapper))return {who:direct,until:null};
    const [a,d]=await Promise.all([call(wrapper,'ownerOf(uint256)',off),call(wrapper,'getData(uint256)',off)]);
    const [who]=words(a,1),[record,fuses,expiry]=words(d,3);
    const fuse=BigInt('0x'+fuses),until=BigInt('0x'+expiry);
    if(fuse>0xffffffffn||until>0xffffffffffffffffn)throw Error('unavailable');
    return {who:addr(who)===addr(record)?addr(who):zero,until:(fuse&65536n)?until:null};
  };
  let result;
  if(path==='club'){
    const value=normalized(label);
    const [m,p,r,e,grace]=await Promise.all([
      owner(namehash(value+'.club.agi.eth')),owner(namehash('club.agi.eth')),owner(namehash('agi.eth')),
      call(registrar,'nameExpires(uint256)',hx(k256('agi'))),call(registrar,'GRACE_PERIOD()')
    ]);
    const time=BigInt(Math.max(stamp,Math.floor(now/1000)));
    const lease=BigInt('0x'+words(e,1)[0]),extension=BigInt('0x'+words(grace,1)[0]);
    result=same(m.who,account)&&lease>0n&&lease+extension>time&&
      [m,p,r].every(x=>x.who!==zero&&(x.until===null||x.until>time));
  }else{
    const [code,dec,sym,bal]=await Promise.all([
      ask('eth_getCode',token,block.number),call(token,'decimals()'),call(token,'symbol()'),
      call(token,'balanceOf(address)',account.slice(2).toLowerCase().padStart(64,'0'))
    ]);
    const symExpected=word(32)+word(8)+hx(enc.encode('AGIALPHA')).padEnd(64,'0');
    if(typeof code!=='string'||!/^0x(?:[0-9a-f]{2})+$/i.test(code)||
       BigInt('0x'+words(dec,1)[0])!==18n||typeof sym!=='string'||sym.toLowerCase()!=='0x'+symExpected)throw Error('unavailable');
    result=BigInt('0x'+words(bal,1)[0])>=min;
  }
  const check=await ask('eth_getBlockByNumber',block.number,false);
  if(!same(check?.hash,block.hash)||await wallet.request({method:'eth_chainId'})!=='0x1')throw Error('unavailable');
  return result;
}

export function signInMessage(origin,account,path,now,nonce){
  return [
    'FRONTIER Ω ALPHA · Public research sign-in',
    'This message does not approve a transaction or token transfer.',
    'Origin: '+origin,'Wallet: '+account,'Network: Ethereum mainnet',
    'Access check: '+(path==='club'?'ENSv1 AGI Club':'$AGIALPHA'),
    'Issued: '+new Date(now).toISOString(),'Nonce: '+nonce
  ].join('\n');
}

function showBrief(target, edition, sourceLabel) {
  const element = (tag, text) => {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  };
  const meta = element('p', edition.edition);
  meta.className = 'packet-meta';
  const title = element('h3', edition.title);
  title.id = 'brief-title';
  title.tabIndex = -1;
  target.setAttribute('aria-labelledby', title.id);
  target.replaceChildren(meta, title);
  for (const section of edition.sections) {
    target.append(element('h4', section.heading));
    for (const paragraph of section.paragraphs) target.append(element('p', paragraph));
  }
  const list = document.createElement('ul');
  for (const source of edition.sources) {
    const item = document.createElement('li');
    const link = element('a', source.label);
    link.href = source.href;
    item.append(link);
    list.append(item);
  }
  target.append(element('h4', sourceLabel), list);
  target.hidden = false;
  title.focus();
}

function mount(){
  const fr=document.documentElement.lang==='fr';
  const s=fr?{
    checking:'Vérification sur Ethereum…',
    wallet:'Ouvrez ce site dans MetaMask Mobile ou installez l’extension MetaMask sur votre navigateur.',
    network:'Sélectionnez le réseau principal Ethereum dans MetaMask, puis réessayez.',
    label:'Saisissez seulement l’identifiant avant .club.agi.eth. Utilisez des lettres ASCII, des chiffres ou des traits d’union.',
    clubNo:'Ce portefeuille ne détient pas le nom admissible. Vérifiez l’identifiant, le propriétaire et l’expiration.',
    tokenNo:'Ce portefeuille ne satisfait pas au seuil de 1 000 000 de $AGIALPHA. Vérifiez le compte sélectionné.',
    sign:'Vérifiez le message de connexion dans MetaMask.',
    clubVerified:'Adhésion AGI CLUB vérifiée', tokenVerified:'Admissibilité $AGIALPHA vérifiée',
    cancelled:'Signature annulée. Vous pouvez réessayer.', unavailable:'Vérification impossible pour le moment. Réessayez.',
    changed:'Session verrouillée. Reconnectez-vous pour vérifier le portefeuille.',
    opening:'Nouvelle vérification de l’admissibilité…', sources:'Sources et données d’essai',
    briefError:'Le dossier ne peut pas être ouvert pour le moment. Réessayez.'
  }:{
    checking:'Checking on Ethereum…',
    wallet:'Open this site in MetaMask Mobile or install the MetaMask browser extension.',
    network:'Select Ethereum Mainnet in MetaMask, then try again.',
    label:'Enter only the label before .club.agi.eth, using ASCII letters, numbers or hyphens.',
    clubNo:'This wallet does not meet the ownership requirement. Check the name, owner and expiry.',
    tokenNo:'This wallet does not meet the 1,000,000 $AGIALPHA threshold. Check the selected account.',
    sign:'Review the sign-in message in MetaMask.',
    clubVerified:'AGI CLUB membership verified', tokenVerified:'$AGIALPHA eligibility verified',
    cancelled:'Signature canceled. You can try again.', unavailable:'Could not verify right now. Please try again.',
    changed:'Session locked. Sign in again to verify your wallet.',
    opening:'Checking eligibility again…', sources:'Sources and test inputs',
    briefError:'The brief could not be opened. Try again.'
  };
  const el=id=>document.getElementById(id);
  const status=el('status'),member=el('member'),entry=el('access'),preview=el('member-preview');
  const club=el('enter-club'),clubForm=el('club-form'),clubLabel=el('club-label'),help=el('entry-help');
  const tokenEntry=document.querySelector('[data-connect="token"]');
  const buttons=[club,...document.querySelectorAll('[data-connect]')];
  const memberNav=el('member-nav'),route=el('member-route');
  const briefButton=el('open-brief'),briefStatus=el('brief-status'),brief=el('brief-content');
  if (!route || !briefButton) return; // Member HTML is inserted by public release staging.
  const say=k=>{status.textContent=s[k]??s.unavailable;};
  const selectedWallet=()=>{
    const injected=window.ethereum;
    return injected?.providers?.find(p=>p.isMetaMask)??injected;
  };
  const canSign=w=>w?.isMetaMask&&typeof w.request==='function';
  const deny=path=>say(path==='club'?'clubNo':'tokenNo');
  function showWalletHelp(){
    help.open=true;
    say('wallet');
  }
  let epoch=0,timer,provider,session,pending;
  function resetBrief() {
    session = null;
    brief.hidden = true;
    brief.replaceChildren();
    briefStatus.textContent = '';
    briefButton.disabled = false;
    briefButton.setAttribute('aria-expanded', 'false');
  }
  const lock=()=>{
    const returnToEntry=!member.hidden && member.contains(document.activeElement);
    const previousPath=session?.path;
    epoch++;
    clearTimeout(timer);
    member.hidden=true;
    entry.hidden=preview.hidden=false;
    memberNav.href='#access';
    route.textContent='';
    pending=null;
    resetBrief();
    window.dispatchEvent(new Event('frontier:member-lock'));
    buttons.forEach(b=>b.disabled=false);
    say('changed');
    if(returnToEntry)(previousPath==='club'?club:tokenEntry).focus();
  };
  const accountsChanged = accounts => {
    const active = pending ?? session;
    const selected = accounts?.[0];
    if (active && isAddr(selected) && (!active.account || same(active.account, selected))) return;
    lock();
  };
  async function openBrief() {
    if (!session) return;
    if (Date.now() >= session.expires) { lock(); return; }
    if (!brief.hidden) {
      el('brief-title').focus();
      return;
    }
    const {id, w, account, path, label} = session;
    briefButton.disabled = true;
    briefStatus.textContent = s.opening;
    try {
      const [current] = await w.request({method:'eth_accounts'});
      if (!same(current, account) || !await eligible(w, account, path, label)) {
        if (id === epoch) { lock(); deny(path); }
        return;
      }
      if (id !== epoch) return;
      const {brief001} = await import('./member-brief-001.js');
      if (id !== epoch) return;
      if (Date.now() >= session.expires) { lock(); return; }
      showBrief(brief, brief001[fr ? 'fr' : 'en'], s.sources);
      briefButton.setAttribute('aria-expanded', 'true');
      briefStatus.textContent = '';
    } catch {
      if (id === epoch) briefStatus.textContent = s.briefError;
    } finally {
      if (id === epoch) briefButton.disabled = false;
    }
  }
  async function enter(path){
    const id=++epoch;
    clearTimeout(timer);member.hidden=true;buttons.forEach(b=>b.disabled=true);
    resetBrief();
    const attempt={account:null};
    pending=attempt;
    try{
      const label=path==='club'?normalized(clubLabel.value):'';
      const w=selectedWallet();
      if(!canSign(w))throw Error('wallet');
      if(w!==provider){
        for (const [event, listener] of Object.entries({accountsChanged,chainChanged:lock,disconnect:lock})) {
          provider?.removeListener?.(event,listener);
          w.on?.(event,listener);
        }
        provider=w;
      }
      say('checking');
      const [account]=await w.request({method:'eth_requestAccounts'});
      if(id!==epoch)return;
      if(!isAddr(account))throw Error('wallet');
      attempt.account=account;
      if(!await eligible(w,account,path,label))throw Error('no');
      if(id!==epoch)return;
      const [selected]=await w.request({method:'eth_accounts'});
      if(id!==epoch)return;
      if(!same(selected,account))throw Error('no');
      say('sign');
      const message=signInMessage(window.location.origin,account,path,Date.now(),hx(crypto.getRandomValues(new Uint8Array(16))));
      const signature=await w.request({method:'personal_sign',params:['0x'+hx(enc.encode(message)),account]});
      if(id!==epoch)return;
      if(typeof signature!=='string'||!/^0x[0-9a-f]{130}$/i.test(signature))throw Error('unavailable');
      const [confirmed]=await w.request({method:'eth_accounts'});
      if(!same(confirmed,account)||!await eligible(w,account,path,label))throw Error('no');
      if(id!==epoch)return;
      session={id,w,account,path,label,expires:Date.now()+sessionLifetime};
      status.textContent='';
      entry.hidden=preview.hidden=true;
      memberNav.href='#member';
      route.textContent=s[path==='club'?'clubVerified':'tokenVerified'];
      member.hidden=false;
      window.dispatchEvent(new Event('frontier:member-enter'));
      el('workspace-title').focus({preventScroll:true});
      window.scrollTo({top:0,behavior:'instant'});
      timer=setTimeout(lock,sessionLifetime);
    }catch(e){
      if(id!==epoch)return;
      if(e?.message==='wallet')showWalletHelp();
      else if(e?.message==='no')deny(path);
      else say(e?.code===4001?'cancelled':e?.message);
    }
    finally{
      if(pending===attempt)pending=null;
      if(id===epoch)buttons.forEach(b=>b.disabled=false);
    }
  }
  buttons.forEach(b=>b.disabled=false);
  club.addEventListener('click',()=>{
    if(!canSign(selectedWallet())){showWalletHelp();return;}
    clubForm.hidden=!clubForm.hidden;
    club.setAttribute('aria-expanded',String(!clubForm.hidden));
    if(!clubForm.hidden)clubLabel.focus();
  });
  for(const link of document.querySelectorAll('[data-entry-help]')){
    link.addEventListener('click',()=>{help.open=true;});
  }
  clubForm.addEventListener('submit',e=>{e.preventDefault();void enter('club');});
  tokenEntry.addEventListener('click',()=>void enter('token'));
  briefButton.addEventListener('click',()=>void openBrief());
  el('lock').addEventListener('click',lock);
  window.addEventListener('pagehide',lock);
  document.addEventListener('visibilitychange', async () => {
    if (document.hidden || !session) return;
    const active = session;
    if (Date.now() >= active.expires) { lock(); return; }
    try {
      const [account] = await active.w.request({method:'eth_accounts'});
      const owns = same(account, active.account) && await eligible(active.w, active.account, active.path, active.label);
      if (session === active && (!owns || Date.now() >= active.expires)) lock();
    } catch {
      if (session === active) lock();
    }
  });
}
if(typeof document!=='undefined')mount();
