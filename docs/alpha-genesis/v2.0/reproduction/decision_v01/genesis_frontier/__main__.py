import argparse
import json
from pathlib import Path
from html import escape
from fractions import Fraction
from .model import Config, Planner


def fstr(x):
    return f"{float(x):.4f}"


def main():
    parser=argparse.ArgumentParser(description="GENESIS: finite belief-aware planning demonstration (not a trained MuZero)")
    parser.add_argument("--scenario", default="scenarios/default.json")
    parser.add_argument("--output", required=True, help="New output directory; refuses overwrite")
    args=parser.parse_args()
    out=Path(args.output).resolve()
    if out.exists():
        raise SystemExit("Output directory already exists; choose a new location")
    c=Config.from_dict(json.loads(Path(args.scenario).read_text()))
    p=Planner(c)
    s=p.initial()
    val, first=p.choose(s)
    greedy, seq=p.greedy_no_experiment(s)
    ranking=p.ranking(s)
    branches=[]
    if first == "probe":
        for i, (prob, reward, next_state) in enumerate(p.outcomes(s,first)):
            bvalue, baction=p.choose(next_state)
            branches.append({"signal":"positive" if i==0 else "negative", "probability":fstr(prob),"posterior_good":fstr(next_state.p_good), "next_action":baction,"continuation_value":fstr(bvalue)})
    result={
        "status":"ILLUSTRATIVE_EXACT_FINITE_MODEL_ONLY",
        "source_scenario":str(Path(args.scenario)),
        "title":c.title,
        "premises":"Numbers, likelihoods and offered returns are invented toy-model premises; not market observations, AI benchmarks, physical data or executed commercial evidence.",
        "not_implemented":["MuZero neural world-model training", "open-web frontier event discovery", "calibrated causal model", "real buyer or competitor strategic response", "physical qualification", "deployment to customers"],
        "horizon":c.horizon, "starting_cash":c.starting_cash, "protected_reserve":c.protected_reserve,
        "initial_viability_prior":fstr(c.initial_p_good),
        "optimal_first_action":first, "optimal_expected_net_surplus":fstr(val),
        "myopic_control_net_surplus":fstr(greedy), "myopic_actions":seq,
        "conditional_planning_gain":fstr(val-greedy),
        "root_ranked_actions":[{"action":a,"expected_complete_plan_net":fstr(v)} for a,v in ranking],
        "posterior_branches":branches,
        "action_meanings":{
            "probe":"Purchase one informative diagnostic; update belief without claiming proof",
            "construct":"Pay construction+qualification cost; outcome may qualify a new asset or fail; qualified asset unlocks cheaper new deliveries",
            "frontier:A/B":"Use an already-accessible frontier agent for that delivery, with the specified net contribution",
            "specialist:A/B":"Use a qualified specialist route for that delivery",
            "own:A/B":"Use newly constructed and qualified capability for that delivery; included maintenance cost",
            "stop":"Make no speculative investment"}
    }
    out.mkdir(parents=True)
    (out/"decision.json").write_text(json.dumps(result,indent=2)+"\n")
    cards=''.join(f'<tr><td>{escape(x["action"])}</td><td class="num">{escape(x["expected_complete_plan_net"])}</td></tr>' for x in result['root_ranked_actions'])
    detail=''.join(f'<div class="branch"><strong>{b["signal"].title()} signal</strong><span>Likelihood {b["probability"]} · posterior viability {b["posterior_good"]} · next action <b>{escape(b["next_action"])}</b></span></div>' for b in branches)
    html=f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GENESIS Ω · Frontier Decision</title><style>
:root{{--bg:#130e22;--line:#ba9852;--text:#f9efd3;--muted:#b8a9b3}}body{{margin:0;font-family:system-ui,-apple-system,sans-serif;background:radial-gradient(circle at 50% -20%,#512149 0%,#130e22 48%);color:var(--text)}}main{{max-width:930px;margin:auto;padding:45px 24px 60px}}.eyebrow{{color:#e4ba74;letter-spacing:.2em;font-size:12px}}h1{{font-family:Georgia,serif;font-weight:400;font-size:clamp(32px,6vw,67px);color:#f6d38b;margin:10px 0}}h2{{font-family:Georgia,serif;font-weight:400;color:#f6d38b;margin-top:32px}}p{{line-height:1.6}}.lead{{font-size:20px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:26px 0}}.card{{border:1px solid #8b643d;background:#ffffff08;border-radius:14px;padding:20px}}.metric{{font-size:34px;font-family:Georgia,serif;color:#f2d48b}}small,.muted{{color:var(--muted)}}table{{border-collapse:collapse;width:100%;background:#ffffff05}}th,td{{padding:12px 15px;text-align:left;border-bottom:1px solid #ffffff23}}th{{color:#e7c686}}.num{{font-variant-numeric:tabular-nums}}.branch{{display:flex;flex-direction:column;gap:5px;margin:9px 0;padding:14px;border-left:3px solid #cfab61;background:#ffffff09}}footer{{margin-top:35px;color:#c6b5bb;font-size:13px}}a{{color:#f6d38b}}</style></head>
<body><main><div class="eyebrow">MONTREAL.AI · GENESIS FRONTIER WORLD MODEL · Ω</div><h1>The advantage worth choosing.</h1><p class="lead">A finite, belief-aware decision model compares existing frontier intelligence, conventional specialists, new construction, experiments, and non-entry. It never rewards invention for its own sake.</p><div class="cards"><div class="card"><small>Best first action</small><div class="metric">{escape(first)}</div></div><div class="card"><small>Modeled expected net surplus</small><div class="metric">{fstr(val)}</div></div><div class="card"><small>Myopic control</small><div class="metric">{fstr(greedy)}</div></div></div><h2>Actions under the declared finite game</h2><table><thead><tr><th>Initial action</th><th>Expected net outcome, after continuation</th></tr></thead><tbody>{cards}</tbody></table><h2>Information changes what is worth building</h2>{detail if detail else '<p>The best first action is not a probe in this declared scenario.</p>'}<h2>What this does not establish</h2><p>These are explicitly authored model assumptions, not observed customer demand, real frontier performance, calibrated probabilities, a real MuZero neural network, or demonstrated autonomous discovery. The choice is exactly optimal only for the specified four-step decision model.</p><footer>Evidence before advantage · This model is for research and design, not financial advice or deployment of physical equipment. <a href="decision.json">Inspect machine-readable results</a>.</footer></main></body></html>'''
    (out/"index.html").write_text(html)
    print(json.dumps({"first_action":first,"optimal":fstr(val),"myopic":fstr(greedy),"branches":branches,"path":str(out)},indent=2))

if __name__ == "__main__":
    main()
