"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const page = document.body.dataset.page;
  const params = new URLSearchParams(location.search);
  let language = params.get("lang");
  if (!["en", "fr"].includes(language)) {
    try { language = localStorage.getItem("ignition-language"); } catch {}
  }
  if (!["en", "fr"].includes(language)) language = navigator.language.startsWith("fr") ? "fr" : "en";
  if (params.has("lang")) {
    try {localStorage.setItem("ignition-language", language);} catch {}
  }
  const t = (en, fr) => language === "fr" ? fr : en;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const json = value => JSON.stringify(value, null, 2);
  const read = id => $(id).value.trim();
  let session = null, service = null, pending = null, current = null, runs = [], timer, busy = false, generation = 0;
  let commercial = null, approvalKey = null, trialKey = null, sourceRun = null;
  const announce = value => { $("notices").textContent = value; };
  const notKnown = () => t("Unmeasured","Non mesuré");
  function facts(list) {
    const dl = el("dl");
    for (const [label, value] of list) dl.append(el("dt", label), el("dd", value ?? notKnown()));
    return dl;
  }
  function button(label, handler) {
    const node = el("button", label); node.type = "button"; node.disabled = busy;
    node.addEventListener("click", handler);
    return node;
  }
  function localError(error) {
    if (error instanceof SyntaxError) return t("Enter valid JSON for the input.","Entrez des données JSON valides.");
    if (error.message && !error.status && !(error instanceof TypeError)) return error.message;
    const messages = {
      400:t("The request did not meet the mission rules.","La demande ne respecte pas les règles de la mission."),
      401:t("Sign in with a valid invitation.","Connectez-vous avec une invitation valide."),
      403:t("This action requires additional authority.","Cette action nécessite une autorisation supplémentaire."),
      404:t("This record is unavailable in this workspace.","Ce dossier est inaccessible dans cet espace."),
      409:t("The record changed. Refresh before trying again.","Le dossier a changé. Actualisez-le avant de réessayer."),
      429:t("The service is at its limit. Try again later.","Le service a atteint sa limite. Réessayez plus tard."),
      503:t("The worker is unavailable. Your saved missions remain in the workspace.","Le service d’exécution est indisponible. Vos missions enregistrées restent dans votre espace.")
    };
    return messages[error.status] || t("The connection failed. Your last confirmed record is preserved.","La connexion a échoué. Votre dernier dossier confirmé est conservé.");
  }
  async function api(url, body) {
    const options = {credentials:"same-origin", cache:"no-store", headers:{Accept:"application/json"}};
    if (body !== undefined) {
      options.method = "POST";
      options.headers["Content-Type"] = "application/json";
      options.headers["X-Ignition-Request"] = "1";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    if (!response.ok) {
      const error = new Error("HTTP " + response.status); error.status = response.status;
      if (response.status === 401 && session?.authenticated) {
        clearTimeout(timer);
        location.replace("/studio?lang=" + language);
      }
      throw error;
    }
    return response.json();
  }
  function demo() {
    const step = document.querySelector('input[name="metric"]:checked').value === "step";
    $("demo-result").replaceChildren(
      el("p",step ? t("208.27 → 92.82 ms","208,27 → 92,82 ms") : t("8.005 s → 8.005 s","8,005 s → 8,005 s"), "demo-number"),
      el("p", step ? t("Summed median normalization time across 24 windows. Two windows accounted for 98.73% of the gain.","Somme des temps médians de normalisation pour 24 fenêtres. Deux fenêtres représentaient 98,73 % du gain.") :
        t("Mean whole-reader CPU time on the sparse panel. The original and patched readers tied. No beneficiary speedup or payment was established.","Temps moyen de lecture complète sur processeur pour le panneau peu dense. Les deux versions sont à égalité. Aucun gain pour le bénéficiaire ni aucun paiement n’a été établi."))
    );
    document.querySelector(".chart").classList.toggle("step",step);
  }
  function languages() {
    document.documentElement.lang = language;
    document.querySelectorAll("[data-en][data-fr]").forEach(node => { node.textContent = node.dataset[language]; });
    for (const code of ["en","fr"]) $(code).setAttribute("aria-pressed",String(code === language));
    if (page === "demo") demo();
    if (page === "studio") {
      templateChanged(); environment(); inventory();
      if (pending) review();
      if (current) renderRun(true);
    }
  }
  for (const code of ["en","fr"]) $(code).onclick = () => {
    language = code;
    try {localStorage.setItem("ignition-language",code);} catch {}
    const url = new URL(location.href); url.searchParams.set("lang",code); history.replaceState(null,"",url);
    languages();
  };
  const stateLabels = {
    active:["Active","Active"], paused:["Paused","En pause"], stopped:["Cancelled","Annulée"],
    queued:["Queued","En attente"], running:["Running","En cours"], verified:["Verified construction","Construction vérifiée"],
    failed:["Verification or execution failed","Échec de l’exécution ou de la vérification"],
    deferred:["No construction justified","Construction non justifiée"], blocked:["Blocked","Bloquée"],
    stale:["Source changed","Source modifiée"], awaiting_contract:["Scope approval required","Approbation de la portée requise"],
    awaiting_choice:["A decision is needed","Décision requise"], awaiting_model:["Awaiting a model response","Réponse du modèle attendue"],
    identified:["Opportunity identified","Occasion identifiée"], offered:["Offer recorded","Offre consignée"], accepted:["Accepted","Acceptée"],
    delivered:["Delivered","Livrée"], paid:["Payment reconciled","Paiement rapproché"], unassessed:["No commercial evidence recorded","Aucune preuve commerciale consignée"],
    validated:["Validated","Validée"], withheld:["Withheld","Suspendue"], tie:["Equal on the measured workflow","Égalité sur le parcours mesuré"],
    baseline_wins:["Existing method wins","Avantage à la méthode existante"], candidate_wins:["Candidate wins","Avantage à la solution proposée"],
    incomparable:["Comparison inconclusive","Comparaison non concluante"]
  };
  const label = key => stateLabels[key] ? t(...stateLabels[key]) : key || notKnown();
  const status = run => run.operation?.state === "paused" || run.operation?.state === "stopped" ? run.operation.state : run.status;
  const active = () => current && ["queued","running"].includes(status(current));
  function environment() {
    if (page !== "studio") return;
    const names = {local:t("Local execution","Exécution locale"), staging:t("Staging · qualification only","Préproduction · qualification"),production:t("Production · private","Production · privée")};
    $("environment").textContent = session?.authenticated ? names[session.environment] || t("Environment unconfirmed","Environnement non confirmé") : "";
    $("signout").hidden = !session?.authenticated || session.environment === "local";
  }
  function templateChanged() {
    const kind = $("template").value;
    $("template").disabled=Boolean(sourceRun);
    $("reuse-scope").hidden=$("reuse-rights").disabled=!sourceRun;
    if(sourceRun) $("reuse-origin").textContent=t("Source mission · ","Mission source · ")+sourceRun.purpose+
      t(". The original program is tested unchanged. Supply a fresh positive case. A changed mapping or trusted manifest can fail the new contract.",
        ". Le programme d’origine est testé tel quel. Fournissez un nouveau cas positif. Une conversion ou un manifeste de référence différent peut faire échouer le nouveau contrat.");
    for (const id of ["migration","integrity"]) {
      const box = $(id+"-fields"); box.hidden = box.disabled = id !== kind;
    }
    $("custom-fields").hidden = Boolean(kind);
    for (const item of $("custom-fields").querySelectorAll("textarea,input")) item.disabled = Boolean(kind);
    $("call-budget").disabled = Boolean(kind) || !$("model").checked;
    const unavailable = !service || service.mode !== "local";
    $("guided-model-label").hidden = !kind || unavailable || Boolean(sourceRun);
    $("guided-model").disabled = !kind || unavailable || Boolean(sourceRun);
    if (unavailable || sourceRun) $("guided-model").checked = false;
    $("model").disabled = Boolean(kind) || Boolean(unavailable);
    if (unavailable) { $("model").checked = false; $("call-budget").disabled = true; }
    $("template-hint").textContent = kind ? t("Build a new tool from your inputs. By default the built-in constructor works locally without model calls.","Construisez un nouvel outil à partir de vos données. Par défaut, le constructeur intégré s’exécute localement sans appel au modèle.") :
      unavailable ? t("The local model is unavailable. Guided constructions still run. Open-ended requests may stop for lack of evidence or model access.","Le modèle local est indisponible. Les constructions guidées fonctionnent. Une mission libre peut être suspendue faute de preuves ou d’accès au modèle.") :
      t("Describe the ambition and the evidence it must meet. The engine can investigate it or record why construction should wait.","Décrivez l’ambition et les preuves requises. Le moteur peut l’étudier ou expliquer pourquoi la construction doit attendre.");
  }
  function inventory() {
    if (page !== "studio") return;
    const host = $("inventory");
    host.replaceChildren();
    if (!session?.authenticated) return;
    if (!runs.length) host.append(el("p",t("No saved missions yet.","Aucune mission enregistrée pour le moment."),"hint"));
    for (const r of runs) {
      const node = button("", () => openRun(r.id)); node.className="mission-item";
      node.append(el("span",r.purpose),el("small",label(r.operation_state === "active" ? r.observed_status : r.operation_state)));
      host.append(node);
    }
  }
  async function refreshInventory() {
    const data = await api("/api/runs");
    runs = data.runs; inventory();
  }
  async function getSession() {
    session = await api("/api/session");
    $("signin").hidden = Boolean(session.authenticated); $("workspace").hidden = !session.authenticated;
    environment();
    if (session.authenticated) {
      service = await api("/api/status"); templateChanged();
      await refreshInventory();
      const id = new URLSearchParams(location.hash.slice(1)).get("mission");
      if (id && /^[a-f0-9]{32}$/.test(id)) await openRun(id);
    }
  }
  function fieldName(id) {
    const s = read(id);
    if (!/^[A-Za-z_][A-Za-z_0-9. -]{0,79}$/.test(s)) throw Error(t("Field names must begin with a letter or underscore and use only letters A–Z, digits, spaces, dots, hyphens or underscores.","Les noms de champ doivent commencer par une lettre ou un soulignement et contenir uniquement des lettres A–Z, des chiffres, des espaces, des points, des tirets ou des soulignements."));
    return s;
  }
  async function brief() {
    const kind = $("template").value;
    const sources = [];
    const mission = {purpose:read("purpose"),beneficiary:read("beneficiary"),requirements:[],authority:{},resources:{},time:{},construction_spec:{}};
    if (!mission.purpose || !mission.beneficiary) throw Error(t("Enter an outcome and a beneficiary.","Indiquez un résultat et un bénéficiaire."));
    const minutes = Number($("time-budget").value);
    const deadline = new Date(Date.now() + minutes * 60000);
    if (!Number.isSafeInteger(minutes) || minutes < 1 || !Number.isFinite(deadline.getTime()))
      throw Error(t("Enter a valid time allowance in whole minutes.", "Indiquez un délai valide en minutes entières."));
    mission.time.deadline = deadline.toISOString();
    if (!kind) {
      mission.requirements = read("requirements").split("\n").map(x=>x.trim()).filter(Boolean);
      if (!mission.requirements.length) throw Error(t("Add an acceptance requirement.","Ajoutez un critère de réussite."));
      mission.authority = {local_model:$("model").checked,public_sources:$("feeds").checked};
      mission.resources = {execution_strategy:"research",max_model_calls:$("model").checked ? Number($("call-budget").value) : 0,max_repairs:1};
      const sourceIds=["source-url","source-publisher","source-title","source-rights","source-text","source-date"];
      if(sourceIds.some(id=>read(id))) {
        if(sourceIds.slice(0,-1).some(id=>!read(id)) || !read("source-url").startsWith("https://"))
          throw Error(t("Include an HTTPS URL, publisher, title, rights and excerpt for the evidence source.","Indiquez l’adresse HTTPS, l’organisme éditeur, le titre, les droits et l’extrait de la source."));
        const snapshot={url:read("source-url"),publisher:read("source-publisher"),title:read("source-title"),rights:read("source-rights"),text:read("source-text"),retrieved_at:new Date().toISOString()};
        if(read("source-date"))snapshot.event_at=read("source-date")+"T00:00:00Z";
        sources.push(snapshot);
      }
    } else {
      let definition, cases;
      mission.resources = {execution_strategy:"adaptive",max_model_calls:0,max_repairs:0};
      if(sourceRun) Object.assign(mission.resources,{execution_strategy:"direct",direct_method:"specialist"});
      if($("guided-model").checked && !$("guided-model").disabled) {
        mission.authority.local_model=true;
        Object.assign(mission.resources,{direct_method:"model",max_model_calls:2,max_repairs:1});
      }
      if (kind === "migration") {
        const from=fieldName("from-field"), to=fieldName("to-field");
        definition={columns:[{source:from,target:to,type:"text"}],extra_fields:"reject"};
        cases=[
          {name:t("Operator example","Exemple fourni"),input:{rows:[{[from]:$("sample-value").value}]},expected:{rows:[{[to]:$("expected-value").value}]}},
          {name:t("Missing required field","Champ requis absent"),input:{rows:[{}]},error:"missing_field"}
        ];
        mission.requirements=[t("Rename the specified text field, preserve its value and reject an incomplete row.","Renommer le champ texte indiqué, conserver sa valeur et refuser les lignes incomplètes.")];
      } else {
        const file = $("file").files[0], digest=read("digest").toLowerCase();
        if (!file || file.size>65536 || !/^[A-Za-z0-9_. -]{1,240}$/.test(file.name) || [".",".."].includes(file.name))
          throw Error(t("Choose a file of at most 64 KiB with a portable filename using letters A–Z, digits, spaces, underscores, dots or hyphens.","Choisissez un fichier d’au plus 64 Kio dont le nom contient uniquement des lettres A–Z, des chiffres, des espaces, des soulignements, des points ou des tirets."));
        const bytes = new Uint8Array(await file.arrayBuffer());
        const measured = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),x=>x.toString(16).padStart(2,"0")).join("");
        let raw = ""; for (const value of bytes) raw += String.fromCharCode(value);
        const match = measured === digest;
        definition={manifest:{[file.name]:digest}};
        cases=[
          {name:t("File received","Fichier reçu"),input:{files:{[file.name]:btoa(raw)}},expected:{ok:match,matched:match?[file.name]:[],changed:match?[]:[file.name],missing:[],unexpected:[]}},
          {name:t("File absent","Fichier absent"),input:{files:{}},expected:{ok:false,matched:[],changed:[],missing:[file.name],unexpected:[]}}
        ];
        mission.requirements=[t("Classify the supplied file against the trusted digest and report an omitted file.","Comparer le fichier à l’empreinte de référence et signaler son absence.")];
      }
      mission.construction_spec={kind:kind==="migration" ? "record_migration":"manifest_audit",purpose:mission.purpose,definition,cases};
    }
    mission.authority.allow_program_reuse=$("allow-reuse").checked;
    const price=read("offer-price").replace(",",".");
    if(price){
      const currency=read("offer-currency").toUpperCase();
      if(!/^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(price) || !/[1-9]/.test(price) || !/^[A-Z]{3}$/.test(currency)){
        $("offer-pricing").open=true;
        throw Error(t("Enter a positive proposed price and a three-letter currency code.","Indiquez un prix proposé positif et un code de devise de trois lettres."));
      }
      mission.resources.commercial_case={
        currency,unit:t("verified package","paquet vérifié"),horizon:t("one delivery","une livraison"),
        price:{low:price,high:price,provenance:"assumption",source:t("Proposed by the invited user for a private offer draft.","Prix proposé par la personne invitée pour un projet d’offre privé.")}
      };
    }
    return {mission,sources,request_id:crypto.randomUUID()};
  }
  function review() {
    const m=pending.mission;
    const def=m.construction_spec.definition;
    const terms=m.resources.commercial_case;
    const details=def?.columns ? def.columns.map(col=>[t("Conversion","Conversion"),col.source+" → "+col.target]) :
      def?.manifest ? Object.entries(def.manifest).map(([name,hash])=>[name,"SHA-256 · "+hash]):[];
    $("review-content").replaceChildren(facts([
      [t("Outcome","Résultat"),m.purpose],[t("Beneficiary","Bénéficiaire"),m.beneficiary],
      [t("Acceptance","Critères de réussite"),m.requirements.join(" · ")],
      ...details,
      [t("Supplied evidence","Sources fournies"),String(pending.sources.length)],
      [t("Stop starting new work after","Cesser de lancer de nouvelles étapes après"),new Date(m.time.deadline).toLocaleString(language)],
      [t("Paid provider budget","Budget de services payants"),"0 USD"],
      [t("Model-call limit","Appels au modèle"),String(m.resources.max_model_calls)],
      [t("Repair limit","Tentatives de correction"),String(m.resources.max_repairs)],
      [t("Source access","Accès aux sources"),m.authority.public_sources ? t("Approved public feeds","Flux publics approuvés"):t("Supplied inputs only","Données fournies uniquement")],
      ...(sourceRun?[[t("Source program","Programme source"),sourceRun.purpose],[t("Basis for this reuse","Droits permettant cette réutilisation"),read("reuse-rights")]]:[]),
      [t("Future program reuse","Réutilisation future"),m.authority.allow_program_reuse?t("Permitted after a fresh review","Autorisée après un nouvel examen"):t("No permission granted","Aucune autorisation accordée")],
      ...(terms?[[t("Proposed price per verified package","Prix proposé par paquet vérifié"),terms.currency+" "+terms.price.low]]:[]),
      [t("Financial authority","Autorisation financière"),t("No purchases or payments. Vincent handles transactions.","Aucun achat ni paiement. Vincent effectue les transactions.")],
      [t("External contact","Contact externe"),t("None authorized","Aucun contact autorisé")]
    ]));
    $("review-panel").hidden=false; $("intake").hidden=true;
  }
  function stageText(s) {
    return ({
      verified:t("Download the verified artifact or run it on your own input below.","Téléchargez l’outil vérifié ou essayez-le sur vos propres données ci-dessous."),
      deferred:t("The evidence did not justify construction. Review the decision before proposing new work.","Les preuves ne justifient pas une construction. Consultez la décision avant de proposer une nouvelle mission."),
      blocked:t("Execution stopped at a dependency or permission boundary. Inspect the recorded reason before resuming.","L’exécution s’est arrêtée à cause d’une dépendance ou d’une limite d’autorisation. Consultez la raison avant de reprendre."),
      failed:t("Inspect the mismatch or execution error. The record retains the failed result.","Consultez l’écart observé ou l’erreur d’exécution. Le dossier conserve le résultat de cet échec."),
      paused:t("Further work waits until you resume this mission.","La mission attend votre décision de reprise."),
      stopped:t("The mission is closed. Its evidence remains available.","La mission est clôturée. Ses résultats restent accessibles."),
      stale:t("The source or provider has changed. Start a new mission to evaluate the current version.","Le code ou le fournisseur a changé. Lancez une mission pour évaluer la version actuelle."),
      awaiting_contract:t("Review the proposed scope and provide an independent test before approving construction.","Examinez la portée proposée et fournissez un test indépendant avant d’autoriser la construction."),
      awaiting_choice:t("Select the rule that matches your intended result, or decline to choose.","Sélectionnez la règle correspondant au résultat souhaité ou déclinez le choix."),
      awaiting_model:t("An operator-assisted model response is pending. Its request is in the technical record.","Une réponse assistée par un opérateur est attendue. La demande figure dans le dossier technique."),
      queued:t("Your mission is saved and waiting for a worker.","Votre mission est enregistrée et attend une capacité d’exécution."),
      running:t("The worker is executing the approved scope. This record updates automatically.","Le moteur exécute la mission autorisée. Cette page s’actualise automatiquement.")
    })[s] || t("Inspect the latest recorded event below.","Consultez le dernier événement consigné ci-dessous.");
  }
  function control(action) {
    if (action === "stop" && !window.confirm(t("Cancel this mission permanently and preserve the record?","Annuler définitivement cette mission et conserver son dossier ?"))) return;
    mutate("operation",{operation:action,sequence:current.operation.sequence});
  }
  function confirmationForm(spec, retained) {
    const form=el("form");
    const field=(name,title,type="text")=>{
      const input=el("input");
      input.type=type;input.required=true;input.id="confirm-"+name;
      const lab=el("label",title);lab.htmlFor=input.id;form.append(lab,input);
      if(retained.has(input.id) && type!=="file")input.value=retained.get(input.id);
      return input;
    };
    const def=spec.definition;
    let build;
    if(spec.kind==="record_migration") {
      const columns=def.columns || [];
      const sources=def.input_fields || [...new Set(columns.flatMap(c=>c.sources || [c.source]))];
      const targets=def.targets || columns.map(c=>({name:c.target,type:c.type}));
      form.append(el("p",t("Enter one new input row and the output you independently expect. The engine checks both against the frozen proposal.","Saisissez une nouvelle ligne d’entrée et la sortie que vous attendez de façon indépendante. Le moteur les compare à la proposition figée.")));
      const declared=spec.cases?.find(c=>c.input?.rows?.length)?.input.rows[0] || {};
      function cell(name,title,type) {
        const input=field(name,title,type==="boolean"?"checkbox":type==="integer"?"number":"text");
        if(type==="boolean") {input.required=false;input.checked=retained.get(input.id)==="checked";}
        if(type==="integer") input.step="1";
        return ()=>type==="boolean" ? input.checked : type==="integer" ? Number(input.value) : input.value;
      }
      const src=sources.map((key,i)=>[key,cell("input-"+i,t("Input · ","Entrée · ")+key,
        typeof declared[key]==="number"?"integer":typeof declared[key]==="boolean"?"boolean":"text")]);
      const dst=targets.map((v,i)=>[v.name,cell("output-"+i,t("Expected output · ","Sortie attendue · ")+v.name,v.type)]);
      const row=items=>Object.fromEntries(items.map(([name,get])=>[name,get()]));
      build=async()=>[{name:"Independent studio confirmation",input:{rows:[row(src)]},expected:{rows:[row(dst)]}}];
    } else if(spec.kind==="manifest_audit") {
      form.append(el("p",t("Choose a fresh authorized file and classify the expected result using your independent knowledge of the delivery. The private mission retains the bytes.","Choisissez un nouveau fichier autorisé et indiquez le résultat attendu selon votre connaissance indépendante de la livraison. La mission privée conserve son contenu.")));
      const file=field("file",t("Independent file, up to 64 KiB","Fichier indépendant, jusqu’à 64 Kio"),"file");
      const logical=field("path",t("Filename in the delivery","Nom du fichier dans la livraison"));
      file.onchange=()=>{if(!logical.value && file.files[0])logical.value=file.files[0].name;};
      const select=el("select");select.id="confirm-result";
      for(const [value,name] of [["matched",t("Matches the manifest","Conforme au manifeste")],["changed",t("Content differs","Contenu modifié")],["unexpected",t("Absent from the manifest","Absent du manifeste")]]) {
        const op=el("option",name);op.value=value;select.append(op);
      }
      const lab=el("label",t("Expected classification","Classement attendu"));lab.htmlFor=select.id;form.append(lab,select);
      if(retained.has(select.id))select.value=retained.get(select.id);
      build=async()=>{
        const f=file.files[0],name=logical.value,kind=select.value;
        if(!f || f.size>65536)throw Error(t("Select a file no larger than 64 KiB.","Sélectionnez un fichier d’au plus 64 Kio."));
        let raw="";for(const b of new Uint8Array(await f.arrayBuffer()))raw+=String.fromCharCode(b);
        const missing=Object.keys(def.manifest).filter(key=>key!==name).sort();
        const expected={ok:kind==="matched" && !missing.length,matched:[],changed:[],missing,unexpected:[]};
        expected[kind].push(name);
        return [{name:"Independent studio confirmation",input:{files:{[name]:btoa(raw)}},expected}];
      };
    }
    const advanced=el("details");advanced.append(el("summary",t("Advanced confirmation data","Données de confirmation avancées")));
    const labelNode=el("label",t("Optional JSON array of fresh cases","Tableau JSON facultatif de nouveaux cas"));labelNode.htmlFor="confirmation";
    const text=el("textarea");text.rows=4;text.id="confirmation";text.value=retained.get(text.id)||"";
    advanced.append(labelNode,text);form.append(advanced);
    const submit=el("button",t("Approve scoped construction","Approuver la construction proposée"));submit.type="submit";
    submit.className="primary";form.append(submit);
    form.noValidate=true;
    form.onsubmit=async event=>{
      event.preventDefault();
      try {
        if(!text.value.trim() && !form.reportValidity())return;
        const version=current.version, hash=current.contract_sha256;
        const confirmations=text.value.trim()?JSON.parse(text.value):await build();
        if(current?.version!==version || current.contract_sha256!==hash)return;
        await mutate("approve",{contract_sha256:hash,confirmations});
      } catch(e){announce(localError(e));}
    };
    return form;
  }
  function approval(force) {
    const key=[current.id,current.version,status(current),current.contract_sha256,current.mapping_choice?.sha256].join("/");
    if (approvalKey===key && !force) return;
    const host=$("pending");
    const same=key===approvalKey;
    const retained=new Map();
    if(same)for(const input of host.querySelectorAll("input,select,textarea"))
      retained.set(input.id,input.type==="checkbox"?(input.checked?"checked":""):input.value);
    host.replaceChildren(); approvalKey=key;
    if (status(current)==="awaiting_contract" && current.proposed_contract) {
      const spec=current.proposed_contract.spec;
      const technical=el("details");technical.append(el("summary",t("Inspect the complete proposed specification","Examiner la spécification proposée")),el("pre",json(spec)));
      host.append(el("h3",t("Confirm the proposed scope","Confirmer la portée proposée")),el("p",spec.purpose),technical,
        confirmationForm(spec,retained),button(t("Decline and cancel","Refuser et annuler"),()=>control("stop")));
    } else if (status(current)==="awaiting_choice" && current.mapping_choice) {
      const menu=current.mapping_choice;
      host.append(el("h3",t("Choose a mapping rule","Choisir une règle de conversion")),el("p",menu.question));
      for(const c of menu.candidates) host.append(button(c.description,()=>mutate("choose",{choice:c.id,sha256:menu.sha256})));
      host.append(button(t("Abstain","S’abstenir"),()=>mutate("choose",{choice:"abstain",sha256:menu.sha256})));
    }
  }
  function renderRun(force=false) {
    const r=current,s=status(r),version="?version="+r.version,path="/api/runs/"+r.id;
    $("run-title").textContent=r.mission.purpose; $("run-status").textContent=label(s); $("next").textContent=stageText(s);
    const controls=$("control-actions"); controls.replaceChildren();
    const ended=["verified","failed","deferred","stopped","stale"].includes(s);
    if (s==="paused") controls.append(button(t("Resume mission","Reprendre la mission"),()=>control("resume")));
    else if (!ended) controls.append(button(t("Pause mission","Mettre en pause"),()=>control("pause")));
    if (!ended && s==="blocked") controls.append(button(t("Retry checkpoint","Réessayer depuis le point d’arrêt"),()=>mutate("resume",{})));
    if (!ended) controls.append(button(t("Cancel mission","Annuler la mission"),()=>control("stop")));
    approval(force);
    $("pending").querySelectorAll("button").forEach(node=>{node.disabled=busy;});
    const verified=s==="verified";
    $("delivery").hidden=!verified; $("run-evidence").hidden=verified;
    $("bundle").href=path+"/bundle"+version; $("evidence").href=$("run-evidence").href=path+"/evidence"+version;
    $("offer-draft").href=path+"/offer"+version+"&lang="+language;
    $("reuse-program").hidden=!(verified && r.operation?.state==="active" && r.mission.authority?.allow_program_reuse===true && ["manifest_audit","record_migration"].includes(r.artifact?.kind));
    if(verified) trialEditor(r);
    const usage=r.economics?.usage, ev=r.evaluation, comp=ev?.comparison;
    const values=[
      [t("Model steps completed","Étapes modèle terminées"),usage?.completed_steps],
      [t("Measured model time (s)","Temps modèle mesuré (s)"),usage?.observed_step_wall_seconds],
      [t("Actual cost","Coût réel"),usage?.incurred_cost ?? notKnown()],
      [t("Commercial evidence","Preuve commerciale"),commercial ? label(commercial.commercial_state) : t("Awaiting the commercial record","En attente du dossier commercial")]
    ];
    if(ev?.cases) values.unshift([t("Verification cases passed","Cas de vérification réussis"),ev.cases.filter(c=>c.candidate_pass===true).length+" / "+ev.cases.length]);
    if(comp?.outcome) values.unshift([t("Comparison result","Résultat de la comparaison"),label(comp.outcome)]);
    $("outcome").replaceChildren(facts(values));
    if(r.error || r.research?.decision_reason) {
      const details=el("details");details.open=!!r.error || ["deferred","failed","blocked"].includes(s);
      details.append(el("summary",t("Reason recorded by the engine · original text","Motif consigné par le moteur · texte d’origine")),
        el("p",r.error || r.research.decision_reason));
      $("outcome").append(details);
    }
    $("events").replaceChildren(...(r.events||[]).map(e=>{const li=el("li");li.append(el("time",new Date(e.at).toLocaleString(language)),el("p",e.message));return li;}));
    $("record").textContent=json(r);
  }
  function trialEditor(run) {
    const key=run.id+"/"+run.version+"/"+language;
    if(trialKey===key)return;
    trialKey=key;
    const host=$("typed-try");host.replaceChildren();
    const spec=run.contract?.spec;
    if(!spec)return;
    const definition=spec.definition;
    const form=el("form");
    const inputField=(name,title,type)=>{
      const input=el("input");input.id="trial-"+name;input.type=type;input.required=true;
      const lab=el("label",title);lab.htmlFor=input.id;form.append(lab,input);
      return input;
    };
    let getInput;
    if(spec.kind==="record_migration") {
      const columns=run.artifact?.program?.columns || definition.columns || [];
      const fields=definition.input_fields || [...new Set(columns.flatMap(c=>c.sources || [c.source]))];
      if(!fields.length)return;
      const observed=spec.cases?.find(c=>c.input?.rows?.length)?.input.rows[0] || {};
      const inputs=fields.map((field,i)=>{
        const type=typeof observed[field];
        const input=inputField(i,t("Input field · ","Champ d’entrée · ")+field,type==="number"?"number":type==="boolean"?"checkbox":"text");
        if(type==="boolean")input.required=false;
        return [field,()=>type==="boolean"?input.checked:type==="number"?Number(input.value):input.value];
      });
      getInput=async()=>({rows:[Object.fromEntries(inputs.map(([key,value])=>[key,value()]))]});
    } else if(spec.kind==="manifest_audit") {
      const field=inputField("file",t("Check a file (up to 64 KiB)","Vérifier un fichier (jusqu’à 64 Kio)"),"file");
      getInput=async()=>{
        const f=field.files[0]; if(!f || f.size>65536)throw Error(t("Choose a file of at most 64 KiB.","Sélectionnez un fichier d’au plus 64 Kio."));
        let raw="";for(const b of new Uint8Array(await f.arrayBuffer()))raw+=String.fromCharCode(b);
        return {files:{[f.name]:btoa(raw)}};
      };
    } else return;
    const go=el("button",t("Test this input","Tester ces données"));go.type="submit";form.append(go);
    form.onsubmit=async ev=>{
      ev.preventDefault();go.disabled=true;
      try{const input=await getInput();if(current?.id!==run.id)return;
        $("sample").value=json(input);$("try-form").requestSubmit();}
      catch(error){announce(localError(error));}
      finally{go.disabled=false;}
    };
    host.append(form);
  }
  function show(r, focus=false) {
    if (!r?.id) throw Error(t("The service returned an incomplete mission record.","Le service a renvoyé un dossier de mission incomplet."));
    const changed=r.id!==current?.id||r.version!==current?.version;
    current=r; pending=null;sourceRun=null;
    $("review-panel").hidden=$("intake").hidden=true; $("mission").hidden=false;
    if (changed) {
      commercial=null; approvalKey=null;
      $("sample").value=json(r.contract?.spec?.cases?.find(c=>"expected" in c)?.input ?? {});
      $("output").textContent=""; $("try-panel").open=false;
    }
    if (r.status==="verified" && $("sample").value==="{}") $("sample").value=json(r.contract?.spec?.cases?.find(c=>"expected" in c)?.input ?? {});
    renderRun(); history.replaceState(null,"","#mission="+r.id);
    if (focus) $("run-title").focus();
    const known=runs.find(row=>row.id===r.id);
    const row={id:r.id,purpose:r.mission.purpose,observed_status:r.status,operation_state:r.operation?.state||"active"};
    if(known) Object.assign(known,row); else runs.unshift(row);
    inventory();
  }
  function schedule(id,token,delay=1100) {
    clearTimeout(timer);
    timer=setTimeout(async()=>{
      if(token!==generation || busy) return;
      try {
        const r=await api("/api/runs/"+id);
        if(token!==generation)return;
        show(r); announce("");
        if(active()) schedule(id,token); else refreshCommercial(id,token);
      } catch(e) {if(token===generation) {announce(localError(e));schedule(id,token,4000);}}
    },delay);
  }
  async function refreshCommercial(id,token) {
    try {
      const data=await api("/api/runs/"+id+"/commercial?version="+current.version);
      if(token===generation && current?.id===id) {commercial=data;renderRun();}
    } catch { /* The underlying evidence download remains available. */ }
  }
  async function openRun(id) {
    if (busy) return;
    const token=++generation;clearTimeout(timer);
    try {const r=await api("/api/runs/"+id);if(token!==generation)return;
      show(r,true);announce("");if(active()) schedule(id,token); else refreshCommercial(id,token);
    } catch(e){if(token===generation)announce(localError(e));}
  }
  async function mutate(action,data) {
    if (busy||!current) return;
    busy=true; const token=++generation,id=current.id;clearTimeout(timer);renderRun();
    try {
      const r=await api("/api/runs/"+id+"/"+action,{version:current.version,...data});
      if(token===generation) {show(r);announce("");}
    } catch(e){announce(localError(e));}
    finally {
      busy=false;
      if (token===generation && current) {renderRun();if(active()) schedule(id,token);else refreshCommercial(id,token);}
    }
  }
  if (page==="demo") {
    document.querySelectorAll('input[name="metric"]').forEach(node=>node.onchange=demo);
  }
  if (page==="studio") {
    $("template").onchange=templateChanged; $("model").onchange=templateChanged;
    $("signin-form").onsubmit=async event=>{
      event.preventDefault(); $("signin-button").disabled=true;
      try {await api("/api/session",{invite:$("invite").value.trim()}); $("invite").value=""; await getSession();announce("");$("template").focus();}
      catch(e){announce(localError(e));} finally {$("signin-button").disabled=false;}
    };
    $("signout").onclick=async()=>{try{await api("/api/logout",{});location.replace("/studio?lang="+language);}catch(e){announce(localError(e));}};
    $("mission-form").onsubmit=async event=>{
      event.preventDefault(); $("review").disabled=true;
      try{pending=await brief();review();announce("");$("review-title").focus();}
      catch(e){announce(localError(e));$("notices").focus();}finally{$("review").disabled=false;}
    };
    $("edit").onclick=()=>{if(busy)return;pending=null;$("review-panel").hidden=true;$("intake").hidden=false;$("purpose").focus();};
    $("start").onclick=async()=>{
      if (busy||!pending)return;
      busy=true; const token=++generation; $("start").disabled=$("edit").disabled=true;
      const path=sourceRun?"/api/runs/"+sourceRun.id+"/successor":"/api/runs";
      const request=sourceRun?{...pending,version:sourceRun.version,rights:read("reuse-rights")}:pending;
      try {const r=await api(path,request);if(token===generation){show(r,true);announce("");}}
      catch(e){announce(localError(e));}
      finally {busy=false; $("start").disabled=$("edit").disabled=false;if(current&&token===generation){renderRun();if(active())schedule(current.id,token);else refreshCommercial(current.id,token);}}
    };
    function startAnother(previous=null) {
      if(busy)return;
      ++generation;clearTimeout(timer);current=pending=null;commercial=null;sourceRun=previous;
      $("mission-form").reset();if(previous){
        $("template").value=previous.kind==="record_migration"?"migration":"integrity";
        $("beneficiary").value=previous.beneficiary;
      }
      templateChanged();$("mission").hidden=$("review-panel").hidden=true;$("intake").hidden=false;
      history.replaceState(null,"",location.pathname+location.search);announce("");(previous?$("purpose"):$("template")).focus();
    }
    $("new-mission").onclick=()=>startAnother();
    $("reuse-program").onclick=()=>{if(!current)return;startAnother({id:current.id,version:current.version,
      purpose:current.mission.purpose,beneficiary:current.mission.beneficiary,kind:current.artifact.kind});};
    $("reload").onclick=async()=>{try{await refreshInventory();if(current)await openRun(current.id);else announce(t("Mission list updated.","Liste des missions actualisée."));}catch(e){announce(localError(e));}};
    $("try-form").onsubmit=async event=>{event.preventDefault();if(!current)return;const id=current.id;$("try").disabled=true;
      try{const input=JSON.parse($("sample").value);const data=await api("/api/runs/"+id+"/try",{version:current.version,input});if(current?.id===id)$("output").textContent=json(data.output);}
      catch(e){announce(localError(e));}finally{$("try").disabled=false;}};
  }
  languages();
  if (page==="studio") getSession().catch(e=>announce(localError(e)));
})();
