from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import argparse
import hashlib
import json
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, SymLogNorm
from matplotlib.ticker import FuncFormatter
import numpy as np


MICRO = 1_000_000
WINDOW = {"start_inclusive": "2028-11-01T00:00:00Z", "end_exclusive": "2029-11-01T00:00:00Z"}
ROUTES = ("purpose", "interface", "complementarity", "arrangement", "foundry")
COLORS = {"purpose":"#5e3c78", "interface":"#246d84", "complementarity":"#a77826", "arrangement":"#ac475c", "foundry":"#36785c"}
TITLE = "Finite authored support-package scenarios · no actual commerce"


def exact_usd(value):
    if type(value) is not int:
        raise ValueError("monetary source values must be integer microUSD")
    amount = Decimal(value) / Decimal(MICRO)
    return f"{amount:,.6f}".rstrip("0").rstrip(".")


def money(value):
    return "$" + exact_usd(value)


def day(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def display_usd(value, _position=None):
    sign, value = ("−", -value) if value < 0 else ("", value)
    for scale, suffix in ((1e9,"B"),(1e6,"M"),(1e3,"k")):
        if value >= scale:
            return f"{sign}${value/scale:g}{suffix}"
    return f"{sign}${value:g}"


@dataclass
class SourceDataSummary:
    public_root: Path
    hashes: dict
    files_read: list

    def read(self, relative):
        candidate = (self.public_root / relative).resolve(strict=True)
        if not candidate.is_relative_to(self.public_root) or not candidate.is_file():
            raise ValueError("report input escapes the supplied public directory")
        data = candidate.read_bytes()
        self.hashes[str(relative)] = hashlib.sha256(data).hexdigest()
        self.files_read.append(str(relative))
        return json.loads(data)


def compact_case(record):
    final = record["final_native_summary_microUSD"]
    observer = record["observer"]
    return {
        "case_id":record["case_id"], "route":record["route"], "scenario":record["scenario"],
        "opening_microUSD":record["opening_microUSD"],
        "cumulative_company_profit_microUSD":final["profit"],
        "final_365_day_company_profit_microUSD":observer["trailing_365_day_profit_microUSD"],
        "final_cash_microUSD":final["cash"], "final_available_microUSD":final["available"],
        "protected_cash_microUSD":final["cash"]-final["available"],
        "payables_microUSD":final["payables"], "tail_reserve_microUSD":final["tailReserve"],
        "revenue_microUSD":final["revenue"], "expenses_microUSD":final["expenses"],
        "tax_assessed_microUSD":record["tax_assessed_microUSD"],
        "accepted_and_collected_orders":record["accepted_and_collected_orders"],
        "actual_package_deliveries":record["actual_package_deliveries"],
        "producer_native_audit_accepted":record["audit"]["accepted"],
        "account_summary_covered":record["account_summary_covered"],
        "source_sha256":record["native_source_sha256"],
        "window_calendar_utc":record["window_calendar_utc"],
        "target_1b":record["target_1b"], "target_3b":record["target_3b"],
        "k2_investment":record["k2_investment"],
        "one_step_regret_max_microUSD":record["one_step_regret_max_microUSD"]
    }


def validate_case(record, expected_id):
    if record["case_id"] != expected_id or record["route"] not in ROUTES:
        raise ValueError("case identity mismatch")
    if record["window_calendar_utc"] != WINDOW:
        raise ValueError("unexpected modeled operating window")
    observer = record["observer"]
    if observer["qualification"] != "FULL_OPERATING_YEAR" or not observer["complete_365_day_operating_history"]:
        raise ValueError("incomplete operating year cannot support final report")
    if observer["interval"]["end_hour_exclusive"]-observer["interval"]["start_hour_inclusive"] != 365*24:
        raise ValueError("observer is not exactly 365 days")
    profit = observer["trailing_365_day_profit_microUSD"]
    for label, threshold in (("target_1b",1_000_000_000),("target_3b",3_000_000_000)):
        if record[label] != (profit >= threshold*MICRO):
            raise ValueError("milestone flag contradicts native observer")
    if record["actual_revenue_usd"] != 0 or record["observed_market_calibration"] or record["physical_deployment_qualified"]:
        raise ValueError("unexpected external-validation claim requires separate review")
    if not record["audit"]["accepted"]:
        raise ValueError("producer native audit rejected")
    if len(record["monthly"]) != 36 or [x["month"] for x in record["monthly"]] != list(range(1,37)):
        raise ValueError("expected full 36-month public history")
    for summary in [record["final_native_summary_microUSD"]] + [x["state_microUSD"] for x in record["monthly"]]:
        for field in ("cash","available","profit","payables","tailReserve"):
            if type(summary[field]) is not int:
                raise ValueError("native summary currency must remain exact integer microUSD")
        if summary["cash"] < summary["available"] or summary["cash"] < 0:
            raise ValueError("invalid cash/availability order")


def load_public(public, preview):
    root = Path(public).resolve(strict=True)
    if root.name != "public" or not root.is_dir():
        raise ValueError("--public must identify the public directory itself")
    source = SourceDataSummary(root,{},[])
    protocol = source.read("protocol.json")
    identity = source.read("RUN_IDENTITY.json")
    amendment = source.read("QUALIFICATION_AMENDMENT_R2.json")
    routes = amendment["plan"]["routes"]
    if tuple(routes) != ROUTES:
        raise ValueError("unexpected route registry")
    expected = [f"{route}-{scenario['id']}" for route in routes for scenario in protocol["registered_scenarios"]]
    if len(expected) != 110 or len(set(expected)) != 110 or amendment["plan"]["registered_cases"] != 110:
        raise ValueError("registered case denominator changed")
    complete = None
    if not preview:
        if not (root/"RESULTS.json").exists():
            raise ValueError("final RESULTS.json absent: refusing a final report; use --preview outside the repository")
        complete = source.read("RESULTS.json")
        if (complete.get("status") != "COMPLETE"
                or complete.get("registered_businesses") != len(expected)
                or complete.get("completed_businesses") != len(expected)
                or complete.get("failed_businesses") != 0
                or [row.get("case_id") for row in complete.get("cases",[])] != expected):
            raise ValueError("campaign does not declare completion without failed cases")
    cases, missing = {}, []
    for identifier in expected:
        relative = f"{identifier}/RESULT.json"
        if not (root/relative).exists():
            missing.append(identifier)
            continue
        record = source.read(relative)
        validate_case(record,identifier)
        cases[identifier] = record
    if not preview and missing:
        raise ValueError(f"only {len(cases)}/110 registered public cases are complete")
    if not cases:
        raise ValueError("no completed public cases")
    natives = {r["native_source_sha256"] for r in cases.values()}
    if len(natives) != 1:
        raise ValueError("source identities differ across the proposed comparison")
    if complete is not None:
        for compact in complete["cases"]:
            record = cases[compact["case_id"]]
            final = record["final_native_summary_microUSD"]
            expected_fields = {"opening_microUSD":record["opening_microUSD"],
                "profit_microUSD":final["profit"], "cash_microUSD":final["cash"],
                "trailing_365_profit_microUSD":record["observer"]["trailing_365_day_profit_microUSD"],
                "target_1b":record["target_1b"], "target_3b":record["target_3b"],
                "native_source_sha256":record["native_source_sha256"]}
            if any(compact.get(key) != value for key,value in expected_fields.items()):
                raise ValueError("campaign summary contradicts its public case: "+compact["case_id"])
    return source,protocol,identity,amendment,cases,missing


def style():
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":9, "axes.titlesize":10, "axes.labelsize":9,
        "axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#c8c4c1",
        "axes.labelcolor":"#38313c","text.color":"#38313c","xtick.color":"#635d65","ytick.color":"#635d65",
        "figure.facecolor":"white","axes.facecolor":"#fcfbf8","grid.color":"#e7e3df","grid.linewidth":0.6,
        "svg.fonttype":"none", "svg.hashsalt":"public-portfolio-r2-report-v1", "savefig.bbox":"tight"})


def save(fig,output,name):
    fig.savefig(output/name,format="svg",metadata={"Date":None,"Description":TITLE})
    plt.close(fig)


def axes_money(axis):
    axis.yaxis.set_major_formatter(FuncFormatter(display_usd))
    axis.axhline(0,color="#9e969d",linewidth=0.8)
    axis.grid(axis="y")


def selected_records(cases):
    return [cases[f"{r}-central-100k"] for r in ROUTES if f"{r}-central-100k" in cases]


def liquidity_plot(cases,output,prefix):
    selected = selected_records(cases)
    if not selected:
        return None
    fig,axes = plt.subplots(len(selected),2,figsize=(12,2.15*len(selected)),squeeze=False,constrained_layout=True)
    fig.suptitle(TITLE+"\n36-month central $100,000 accounts: cash, availability and protected cash",fontsize=12)
    for row,record in enumerate(selected):
        points = record["monthly"]
        months = [p["month"] for p in points]
        cash = [p["state_microUSD"]["cash"]/MICRO for p in points]
        available = [p["state_microUSD"]["available"]/MICRO for p in points]
        protected = [(p["state_microUSD"]["cash"]-p["state_microUSD"]["available"])/MICRO for p in points]
        payables = [p["state_microUSD"]["payables"]/MICRO for p in points]
        color = COLORS[record["route"]]
        left,right = axes[row]
        left.plot(months,cash,label="Cash",color=color,lw=1.9)
        left.plot(months,available,label="Available",color="#b88025",lw=1.3,ls="--")
        left.set_title(record["case_id"],loc="left",fontweight="bold")
        right.plot(months,protected,label="Protected cash = cash − available",color=color,lw=1.6)
        right.plot(months,payables,label="Incurred unpaid obligations",color="#ac475c",lw=1.2,ls=":")
        right.set_title("Protection is cash restriction, not an additional expense",loc="left",fontsize=9)
        if not any(protected) and not any(payables):
            right.set_ylim(0,1)
            right.text(0.5,0.48,"Both zero throughout",ha="center",va="center",transform=right.transAxes,color="#79717a",fontsize=9)
        for axis in (left,right):
            axes_money(axis)
            axis.set_xlim(1,36)
            axis.set_xticks([1,6,12,18,24,30,36])
            axis.set_xlabel("Registered month (730 native hours each)")
            axis.legend(loc="best",fontsize=7,frameon=False)
    name=prefix+"liquidity.svg"
    save(fig,output,name)
    return name


def profit_plot(cases,output,prefix):
    selected=selected_records(cases)
    if not selected:
        return None
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),constrained_layout=True)
    fig.suptitle(TITLE+"\nCompany profit is separate from seed capital and cash",fontsize=12)
    for record in selected:
        points=record["monthly"]
        dates=[day(p["calendar_utc"]) for p in points]
        color=COLORS[record["route"]]
        axes[0].plot(dates,[p["state_microUSD"]["profit"]/MICRO for p in points],label=record["route"],color=color,lw=1.7)
        full=[p for p in points if p["trailing_365_profit_microUSD"] is not None]
        xs=[day(p["calendar_utc"]) for p in full]+[day(WINDOW["end_exclusive"])]
        ys=[p["trailing_365_profit_microUSD"]/MICRO for p in full]+[record["observer"]["trailing_365_day_profit_microUSD"]/MICRO]
        axes[1].plot(xs,ys,label=record["route"],color=color,lw=1.7)
        axes[1].scatter(xs[-1:],ys[-1:],color=color,s=12)
    axes[0].set_title("Cumulative native company profit · central $100k")
    axes[1].set_title("Exact trailing 365-day profit · completed windows only")
    for axis in axes:
        axes_money(axis)
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        axis.tick_params(axis="x",rotation=25)
        axis.legend(frameon=False,fontsize=8)
    name=prefix+"profit-history.svg"
    save(fig,output,name)
    return name


def frontier_plot(cases,output,prefix):
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),constrained_layout=True)
    fig.suptitle(TITLE+"\nFinite registered capital comparison; each marker is a separate native account",fontsize=12)
    for route in ROUTES:
        selected=[cases[f"{route}-{s}"] for s in ("central-100k","central-1m","central-1b") if f"{route}-{s}" in cases]
        if not selected:
            continue
        x=[r["opening_microUSD"]/MICRO for r in selected]
        y1=[r["observer"]["trailing_365_day_profit_microUSD"]/MICRO for r in selected]
        y2=[r["final_native_summary_microUSD"]["profit"]/MICRO for r in selected]
        axes[0].plot(x,y1,marker="o",lw=1.3,color=COLORS[route],label=route)
        axes[1].plot(x,y2,marker="o",lw=1.3,color=COLORS[route],label=route)
    axes[0].set_title("Final exact trailing-year profit")
    axes[1].set_title("Final cumulative company profit")
    for axis in axes:
        axes_money(axis)
        axis.set_xscale("log")
        axis.set_xticks([100_000,1_000_000,1_000_000_000],labels=["$100k","$1M","$1B"])
        axis.set_xlabel("Hypothetical initial equity · not profit or secured financing")
        axis.legend(frameon=False,fontsize=8)
    name=prefix+"capital-frontier.svg"
    save(fig,output,name)
    return name


def scenario_plot(cases,protocol,output,prefix):
    names=[s["id"] for s in protocol["registered_scenarios"]]
    values=np.full((len(ROUTES),len(names)),np.nan)
    for i,route in enumerate(ROUTES):
        for j,scenario in enumerate(names):
            record=cases.get(f"{route}-{scenario}")
            if record:
                values[i,j]=record["observer"]["trailing_365_day_profit_microUSD"]/MICRO
    bound=max(1,float(np.nanmax(np.abs(values))))
    cmap=LinearSegmentedColormap.from_list("profit",["#a13b54","#fcfbf8","#2e657c"])
    cmap.set_bad("#dddddd")
    fig,axis=plt.subplots(figsize=(15,4.9),constrained_layout=True)
    image=axis.imshow(values,cmap=cmap,norm=SymLogNorm(linthresh=100,vmin=-bound,vmax=bound),aspect="auto")
    axis.set_xticks(range(len(names)),labels=names,rotation=55,ha="right",fontsize=7)
    axis.set_yticks(range(len(ROUTES)),labels=ROUTES)
    axis.set_title(TITLE+"\nAll registered endpoint trailing-365-day results; red losses, blue gains, grey unfinished",fontsize=11,pad=14)
    bar=fig.colorbar(image,ax=axis,pad=0.02)
    bar.set_label("Modeled USD · symmetric logarithmic color scale")
    bar.ax.yaxis.set_major_formatter(FuncFormatter(display_usd))
    name=prefix+"all-scenarios.svg"
    save(fig,output,name)
    return name


def table(records):
    header="| Account | Initial equity | Cumulative company profit | Exact final 365-day profit | Cash | Available | Protected cash | Unpaid obligations | Collected orders |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    rows=[]
    for record in records:
        case=compact_case(record)
        row=[case["case_id"]]+[money(case[k]) for k in ("opening_microUSD","cumulative_company_profit_microUSD","final_365_day_company_profit_microUSD","final_cash_microUSD","final_available_microUSD","protected_cash_microUSD","payables_microUSD")]+[str(case["accepted_and_collected_orders"])]
        rows.append("| "+" | ".join(row)+" |")
    return header+"\n"+"\n".join(rows)


def generate(public,output,preview=False):
    source,protocol,identity,amendment,cases,missing=load_public(public,preview)
    destination=Path(output).resolve()
    if destination.is_relative_to(source.public_root) or source.public_root.is_relative_to(destination):
        raise ValueError("output must be separate from the public evidence input")
    repo_root=Path(__file__).resolve().parents[3]
    if preview and destination.is_relative_to(repo_root):
        raise ValueError("exploratory preview must remain outside the repository")
    destination.mkdir(parents=True,exist_ok=True)
    prefix="EXPLORATORY_" if preview else ""
    style()
    charts=[liquidity_plot(cases,destination,prefix),profit_plot(cases,destination,prefix),frontier_plot(cases,destination,prefix),scenario_plot(cases,protocol,destination,prefix)]
    charts=[name for name in charts if name]
    ordered=list(cases.values())
    best=max(ordered,key=lambda r:r["observer"]["trailing_365_day_profit_microUSD"])
    worst=min(ordered,key=lambda r:r["observer"]["trailing_365_day_profit_microUSD"])
    target1=[r["case_id"] for r in ordered if r["target_1b"]]
    target3=[r["case_id"] for r in ordered if r["target_3b"]]
    uncovered=[r["case_id"] for r in ordered if not r["account_summary_covered"]]
    central=[cases[f"{r}-{s}"] for r in ROUTES for s in ("central-100k","central-1m","central-1b") if f"{r}-{s}" in cases]
    controls=[cases[f"{r}-{s}"] for r in ROUTES for s in ("non-entry","rights-unresolved") if f"{r}-{s}" in cases]
    frontier=[]
    for route in ROUTES:
        eligible=[r for r in ordered if r["route"]==route]
        nondominated=[]
        for record in eligible:
            capital=record["opening_microUSD"]
            profit=record["observer"]["trailing_365_day_profit_microUSD"]
            dominated=any(other["opening_microUSD"]<=capital and other["observer"]["trailing_365_day_profit_microUSD"]>=profit and (other["opening_microUSD"]<capital or other["observer"]["trailing_365_day_profit_microUSD"]>profit) for other in eligible)
            if not dominated:
                nondominated.append(record["case_id"])
        frontier.append({"route":route,"nondominated_native_records":nondominated,"scope":"Read-only capital/endpoint-profit comparison across the finite registered records, including different authored worlds and controls; not a causal or global strategy optimum"})
    prospect_count=protocol["finite_market"]["prospects_per_route"]
    largest_price=max(Decimal(str(value))*MICRO for profile in protocol["profiles_usd"].values() for value in profile["price_grid"])
    if largest_price != largest_price.to_integral_value():
        raise ValueError("posted price bound requires exact microUSD")
    gross_bound=int(largest_price)*prospect_count*3
    r1=identity.get("r1_reference",{})
    summary={"schema":"public-portfolio/read-only-report/v1","status":"EXPLORATORY_PARTIAL_PREVIEW" if preview else "COMPLETE_REGISTERED_R2_REPORT","completed_cases":len(cases),"registered_cases":110,"missing_case_ids":missing,"window_calendar_utc":WINDOW,"SourceDataSummary":{"read_policy":"Only explicit files beneath the supplied public directory; symlink escapes rejected; no private recovery or signing directory read","files_read":source.files_read,"sha256":source.hashes,"R2_code_commit":identity.get("code_commit"),"R2_native_source_sha256":sorted({r["native_source_sha256"] for r in ordered}),"protocol_sha256":identity.get("protocol_sha256"),"R1_failed_prefix_preserved":{"completed_cases":len(r1.get("completed_case_ids",[])),"status":"SOURCE_CLOSURE_QUALIFICATION_FAILED; preserved separately, never imported as R2 funds or fresh confirmation"}},"method":{"currency":"Exact integer microUSD copied from native summaries and observers; only SVG coordinates use floating-point USD","profit_scope":"One account at a time. No sum across accounts, annualization, inferred industrial scale or initial-equity income","report_is_not_ledger":True,"independent_audit_scope":"Producer native-audit flags copied from public data; this generator is not an independent financial replay","reserve_scope":"Protected cash is cash minus available; not an additional expense. Payables remain incurred expenses and are shown separately where relevant"},"endpoint_comparison":{"best_case":compact_case(best),"worst_case":compact_case(worst),"target_1b_cases":target1,"target_3b_cases":target3},"finite_frontier":frontier,"case_summaries":[compact_case(r) for r in ordered],"claims":{"actual_commerce":"NOT_ESTABLISHED; actual revenue remains zero","physical_or_industry_creation":"NOT_ESTABLISHED","scientific_limits":"All original five route boundaries remain: conventional/equal-content ties, simulation-only physical claims and incomplete transfer/admission cannot be upgraded by economic results","human_baseline_productivity":"UNMEASURED","market_prices_demand_rights":"UNCALIBRATED_AUTHORED_HYPOTHESES; rights-unresolved controls refuse licensing; other cases assume clearance","capital":"HYPOTHETICAL_INITIAL_EQUITY_NOT_PROFIT_OR_SECURED_FINANCING","global_game_theoretic_optimality":"NOT_ESTABLISHED; only recorded finite current-unit price-grid regret exists","actual_host_model_billing":"UNKNOWN_NULL_NOT_ZERO"},"charts":charts}
    qualifier="EXPLORATORY PREVIEW — unfinished matrix" if preview else "R2 complete finite comparison"
    lines=[f"# AGI ALPHA: {qualifier}","",f"{len(cases)} of 110 registered, separately funded native scenarios are represented. These are hypothetical nonexclusive computational packages, checking and prepaid support. They establish no actual commerce, physical deployment, industry creation or measured human-productivity gain.","",f"The exact final operating window is **{WINDOW['start_inclusive']} to {WINDOW['end_exclusive']}**, start inclusive and end exclusive. The 36 registered months contain 730 native hours each. Earlier short histories are not annualized; completed trailing-365-day observations begin only after a full year.","",f"Best final trailing-year record: **{best['case_id']}**, {money(best['observer']['trailing_365_day_profit_microUSD'])}. Worst: **{worst['case_id']}**, {money(worst['observer']['trailing_365_day_profit_microUSD'])}. These are individual accounts, never pooled. Endpoint $1B milestone cases: {len(target1)}; $3B milestone cases: {len(target3)}.","","## Central capital comparison","","Each row is a distinct authored business/account. Initial equity, including $1B, is neither profit nor secured funding. Cumulative native company profit, exact final trailing-year profit and final cash are separate quantities. Cash restrictions are not charged again as expenses; post-operating settlements remain on the original account.","",table(central),"","## Non-entry and rights controls","","Non-entry and licensing refusal are valid outcomes. Rights-qualified central arms are counterfactual assumptions, not legal clearance; public source availability does not supply commercial rights.","",table(controls),"","## Histories and finite frontier","","![Cash and protection]("+prefix+"liquidity.svg)","","![Profit histories]("+prefix+"profit-history.svg)","","![Finite capital comparison]("+prefix+"capital-frontier.svg)","","![All registered scenarios]("+prefix+"all-scenarios.svg)","","Every negative result remains represented. The frontier compares existing native records across registered capital/strategy/world combinations, including non-entry. It is not a causal ranking between changed worlds, an investor commitment, a new ledger or a globally optimal enterprise. Exact monetary values and all case identities are retained in the claims file.","","## Evidence and remaining limits","",f"R1's {len(r1.get('completed_case_ids',[]))}-case prefix remains preserved with failed executable source-closure qualification. R2 is a separately qualified-source engineering reproduction of the original authored financial comparisons; no R1 cash, obligations or account authority was imported, and it is not new blinded market calibration.","","This report reads only public R2 records and copies the native observer. Producer audit acceptance is not a replacement for the separately required independent replay. SourceDataSummary records every read file and SHA-256 in the claims file. The scientific limits of all five original routes remain unchanged. Prices, demand, competition, rights clearance, cost profiles and tax treatment are authored scenario inputs; actual host/model billing remains unknown. No revenue is inferred from scientific novelty, valuation, financing proceeds or customer value.","","Reproduce from a complete public evidence directory:","","```bash","python experiments/public_portfolio_20261102/reporting/generate.py --public /absolute/path/public --output /absolute/path/report","```",""]
    summary["finite_market_scope"]={"prospects_per_independent_account":prospect_count,
        "maximum_scheduled_purchase_opportunities_per_buyer":3,
        "largest_registered_posted_price_microUSD":int(largest_price),
        "loose_three_year_gross_contract_value_ceiling_microUSD":gross_bound,
        "scope":"Finite authored comparison screen. Larger seed does not enlarge registered demand; these small-market instances leave billion-scale viability and impossibility unidentified."}
    lines[4:4]=[f"Each account has **{prospect_count} authored prospects** and at most three scheduled purchase opportunities per buyer (initial K1, one renewal, K2). The largest registered posted price is {money(int(largest_price))}, giving a loose **{money(gross_bound)} gross-contract ceiling over all three years** per account. The registered $1B initial-equity comparison leaves demand unchanged. This small-market screen leaves the $3B scale path unidentified; zero attainment supplies no global business impossibility result.",""]
    summary["monthly_native_observations"]={record["case_id"]:[{
        "month":point["month"], "hour":point["hour"], "calendar_utc":point["calendar_utc"],
        "cash_microUSD":point["state_microUSD"]["cash"],
        "available_microUSD":point["state_microUSD"]["available"],
        "protected_cash_microUSD":point["state_microUSD"]["cash"]-point["state_microUSD"]["available"],
        "payables_microUSD":point["state_microUSD"]["payables"],
        "cumulative_profit_microUSD":point["state_microUSD"]["profit"],
        "observed_window_profit_microUSD":point["observed_short_window_profit_microUSD"],
        "trailing_365_profit_microUSD":point["trailing_365_profit_microUSD"]
    } for point in record["monthly"]] for record in ordered}
    summary["reporting_provenance"]={"generator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"python":platform.python_version(),"numpy":np.__version__,"matplotlib":matplotlib.__version__,"chart_dates_embedded":False}
    summary["funding_coverage"]={"uncovered_case_ids":uncovered,"count":len(uncovered),"meaning":"Native audit acceptance can coexist with a negative business outcome: incurred unpaid obligations or inadequate available cash. These cases remain included; coverage is not silently converted to success."}
    insertion=lines.index("## Histories and finite frontier")
    lines[insertion:insertion]=[f"**Funding failures remain visible:** {len(uncovered)} reported accounts have account_summary_covered=false. Their incurred obligations remain expenses, and their unpaid amounts are retained in CLAIMS.json; native arithmetic acceptance does not turn them into funded success.",""]
    if preview:
        lines.insert(4,"**This is an exploratory view of completed public cases only. Missing cases are unfinished, not zero. No final 110-case conclusion is warranted.**")
    report_name="EXPLORATORY_PREVIEW.md" if preview else "REPORT.md"
    claims_name="EXPLORATORY_CLAIMS.json" if preview else "CLAIMS.json"
    (destination/report_name).write_text("\n".join(lines))
    (destination/claims_name).write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    return {"status":summary["status"],"completed_cases":len(cases),"registered_cases":110,"report":str(destination/report_name),"claims":str(destination/claims_name),"charts":charts}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Read-only public R2 report; no financial runtime imports or account mutations")
    parser.add_argument("--public",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--preview",action="store_true",help="Write explicitly exploratory preview outside repository; final RESULTS is not required")
    args=parser.parse_args()
    try:
        print(json.dumps(generate(args.public,args.output,args.preview),indent=2))
    except (ValueError,FileNotFoundError,KeyError,json.JSONDecodeError) as error:
        raise SystemExit(f"report refused: {error}")
