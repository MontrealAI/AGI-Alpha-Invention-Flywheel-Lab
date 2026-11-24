// P0-270 source-bound static inspection; no source is imported or executed.
// Node >=18. Run: node inspect.cjs /path/to/checkout-of-owner-ced6c1cb004887dcdafaea59a2976020be649f8e
const fs=require("node:fs");
const path=require("node:path");
const crypto=require("node:crypto");
const pins={
  "connected_enterprise/upgrades.py": "9866d004c412fc05c9f6292cf898307f177359df",
  "connected_enterprise/finance.py": "c01e5cd97fb32b3e5fcd5cea190424d8f4f5d5ec",
  "connected_enterprise/transition_evidence.py": "2397091ef8e1960ad13950693d5b3cd04e2ff7c5",
  "connected_enterprise/migration.py": "7d0ddf8b1226571d2fa0eb6c49252840a930b67e",
  "adaptive_enterprise/account.py": "d8b3c159af21519c1bcc3c2cde0dc8c572ca1122",
  "adaptive_enterprise/instruments.py": "d2a8474573c80800b7baa768dd5dc3128cd3691c",
  "commercial/ledger.py": "6cacd0a6ecc16216c498969c30f40b9c75244732"
};
function inspect(sources,pins){
 const U="connected_enterprise/upgrades.py", F="connected_enterprise/finance.py",E="connected_enterprise/transition_evidence.py",M="connected_enterprise/migration.py",A="adaptive_enterprise/account.py",L="commercial/ledger.py",I="adaptive_enterprise/instruments.py";
 const checks=[];
 function anchor(path,fragment,label,expected=1){
   const lines=sources[path].split("\n").flatMap((s,i)=>s.includes(fragment)?[{line:i+1,text:s.trim()}]:[]);
   const pass=lines.length===expected;
   checks.push({label,path,blob:pins[path],expected,observed:lines.length,pass,lines});
   return lines.map(x=>x.line);
 }
 anchor(F,"checked = audit_account(record, root=root, manifest=manifest, pending_source_transition=pending_transition)","journal invokes adaptive audit");
 anchor(F,"validated_history = _validate_source_history(journal, record, manifest, root)","journal history validation before entry checks");
 anchor(F,"if _validate_source_history(journal, record, manifest, root) != validated_history:","journal history validation after entry checks");
 anchor(F,"        verify_historical(ticket, manifest, root=root)","journal history calls historical verifier");
 anchor(A,"        verify_historical(ticket, manifest, root=root)","adaptive audit committed history calls historical verifier");
 anchor(A,"        verify_historical(pending_source_transition, manifest, root=root)","adaptive audit pending transition calls historical verifier");
 anchor(U,"cache_key = digest({'ticket': ticket, 'manifest': manifest, 'root': str(root),","historical cache key prefix");
 anchor(U,"                        'verifier_files': body['verifier_files']})","historical cache key suffix");
 anchor(U,"return copy.deepcopy(_HISTORICAL_AUDITS[cache_key])","hit returns before child launch");
 anchor(U,"'evidence_dir': current_store_directory()","child payload carries store route");
 anchor(U,"scope=evidence_directory(p['evidence_dir'])","child enters directory scope");
 anchor(U,"r=audit_journal(p['record'],root=p['root'],manifest=p['manifest'])","child recurses through journal audit");
 anchor(U,"done = subprocess.run([sys.executable, '-c', code], input=json.dumps(payload),","historical replay and authorization launch separately",2);
 anchor(U,"'historical-source-versions'} for part in relative.parts","inventory excludes historical descendants");
 anchor(E,"        _recover_published_aliases(fd)","directory scope invokes recovery");
 anchor(E,"        os.unlink(pending,dir_fd=fd);os.fsync(fd)","verified staging-alias cleanup has durable effects");
 anchor(E,"        fcntl.flock(fd,fcntl.LOCK_EX)","directory scope and persistence lock",2);
 anchor(E,"return getattr(store,'path',None)","directory routing uses store path");
 anchor(E,"token=_store.set(MappingProxyType(verified))","in-memory scope installs immutable byte map");
 anchor(E,"raw=store.get(ref['sha256'])","ticket reads referenced blob");
 anchor(E,"if raw is None or len(raw)!=ref['bytes'] or _sha(raw)!=ref['sha256']:","ticket rebinds size and bytes");
 anchor(E,"if not hmac.compare_digest(expected,str(ticket['signature'])):","keyed ticket authentication remains separate");
 anchor(U,"if not hmac.compare_digest(expected, str(ticket['signature'])):","upgrade validates keyed ticket");
 anchor(M,"if not hmac.compare_digest(str(envelope['signature']), signature):","operating checkpoint authentication remains separate");
 anchor(F,"if not hmac.compare_digest(str(envelope['signature']), self._signature(body)):","owned journal authentication");
 anchor(F,"authority = validate_ticket(ticket, key=self._account._key, root=self.root, path=self.path)","owned journal validates target/path with key");
 anchor(A,"body = validate_ticket(ticket, key=self._key, root=self.root, path=self.path)","owned adaptive ticket validation",3);
 anchor(A,"atomic_bytes(self._transitions_path,raw+b'\\n')","owned transition writes authority state");
 anchor(A,"self._owner.execute('source_transition', args, body['day'])","owned transition commits native action");
 anchor(F,"with tempfile.TemporaryDirectory(prefix='connected014-rejection-audit-')","rejection verifier uses isolated temporary state");
 anchor(L,"with tempfile.TemporaryDirectory(prefix='commercial010-audit-')","native replay uses isolated temporary state");
 anchor(L,"return adaptive_jobs(root, manifest)","adaptive service manifest delegates to instrument verifier");
 anchor(I,"hashlib.sha256(source.read_bytes()).hexdigest()!=expected","adaptive service verifier binds source bytes");
 return {kind:"source_anchor_inventory_not_runtime_trace",checks,passed:checks.filter(x=>x.pass).length,total:checks.length,all_pass:checks.every(x=>x.pass),
 conclusions:{
  journal_replay_fanout:"The inspected implementation requests historical verification from adaptive committed history, journal history before entry checks, and journal history again after entry checks. Pending and owned calls are separate. Different versions need independent inspection.",
  cache_key_boundary:"The exact key contains ticket, manifest, selected root and verifier_files. The separately resolved child evidence directory is not a key field. This does not prove a context collision in a native execution.",
  effect_boundary:"A directory-backed historical launch can perform verified staging-alias recovery on entry, including unlink and fsync. A cache hit bypasses this child invocation. Treat recovery and pure semantic replay as different obligations; do not bypass recovery to obtain speed.",
  pure_cache_eligible:false,
  owned_authorization_cache_eligible:false,
  native_equivalence_established:false
 }};
}
const sources={};
if(process.argv.length!==3)throw new Error("Supply the exact historical source checkout root.");
for(const [name,expected] of Object.entries(pins)){
 const bytes=fs.readFileSync(path.join(process.argv[2],name));
 const actual=crypto.createHash("sha1").update(Buffer.from("blob "+bytes.length+"\0")).update(bytes).digest("hex");
 if(actual!==expected)throw new Error("GIT_BLOB_MISMATCH:"+name);
 sources[name]=bytes.toString("utf8");
}
const result=inspect(sources,pins);
console.log(JSON.stringify(result,null,2));
if(!result.all_pass)process.exitCode=1;
