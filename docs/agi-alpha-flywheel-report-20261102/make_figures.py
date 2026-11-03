import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#b5adca','axes.labelcolor':'#282038','text.color':'#282038','xtick.color':'#51485d','ytick.color':'#51485d'})
def main():
    d=json.loads((HERE/'evidence/observations.json').read_text());out=HERE/'figures';out.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(7.05,2.85),gridspec_kw={'width_ratios':[1,1.05]})
    order=['fresh','frozen_first','accumulating','conventional'];labels=['Fresh','First retained','Accumulating','Conventional'];vals=[d['foundry']['summary']['all'][x]['arithmetic'] for x in order]
    ax=axes[0];bars=ax.barh(range(4),vals,color=['#d4cede','#bda6d5','#7552a3','#237b78']);ax.set_yticks(range(4),labels);ax.invert_yaxis();ax.set_xlim(0,64000);ax.set_xlabel('Declared scalar arithmetic operations')
    for bar,value in zip(bars,vals):ax.text(value+700,bar.get_y()+bar.get_height()/2,f'{value:,}',va='center',fontsize=8)
    ax.set_title('A · Same 36 requests per arm',loc='left',fontweight='bold');ax.grid(axis='x',alpha=.13);ax.set_axisbelow(True)
    ax=axes[1];cats=['PoH primary','Equal content','Linear ridge','Kernel exploit','Hash mean'];hits=[14,14,15,15,5.53125];ax.barh(range(5),hits,color=['#7552a3','#bda6d5','#237b78','#237b78','#d4cede']);ax.set_yticks(range(5),cats);ax.invert_yaxis();ax.set_xlim(0,18);ax.set_xlabel('Targets found in 23 additional queries');ax.set_title('B · NEXT072: same exposed panel',loc='left',fontweight='bold')
    for i,v in enumerate(hits):ax.text(v+.25,i,f'{v:g}',va='center',fontsize=8)
    ax.grid(axis='x',alpha=.13);ax.set_axisbelow(True);fig.tight_layout(w_pad=2);fig.savefig(out/'comparators.pdf',bbox_inches='tight');plt.close(fig)
    rows=sorted(d['r2']['cases'],key=lambda x:(x['route'],x['case_id']));palette={'arrangement':'#71519a','complementarity':'#267d7a','foundry':'#a97e3a','interface':'#7b9cad','purpose':'#b087a4'}
    fig,ax=plt.subplots(figsize=(7.05,2.7));ys=[x['final_365_day_company_profit_microUSD']/1e6 for x in rows];ax.bar(range(110),ys,width=.9,color=[palette[x['route']] for x in rows]);ax.axhline(0,color='#282038',lw=.7);ax.set_ylim(-39500,3500);ax.set_xlim(-1,110);ax.set_ylabel('Final trailing-365-day profit, US$');ax.set_xticks([10.5,32.5,54.5,76.5,98.5],['Arrangement','Complementarity','Foundry','Interface','Purpose']);ax.tick_params(axis='x',labelsize=8);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True);ax.text(.99,.06,'110 separately seeded authored accounts\nBest final year: $0 · 23 uncovered accounts',ha='right',va='bottom',transform=ax.transAxes,fontsize=8.5,bbox={'facecolor':'white','edgecolor':'#d4cede','pad':5});fig.tight_layout();fig.savefig(out/'financial_screen.pdf',bbox_inches='tight');plt.close(fig)
    with (out/'chart_data.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['study','case_or_arm','value','unit'])
        for k,v in zip(order,vals):w.writerow(['foundry',k,v,'declared scalar arithmetic operations'])
        for k,v in zip(cats,hits):w.writerow(['NEXT072',k,v,'targets found; hash row is fixed-control mean'])
        for r in rows:w.writerow(['R2',r['case_id'],r['final_365_day_company_profit_microUSD'],'integer microUSD'])
if __name__=='__main__':main()
