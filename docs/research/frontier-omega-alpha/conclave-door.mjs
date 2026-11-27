import {eligible,k256} from './wallet-check.js';

const copy={
  en:{
    title:'Enter the observatory',
    intro:'Use MetaMask on Ethereum Mainnet with the wallet that owns your active .club.agi.eth name. Tokens alone do not qualify.',
    label:'Your name before .club.agi.eth',placeholder:'your-name',enter:'Verify AGI CLUB membership',
    scope:'A message signature only: no gas, payment, or asset transfer. Your wallet’s Ethereum provider checks the signature. This is a display gate on a public site, not private delivery or event admission.',
    workspace:'The First Light member observatory',open:'AGI CLUB membership verified',lock:'Lock observatory',
    checking:'Checking ENSv1 membership…',signing:'Approve the sign-in message in MetaMask.',
    invalid:'Enter the name before .club.agi.eth.',wallet:'Open this page with MetaMask.',
    network:'Switch MetaMask to Ethereum Mainnet, then retry.',
    ineligible:'This wallet does not own the current AGI CLUB name.',
    unavailable:'Could not verify or open the observatory. Try again.',
    canceled:'Sign-in canceled.',locked:'Observatory locked.'
  },
  fr:{
    title:'Entrez dans l’observatoire',
    intro:'Utilisez MetaMask sur Ethereum Mainnet avec le portefeuille qui détient votre nom .club.agi.eth valide. Les jetons seuls ne donnent pas accès.',
    label:'Votre nom avant .club.agi.eth',placeholder:'votre-nom',enter:'Vérifier l’adhésion à l’AGI CLUB',
    scope:'Signature d’un message seulement : aucuns frais de réseau, aucun paiement ni transfert. Le fournisseur Ethereum de votre portefeuille vérifie la signature. Il s’agit d’un contrôle d’affichage sur un site public, et non d’une livraison privée ni d’une admission à l’événement.',
    workspace:'L’observatoire Première Lumière des membres',open:'Adhésion à l’AGI CLUB vérifiée',lock:'Verrouiller l’observatoire',
    checking:'Vérification de l’adhésion ENSv1…',signing:'Approuvez le message de connexion dans MetaMask.',
    invalid:'Saisissez votre nom avant .club.agi.eth.',wallet:'Ouvrez cette page dans MetaMask.',
    network:'Passez à Ethereum Mainnet dans MetaMask, puis réessayez.',
    ineligible:'Ce portefeuille ne détient pas le nom AGI CLUB valide.',
    unavailable:'Impossible de vérifier l’adhésion ou d’ouvrir l’observatoire. Réessayez.',
    canceled:'Connexion annulée.',locked:'Observatoire verrouillé.'
  }
};
const root=document.getElementById('club-door');
const workspace=document.getElementById('member');
const $=id=>document.getElementById('conclave-club-'+id);
const bytes=new TextEncoder();
const hex=arr=>Array.from(arr,x=>x.toString(16).padStart(2,'0')).join('');
const isAddress=s=>typeof s==='string'&&/^0x[\da-f]{40}$/i.test(s);
const same=(a,b)=>isAddress(a)&&isAddress(b)&&a.toLowerCase()===b.toLowerCase();
const ecrecover='0x0000000000000000000000000000000000000001';
const lifetime=5*60*1000;

// EIP-191 proof of wallet control, using Ethereum's standard ECRecover
// precompile via the same mainnet provider as the independent ENSv1 read.
async function validSignature(wallet,message,sig,account) {
  if(typeof sig!=='string'||!/^0x[\da-f]{130}$/i.test(sig))return false;
  const v=Number.parseInt(sig.slice(130),16);
  if(![0,1,27,28].includes(v))return false;
  const hash=hex(k256('\x19Ethereum Signed Message:\n'+bytes.encode(message).length+message));
  const data='0x'+hash+(v<2?v+27:v).toString(16).padStart(64,'0')+sig.slice(2,130);
  const recovered=await wallet.request({method:'eth_call',params:[{to:ecrecover,data},'latest']});
  return typeof recovered==='string'&&/^0x0{24}[\da-f]{40}$/i.test(recovered)&&same('0x'+recovered.slice(-40),account);
}

let clock,poll,checkingSession,generation=0,locale='en',session=null,pending=null,activeWallet=null,cleanup=null,state='';
const languages=[...root.querySelectorAll('[data-club-lang]')];
function status(k) {
  state=k;
  $('status').textContent=copy[locale][k]??'';
}
function localize(next) {
  locale=next;
  $('copy').lang=locale;
  workspace.lang=locale;
  workspace.setAttribute('aria-label',copy[locale].workspace);
  $('verified').textContent=copy[locale].open;
  $('lock').textContent=copy[locale].lock;
  $('label').placeholder=copy[locale].placeholder;
  for(const node of root.querySelectorAll('[data-club-copy]'))node.textContent=copy[locale][node.dataset.clubCopy];
  for(const button of languages)button.setAttribute('aria-pressed',String(button.dataset.clubLang===locale));
  status(state);
}
function lock(reason='locked'){
  const restore=workspace.contains(document.activeElement);
  generation++;
  clearTimeout(clock);
  clearInterval(poll);
  session=null;
  pending=null;
  workspace.hidden=true;
  document.getElementById('top').hidden=false;
  $('legacy').hidden=true;
  window.dispatchEvent(new Event('frontier:member-lock'));
  if(typeof cleanup==='function')cleanup();
  cleanup=null;
  $('content').replaceChildren();
  root.hidden=false;
  $('enter').disabled=false;
  status(reason);
  if(restore)$('label').focus();
}
const events={
  accountsChanged(accounts){
    const attempt=pending??session;
    const account=accounts?.[0];
    if(attempt&&(!isAddress(account)||(attempt.account&&!same(attempt.account,account))))lock();
  },
  chainChanged(){if(pending||session)lock();},
  disconnect(){if(pending||session)lock();}
};
async function recheck(active) {
  if(Date.now()>=active.until)return false;
  const [account]=await active.wallet.request({method:'eth_accounts'});
  return same(account,active.account)&&await eligible(active.wallet,account,'club',active.label)&&Date.now()<active.until;
}
function selectedWallet(){
  const injected=window.ethereum;
  const wallet=injected?.providers?.find(x=>x.isMetaMask)??injected;
  if(!wallet?.isMetaMask||typeof wallet.request!=='function')throw Error('wallet');
  return wallet;
}

$('form').addEventListener('submit',async event=>{
  event.preventDefault();
  const id=++generation;
  const attempt={account:null};
  pending=attempt;
  $('enter').disabled=true;
  status('checking');
  try{
    const label=$('label').value.trim().toLowerCase();
    if(!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)||label.slice(2,4)==='--')throw Error('invalid');
    const wallet=selectedWallet();
    if(activeWallet!==wallet){
      for(const [name,listener] of Object.entries(events)){
        activeWallet?.removeListener?.(name,listener);
        wallet.on?.(name,listener);
      }
      activeWallet=wallet;
    }
    const [account]=await wallet.request({method:'eth_requestAccounts'});
    if(id!==generation)return;
    if(!isAddress(account))throw Error('wallet');
    attempt.account=account;
    if(!await eligible(wallet,account,'club',label))throw Error('ineligible');
    if(id!==generation)return;
    const [selected]=await wallet.request({method:'eth_accounts'});
    if(!same(selected,account))throw Error('ineligible');
    if(id!==generation)return;
    const issued=Date.now();
    const message=['THE FRONTIER CONCLAVE Ω · AGI CLUB observatory',
      'Sign-in only. No transaction or token transfer.',
      'URI: '+location.origin+location.pathname,'Wallet: '+account,
      'Chain ID: 1','ENSv1 name: '+label+'.club.agi.eth',
      'Issued At: '+new Date(issued).toISOString(),
      'Expires At: '+new Date(issued+lifetime).toISOString(),
      'Nonce: '+hex(crypto.getRandomValues(new Uint8Array(16)))].join('\n');
    status('signing');
    const sig=await wallet.request({method:'personal_sign',params:['0x'+hex(bytes.encode(message)),account]});
    if(id!==generation)return;
    if(!await validSignature(wallet,message,sig,account))throw Error('unavailable');

    // Import the same module as the canonical member portal before insertion.
    // Its existing auto-mount finds no live demo inside the inert templates.
    const {mountDoubleFlywheel}=await import('./double-flywheel.mjs');
    const next={account,label,wallet,until:issued+lifetime};
    if(!await recheck(next))throw Error('ineligible');
    if(id!==generation)return;
    const fragment=document.getElementById('conclave-demo-'+locale).content.cloneNode(true);
    const host=fragment.querySelector('[data-double-flywheel]');
    if(!host)throw Error('unavailable');
    $('content').replaceChildren(fragment);
    host.hidden=false;
    cleanup=mountDoubleFlywheel(host,locale);
    if(host.querySelector('[data-df="start"]')?.disabled!==false)throw Error('unavailable');
    session=next;
    status('open');
    workspace.hidden=false;
    $('legacy').hidden=false;
    root.hidden=true;
    document.getElementById('top').hidden=true;
    workspace.scrollIntoView({block:'start',behavior:'instant'});
    host.querySelector('#df-title')?.focus({preventScroll:true});
    clock=setTimeout(()=>lock(),Math.max(0,next.until-Date.now()));
    poll=setInterval(checkActiveSession,30_000);
  }catch(error){
    if(id===generation){
      const code=error?.code===4001?'canceled':Object.hasOwn(copy[locale],error?.message)?error.message:'unavailable';
      if($('content').firstChild)lock(code);
      else status(code);
    }
  }finally{
    if(pending===attempt)pending=null;
    if(id===generation)$('enter').disabled=false;
  }
});
$('lock').addEventListener('click',()=>lock());
for(const button of languages){
  button.disabled=false;
  button.addEventListener('click',()=>{if(!pending&&!session)localize(button.dataset.clubLang);});
}
window.addEventListener('pagehide',()=>{if(pending||session)lock();});
async function checkActiveSession(){
  const active=session;
  if(document.hidden||!active||checkingSession===active)return;
  checkingSession=active;
  try{if(!await recheck(active)&&active===session)lock();}
  catch{if(active===session)lock();}
  finally{if(checkingSession===active)checkingSession=null;}
}
document.addEventListener('visibilitychange',checkActiveSession);
$('enter').disabled=false;
