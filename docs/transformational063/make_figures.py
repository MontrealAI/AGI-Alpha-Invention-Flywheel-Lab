from pathlib import Path
import argparse
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def build(technical, output):
    report = json.loads(Path(technical).read_text())
    rows = report['profiles']
    if len(rows) != 4 or any(not r['ordinary_tie'] for r in rows):
        raise ValueError('Figure requires the reported four-profile tied comparison')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.spines.top': False,
                         'axes.spines.right': False, 'pdf.fonttype': 42})
    colors = {'individual': '#8b93a7', 'conventional': '#7863ce', 'pooled': '#168c85'}
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.2), gridspec_kw={'width_ratios': [0.9, 1.5]})
    counts = [sum(r['controls'][arm]['feasible'] and r['controls'][arm].get('receipt', {}).get('accepted', False)
                  for r in rows) for arm in colors]
    axes[0].bar(range(3), counts, color=list(colors.values()), width=.58)
    axes[0].set_xticks(range(3), ['Isolated\nresource', 'Ordinary\npooling', 'AGI ALPHA\npooling'])
    axes[0].set_yticks(range(5))
    axes[0].set_ylabel('Accepted authored requests / 4')
    axes[0].set_ylim(0, 4.6)
    for x, count in enumerate(counts):
        axes[0].text(x, count + .12, str(count), ha='center', fontweight='bold')
    x = np.arange(len(rows))
    for arm, shift in [('conventional', -.17), ('pooled', .17)]:
        values = [r['controls'][arm]['participant_payment_microUSD'] / 1_000_000 for r in rows]
        axes[1].bar(x + shift, values, width=.3, label='Ordinary pooling' if arm == 'conventional' else 'AGI ALPHA pooling', color=colors[arm])
    axes[1].set_xticks(x, ['100 kWh', '110 kWh', '120 kWh', '65 + 65 kWh\nFresh successor'])
    axes[1].set_ylabel('Modeled participant compensation (US$)')
    axes[1].set_ylim(0, 30)
    for i, row in enumerate(rows):
        value = row['controls']['pooled']['participant_payment_microUSD'] / 1_000_000
        axes[1].text(i, value + .7, f'${value:.2f}', ha='center', fontsize=8)
    axes[1].legend(frameon=False, loc='upper left', fontsize=8)
    fig.suptitle('A formulation-relative threshold crossing, with an ordinary complete comparator that ties',
                 x=.01, ha='left', fontsize=10.3, fontweight='bold')
    fig.text(.01, .005, 'Executed software on synthetic profiles. Compensation is not enterprise revenue or complete delivery cost.', fontsize=8, color='#4e586d')
    fig.tight_layout(rect=[0, .05, 1, .93])
    fig.savefig(output / 'technical-results.pdf', bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--technical', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.technical, args.output)
