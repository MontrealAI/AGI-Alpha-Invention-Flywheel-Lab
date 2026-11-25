function comparePair(oldTree,newTree){
  if(oldTree.truncated!==false||newTree.truncated!==false)throw Error("NONTRUNCATED_TREES_REQUIRED");
  function index(t){
    const entries=new Map();
    for(const e of t.tree){if(entries.has(e.path))throw Error("DUPLICATE_TREE_PATH");entries.set(e.path,e)}
    const dirs=new Map();
    for(const e of t.tree){
      if(!e.path.endsWith("/SKILL.md"))continue;
      const path=e.path.slice(0,-9),d=entries.get(path);
      if(!d||d.type!=="tree")throw Error("SKILL_DIRECTORY_REQUIRED");
      const leaves=t.tree.filter(f=>f.path.startsWith(path+"/")&&f.type!=="tree").map(f=>JSON.stringify([f.path.slice(path.length+1),f.mode,f.type,f.sha])).sort();
      dirs.set(path,{tree:d.sha,skill:e.sha,mode:e.mode,leaves});
    }
    return dirs;
  }
  const a=index(oldTree),b=index(newTree);
  const rows=[];
  for(const [path,x] of a){
    const y=b.get(path);if(!y)continue;
    const treeChanged=x.tree!==y.tree, leafChanged=JSON.stringify(x.leaves)!==JSON.stringify(y.leaves);
    rows.push({path,old_tree:x.tree,new_tree:y.tree,old_skill:x.skill,new_skill:y.skill,old_mode:x.mode,new_mode:y.mode,treeChanged,leafChanged,old_files:x.leaves.length,new_files:y.leaves.length});
  }
  return {old_dirs:a.size,new_dirs:b.size,common:rows.length,added:[...b.keys()].filter(p=>!a.has(p)).sort(),removed:[...a.keys()].filter(p=>!b.has(p)).sort(),rows:rows.sort((x,y)=>x.path.localeCompare(y.path))};
}

function readMetadata(content){
  const lines=content.replace(/\r\n/g,"\n").split("\n");
  if(lines[0]!=="---")return {valid:false,reason:"NO_FRONTMATTER"};
  const end=lines.indexOf("---",1);
  if(end<1)return {valid:false,reason:"NO_FRONTMATTER_END"};
  const result={name:null,version:null};
  for(const key of ["name","version"]){
    const matches=lines.slice(1,end).filter(l=>new RegExp("^"+key+"\\s*:").test(l));
    if(matches.length>1)return {valid:false,reason:"DUPLICATE_"+key};
    if(matches.length===1){
      let v=matches[0].slice(matches[0].indexOf(":")+1).trim();
      if((v.startsWith('"')&&v.endsWith('"'))||(v.startsWith("'")&&v.endsWith("'")))v=v.slice(1,-1);
      if(!/^[A-Za-z0-9._+-]+$/.test(v))return {valid:false,reason:"UNSUPPORTED_"+key};
      result[key]=v;
    }
  }
  if(!result.name||result.name.length>64||!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(result.name))return {valid:false,reason:"INVALID_NAME"};
  return {valid:true,...result};
}

function classify(row,oldMetadata,newMetadata){
  if(!row.treeChanged)return "UNCHANGED_TREE";
  if(!oldMetadata?.valid||!newMetadata?.valid)return "UNKNOWN_METADATA";
  if(oldMetadata.name!==newMetadata.name||oldMetadata.version!==newMetadata.version)return "METADATA_CHANGED";
  return oldMetadata.version===null?"SAME_VERSIONLESS_NAME_DIFFERENT_TREE":"SAME_EXPLICIT_VERSION_DIFFERENT_TREE";
}

export {comparePair,readMetadata,classify};
