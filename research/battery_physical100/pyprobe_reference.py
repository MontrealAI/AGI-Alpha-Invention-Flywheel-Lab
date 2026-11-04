"""Direct, unmodified PyProBE reference on accepted contiguous episodes.

Selection/quality rules belong to the separately reviewed measurement protocol.
This adapter establishes numerical agreement, not independent physical truth,
forecast superiority, or a fresh implementation of PyProBE's algorithm.
"""
from importlib.metadata import version
import math

EXPECTED_VERSION = '2.6.1'

def compare_episode(episode):
    """Rows are (test_time_s, voltage_V, current_A, cycle, step, step_capacity_Ah)."""
    import polars as pl
    from pyprobe.rawdata import RawData
    installed = version('PyProBE-Data')
    if installed != EXPECTED_VERSION:
        raise ValueError(f'Expected PyProBE-Data {EXPECTED_VERSION}; found {installed}')
    if len(episode) < 3:
        raise ValueError('At least three measured rows required')
    if any(len(r) != 6 or any(not math.isfinite(float(x)) for x in r) for r in episode):
        raise ValueError('Nonfinite or malformed measured episode')
    identity = episode[0][3:5]
    if any(r[3:5] != identity for r in episode):
        raise ValueError('Do not combine different cycle/step episodes')
    if any(b[0] < a[0] for a,b in zip(episode,episode[1:])):
        raise ValueError('Reference requires nondecreasing measured time')
    # BDF reports positive step discharge accumulation; PyProBE uses signed
    # net charge. The additive origin is irrelevant to its range calculation.
    frame = pl.DataFrame({
        'Time [s]':[float(r[0]) for r in episode],
        'Step':[int(r[4]) for r in episode],
        'Event':[0]*len(episode),
        'Current [A]':[float(r[2]) for r in episode],
        'Voltage [V]':[float(r[1]) for r in episode],
        'Capacity [Ah]':[-float(r[5]) for r in episode],
    })
    raw = RawData(lf=frame.lazy(), info={'source':'measured BDF contiguous discharge episode'})
    reference = float(raw.capacity)
    reported_delta = float(episode[-1][5]-episode[0][5])
    integral = sum(-0.5*(a[2]+b[2])*(b[0]-a[0])/3600 for a,b in zip(episode,episode[1:]))
    return {'library':'PyProBE-Data','version':installed,
            'method':'pyprobe.rawdata.RawData.capacity',
            'scope':'same accepted episode; supplied cycler capacity, not independent sensor truth',
            'cycle':int(episode[0][3]), 'step':int(episode[0][4]),
            'rows':len(episode),
            'duplicate_timestamps':sum(a[0]==b[0] for a,b in zip(episode,episode[1:])),
            'positive_current_rows':sum(r[2]>0 for r in episode),
            'capacity_decrease_count':sum(b[5]<a[5] for a,b in zip(episode,episode[1:])),
            'pyprobe_delta_ah':reference,
            'reported_delta_ah':reported_delta,
            'reported_terminal_ah':float(episode[-1][5]),
            'unobserved_initial_capacity_ah':float(episode[0][5]),
            'current_integral_delta_ah':integral,
            'absolute_delta_disagreement_ah':abs(reference-reported_delta)}


def main():
    """Direct conventional reference path, sharing only declared episode selection."""
    import argparse,json
    from pathlib import Path
    from .measurement import episodes,extract,inspect_episode,read_prefix
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--rated-capacity-ah',type=float,required=True)
    parser.add_argument('--cutoff',type=int,default=100)
    args=parser.parse_args()
    measured=extract(args.input,args.rated_capacity_ah,args.cutoff)
    checks=[]
    for ep in episodes(read_prefix(args.input,args.cutoff)):
        if ep[0][3] not in measured.cycles:continue
        candidate=inspect_episode(ep,args.rated_capacity_ah)
        if candidate and not candidate['errors']:checks.append(compare_episode(ep))
    print(json.dumps({'reference':'PyProBE-Data 2.6.1 RawData.capacity','checks':checks,'selection_flags':measured.flags},indent=2,allow_nan=False))

if __name__=='__main__':main()
