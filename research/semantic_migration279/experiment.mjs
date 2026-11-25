/*
SEMANTIC MIGRATION 279 — frozen development protocol; 2026-11-25
Owner: isolated independent research, not financial owner. Parent main 297a51c25c48031e1e6f964835f4dfae3ddb8023.
Objective: a portable full-domain equivalence receipt for a narrow integer piecewise-affine rule representation, without access to individual records. Potential successor: independently check rule changes before a migration buyer approves cutover. No claim that this covers COBOL programs or SSA eligibility, COLA, disability or retirement calculations.
Public source facts transcribed (not downloaded-byte hashes):
https://www.ssa.gov/oact/progdata/retirebenefit2.html (2026 case A: 5825, 2609.80)
https://www.ssa.gov/OACT/COLA/piaformula.html (2027 PIA bend points and rates)
https://www.ssa.gov/OACT/COLA/familymax.html (2027 retirement/survivor family maximum)
Domains: AIME integer dollars 0..20000; PIA integer dimes 0..200000; artificial finite bounds, not beneficiary distribution. Output in dimes. Family maximum uses PIA in dimes and denominator 100. Source rules expressed as explicit separate reference segments and direct progressive formula.
Frozen acceptance: all 21 arms exactly expected, exhaustive independent direct arithmetic agrees, all counterexamples independently confirmed, published example equals 26098 dimes. Missing-domain arms must reject. One pass, retain all results; no seed resampling.
Proof: on the intersection of two affine segments, restrict x to residue classes modulo LCM of positive denominators. Each floored quotient is affine in the integer progression index, because the step is divisible by both denominators. Equality at first and last implies equality throughout; unequal endpoint is an explicit witness. Restrict to validated nonnegative numerators and exact bounded integer coefficients. No equivalence claim for arbitrary executable code; binding runtime to IR is an outstanding requirement.
Control: direct exhaustive progressive formula vs candidate segment evaluation on all points. Strong ordinary exact symbolic proof is the same known method, not a novelty or AI-vs-human result. Count endpoints and exhaustive evaluations separately, not speedup or money.
Selection: (1) independent migration assurance (selected for finite test) vs full migration from IBM/AWS (already offers functional equivalence testing); (2) automated accessibility remediation (Canadian challenge awards and established products; semantic accessibility acceptance missing); (3) SBOM reachability evidence (DARPA E-BOSS already targets this; actual authorized deployment evidence unavailable); (4) no deployment (commercial decision until actual residual and complete costs established).
Commercial sources:
https://canadabuys.canada.ca/en/tender-opportunities/contract-history/e60zr-202861/002/el-005 (CAD 3212805.60 total amended COBOL consultation, 2020-25, not verification price or collectible demand)
https://www.gao.gov/products/gao-26-107737 (modernization investment and savings uncertainty)
https://aws.amazon.com/about-aws/whats-new/2025/12/transform-mainframe-testing-automation/
https://www.ibm.com/docs/en/watsonx/watsonx-code-assistant-4z/2.x?topic=validate-using-z-validation-assistant-watsonx-code-assistant-z-chat-280
https://canadabuys.canada.ca/en/tender-opportunities/contract-history/cw2372310-000
https://www.darpa.mil/research/programs/enhanced-sbom-for-optimized-software-sustainment
No customer data, transactions, native account, paid tools, or financial commitments. Actual buyer demand, delivery capacity, costs and billing unknown. No inference of profit. Candidate cannot advance commercially without a rights-cleared real program, stronger complete alternative comparison, proof of execution binding, acquisition/support/repair costs and buyer evidence.
*/
function run() {
  // Source-bound public numeric rule slices, not an SSA application or advice.
  const cases=[
    {id:"pia2026",max:20000,b:[1286,7749],r:[90,32,15],d:10,
     ref:[[0,1285,90,0,10],[1286,7748,32,58*1286,10],[7749,20000,15,58*1286+17*7749,10]],
     baseline:x=>Math.floor((90*Math.min(x,1286)+32*Math.min(Math.max(x-1286,0),6463)+15*Math.max(x-7749,0))/10)},
    {id:"pia2027",max:20000,b:[1340,8077],r:[90,32,15],d:10,
     ref:[[0,1339,90,0,10],[1340,8076,32,58*1340,10],[8077,20000,15,58*1340+17*8077,10]],
     baseline:x=>Math.floor((90*Math.min(x,1340)+32*Math.min(Math.max(x-1340,0),6737)+15*Math.max(x-8077,0))/10)},
    {id:"familymax2027",max:200000,b:[17120,24710,32230],r:[150,272,134,175],d:100,
     ref:[[0,17119,150,0,100],[17120,24709,272,-122*17120,100],[24710,32229,134,-122*17120+138*24710,100],[32230,200000,175,-122*17120+138*24710-41*32230,100]],
     baseline:x=>Math.floor((150*Math.min(x,17120)+272*Math.min(Math.max(x-17120,0),7590)+134*Math.min(Math.max(x-24710,0),7520)+175*Math.max(x-32230,0))/100)}
  ];
  function compile(b,r,d,max) {
    let prev=0,carry=0; const result=[];
    for(let i=0;i<r.length;i++){
      const end=i<b.length?b[i]-1:max;
      result.push([prev,end,r[i],carry-r[i]*prev,d]);
      if(i<b.length){carry+=r[i]*(b[i]-prev);prev=b[i];}
    }
    return result;
  }
  function valid(rows,max) {
    let next=0;
    for(const row of rows){
      if(!Array.isArray(row)||row.length!==5||!row.every(Number.isSafeInteger))return false;
      const [lo,hi,a,b,d]=row;
      if(lo!==next||hi<lo||hi>max||d<1||d>100||Math.abs(a)>1000||Math.abs(b)>1000000000)return false;
      if(a*lo+b<0||a*hi+b<0)return false;
      next=hi+1;
    }
    return next===max+1;
  }
  const gcd=(a,b)=>b?gcd(b,a%b):a;
  function check(ref,candidate,max) {
    if(!valid(ref,max)||!valid(candidate,max))return {status:"REJECT_INVALID_DOMAIN",endpoints:0,groups:0};
    let endpoints=0,groups=0,witness=null;
    function ev(row,x){return (BigInt(row[2])*BigInt(x)+BigInt(row[3]))/BigInt(row[4]);}
    for(const a of ref)for(const b of candidate){
      const l=Math.max(a[0],b[0]),h=Math.min(a[1],b[1]);if(l>h)continue;
      const m=a[4]*b[4]/gcd(a[4],b[4]);
      for(let residue=0;residue<m;residue++){
        const first=l+((residue-l%m+m)%m);
        if(first>h)continue;
        const last=h-((h-residue+m)%m);
        groups++;
        for(const x of first===last?[first]:[first,last]){
          endpoints++;
          const p=ev(a,x),q=ev(b,x);
          if(p!==q&&(witness===null||x<witness.x))witness={x,reference:Number(p),candidate:Number(q)};
        }
      }
    }
    return {status:witness?"NOT_EQUIVALENT":"EQUIVALENT",endpoints,groups,witness};
  }
  function exhaustive(c,rows) {
    if(!valid(rows,c.max))return {status:"REJECT_INVALID_DOMAIN",evaluated:0};
    let first=null,mismatches=0,i=0;
    for(let x=0;x<=c.max;x++){
      while(x>rows[i][1])i++;
      const row=rows[i],actual=Math.floor((row[2]*x+row[3])/row[4]),expected=c.baseline(x);
      if(actual!==expected){mismatches++;if(first===null)first={x,reference:expected,candidate:actual};}
    }
    return {status:mismatches?"NOT_EQUIVALENT":"EQUIVALENT",evaluated:c.max+1,mismatches,first};
  }
  const results=[];
  const example=cases[0].baseline(5825);
  for(const c of cases){
    const correct=compile(c.b,c.r,c.d,c.max);
    const changedB=c.b.slice();changedB[0]++;
    const changedR=c.r.slice();changedR[1]++;
    const shifted=correct.map((x,i)=>i===1?[x[0],x[1],x[2],x[3]+Math.floor(x[4]/2),x[4]]:x.slice());
    const gap=correct.map(x=>x.slice());gap[1][0]++;
    const point=c.b[0]+1;
    const singleton=correct.flatMap((row,i)=>i===1?[[row[0],point-1,...row.slice(2)],[point,point,row[2],row[3]+row[4],row[4]],[point+1,row[1],...row.slice(2)]]:[row]);
    const split=correct.flatMap((row,i)=>i===1?[[row[0],point,...row.slice(2)],[point+1,row[1],...row.slice(2)]]:[row]);
    const arms=[["exact",correct,"EQUIVALENT"],["equivalent_split",split,"EQUIVALENT"],["bend_plus_one",compile(changedB,c.r,c.d,c.max),"NOT_EQUIVALENT"],["rate_plus_one",compile(c.b,changedR,c.d,c.max),"NOT_EQUIVALENT"],["rounding_offset",shifted,"NOT_EQUIVALENT"],["isolated_point",singleton,"NOT_EQUIVALENT"],["missing_point",gap,"REJECT_INVALID_DOMAIN"]];
    for(const [arm,rows,expected] of arms){
      const proof=check(c.ref,rows,c.max),control=exhaustive(c,rows);
      const w=proof.witness;
      const witnessConfirmed=!w||(c.baseline(w.x)===w.reference&&Math.floor((rows.find(r=>r[0]<=w.x&&r[1]>=w.x)[2]*w.x+rows.find(r=>r[0]<=w.x&&r[1]>=w.x)[3])/rows.find(r=>r[0]<=w.x&&r[1]>=w.x)[4])===w.candidate&&w.reference!==w.candidate);
      results.push({case:c.id,arm,expected,proof,control,witnessConfirmed,pass:proof.status===expected&&control.status===expected&&witnessConfirmed});
    }
  }
  return {scope:"authored finite integer-domain representation equivalence, public formula parameters; no native business or SSA application",source_example_2026_dimes:example,source_example_pass:example===26098,arms:results.length,passed:results.filter(x=>x.pass).length,total_exhaustive_evaluations:results.reduce((n,x)=>n+x.control.evaluated,0),total_certificate_endpoint_evaluations:results.reduce((n,x)=>n+x.proof.endpoints,0),results,commercial_verdict:"UNQUALIFIED_NO_DEPLOY"};
}
console.log(JSON.stringify(run(), null, 2));
