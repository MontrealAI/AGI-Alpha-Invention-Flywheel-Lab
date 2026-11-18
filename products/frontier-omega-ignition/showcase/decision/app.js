(() => {
  "use strict";
  const doc = document;
  const data = JSON.parse(doc.getElementById("public-data").textContent);
  const el = id => doc.getElementById(id);
  const fmt = value => new Intl.NumberFormat(locale === "fr" ? "fr-CA" : "en-CA",
    {maximumFractionDigits:4}).format(Number(value));
  const mark = (tag, value) => { const n = doc.createElement(tag); n.textContent = value; return n; };
  const publicSources = new Map(data.sources.map(s => [s.id,s]));
  const scenarios = new Map(data.scenarios.map(s => [s.id,s]));
  const documentUrl = (value,type) => URL.createObjectURL(new Blob([value], {type}));
  const archive = Uint8Array.from(atob(data.archive.bytes), c => c.charCodeAt(0));
  el("download").href = documentUrl(archive,"application/zip");
  el("kit-hash").textContent = data.archive.sha256;
  el("numeric-link").href = documentUrl(JSON.stringify({registered:data.numeric,independent:data.numeric_audit,recovery:data.recovery},null,2),"application/json");
  const served = location.pathname === "/frontier";
  el("standalone").href=served?"/frontier?download=1":location.href.split("#")[0];
  el("reading").href = served ? "/exhibition" : "FRONTIER_IGNITION.html";
  el("pairing").href = served ? "/showcase" : "PAIRING_LAB.html";
  let locale = "en", cardIndex = 0, caseId = "interactive_gpt", receiptUrl = null;
  let systemId = data.sources.find(s => s.status === "PUBLISHED" && s.model === "GPT-OSS 120B").id;
  let maxLatency = 500, minSpeed = 100, briefUrl = null;
  const t = () => data.copy[locale];
  const native = (en,fr) => locale === "en" ? en : fr;
  const pointName = (source,p) => source.submitter+" · "+source.model+" · "+t().run+" "+p.run;
  const option = (name,id) => new Option(name,id);
  const finiteValue = value => value !== null && value !== "" && Number.isFinite(Number(value));
  function within(point) {
    return finiteValue(point.ttft_p90_ms) && finiteValue(point.tps_per_user) &&
      Number(point.ttft_p90_ms) <= maxLatency && Number(point.tps_per_user) >= minSpeed;
  }
  function titleFor(key) {
    return t().caseNames[key] || ({
      agentic_turn:native("End-to-end agent turn","Tour d’agent de bout en bout"),
      require_agentic_e2e:native("End-to-end agent turn","Tour d’agent de bout en bout")
    })[key] || key.replaceAll("_"," ");
  }
  function drawSweep(source) {
    const points = source.points.filter(p => p.concurrency>0 && Number(p.ttft_p90_ms)>0)
      .slice().sort((a,b) => a.concurrency-b.concurrency);
    const ns = "http://www.w3.org/2000/svg";
    const g = el("plot-drawing");
    g.replaceChildren();
    const plot = (tag,attrs,label) => {
      const n = doc.createElementNS(ns,tag);
      for (const [k,v] of Object.entries(attrs)) n.setAttribute(k,String(v));
      if (label !== undefined) n.textContent = label;
      g.append(n);
      return n;
    };
    if (!points.length) return;
    const right=532,left=66,top=42,bottom=260;
    const axes = vals => {
      const lo=Math.min(...vals), hi=Math.max(...vals);
      return [lo/1.22,Math.max(lo*1.02,hi)*1.25];
    };
    const [xmin,xmax]=axes(points.map(p=>p.concurrency));
    const [ymin,ymax]=axes(points.map(p=>Number(p.ttft_p90_ms)));
    const scale = (n,a,b,first,last) => first+(last-first)*(Math.log(n)-Math.log(a))/(Math.log(b)-Math.log(a));
    const x=n=>scale(n,xmin,xmax,left,right), y=n=>scale(n,ymin,ymax,bottom,top);
    const xticks = [...new Set([0,1,2,3].map(i=>points[Math.round(i*(points.length-1)/3)].concurrency))];
    for (const n of xticks) {
      plot("line",{x1:x(n),x2:x(n),y1:top,y2:bottom,class:"gridline"});
      plot("text",{x:x(n),y:bottom+20,class:"axis-text","text-anchor":"middle"},fmt(n));
    }
    for (let exp=Math.floor(Math.log10(ymin));exp<=Math.ceil(Math.log10(ymax));exp++) {
      for (const mult of [1,2,5]) {
        const n=mult*10**exp;
        if(n<ymin||n>ymax)continue;
        plot("line",{x1:left,x2:right,y1:y(n),y2:y(n),class:"gridline"});
        plot("text",{x:left-10,y:y(n)+4,class:"axis-text","text-anchor":"end"},fmt(n));
      }
    }
    if(maxLatency>=ymin && maxLatency<=ymax) {
      plot("line",{x1:left,x2:right,y1:y(maxLatency),y2:y(maxLatency),stroke:"#e4ab64","stroke-width":1.4,"stroke-dasharray":"7 4"});
      plot("text",{x:right,y:y(maxLatency)-6,"text-anchor":"end",class:"annot"},t().threshold);
    }
    plot("polyline",{points:points.map(p=>x(p.concurrency)+","+y(Number(p.ttft_p90_ms))).join(" "),class:"sweep-line"});
    for(const p of points){
      const dot=plot("circle",{cx:x(p.concurrency),cy:y(Number(p.ttft_p90_ms)),r:within(p)?5.1:4.2,class:"sweep-point"+(within(p)?"":" muted")});
      const name=doc.createElementNS(ns,"title");
      name.textContent=t().run+" "+p.run+" · "+fmt(p.concurrency)+" · "+fmt(p.ttft_p90_ms)+" ms";
      dot.append(name);
    }
    plot("text",{x:left,y:20,class:"axis-text"},t().vertical);
    plot("text",{x:right,y:bottom+45,class:"axis-text","text-anchor":"end"},t().horizontal);
    el("plot-title").textContent=t().atlas+" · "+source.submitter+" · "+source.model;
    el("plot-desc").textContent=t().atlasCaption+" "+t().eligible+": "+points.filter(within).length+"/"+points.length+".";
    el("sweep-count").textContent=source.submitter+" · "+points.length+" "+t().point;
  }
  function renderRows(){
    const source = publicSources.get(systemId);
    el("system").value=systemId;
    el("rows").replaceChildren(...source.points.map(p=>{
      const row=doc.createElement("tr"), fits=within(p);
      row.dataset.eligible=String(fits);
      for(const v of [p.run,p.concurrency,p.ttft_p90_ms,p.tps_per_user,p.system_tps])
        row.append(mark("td",finiteValue(v)?fmt(v):"—"));
      row.append(mark("td",t()[fits?"yes":"no"]));
      return row;
    }));
    const fits=source.points.filter(within);
    el("filter-result").textContent=t().eligible+" · "+fits.length+" / "+source.points.length+" · "+
      (source.status === "PUBLISHED" ? native("Published report","Rapport publié") : native("Provisional report","Rapport provisoire"));
    el("report").href=source.url;
    el("report").textContent=source.submitter+" · "+source.model+" · "+source.published+" ↗";
    drawSweep(source);
  }
  function caseView(changeFilter){
    const sc=scenarios.get(caseId), req=sc.requirement, result=sc.result;
    const body=el("decision-body");
    body.replaceChildren();
    el("scenario").value=caseId;
    el("model").textContent=req.model;
    el("dataset").textContent=req.dataset;
    let rate=req.rate_metric==="inverse_p90_tpot"?t().tailMetric:t().reportedMetric;
    el("contract-desc").textContent=t().maxStart+" "+fmt(req.max_ttft_p90_ms)+" ms · "+t().minRate+" "+fmt(req.min_tps_per_user)+" "+rate+".";
    const chosen=result.selected;
    el("decision-state").textContent=t()[chosen.length?"recorded":"withheld"];
    if(chosen.length){
      const first=chosen[0], source=publicSources.get(first.source);
      body.append(mark("p",fmt(first.concurrency)),mark("strong",t().concurrencyUnit));
      body.firstChild.className="decision-number";
      const dl=doc.createElement("dl");
      for(const [k,v] of [[t().sourceRun,pointName(source,first)],[t().ttft,fmt(first.ttft_p90_ms)],
          [t().perUser,fmt(first.tps_per_user)],[t().aggregate,fmt(first.system_tps)]]){
        dl.append(mark("dt",k),mark("dd",v));
      }
      body.append(dl);
      el("decision-note").textContent=t().chosenNote;
    }else{
      const headline=mark("p",t().abstainHeadline);headline.className="decision-number";body.append(headline);
      const missing = req.require_price ? native("The reports do not include an effective service price.","Les rapports ne précisent pas le prix effectif du service.")
        : req.require_access ? native("The lab’s right to operate this system is undocumented.","Le droit d’exploitation de ce système par le laboratoire n’est pas documenté.")
        : req.require_point_accuracy ? native("Accuracy at the requested measurement point is unavailable.","L’exactitude au point de mesure demandé est inconnue.")
        : req.load_mode === "online" ? native("These GPT-OSS rows lack the required explicit online label.","Ces lignes GPT-OSS ne portent pas la mention « en ligne » exigée.")
        : req.dataset === "own-MontrealAI-traffic" ? native("The published workloads do not include MONTREAL.AI’s traffic.","Les charges publiées ne comprennent pas les requêtes de MONTREAL.AI.")
        : t().nothing;
      el("decision-note").textContent=missing;
    }
    const next=result.next_test;
    if(next && next.targets && next.targets.length) {
      const n=next.targets[0];
      const hint=mark("p",native("Next run to measure on intended traffic","Prochain essai sur la charge prévue")+" · "+
         pointName(publicSources.get(n.source),n)+" · "+t().load+" "+fmt(n.concurrency)+".");
      body.append(hint);
    }
    const challengeSources=data.sources.filter(s=>s.status==="PUBLISHED"&&s.model===req.model&&s.dataset===req.dataset);
    const alternatives=challengeSources.flatMap(s=>s.points.filter(p=>finiteValue(p.system_tps)).map(p=>({s,p})))
      .sort((a,b)=>Number(b.p.system_tps)-Number(a.p.system_tps));
    if(alternatives.length){
      const {s,p}=alternatives[0];
      el("peak-text").textContent=t().peakLead+" · "+pointName(s,p)+". "+fmt(p.system_tps)+" "+
        native("output tokens/s","jetons produits/s")+", "+fmt(p.ttft_p90_ms)+" ms P90, "+fmt(p.tps_per_user)+" "+
        native("tokens/s per user","jetons/s par personne")+". "+t().peakBoundary;
    }else el("peak-text").textContent=t().unavailablePeak;
    const cmd="python3 decide.py --contract contracts.json --case "+caseId+" --output decision.json";
    el("command").textContent=cmd;
    if(receiptUrl) URL.revokeObjectURL(receiptUrl);
    receiptUrl=documentUrl(JSON.stringify({case:caseId,requirement:req,result,source_sha256:data.reports_sha256},null,2),"application/json");
    el("receipt").href=receiptUrl;
    if(changeFilter){
      systemId=chosen[0]?.source||challengeSources[0]?.id||systemId;
      maxLatency=Number(req.max_ttft_p90_ms);minSpeed=Number(req.min_tps_per_user);
      el("latency").value=maxLatency;el("speed").value=minSpeed;
    }
    renderRows();experimentBrief();
  }
  function experimentBrief(){
    const sc=scenarios.get(caseId), card=data.field.opportunities[cardIndex], decision=sc.result;
    const instrument = {contract:sc.requirement,decision:decision.decision,observed_points:decision.selected,
      next_test:decision.next_test,source_urls:[...new Set(decision.selected.map(row=>publicSources.get(row.source).url))],
      reports_sha256:data.reports_sha256};
    const selectedOpportunity = {id:card.id,title:card[locale].title,competing_method:card[locale].alternative,
      experiment:card[locale].test,source:card.source};
    const brief = {schema:"frontier/experiment-brief/v1",locale,ambition:el("purpose").value,
      opportunity:selectedOpportunity,endpoint_case:instrument,
      status:"proposed_experiment",deployment_authorized:false,
      missing_field_observations:["representative_workload","access_rights","accepted_outcomes","complete_operating_cost"]};
    if(briefUrl) URL.revokeObjectURL(briefUrl);
    briefUrl=documentUrl(JSON.stringify(brief,null,2),"application/json");
    el("brief").href=briefUrl;
  }
  function forgeView(){
    const exec=data.execution.endpoint, model=data.execution.numeric_model;
    const seconds=model.calls.reduce((n,c)=>n+c.wall_seconds,0);
    const events=[
      [native("Recorded · published load runs","Enregistré · essais de charge publiés"),
       native("Three official MLPerf submissions contributed 28 measured points. Two published Google reports qualify. The NVIDIA report was pending peer review on November 17, 2026.",
              "Trois soumissions officielles MLPerf fournissent 28 observations. Deux rapports publiés de Google sont admissibles. Le rapport de NVIDIA attendait une vérification le 17 novembre 2026.")],
      [native("Reproduced · contract and SQL","Reproduit · exigences et SQL"),
       native("Nine registered cases and 800 sensitivity comparisons ran in ","Neuf cas préenregistrés et 800 comparaisons de sensibilité ont pris ")+
        fmt(exec.wall_seconds)+" s. "+native("Incremental paid services: ","Services payants supplémentaires : ")+fmt(exec.incremental_paid_services)+
        native(". Acquisition, development, human review and ownership costs remain unmeasured.",". Les coûts d’acquisition, de développement, de révision humaine et d’exploitation restent à mesurer.")],
      [native("Recorded · table extraction","Enregistré · extraction de tableaux"),model.repository+" · "+fmt(model.calls.length)+
        native(" CPU image generations, "," générations d’images sur processeur, ")+fmt(Math.round(seconds*100)/100)+
        native(" s wall time. The published table reports simulated outcomes. The two-page calibration was synthetic.",
               " s de temps écoulé. Le tableau publié présente des résultats simulés. L’étalonnage de deux pages est synthétique.")],
      [native("Unavailable · field operation","Indisponible · exploitation réelle"),
       native("A deployment decision needs traffic, rights and full cost evidence from the intended service. Live local filtering, above, tests reported rows only.",
              "Une décision de déploiement exige des données sur le trafic, les droits et les coûts du service visé. Le filtre interactif ci-dessus examine les seules lignes publiées.")]
    ];
    const list=el("events");list.replaceChildren();
    for(const [status,description] of events) list.append(mark("dt",status),mark("dd",description));
  }
  function cardView(){
    const card=data.field.opportunities[cardIndex], c=card[locale];
    for(const [i,b] of [...el("choices").children].entries()) b.setAttribute("aria-pressed",String(i===cardIndex));
    el("candidate-state").textContent=t()[card.selected?"selected":card.overlooked?"overlooked":"candidate"];
    el("candidate-title").textContent=c.title;
    el("candidate-benefit").textContent=c.benefit;
    const dl=el("candidate-detail");dl.replaceChildren();
    for(const [key,value] of [["changed",c.change],["alternative",c.alternative],["test",c.test]])dl.append(mark("dt",t()[key]),mark("dd",value));
    el("candidate-source").href=card.source.url;
    el("candidate-source").textContent=card.source.publisher+" · "+card.source.date+" ↗";
    experimentBrief();
  }
  function rateView(){
    const n=Number(el("rate").value), [reported,inverse]=data.sensitivity.rows[n-1];
    el("rate-value").textContent=fmt(n)+" "+native("tokens/s","jetons/s");
    el("reported-load").textContent=reported===null?t().withheld:fmt(reported);
    el("inverse-load").textContent=inverse===null?t().withheld:fmt(inverse);
    const record=data.sensitivity;
    el("rate-stat").textContent=native("The definitions changed the choice at ","Le choix a changé pour ")+
      fmt(record.different)+native(" of "," des ")+fmt(record.rows.length)+native(" tested thresholds. Independent SQL agreed on all "," seuils testés. Le calcul SQL indépendant confirme les ")+
      fmt(record.comparisons)+native(" decisions."," décisions.");
  }
  function render(){
    const l=t();
    doc.documentElement.lang=locale;
    for(const n of doc.querySelectorAll("[data-t]"))n.textContent=l[n.dataset.t];
    const language=locale==="en"?"fr":"en";
    el("locale").textContent=language.toUpperCase();el("locale").lang=language;
    el("locale").setAttribute("aria-label",language==="fr"?"Français":"English");
    for(const [id,k] of [["main-nav","navLabel"],["choices","fieldAria"],["table-wrap","tableAria"]])el(id).setAttribute("aria-label",l[k]);
    el("scenario").replaceChildren(...data.scenarios.map(s=>option(titleFor(s.id),s.id)));
    el("system").replaceChildren(...data.sources.map(s=>option(s.submitter+" · "+s.model+
        (s.status==="PUBLISHED"?"":" · "+native("provisional","provisoire")),s.id)));
    el("ambition").textContent=data.field.ambition[locale];
    el("choices").replaceChildren(...data.field.opportunities.map((c,i)=>{
      const n=mark("button",c[locale].title);n.type="button";
      n.onclick=()=>{cardIndex=i;cardView()};return n;
    }));
    el("reader-note").textContent=l.readerStatus+" "+native("Completed reader sessions","Séances de lecture terminées")+" · "+fmt(data.reader_count)+".";
    const pub=data.numeric.tables.publication.model, recovery=data.recovery;
    el("numeric-note").textContent=native(
      "All four workflows recovered "+pub.correct_cells+"/"+pub.total_cells+" cells in a published simulated-outcomes table. On the separate calibration, the original model adapter withheld. A later receiver recovered all "+recovery.correct_cells+" cells and both qualifying notes from the same generation. Direct source and conventional native extraction also passed.",
      "Les quatre méthodes ont récupéré "+pub.correct_cells+" cellules sur "+pub.total_cells+" dans un tableau publié de résultats simulés. Au test d’étalonnage distinct, l’adaptateur initial du modèle s’est abstenu. Un traitement ultérieur de la même sortie a retrouvé les "+recovery.correct_cells+" cellules et les deux notes. La source directe et l’extraction classique du texte natif ont aussi réussi.");
    rateView();forgeView();
    cardView();caseView(false);
  }
  el("purpose").addEventListener("input",experimentBrief);
  el("rate").addEventListener("input",rateView);
  el("filter-form").addEventListener("submit",e=>{
    e.preventDefault();systemId=el("system").value;maxLatency=el("latency").valueAsNumber;
    minSpeed=el("speed").valueAsNumber;if(Number.isFinite(maxLatency)&&Number.isFinite(minSpeed))renderRows();
  });
  el("scenario").addEventListener("change",()=>{caseId=el("scenario").value;caseView(true)});
  el("locale").addEventListener("click",()=>{locale=locale==="en"?"fr":"en";render()});
  el("latency").value=maxLatency;el("speed").value=minSpeed;
  render();
})();
