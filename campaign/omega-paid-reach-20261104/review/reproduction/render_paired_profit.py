"""Render the five independent, paired effects. No aggregation of enterprise accounts."""
import argparse, json, pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator

ap=argparse.ArgumentParser();ap.add_argument('input',type=pathlib.Path);ap.add_argument('output',type=pathlib.Path)
o=ap.parse_args(); x=json.loads(o.input.read_bytes())
assert x['schema']=='omega/earned-paid-reach-paired-evidence/v1' and x['actual_revenue_usd']==0
rows=[('central','Central'),('weak','Weak demand'),('copycat','Copycat'),('no_demand','No fresh demand'),('failed_activation','Activation failure')]
assert set(x['pairs'])=={k for k,_ in rows}
values=[x['pairs'][k]['comparison']['pilot_minus_organic_financial_microUSD']['profit_after_modeled_tax']/1e6 for k,_ in rows]
orders=[x['pairs'][k]['comparison']['pilot_minus_organic_counts']['settled_baskets'] for k,_ in rows]
renewals=[x['pairs'][k]['pilot']['tranches'][1]['action']=='BUY' for k,_ in rows]
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','svg.hashsalt':'omega-paid-reach-20261104','axes.unicode_minus':False})
fig=plt.figure(figsize=(10.2,4.5),facecolor='#fcfbf8'); ax=fig.add_axes([.21,.22,.50,.58],facecolor='#fcfbf8')
limit=max(10,max(abs(v) for v in values)*1.38); lower=min(-limit*.18,min(values)*1.50)
ax.set_xlim(lower,limit); ax.set_ylim(4.6,-.6); ax.set_axisbelow(True)
ax.grid(axis='x',color='#deded8',linewidth=.8); ax.axvline(0,color='#42484a',linewidth=1.2)
for i,(v,order,renewal) in enumerate(zip(values,orders,renewals)):
    color='#19665d' if v>0 else '#ad562d' if v<0 else '#7e8585'
    ax.barh(i,v,height=.46,color=color,zorder=3)
    val=(f'+${abs(v):,.3f}' if v>0 else f'-${abs(v):,.3f}' if v<0 else '$0.000')
    ax.annotate(val,(v,i),xytext=(5 if v>=0 else -5,0),textcoords='offset points',ha='left' if v>=0 else 'right',va='center',fontsize=9,color='#20282a')
    ax.text(1.08,i,f'{order:+d}',transform=ax.get_yaxis_transform(),va='center',ha='center',fontsize=10,color='#253337')
    ax.text(1.33,i,'Renewed' if renewal else 'Stopped',transform=ax.get_yaxis_transform(),va='center',ha='center',fontsize=10,color='#253337')
ax.set_yticks(range(5),[t for _,t in rows],fontsize=10); ax.tick_params(axis='both',length=0,pad=7)
ax.xaxis.set_major_locator(MaxNLocator(5));ax.xaxis.set_major_formatter(FuncFormatter(lambda a,_:f'{a:,.0f}'))
for s in ax.spines.values():s.set_visible(False)
fig.text(.035,.91,'Did paid reach improve the enterprise?',fontsize=19,color='#152b2b',weight='bold')
fig.text(.035,.84,'Difference from matched organic operation over simulated days 0–364',fontsize=11,color='#4e5c5c')
ax.text(1.08,1.025,'Extra orders',transform=ax.transAxes,ha='center',fontsize=8,color='#4e5c5c')
ax.text(1.33,1.025,'Second tranche',transform=ax.transAxes,ha='center',fontsize=8,color='#4e5c5c')
ax.set_xlabel('Additional profit after modeled tax (US dollars)',color='#3f4a4b',fontsize=10,labelpad=9)
fig.text(.035,.035,'Each row compares two separately funded simulated accounts. No observed demand or actual revenue.',fontsize=9,color='#4f5b5a')
fig.savefig(o.output,format='svg',metadata={'Date':None},facecolor=fig.get_facecolor());plt.close(fig)

# Normalize vector path formatting without changing the coordinates.
o.output.write_text('\n'.join(line.rstrip() for line in o.output.read_text().splitlines()) + '\n')
