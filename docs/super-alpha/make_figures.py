from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
rows=[(n,20+12*n,30+7*n,13*n,12*n) for n in range(1,26)]
with (ROOT/'figures/thresholds.csv').open('w',newline='') as f:
    w=csv.writer(f,lineterminator="\n");w.writerow(['buyers','old_pooled_cost','new_pooled_cost','total_value','selected_price_revenue']);w.writerows(rows)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#aaa4b4','axes.labelcolor':'#151224','text.color':'#151224','xtick.color':'#615a70','ytick.color':'#615a70','pdf.fonttype':42})
fig,ax=plt.subplots(figsize=(7.1,3.65),layout='constrained')
x=[r[0] for r in rows]
ax.plot(x,[r[1] for r in rows],color='#69469D',lw=2,label='Old pooled cost')
ax.plot(x,[r[2] for r in rows],color='#167569',lw=2.2,label='New pooled cost')
ax.plot(x,[r[3] for r in rows],color='#A47A29',lw=1.8,ls='--',label='Total stipulated value')
ax.plot(x,[r[4] for r in rows],color='#615a70',lw=1.5,ls=':',label='Revenue at selected price 12')
ax.axvline(10,color='#b9b2c5',lw=1,ls=':')
for val,col in [(140,'#69469D'),(100,'#167569'),(130,'#A47A29')]:ax.scatter([10],[val],s=32,color=col,zorder=5)
ax.annotate('Cohort of 10\nNew cost 100 < value 130 < old cost 140',xy=(10,140),xytext=(1.4,280),fontsize=9.1,arrowprops={'arrowstyle':'-','color':'#aaa4b4'},color='#151224')
ax.set(xlabel='Accepted outputs / buyers in the authored cohort',ylabel='Abstract units',xlim=(1,25),ylim=(0,365))
ax.set_xticks([1,5,10,15,20,25]);ax.grid(axis='y',alpha=.12)
ax.legend(loc='lower right',frameon=True,facecolor='white',edgecolor='#ded9e5',fontsize=8.5)
fig.savefig(ROOT/'figures/thresholds.pdf',metadata={'Title':'SUPER ALPHA exact authored cost thresholds','Author':'Vincent Boucher','CreationDate':None,'ModDate':None})
plt.close(fig)
