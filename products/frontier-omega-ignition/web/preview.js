// Used only in the standalone archival edition. All executable behavior is local.
const recordings=JSON.parse($("public-preview-data").textContent);
let displayedArchive;
function selectRecording(recording) {
  const run=recording.run;
  $("record").hidden=false;
  $("title").textContent=recording.title;
  $("purpose").textContent=run.mission.purpose;
  $("verdict").textContent="Recorded replay · "+(run.status==="verified"?"Verified within scope":run.status);
  $("attribution").textContent=[run.provider?.mode==="manual"?"Operator-assisted execution":run.provider?.mode,
    run.provider?.provider,run.provider?.model].filter(Boolean).join(" · ");
  for(const b of $("choices").querySelectorAll("button")) b.setAttribute("aria-pressed",String(b.dataset.mission===recording.id));
  const link=$("archive");
  if(displayedArchive){URL.revokeObjectURL(displayedArchive);displayedArchive=null;}
  link.removeAttribute("href");
  $("delivery").hidden=!recording.archive;
  if(recording.archive){
    const raw=Uint8Array.from(atob(recording.archive),ch=>ch.charCodeAt(0));
    displayedArchive=URL.createObjectURL(new Blob([raw],{type:"application/zip"}));
    link.href=displayedArchive;link.download=recording.id+"-artifact.zip";
  }
  results(run);
  $("events").replaceChildren(...run.events.map(ev=>{
    const li=elem("li");li.append(elem("strong",ev.stage),elem("p",ev.message),elem("small",ev.at));return li;
  }));
  $("receipt").textContent=json({run_sha256:recording.run_sha256,...(recording.archive_sha256?{zip_sha256:recording.archive_sha256}:{})});
  $("raw").textContent=json(run);
}
for(const r of recordings){
  const b=elem("button");b.type="button";b.dataset.mission=r.id;
  b.append(elem("strong",r.title),elem("small",r.run.status==="verified"?"Verified within scope · ZIP available":"Deferred · see obstruction"));
  b.addEventListener("click",()=>selectRecording(r));$("choices").append(b);
}
selectRecording(recordings[0]);
