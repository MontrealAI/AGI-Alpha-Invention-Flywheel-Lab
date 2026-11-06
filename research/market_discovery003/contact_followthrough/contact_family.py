"""GENESIS contact-family construction, research only.

Build a contact layout from an existing public, developer-authored request. Then
construct finer tiled layouts preserving its ideal Hertz load/friction law at a
rescaled stroke. Evaluate a normalized transport proxy and adverse checks.

No measured conductivity, physical validation, buyer order, or revenue is implied.
Classical Hertz, contact-constriction and similarity mechanisms are not new laws.
The transport interaction calculation freezes contact radii; it is NOT a coupled
elastic/thermal boundary-element solution. Its approximation error is unqualified.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.linalg import solve

PARENT_SHA = '9b8d6a25ce460f26a8adc30ce05686b150cb45ac'
SPEC_BLOB = 'd2b8b1b423edbac66ec901c8f035d6b933087a20'


@dataclass(frozen=True)
class Contact:
    family: str
    x_mm: float
    y_mm: float
    radius_mm: float
    height_mm: float
    modulus_MPa: float
    static_MPa: float
    dynamic_MPa: float


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def load_parent(path: Path) -> dict:
    raw = path.read_bytes()
    if git_blob(raw) != SPEC_BLOB:
        raise ValueError('The retained parent request is not the inspected source bytes')
    return json.loads(raw)


def construct_parent(s: dict) -> tuple[list[Contact], float, dict]:
    """Ordinary numerical MILP, reimplemented from the inspected parent model.

    This does not run or requalify the complete parent package. A tied optimum may
    have different site types from a prior run. No novelty or superior solver claim.
    """
    choices = [(f, h) for f in s['families'] for h in s['height_menu_mm']]
    matrix, lower, upper = [], [], []
    for state in s['states']:
        depth = np.array([max(0., state['indentation_mm'] - s['reference_height_mm'] + h)
                          for f, h in choices])
        radii = np.array([f['radius_mm'] for f, h in choices])
        area = np.pi * radii * depth
        force = 4/3 * np.array([f['modulus_MPa'] for f, h in choices]) * np.sqrt(radii) * depth**1.5
        fs = area * np.array([f['static_MPa'] for f, h in choices])
        fd = area * np.array([f['dynamic_MPa'] for f, h in choices])
        for key, coeff in (('normal_N', force), ('static_N', fs), ('dynamic_N', fd)):
            unit = max(1., state[key][1])
            matrix.append(coeff / unit)
            lower.append(state[key][0] / unit)
            upper.append(state[key][1] / unit)
        matrix.extend((fs-state['ratio'][0]*fd, fs-state['ratio'][1]*fd))
        lower.extend((0., -np.inf)); upper.extend((np.inf, 0.))
    matrix.append(np.ones(len(choices)))
    lower.append(1); upper.append(s['maximum_contacts'])
    fit = milp(np.ones(len(choices)), integrality=np.ones(len(choices)),
               bounds=Bounds(np.zeros(len(choices)), np.full(len(choices),s['maximum_contacts'])),
               constraints=LinearConstraint(np.array(matrix), lower, upper),
               options={'mip_rel_gap': 0.})
    if fit.status != 0 or fit.x is None or np.max(np.abs(fit.x-np.rint(fit.x))) > 1e-6:
        raise RuntimeError('Ordinary parent constructor did not return an integral optimum')
    pieces = [(f, h) for (f, h), n in zip(choices, np.rint(fit.x).astype(int)) for _ in range(n)]
    side = math.ceil(math.sqrt(len(pieces)))
    pitch = s['pitch_mm']
    contacts = [Contact(f['id'], (i % side + .5)*pitch, (i // side + .5)*pitch,
                        f['radius_mm'], h, f['modulus_MPa'], f['static_MPa'], f['dynamic_MPa'])
                for i,(f,h) in enumerate(pieces)]
    receipt = {'algorithm':'ordinary scipy.optimize.milp / HiGHS',
               'solver_status':int(fit.status), 'solver_message':fit.message,
               'site_count':len(contacts),
               'scope':'Numerical optimum in the supplied parent grammar, not a physical optimum'}
    return contacts, side*pitch, receipt


def tiled(contacts: list[Contact], width: float, factor: int) -> list[Contact]:
    if type(factor) is not int or factor < 1:
        raise ValueError('The linear refinement factor must be a positive integer')
    if not contacts or not math.isfinite(width) or width <= 0:
        raise ValueError('A positive footprint and a nonempty contact list are required')
    # The CLI limits its own declared demonstration, not the general research space.
    # The caller must provision memory/compute for count * factor**2 sites.
    f = factor
    return [replace(c, x_mm=(c.x_mm+tx*width)/f,
                    y_mm=(c.y_mm+ty*width)/f,
                    radius_mm=c.radius_mm/f, height_mm=c.height_mm/f)
            for tx in range(f) for ty in range(f) for c in contacts]


def mechanical(contacts: list[Contact], reference: float, stroke: float) -> dict:
    if not (math.isfinite(reference) and math.isfinite(stroke)) or reference <= 0 or stroke < 0:
        raise ValueError('Invalid displacement')
    a = np.array([[c.radius_mm,c.height_mm,c.modulus_MPa,c.static_MPa,c.dynamic_MPa] for c in contacts])
    if a.ndim != 2 or a.shape[1] != 5 or np.any(~np.isfinite(a)) or np.any(a <= 0):
        raise ValueError('Positive finite contact properties are required')
    depth = np.maximum(0., stroke-reference+a[:,1])
    cr = np.sqrt(a[:,0]*depth)
    area = np.pi * cr**2
    return {
        'normal_N':float(np.sum(4/3*a[:,2]*np.sqrt(a[:,0])*depth**1.5)),
        'static_N':float(area @ a[:,3]), 'dynamic_N':float(area @ a[:,4]),
        'area_mm2':float(area.sum()), 'normal_stiffness_N_per_mm':float(2*cr @ a[:,2]),
        'independent_transport_proxy_mm':float(2*cr.sum()),
        'contact_radii_mm':cr,
    }


def scalar_oracle(contacts: list[Contact], reference: float, stroke: float) -> dict:
    """Independent loop arrangement of the same declared constitutive model."""
    totals = [0.]*6
    for c in contacts:
        d = max(0., c.height_mm + stroke - reference)
        ar = math.sqrt(c.radius_mm * d)
        # F = (4 E / 3 R) a^3, using a instead of the vector evaluator's d^1.5.
        vals = [4*c.modulus_MPa*ar**3/(3*c.radius_mm),
                c.static_MPa*math.pi*ar**2, c.dynamic_MPa*math.pi*ar**2,
                math.pi*ar**2, 2*c.modulus_MPa*ar, 2*ar]
        for j,v in enumerate(vals): totals[j] += v
    keys = ['normal_N','static_N','dynamic_N','area_mm2',
            'normal_stiffness_N_per_mm','independent_transport_proxy_mm']
    return dict(zip(keys, totals))


def transport_screen(contacts: list[Contact], cr: np.ndarray, width: float) -> dict:
    """Frozen-geometry, normalized two-half-space POINT-KERNEL stress calculation.

    Mii=1/(2 ai), Mij=1/(pi rij). Conductivity is normalized, not measured.
    Diagonal: two identical half-space disk spreading resistances. Off-diagonal:
    paired surface point-source Green kernels. Finite-patch interaction and elastic
    redistribution are not solved; do not label this a converged BEM simulation.
    """
    active = cr > 0
    a = cr[active]
    xy = np.array([(c.x_mm,c.y_mm) for c in contacts])[active]
    if len(a) == 0:
        return {'status':'NO_ACTIVE_CONTACT','conductance_proxy_mm':0.}
    distance = np.linalg.norm(xy[:,None,:]-xy[None,:,:],axis=2)
    np.fill_diagonal(distance,np.inf)
    if np.any(distance <= a[:,None] + a[None,:]):
        raise ValueError('Contact disks overlap; point-screen not admitted')
    matrix = 1/(np.pi*distance)
    np.fill_diagonal(matrix,1/(2*a))
    flow = solve(matrix,np.ones(len(a)),assume_a='pos')
    residual = np.max(np.abs(matrix@flow-1))
    value = float(flow.sum())
    # Contact set lies in the square, itself within this fully contacting disk.
    # This ceiling belongs to the stated pure half-space constriction model only.
    circumscribed_disk_ceiling = math.sqrt(2)*width
    return {'status':'APPROXIMATE_TRANSPORT_SCREEN_NOT_PHYSICAL_VALIDATION',
            'conductance_proxy_mm':value,
            'linear_system_residual':float(residual),
            'positive_patch_flux':bool(np.min(flow)>0),
            'uniform_flux_conductance_lower_in_this_matrix_model_mm':float(len(a)**2/matrix.sum()),
            'circumscribed_disk_constriction_ceiling_mm':circumscribed_disk_ceiling,
            'below_circumscribed_disk_ceiling':bool(value<=circumscribed_disk_ceiling*(1+1e-12)),
            'nearest_spacing_over_sum_radii':float(np.min(distance/(a[:,None]+a[None,:]))),
            'scope':'Frozen radii; no elastic interaction, films, radiation, gas, or measured materials'}


def film_gain(factor: float, baseline_film_to_constriction_resistance: float) -> float:
    if not math.isfinite(factor) or factor < 1 or not math.isfinite(baseline_film_to_constriction_resistance) or baseline_film_to_constriction_resistance < 0:
        raise ValueError('Invalid refinement or film ratio')
    b = baseline_film_to_constriction_resistance
    return (1+b)/(1/factor+b)


def write_geometry(out: Path, contacts: list[Contact], width: float, factor: int) -> None:
    path = out/f'layout_x{factor}.csv'
    with path.open('w',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(asdict(contacts[0])))
        writer.writeheader(); writer.writerows(map(asdict,contacts))
    # Editable GEOMETRY ONLY. Different families need an actual multi-material
    # fabrication method, not just colors. This is not a manufacturing drawing.
    lines = ['// Research geometry only; no physical/material qualification.',
             '// mm. Family comments require distinct material realization.',
             '// Base is an unqualified support. Scaling its mechanical/thermal behavior is NOT modeled.',
             '$fn=32;', f'base=1; width={width:.12g};',
             'union() {', ' cube([width,width,base]);']
    for c in contacts:
        r,h = c.radius_mm,c.height_mm
        extent = 2*r
        lines += [f' // {c.family}',
                  f' translate([{c.x_mm:.12g},{c.y_mm:.12g},base]) intersection() {{',
                  f'  translate([0,0,{h-r:.12g}]) sphere(r={r:.12g});',
                  f'  translate([-{extent:.12g},-{extent:.12g},0]) cube([{2*extent:.12g},{2*extent:.12g},{h:.12g}]);',
                  ' }']
    lines += ['}']
    (out/f'layout_x{factor}.scad').write_text('\n'.join(lines)+'\n')


def run(spec: Path, out: Path) -> dict:
    if out.exists(): raise FileExistsError('Use a new evidence directory')
    t0=time.perf_counter(); out.mkdir(parents=True)
    s=load_parent(spec); original,width,solver=construct_parent(s)
    ref=s['reference_height_mm']
    # All these source examples were exposed before this reanalysis. Not fresh
    # physical confirmation, not independent buyer requirements.
    checked=[]
    for state in s['states']:
        v=scalar_oracle(original,ref,state['indentation_mm'])
        v['ratio']=v['static_N']/v['dynamic_N']
        ok=all(limits[0]-1e-8<=v[key]<=limits[1]+1e-8 for key,limits in state.items() if key!='indentation_mm')
        if not ok: raise RuntimeError('Independent scalar parent check failed')
        checked.append({'stroke_mm':state['indentation_mm'],'accepted_in_parent_nominal_model':ok,**v})
    grid=np.linspace(.001,.1,101)
    rows=[]; records=[]; max_eq=0.; max_oracle=0.
    for factor in (1,2,4):
        shape=tiled(original,width,factor)
        write_geometry(out,shape,width,factor)
        for stroke in grid:
            a=mechanical(original,ref,float(stroke))
            b=mechanical(shape,ref/factor,float(stroke)/factor)
            oracle=scalar_oracle(shape,ref/factor,float(stroke)/factor)
            for key in ('normal_N','static_N','dynamic_N','area_mm2'):
                err=abs(b[key]-a[key])/max(1.,abs(a[key])); max_eq=max(max_eq,err)
            for key,val in oracle.items():
                max_oracle=max(max_oracle,abs(val-b[key])/max(1.,abs(val)))
            rows.append({'factor':factor,'reference_stroke_mm':float(stroke),
                         'actual_stroke_mm':float(stroke)/factor,
                         **{k:v for k,v in b.items() if k!='contact_radii_mm'}})
        base=mechanical(original,ref,.1)
        v=mechanical(shape,ref/factor,.1/factor)
        transport=transport_screen(shape,v['contact_radii_mm'],width)
        records.append({'factor':factor,'site_count':len(shape),'footprint_side_mm':width,
                        'stroke_mm':.1/factor,
                        'normal_N':v['normal_N'],'static_N':v['static_N'],'dynamic_N':v['dynamic_N'],
                        'area_mm2':v['area_mm2'],
                        'ideal_constriction_gain':v['independent_transport_proxy_mm']/base['independent_transport_proxy_mm'],
                        'normal_stiffness_multiplier':v['normal_stiffness_N_per_mm']/base['normal_stiffness_N_per_mm'],
                        'transport_screen':transport,
                        'film_sensitivities':[{'assumed_baseline_film_to_spreading_ratio':f,
                                               'gain_in_independent_series_resistance_model':film_gain(factor,f)} for f in (0.,1.,9.)]})
    screen0=records[0]['transport_screen']['conductance_proxy_mm']
    for r in records:
        r['transport_screen']['gain_vs_parent_same_approximation']=r['transport_screen']['conductance_proxy_mm']/screen0
        r['transport_screen']['gain_with_assumed_90pct_baseline_film']=film_gain(r['transport_screen']['gain_vs_parent_same_approximation'],9.)
    with (out/'response_curves.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={
      'status':'CONSTRUCTED_IDEAL_MODEL_FAMILY_PHYSICAL_AND_MARKET_QUALIFICATION_OPEN',
      'parent_source_commit':PARENT_SHA,'parent_spec_git_blob':SPEC_BLOB,
      'constructor':solver,'nominal_parent_checks':checked,
      'max_mechanical_preservation_error_divided_by_max_1_abs_reference':max_eq,
      'max_independent_scalar_vector_error_divided_by_max_1_abs_reference':max_oracle,
      'sampled_strokes_per_variant':len(grid),'variants':records,
      'comparison':'This implementation IS a conventional similarity construction using ordinary optimization. No separate comparative discovery campaign was performed and no algorithmic superiority is claimed.',
      'boundaries':[
        'A newly generated geometry family, not a fabricated or validated material.',
        'Preserves model friction versus load only with rescaled indentation. Does not preserve stroke, stiffness, wear, adhesion or manufacturability.',
        'Unknown conductivities: normalized conductance is a geometric proxy, not a measured W/K or A/V performance.',
        'Do not substitute metal coefficients into calibrated rubber-family assumptions without independent qualification.',
        'Thermal point-interaction screen freezes independent-Hertz contact radii; not a coupled elastic/thermal solution or rigorous error bound.',
        'Original calibration and mixed-family transfer failures remain unresolved.',
        'The film fractions are authored sensitivity cases, not measured contamination.',
        'No identified buyers, accepted terms, investments, payments, or actual revenue.',
        'No model-version ablation or improved-inventor claim.'
      ],
      'python':platform.python_version(),'numpy':np.__version__,
      'scipy':__import__('scipy').__version__, 'elapsed_seconds':time.perf_counter()-t0,
      'protocol':'Exploratory reanalysis of already exposed public source; no preregistered confirmation claim'
    }
    (out/'RESULTS.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'parent_contacts':len(original),'max_invariance_error':max_eq,
                     'variants':[{'factor':r['factor'],'count':r['site_count'],
                                  'ideal_gain':r['ideal_constriction_gain'],
                                  'transport_screen_gain':r['transport_screen']['gain_vs_parent_same_approximation'],
                                  'film_90pct_gain':r['film_sensitivities'][-1]['gain_in_independent_series_resistance_model']} for r in records]},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,default=Path(__file__).with_name('parent_spec.json'))
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.spec,args.out)
