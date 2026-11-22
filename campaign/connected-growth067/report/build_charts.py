from pathlib import Path
import json
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
R=args.output;R.mkdir(parents=True,exist_ok=True);d=json.loads(args.data.read_text())
P='#6D3CE7'; T='#087F8C'; A='#BA6B18'; INK='#24213B'; MUT='#665F79'; GRID='#EAE6F1'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.labelcolor':MUT,'text.color':INK,'xtick.color':MUT,'ytick.color':MUT,'axes.edgecolor':GRID,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'axes.spines.bottom':False,'savefig.facecolor':'white'})
def base(title,sub):
 f,a=plt.subplots(figsize=(12,6.8)); f.subplots_adjust(left=.09,right=.90,top=.77,bottom=.17)
 f.text(.07,.94,title,fontsize=22,fontweight='bold',ha='left');f.text(.07,.875,sub,fontsize=11,color=MUT,ha='left')
 a.grid(axis='y',color=GRID,linewidth=.8);a.set_axisbelow(True);a.tick_params(length=0,pad=8)
 return f,a
def save(f,name,foot):
 f.text(.07,.045,foot,fontsize=10,color=MUT,ha='left')
 f.savefig(R/(name+'.svg'));f.savefig(R/(name+'.png'),dpi=140);plt.close(f)
f,a=base('Profit accumulated over five simulated years','One completed $100,000 control case • actual ledger events • no interpolation')
s=d['series'];q=d['rolling365'];x=[z['hour']/24 for z in s]
a.step(x,[z['profit_microUSD']/1e12 for z in s],where='post',color=P,lw=2.5,label='Cumulative modeled profit')
a.step([z['hour']/24 for z in q],[z['profit_microUSD']/1e12 for z in q],where='post',color=T,lw=2.4,label='Trailing 365-day modeled profit')
a.axhline(0,color=MUT,lw=.6);a.set(xlim=(0,1910),ylim=(-1.0,28),xlabel='Simulation day from opening',ylabel='USD millions');a.set_xticks([0,365,730,1095,1460,1825]);a.legend(loc='upper left',frameon=False,fontsize=11)
a.annotate('$25.262M',(1825,25.2618),xytext=(8,0),textcoords='offset points',color=P,fontweight='bold',fontsize=11)
a.annotate('$16.642M',(1825,16.6417),xytext=(8,-3),textcoords='offset points',color=T,fontweight='bold',fontsize=11)
save(f,'profit','Final annual window: simulation days [1460,1825). Full 365-day history; not an annualized exit rate. No $3B attainment.')
f,a=base('Cash is not all available to spend','Operating horizon only • protected cash remains on the account')
a.step(x,[z['cash_microUSD']/1e12 for z in s],where='post',color=P,lw=2.5,label='Cash')
a.step(x,[z['available_microUSD']/1e12 for z in s],where='post',color=T,lw=2.3,label='Available cash')
a.step(x,[z['protected_microUSD']/1e12 for z in s],where='post',color=A,lw=2.1,label='Cash less available')
a.set(xlim=(0,1910),ylim=(0,28),xlabel='Simulation day from opening',ylabel='USD millions');a.set_xticks([0,365,730,1095,1460,1825]);a.legend(loc='upper left',frameon=False)
for y,txt,c in [(25.361803,'$25.362M',P),(17.589246,'$17.589M',T),(7.772557,'$7.773M',A)]:a.annotate(txt,(1825,y),xytext=(8,0),textcoords='offset points',color=c,fontweight='bold')
save(f,'cash','Post-operating maturity drain is excluded. It releases restrictions, not revenue or profit; residual tail remains $76,511.40.')
f,a=base('Modeled volume and actual production are different','The population model does not turn repeated fixture executions into observed customer work')
labels=['Modeled chosen units','After modeled quality failures','Modeled collected units'];vals=[796591,796591-15826,765114]
a.barh([2,1,0],vals,color=[P,'#9878E9',T],height=.5)
a.set_yticks([2,1,0],labels);a.set_xlim(0,940000);a.set_ylim(-.65,2.65);a.grid(False);a.set_xticks([0,250000,500000,750000],['0','250k','500k','750k']);a.set_xlabel('Modeled merchant-month units')
f.subplots_adjust(left=.26,right=.94,top=.77,bottom=.38)
for i,v in zip([2,1,0],vals):a.text(v+14000,i,f'{v:,}',va='center',fontweight='bold')
f.text(.09,.23,'60',fontsize=29,color=P,fontweight='bold');f.text(.09,.175,'actual accepted production runs',fontsize=11)
f.text(.48,.23,'6',fontsize=29,color=T,fontweight='bold');f.text(.48,.175,'fixed synthetic input packets',fontsize=11)
f.text(.79,.23,'1',fontsize=29,color=A,fontweight='bold');f.text(.79,.175,'fixture grammar',fontsize=11)
save(f,'volume','Modeled attrition: 15,826 quality failures plus 15,651 uncollected units. Actual runs rotate the same six inputs; no live buyers.')
f,a=base('What the model charged','Five-year recognized expenses • exact total $20,635,476.891868')
labels={'resource':'Production resources','tax':'Recorded tax','acquisition':'Acquisition','processing':'Processing','onboarding':'Onboarding','capacity':'Capacity','maintenance':'Maintenance','setup':'Setup'}
items=sorted(d['costs_microUSD'].items(),key=lambda x:x[1],reverse=True)
a.barh(range(len(items)),[v/1e12 for k,v in items],color=[P,T,'#9878E9','#6DAAB2','#AF9DD9','#81A9AD','#BFAFDC','#BACDD0'],height=.58)
a.set_yticks(range(len(items)),[labels[k] for k,v in items]);a.invert_yaxis();a.set_xlim(0,9.4);a.set_xlabel('USD millions');a.grid(axis='x',color=GRID);a.grid(axis='y',visible=False)
f.subplots_adjust(left=.25,right=.94,top=.77,bottom=.17)
for i,(k,v) in enumerate(items):a.text(v/1e12+.10,i,f'$ {v/1e12:.3f}M',va='center',fontsize=11)
save(f,'costs','These are modeled deployment costs, not observed invoices. Actual whole-agent/model billing is unknown; reserves are not expenses.')
print('charts created')
