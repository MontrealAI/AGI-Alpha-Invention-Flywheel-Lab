/* Thermal Interface 300 — standalone finite diagnostic. */
const protocol = {
  "date": "2026-11-26",
  "scope": "Exposed source development; no physical measurement, hidden benchmark, commercial or novelty qualification",
  "source": "Sandell et al. Nanomaterials 10(4),670 (2020), doi:10.3390/nano10040670, equation 2, Tables 1–2, CC BY; transcribed numeric fields, not raw data",
  "source_url": "https://www.mdpi.com/2079-4991/10/4/670",
  "challenge": "https://discoveredmaterials.com/grand-challenges/interfacial-heat-transport/",
  "rules": "https://grandchallenges.discoveredmaterials.com/official-rules",
  "main": "b35f937fcb77199334e267360e9a0c9e438a74ad",
  "rows": [
    {
      "name": "Au",
      "G": 59,
      "k": 0.198
    },
    {
      "name": "Ti",
      "G": 115,
      "k": 0.211
    },
    {
      "name": "Ni",
      "G": 139,
      "k": 0.212
    }
  ],
  "units": "G MW/(m² K); R=1000/G in m² K/GW; k W/(m K)",
  "selection": [
    {
      "route": "predict semiconductor process-to-electrical quality",
      "prize_max_usd": 200000,
      "decision": "hold; five material systems and missing process-specific trap/charge observations",
      "source": "https://discoveredmaterials.com/grand-challenges/interfacial-electrical-properties/"
    },
    {
      "route": "new efficient XC functional",
      "prize_max_usd": 200000,
      "decision": "hold; strong functional and reference calculations plus hidden chemistry not available",
      "source": "https://discoveredmaterials.com/grand-challenges/speed-accuracy-barrier/"
    },
    {
      "route": "identify transferable thermal interface terms through one added reference observation",
      "prize_max_usd": 100000,
      "decision": "selected bounded identifiability diagnostic; not challenge solution"
    },
    {
      "route": "no entry/no deploy",
      "decision": "default until transferable accepted predictions and complete costs"
    }
  ],
  "comparators": [
    "repeated thickness sweep with existing fitted combined resistance",
    "paired contrasts with common substrate",
    "independent bottom-resistance calibration with matched fabrication",
    "competent conventional linear inverse and interval arithmetic"
  ],
  "scenarios": [
    {
      "id": "reported_common",
      "rel": 0.1,
      "drift": 0,
      "cal": null
    },
    {
      "id": "reported_drift1",
      "rel": 0.1,
      "drift": 1,
      "cal": null
    },
    {
      "id": "reported_drift3",
      "rel": 0.1,
      "drift": 3,
      "cal": null
    },
    {
      "id": "hypothetical_reference",
      "rel": 0.1,
      "drift": 0,
      "cal": [
        2,
        3
      ]
    },
    {
      "id": "hypothetical_precise_reference",
      "rel": 0.02,
      "drift": 0,
      "cal": [
        2.4,
        2.6
      ]
    },
    {
      "id": "hypothetical_precise_reference_drift",
      "rel": 0.02,
      "drift": 1,
      "cal": [
        2.4,
        2.6
      ]
    }
  ],
  "interpretation": "Treat published ±10% as authored deterministic independent endpoint boxes, not statistical confidence; 2% and calibration/drift values are hypothetical sensitivity, not measured. Model R_i=T_i+B+delta_i with nonnegative T_i and bottom B+delta_i, delta_i in [-d,d]; no-calibration contrast extrema use freely admissible B=0,deltas=0 for d=0, and B=d for d>0 (fits all registered lower bounds). If B has calibration interval, enforce positivity and reject scenarios if any registered endpoint infeasible. Calibrated contrast cancels B. Threshold width <=1 m² K/GW for all absolute T_i is authored diagnostic not buyer requirement. Robust ordering only if lower endpoint strictly positive. Rank of intercept matrix [I3 | 1] is 3, repeated rows cannot increase rank; add direct B observation gives 4. Recheck rank and null shift on exact algebra, compare every analytic interval to independent corner enumeration. Stop after six scenarios and three pairs each; no tuning or additional cases. Only source-exposed diagnosis, no novel algorithm or claim of transfer. No entry, spending, data submission, account or deployment. Strong ordinary alternatives include FDTR/TDTR, independent reference specimens and atomistic/ML potential approaches (https://arxiv.org/abs/2503.05084, https://arxiv.org/abs/2604.15394)."
};
function run(p){
 const start=Date.now(), out=[]; let checks=0;
 const names=p.rows.map(x=>x.name);
 const near=(a,b)=>Math.abs(a-b)<1e-9;
 function check(x){checks++;if(!x)throw Error("registered check "+checks+" failed")}
 function rank(m){m=m.map(x=>x.slice());let k=0;for(let c=0;c<m[0].length&&k<m.length;c++){let t=m.findIndex((x,i)=>i>=k&&Math.abs(x[c])>1e-10);if(t<0)continue;[m[k],m[t]]=[m[t],m[k]];for(let i=k+1;i<m.length;i++){const f=m[i][c]/m[k][c];for(let j=c;j<m[0].length;j++)m[i][j]-=f*m[k][j]}k++}return k}
 const M=[[1,0,0,1],[0,1,0,1],[0,0,1,1]],v=[-1,-1,-1,1], repeated=[...M,...M,...M], extended=[...M,[0,0,0,1]];
 check(rank(M)===3);check(rank(repeated)===3);check(rank(extended)===4);check(M.every(row=>row.reduce((s,x,i)=>s+x*v[i],0)===0));check(extended[3].reduce((s,x,i)=>s+x*v[i],0)===1);
 for(const s of p.scenarios){
  const {rel,drift:d,cal}=s;const R=p.rows.map(x=>[1000/(x.G*(1+rel)),1000/(x.G*(1-rel))]);
  const B=cal??[d,d]; // no-reference anchor for contrast witness, NOT a calibration
  check(B[0]-d>=0);check(R.every(([l])=>l>=B[1]+d));
  const corners=[]; for(let mask=0;mask<128;mask++){let b=B[(mask>>6)&1];let z=R.map((r,i)=>r[(mask>>i)&1]-b-(((mask>>(i+3))&1)?d:-d));check(z.every(x=>x>=0));corners.push(z)}
  const extrema=a=>[Math.min(...a),Math.max(...a)];
  const abs=cal?R.map(([l,h])=>[l-B[1]-d,h-B[0]+d]):R.map(([l,h])=>[0,h]);
  for(let i=0;i<3;i++){if(cal){let w=extrema(corners.map(z=>z[i]));check(w.every((x,j)=>near(x,abs[i][j])))}else{
   // Without an absolute calibration, exact per-interface bounds with nonnegative terms:
   // min T_i=0 at R_i=l_i if the required B+delta is compatible with the other rows;
   // the more informative common-bottom lower bound uses the limiting other upper endpoint.
   // B may be as high as min_j H_j+d; delta_i<=d; B>=0.
   const maxBottom=Math.min(...R.map(r=>r[1]))+2*d;
   abs[i][0]=Math.max(0,R[i][0]-maxBottom);
   // Construct both extreme witnesses, including arbitrary B and bottom drift.
   const upperR=R.map((r,j)=>j===i?r[1]:r[0]); check(near(upperR[i],abs[i][1]));
   const bi=Math.min(R[i][0],maxBottom), base=Math.max(0,bi-d);
   const chosen=R.map((r,j)=>j===i?r[0]:Math.max(r[0],base-d));
   check(chosen.every((x,j)=>x<=R[j][1]+1e-9));
   const bottom=chosen.map((x,j)=>j===i?bi:Math.max(0,base-d));
   check(bottom.every((x,j)=>x>=0&&x<=chosen[j]+1e-9&&Math.abs(x-base)<=d+1e-9));
   check(near(chosen[i]-bottom[i],abs[i][0]));
  }}
  const pairs=[];for(let i=0;i<3;i++)for(let j=i+1;j<3;j++){const a=[R[i][0]-R[j][1]-2*d,R[i][1]-R[j][0]+2*d];const b=extrema(corners.map(z=>z[i]-z[j]));check(a.every((x,k)=>near(x,b[k])));pairs.push({pair:names[i]+"-"+names[j],interval:a,robust_improvement:a[0]>0})}
  out.push({id:s.id,R,top_intervals:abs,top_widths:abs.map(([l,h])=>h-l),all_absolute_width_le_1:abs.every(([l,h])=>h-l<=1),pairs});
 }
 return {scenarios:out,rank:{existing:rank(M),repeated:rank(repeated),added_reference:rank(extended)},checks,elapsed_ms:Date.now()-start};
}
console.log(JSON.stringify(run(protocol),null,2));
