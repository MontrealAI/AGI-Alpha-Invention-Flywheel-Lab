"""Render the complete error denominator and deterministic image examples."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


def main():
    p=argparse.ArgumentParser();p.add_argument('--confirmation',type=Path,required=True)
    p.add_argument('--images',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=json.loads(a.confirmation.read_text())
    s=json.loads((a.images/'images.json').read_text());im=np.load(a.images/'images.npz')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titleweight':'bold'})
    bg='#f7f6f1';ink='#172b35';blue='#286e91';orange='#ec9c37'
    fig=plt.figure(figsize=(13,12),facecolor=bg)
    fig.text(.06,.955,'A smaller measurement protocol. A real-data test.',size=23,weight='bold',color=ink)
    fig.text(.06,.925,'KTC2023 laboratory tank measurements | 21 held-out targets | Offline replay',size=12,color='#56666c')
    for x,value,label in [(.06,'48 / 76','Current patterns per target'),(.39,'36.8%','Fewer acquired patterns'),(.72,'3.74%','Median inclusion-signal error')]:
        fig.text(x,.87,value,size=30,weight='bold',color=blue)
        fig.text(x,.843,label,size=11,color=ink)
    grid=fig.add_gridspec(3,3,left=.08,right=.94,bottom=.36,top=.80,wspace=.20,hspace=.18)
    ordered=sorted(s['rows'],key=lambda x:x['score_change'])
    selected=[ordered[0],ordered[len(ordered)//2],ordered[-1]]
    cmap=ListedColormap(['#eef0e9','#6daac4','#efb24d'])
    for row,item in enumerate(selected):
        target=Path(item['target']);level=target.parent.name.replace('level','');number=target.stem.replace('data','')
        for col,key in enumerate(['truth','full','recovered']):
            ax=fig.add_subplot(grid[row,col]);ax.set_facecolor(bg)
            ax.imshow(im[f'{level}_{number}_{key}'],cmap=cmap,vmin=0,vmax=2,interpolation='nearest')
            ax.set_xticks([]);ax.set_yticks([])
            for spine in ax.spines.values():spine.set_visible(False)
            if row==0:ax.set_title(['Published ground truth','Full acquisition: 76','Compiled protocol: 48'][col],pad=10,size=11,color=ink)
            if col==0:ax.set_ylabel(['Largest score loss','Median score change','Largest score gain'][row]+'\n'+f'Target {level}-{number}',size=10,color=ink)
            if col>0:ax.text(.5,-.04,f"Score {item['full_score' if col==1 else 'recovered_score']:.4f}",transform=ax.transAxes,ha='center',va='top',size=9,color=ink)
    ax=fig.add_axes([.09,.155,.84,.145],facecolor=bg)
    labels=[Path(row['target']).parent.name.replace('level','')+'-'+Path(row['target']).stem.replace('data','') for row in r['rows']]
    errors=np.array([row['arms']['physics_plus_one']['contrast_relative_rms']*100 for row in r['rows']])
    ax.bar(np.arange(21),errors,color=[blue if e<=5 else orange for e in errors],width=.68)
    ax.axhline(5,color='#9b5927',linestyle='--',linewidth=1)
    ax.set_xticks(np.arange(21),labels,fontsize=8);ax.set_ylim(0,7)
    ax.set_ylabel('Signal error (%)',color=ink);ax.set_title('Every evaluation target is shown',loc='left',size=11,color=ink)
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.text(.06,.10,'Image check: mean score 0.60196 -> 0.60202; at most 0.83% of pixels changed.',size=11,color=ink)
    fig.text(.06,.073,'Registered goal unmet: 48 patterns exceeds the 40-pattern target. Conventional same-algebra control ties.',size=10,color='#9b5927')
    fig.text(.06,.048,'Same illustrative inverse for both inputs. No claim of faster hardware, industrial acceptance, new physics or profit.',size=9,color='#56666c')
    fig.text(.06,.027,'Data: Rasanen et al., KTC2023 v3, doi:10.5281/zenodo.10986692 (CC BY 4.0). New analysis: AGI ALPHA Flywheel.',size=8,color='#56666c')
    fig.savefig(a.output,dpi=180,facecolor=bg)

if __name__=='__main__':main()
