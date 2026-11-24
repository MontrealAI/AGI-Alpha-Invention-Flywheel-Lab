// Independent commercial feasibility screen; no native account or operating authority.
// Base 3cc6bc95a13f991b5158e5bd5064b766b21632a4.
// Public sources: Nscale F-1 2026-11-12, MD&A historical results and pending Anyscale acquisition:
// https://www.sec.gov/Archives/edgar/data/2110365/000119312526458722/ck0002110365-20261112.htm
// Historical PR77 exact-head workflow: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41251886324
// Pure arithmetic only; not a preregistered economic experiment. Tests exercise authored feasibility edges, not buyers.
function evaluate() {
  // All monetary values integer USD or microUSD, explicitly distinguished.
  const target = 3000000000n;
  const ttm = (year, currentHalf, priorHalf) => year + currentHalf - priorHalf;
  const rev = ttm(33000000n,140600000n,10400000n);
  const facility = ttm(45600000n,189600000n,7800000n);
  const tech = ttm(19900000n,51300000n,7900000n);
  const ceil = (a,b) => (a+b-1n)/b;
  // Fee feasibility, integer USD, relative to best complete alternative.
  // A lower benefit bound, upper seller cost bound, other buyer costs and
  // funded reservation are all required; never treat missing costs as zero.
  function participation(benefitLower, buyerOtherUpper, sellerUpper, cash, reserve) {
    if ([benefitLower,buyerOtherUpper,sellerUpper,cash,reserve].some(v=>v===null))
      return {decision:"ABSTAIN_UNKNOWN"};
    if ([benefitLower,buyerOtherUpper,sellerUpper,cash,reserve].some(v=>typeof v!=="bigint"||v<0n))
      throw Error("NONNEGATIVE_EXACT_INPUT_REQUIRED");
    const max = benefitLower-buyerOtherUpper-1n;
    const min = sellerUpper+1n;
    if (cash<reserve) return {decision:"NO_ENTRY_UNFUNDED"};
    if (min>max) return {decision:"NO_ENTRY_NO_MUTUAL_SURPLUS"};
    return {decision:"CONDITIONAL_INTERVAL_ONLY",min:String(min),max:String(max)};
  }
  const observed = {firstMargin:38739380n,successorMargin:32233680n,invoice:1250000n,linkedContribution:50443207n,matchedDelta:38344566n};
  const sourceNet=observed.linkedContribution-observed.invoice;
  const tests=[
    rev===163200000n,facility===227400000n,tech===63300000n,
    ceil(target,facility)===14n,
    sourceNet===49193207n,
    sourceNet-observed.matchedDelta===10848641n,
    participation(null,0n,0n,0n,0n).decision==="ABSTAIN_UNKNOWN",
    participation(100n,10n,89n,100n,1n).decision==="NO_ENTRY_NO_MUTUAL_SURPLUS",
    participation(100n,10n,80n,0n,1n).decision==="NO_ENTRY_UNFUNDED",
    participation(100n,10n,80n,100n,1n).min==="81",
    participation(100n,10n,80n,100n,1n).max==="89"
  ];
  if(!tests.every(Boolean))throw Error("REGISTERED_ARITHMETIC_CHECK_FAILED");
  return {tests:tests.length,period:"2025-07-01 through 2026-06-30",nscale:{revenue_USD:String(rev),facility_cost_ex_DA_USD:String(facility),product_technology_USD:String(tech),direct_provider_gross_revenue_upper_bound_for_this_period_USD:String(rev),gainshare_entire_facility_cost_impossible_100pct_capture_upper_bound_USD:String(facility),minimum_identical_nonoverlapping_cost_pools_at_100pct_capture:String(ceil(target,facility)),minimum_at_authored_10pct_savings_20pct_fee:String(ceil(target,facility*10n/100n*20n/100n)),proposed_Anyscale_equity_consideration_USD:"1650000000",actual_acquisition_profit:null},historical_design041:{matched_delta_microUSD:String(observed.matchedDelta),source_linked_net_microUSD:String(sourceNet),difference_microUSD:String(sourceNet-observed.matchedDelta),strictly_positive_incremental_unmeasured_cost_budget_microUSD:String(observed.matchedDelta-1n),actual_search_cost:null},actual_offer:participation(null,null,null,null,null),native_profit:null,actual_collections:null,target_qualified:false};
}
console.log(JSON.stringify(evaluate(), null, 2));
