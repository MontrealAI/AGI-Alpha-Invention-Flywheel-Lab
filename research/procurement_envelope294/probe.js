// Frozen finite development calculation; run with Node or call probe().
function probe() {
  const raw = [
["R","30-60","EUR","E003/106e",4423,3317],["R","30-60","USD","E003/076e",3603,3123],["R","30-60","USD","E003-098e",2875,2725],
["R","60-120","EUR","E003/132e",4782,3587],["R","60-120","USD","E003/116e",4417,3937],["R","60-120","EUR","E003/059e",5060,4880],
["R","120+","EUR","E003/108e",5704,4278],["R","120+","USD","E003/117e",4829,4349],["R","120+","EUR","E003/040e",5255,5050],
["RF","30-60","EUR","E003/153",7078,6134],["RF","30-60","USD","E003/074e",5143,4593],["RF","30-60","USD","E003-129e",3100,2950],["RF","30-60","EUR","E003/084e",5641,5441],["RF","30-60","EUR","E003/157",7044,5283],
["RF","60-120","EUR","E003-132e",7778,5834],["RF","60-120","USD","E003/135e",6516,5966],["RF","60-120","EUR","E003/048e",6505,6195],
["RF","120+","USD","E003-145",4430,4180],["RF","120+","USD","E003-165",6779,6229],
["F","30-120","USD","E003/086",2350,1870],["F","30-120","EUR","E003/099",3103,2327]
  ];
  let pairs=[], stress=[], checks=0;
  for(const b of raw) for(const c of raw) {
    if(b===c || b.slice(0,3).join()!==c.slice(0,3).join()) continue;
    const lower=(b[5]-c[4])*100,upper=(b[4]-c[5])*100;
    const corners=[b[4],b[5]].flatMap(x=>[c[4],c[5]].map(y=>100*(x-y)));
    if(lower!==Math.min(...corners)||upper!==Math.max(...corners)) throw Error("CORNER_MISMATCH");
    checks+=2;
    pairs.push({group:b.slice(0,3),baseline:b[3],candidate:c[3],lower_cents:lower,upper_cents:upper,status:lower>0?"POSITIVE_CONDITIONAL":upper>0?"POSSIBLE_ONLY":"NO_POSITIVE",admitted:false});
    if(lower>0) for(const x of [lower-1,lower,lower+1]) {
      const residual=lower-x;
      // Integer cents: one cent each minimum for buyer and service, after all extra costs.
      const feasible=residual>=2;
      if(feasible!== (corners.every(v=>v-x>=2))) throw Error("STRESS_MISMATCH");
      checks++;
      stress.push({baseline:b[3],candidate:c[3],extra_cost_cents:x,residual_cents:residual,positive_both_feasible:feasible});
    }
  }
  if(raw.length!==21 || raw.some(r=>r[4]<r[5]||r[5]<=0)) throw Error("SOURCE_ROWS");
  const counts={}; for(const p of pairs) counts[p.status]=(counts[p.status]||0)+1;
  return {rows:raw.length,groups:new Set(raw.map(r=>r.slice(0,3).join())).size,ordered_pairs:pairs.length,counts,checks,pairs,stress,actual_admissions:0,actual_revenue:null,actual_complete_cost:null,native_profit:null};
}
if(typeof require!=="undefined" && require.main===module) console.log(JSON.stringify(probe(),null,2));
