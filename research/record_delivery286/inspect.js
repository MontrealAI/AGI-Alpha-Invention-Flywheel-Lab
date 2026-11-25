// 286: source-bound metadata-only delivery inventory. No image quality or original completeness claim.
// Frozen input: OCR-D/OCR-D-GT-VD-SBB @ 481f7235acfc1f78e88b3c2f22f551595c3f2032.
// All 67 METS workspaces; no replacement of inaccessible inputs. One development manifest inspected before freeze.
// Exact source-specific XML subset, not a general XML validator. Ordinary comparator: sorted path inventory.
// No paid operation, no external transactions, no native account. No original completeness or fixity inferred.
// Stop after one retrieval per manifest. Missing inputs remain blocked. No retries to select favorable results.
function inspect(path, xml, entries) {
  const dir=path.slice(0,path.lastIndexOf("/")+1);
  const paths=entries.filter(x=>x.type==="blob"&&x.path.startsWith(dir)).map(x=>x.path.slice(dir.length));
  const ordinary=paths.filter(x=>/^OCR-D-(?:IMG|GT-PAGE)\//.test(x)).sort();
  const attr=(s,k)=>{const m=s.match(new RegExp("(?:^|\\s)"+k+'="([^"]*)"'));return m?m[1]:null;};
  const errors=[];
  const files=[...xml.matchAll(/<mets:file\s+([^>]+)>([\s\S]*?)<\/mets:file>/g)];
  const ids=new Map(), locs=[];
  for(const f of files){
    const id=attr(f[1],"ID"), ls=[...f[2].matchAll(/<mets:FLocat\s+([^>]+)\/>/g)].map(m=>attr(m[1],"xlink:href"));
    const unique=[...new Set(ls)];
    if(!id||ids.has(id)||unique.length!==1||!unique[0]){errors.push("file_identity_or_location");continue;}
    const loc=unique[0];
    if(!/^OCR-D-(?:IMG|GT-PAGE)\/[A-Za-z0-9_.-]+$/.test(loc))errors.push("unsupported_path");
    ids.set(id,loc);locs.push(loc);
  }
  const pages=[...xml.matchAll(/<mets:div\s+([^>]*TYPE="page"[^>]*)>([\s\S]*?)<\/mets:div>/g)];
  const seen=new Set(), pageids=new Set();
  for(const p of pages){
    const pid=attr(p[1],"ID");
    if(!pid||pageids.has(pid))errors.push("page_identity");pageids.add(pid);
    const refs=[...p[2].matchAll(/<mets:fptr\s+([^>]+)\/>/g)].map(m=>attr(m[1],"FILEID"));
    const resolved=refs.map(id=>ids.get(id));
    if(refs.length!==2||resolved.some(x=>!x))errors.push("page_ref");
    for(const ref of refs){if(seen.has(ref))errors.push("repeated_ref");seen.add(ref);}
    const groups=resolved.filter(Boolean).map(x=>x.split("/")[0]).sort().join(",");
    if(groups!=="OCR-D-GT-PAGE,OCR-D-IMG")errors.push("page_group");
    const suffix=resolved.filter(Boolean).map(x=>x.match(/_(\d+)\.(?:xml|tif)$/)?.[1]);
    if(suffix.length!==2||!suffix[0]||suffix[0]!==suffix[1])errors.push("page_suffix");
  }
  if(seen.size!==ids.size||[...ids.keys()].some(k=>!seen.has(k)))errors.push("unmapped_file");
  if(!pages.length||files.length!==2*pages.length)errors.push("unsupported_shape");
  const missing=locs.filter(x=>!ordinary.includes(x)), extra=ordinary.filter(x=>!locs.includes(x));
  if(missing.length||extra.length||new Set(locs).size!==locs.length)errors.push("inventory_difference");
  // Independent ordinary naming inventory: sort by numeric suffix within each file group.
  const images=ordinary.filter(x=>x.startsWith("OCR-D-IMG/")).map(x=>x.match(/_(\d+)\.tif$/)?.[1]);
  const annotations=ordinary.filter(x=>x.startsWith("OCR-D-GT-PAGE/")).map(x=>x.match(/_(\d+)\.xml$/)?.[1]);
  const ordinaryPaired=images.length>0&&images.every(Boolean)&&annotations.every(Boolean)&&JSON.stringify(images.sort())===JSON.stringify(annotations.sort())&&new Set(images).size===images.length;
  return {path,manifest_files:files.length,physical_pages:pages.length,listed_payloads:ordinary.length,missing,extra,errors,metadata_inventory_pass:errors.length===0,ordinary_filename_pair_pass:ordinaryPaired,ordinary_page_count:images.length};
}
if(typeof module!=="undefined")module.exports={inspect};
