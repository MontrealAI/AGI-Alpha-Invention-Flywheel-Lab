function run(source) {
  const blocks=new Map(source.split(/(?=^Instance: )/m).filter(s=>s.startsWith("Instance: ")).map(s=>[s.split("\n")[0].slice(10).trim(),s]));
  const read=(block,regex)=>[...block.matchAll(regex)].map(m=>m[1]);
  const requestName="ReferralAuthorizationExample";
  const q=blocks.get(requestName);
  if(!q) throw Error("missing registered request");
  const requested=read(q,/^\* item(?:\[\d+\])?\.sequence = (\d+)\s*$/gm).map(Number);
  const official=[
    ["ErrorResponseExample","PROCESSING_ERROR"],
    ["RejectionResponseExample","REQUEST_1_A3"],
    ["PractitionerRequestorResponseExample","REQUEST_1_A1"],
    ["PractitionerRequestorAdditionalContentResponseExample","REQUEST_1_A1|NEW_2_A1"],
    ["PractitionerRequestorPendingResponseExample","REQUEST_1_A4"]
  ];
  function parse(name){
    const s=blocks.get(name);
    if(!s) throw Error("missing registered response "+name);
    const references=read(s,/^\* request = Reference\(([^)]+)\)\s*$/gm);
    const outcomes=read(s,/^\* outcome = #(\w+)\s*$/gm);
    const itemSeq=read(s,/^\* item\.itemSequence = (\d+)\s*$/gm).map(Number);
    const itemCodes=read(s,/^\* item\.adjudication\.extension\[reviewAction\]\.extension\[code\]\.valueCodeableConcept = https:\/\/codesystem\.x12\.org\/005010\/306#(A\d+)(?: [^\n]*)?$/gm);
    const addSeq=read(s,/^  \* itemSequence = (\d+)\s*$/gm).map(Number);
    const addCodes=read(s,/^  \* adjudication\.extension\[reviewAction\]\.extension\[code\]\.valueCodeableConcept = https:\/\/codesystem\.x12\.org\/005010\/306#(A\d+)(?: [^\n]*)?$/gm);
    if(references.length!==1||outcomes.length!==1||itemSeq.length!==itemCodes.length||addSeq.length!==addCodes.length||itemSeq.length>1||addSeq.length>1)throw Error("unsupported FSH grammar "+name);
    return {reference:references[0],outcome:outcomes[0],items:itemSeq.map((n,i)=>[n,itemCodes[i]]),adds:addSeq.map((n,i)=>[n,addCodes[i]])};
  }
  function disposition(v) {
    if(v.reference!==requestName)return "ABSTAIN";
    if(v.outcome==="error")return v.items.length||v.adds.length?"ABSTAIN":"PROCESSING_ERROR";
    if(v.outcome!=="complete")return "ABSTAIN";
    const codes=new Set(["A1","A3","A4","A6"]);
    if(new Set(requested).size!==requested.length||v.items.length!==requested.length)return "ABSTAIN";
    if(new Set(v.items.map(x=>x[0])).size!==v.items.length||new Set(v.adds.map(x=>x[0])).size!==v.adds.length)return "ABSTAIN";
    if(v.items.some(([n,c])=>!requested.includes(n)||!codes.has(c)))return "ABSTAIN";
    if(v.adds.some(([n,c])=>!Number.isSafeInteger(n)||n<=0||c!=="A1"))return "ABSTAIN";
    const items=new Map(v.items);
    for(const [n,c] of items) {
      if((c==="A6")!==v.adds.some(x=>x[0]===n))return "ABSTAIN";
    }
    const out=v.items.map(([n,c])=>"REQUEST_"+n+"_"+c);
    for(const [n,c] of v.adds)out.push((items.has(n)?"MODIFIED_LINK_":"NEW_")+n+"_"+c);
    return out.join("|");
  }
  const rows=official.map(([name,expected])=>({name,role:"exposed_official_example",input:parse(name),expected}));
  const base=rows[2].input;
  const mutations=[
    ["wrong_request",{reference:"AnotherClaim"},"ABSTAIN"],
    ["duplicate_item",{items:[[1,"A1"],[1,"A3"]]},"ABSTAIN"],
    ["missing_item",{items:[]},"ABSTAIN"],
    ["unknown_code",{items:[[1,"A99"]]},"ABSTAIN"],
    ["wrong_item",{items:[[2,"A1"]]},"ABSTAIN"],
    ["error_conflict",{outcome:"error"},"ABSTAIN"],
    ["modified_without_link",{items:[[1,"A6"]]},"ABSTAIN"],
    ["modified_with_link",{items:[[1,"A6"]],adds:[[1,"A1"]]},"REQUEST_1_A6|MODIFIED_LINK_1_A1"],
    ["new_unrequested_item",{adds:[[2,"A1"]]},"REQUEST_1_A1|NEW_2_A1"],
    ["unexplained_addition",{adds:[[1,"A1"]]},"ABSTAIN"],
    ["duplicate_added_item",{adds:[[2,"A1"],[2,"A1"]]},"ABSTAIN"],
    ["unsupported_processing_outcome",{outcome:"partial"},"ABSTAIN"]
  ];
  for(const [name,patch,expected] of mutations)rows.push({name,role:"authored_adversarial",input:{...base,...patch},expected});
  return {requestName,requested,rows:rows.map(x=>({...x,observed:disposition(x.input),outcome_only:x.input.outcome==="complete"?"COMPLETE_UNDIFFERENTIATED":x.input.outcome,match:disposition(x.input)===x.expected})),scope:"Administrative syntax witness on one public example family; no approval, clinical decision, real claim, or full FHIR conformance."};
}
