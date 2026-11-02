"""Plots of executed native histories; never annualize a short period."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def plot(campaign_directory, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    directory, output = Path(campaign_directory), Path(output)
    output.mkdir(parents=True,exist_ok=True)
    campaign = json.loads((directory/"campaign.json").read_text())
    records = [json.loads(p.read_text()) for p in sorted(directory.glob("arm-*/trajectory.json"))]
    if len(records) != campaign["completed_arms"]:
        raise ValueError("Complete native trajectory files required")
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,"axes.titleweight":"bold","figure.facecolor":"#fbfcff","axes.facecolor":"#fbfcff","savefig.facecolor":"#fbfcff"})
    targets = (("central","working_capital_aware",False,"Central / cash-aware","#3556c7"),
               ("stable_gap","working_capital_aware",False,"Stable rival costs","#16856a"),
               ("no_demand","working_capital_aware",False,"No demand","#b45047"),
               ("central","stylized_prepaid_reach_capacity",False,"Upfront reach/capacity","#945fba"))
    fig,axes=plt.subplots(1,2,figsize=(12.8,4.8))
    for world,policy,earned,label,color in targets:
        matches=[r for r in records if r["world"]["name"]==world and r["policy"]==policy and r["capital_usd"]==100000 and r["earned_only_k2"]==earned]
        if not matches:
            continue
        r=matches[0]; daily=r["daily"]
        x=[(d["day"]+1)/365 for d in daily]
        cash=[(d["available_microUSD"]-d.get("pending_tax_commitment_microUSD",0))/1e6 for d in daily]
        rolling=[]
        for end in range(365,len(daily)+1):
            previous=daily[end-366]["profit_microUSD"] if end>365 else 0
            rolling.append((daily[end-1]["profit_microUSD"]-previous)/1e6)
        if abs(rolling[-1]-r["rolling_profit"]["trailing_365_day_profit_microUSD"]/1e6)>1e-6:
            raise ValueError("Plotted rolling profit differs from native observer")
        axes[0].plot(x,cash,label=label,color=color,lw=2)
        axes[1].plot([d/365 for d in range(365,len(daily)+1)],rolling,label=label,color=color,lw=2)
    axes[0].set_title("Cash after obligations and tax holdback")
    axes[1].set_title("Profit over completed trailing 365 days")
    for ax in axes:
        ax.axhline(0,color="#657085",lw=.8)
        ax.set_xlabel("Completed modeled operating years")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1000:,.0f}k"))
        ax.grid(axis="y",alpha=.15)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="lower center",ncol=2,frameon=False,bbox_to_anchor=(.5,.02))
    fig.suptitle("Portfolio 071: conditional native licensing histories",fontsize=16,x=.055,ha="left")
    fig.text(.055,.91,"Separate $100,000 accounts • Authored buyers/costs • Two computational artifacts • No physical deployments",fontsize=9,color="#536079")
    fig.subplots_adjust(top=.80,bottom=.24,wspace=.29,left=.09,right=.97)
    fig.savefig(output/"native_history.png",dpi=180)
    fig.savefig(output/"native_history.svg")
    plt.close(fig)
    capital=[r for r in records if r["world"]["name"]=="central" and r["policy"]=="working_capital_aware" and not r["earned_only_k2"]]
    capital.sort(key=lambda r:r["capital_usd"])
    labels=[f"${r['capital_usd']:,.0f}" for r in capital]
    values=[r["rolling_profit"]["trailing_365_day_profit_microUSD"]/1e6 for r in capital]
    fig,ax=plt.subplots(figsize=(9.4,4.7))
    bars=ax.barh(labels,values,color=["#3556c7" if v>=0 else "#b45047" for v in values],height=.56)
    ax.axvline(0,color="#657085",lw=.8)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1000:,.0f}k"))
    ax.set_ylabel("Separately assumed opening equity")
    ax.set_xlabel("Final completed trailing-year profit (USD)")
    ax.invert_yaxis();ax.grid(axis="x",alpha=.15)
    for bar,value in zip(bars,values):
        ax.annotate(f"${value:,.0f}",(value,bar.get_y()+bar.get_height()/2),xytext=(5 if value>=0 else -5,0),textcoords="offset points",ha="left" if value>=0 else "right",va="center",fontsize=9)
    lo,hi=ax.get_xlim();span=hi-lo;ax.set_xlim(lo-.22*span,hi+.23*span)
    fig.suptitle("More capital does not establish more demand",fontsize=15,x=.06,ha="left")
    fig.text(.06,.90,"Matched finite buyer world; no pooling of accounts and no assumption that funding is secured.",fontsize=9,color="#536079")
    fig.subplots_adjust(top=.80,bottom=.17,left=.22,right=.94)
    fig.savefig(output/"capital_frontier.png",dpi=180)
    fig.savefig(output/"capital_frontier.svg")
    plt.close(fig)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();plot(args.campaign,args.output)
