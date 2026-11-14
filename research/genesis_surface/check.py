"""Scalar checking separate from the optimizer; model validity is not assumed.

No import of the producer, NumPy, SciPy or source-generated analysis. Sensitivity
boxes are explicitly not simultaneous confidence or physical transfer evidence.
"""
from __future__ import annotations
import hashlib
import json
import math


def check(spec, candidate):
    expected = hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if candidate.get('request_sha256') != expected or candidate.get('schema') != 'genesis/surface-design/v1':
        raise ValueError('candidate/request binding')
    if candidate.get('physical_qualification') is not False or candidate.get('commercial_qualification') is not False:
        raise ValueError('unsupported qualification')
    if candidate.get('status') not in ('CANDIDATE_REQUIRES_CHECK','INFEASIBLE_IN_DECLARED_MODEL','UNRESOLVED'):
        raise ValueError('candidate status')
    if candidate['status'] != 'CANDIDATE_REQUIRES_CHECK':
        if candidate.get('contacts'):
            raise ValueError('failed candidate has geometry')
        return {'accepted':False, 'status':candidate['status'], 'physical_qualified':False,
                'commercial_qualified':False, 'rows':[]}
    lookup = {f['id']:f for f in spec['families']}
    contacts = candidate.get('contacts')
    if not isinstance(contacts, list) or not contacts:
        raise ValueError('nonempty geometry required')
    seen = set(); total = 0
    for x in contacts:
        if not isinstance(x,dict) or set(x) != {'family','height_mm','count'}:
            raise ValueError('exact site fields')
        if type(x['count']) is not int or x['count'] < 1 or x['family'] not in lookup:
            raise ValueError('site count/family')
        if type(x['height_mm']) not in (int,float) or x['height_mm'] not in spec['height_menu_mm']:
            raise ValueError('site height')
        key = (x['family'],x['height_mm'])
        if key in seen: raise ValueError('duplicate site type')
        if candidate['family_restriction'] is not None and x['family'] != candidate['family_restriction']:
            raise ValueError('family restriction violated')
        seen.add(key); total += x['count']
    if total > spec['maximum_contacts']:
        raise ValueError('site capacity exceeded')
    rows=[]; feasible=True; robust=True
    for target in spec['states']:
        normal=static=dynamic=0.; slo=shi=dlo=dhi=0.
        for x in contacts:
            f=lookup[x['family']]
            penetration=target['indentation_mm']+x['height_mm']-spec['reference_height_mm']
            if penetration <= 0: continue
            # Expanded scalar formulas, independent of the optimizer's matrix.
            unit_area = math.pi * f['radius_mm'] * penetration
            normal += x['count'] * 4 * f['modulus_MPa'] * (f['radius_mm']*penetration**3)**.5 / 3
            static += x['count'] * unit_area * f['static_MPa']
            dynamic += x['count'] * unit_area * f['dynamic_MPa']
            slo += x['count']*unit_area*f['static_range_MPa'][0]
            shi += x['count']*unit_area*f['static_range_MPa'][1]
            dlo += x['count']*unit_area*f['dynamic_range_MPa'][0]
            dhi += x['count']*unit_area*f['dynamic_range_MPa'][1]
        ratio = static/dynamic if dynamic > 0 else None
        values={'normal_N':normal,'static_N':static,'dynamic_N':dynamic,'ratio':ratio}
        violations=[]
        for key,value in values.items():
            lo,hi=target[key]; tol=1e-7*max(1.,abs(lo),abs(hi))
            if value is None or not math.isfinite(value) or value < lo-tol or value > hi+tol:
                violations.append(key)
        intervals={'static_N':[slo,shi], 'dynamic_N':[dlo,dhi],
                   'ratio':[slo/dhi,shi/dlo] if dlo > 0 else [None,None]}
        interval_pass=all(v[0] is not None and v[0]>=target[k][0]-1e-7 and v[1]<=target[k][1]+1e-7
                          for k,v in intervals.items())
        feasible &= not violations; robust &= interval_pass
        rows.append({'indentation_mm':target['indentation_mm'], **values,
                     'violations':violations,'sensitivity':intervals,'sensitivity_pass':interval_pass})
    return {'accepted':feasible,'status':'NOMINAL_MODEL_PASS' if feasible else 'REJECTED_NUMERICALLY',
            'contacts':total,'rows':rows,'declared_box_sensitivity_pass':robust,
            'physical_qualified':False,'commercial_qualified':False,
            'scope':'Independent numerical reconstruction only. Parameter boxes are sensitivity assumptions, not a calibrated joint confidence region.'}


def homogeneous_obstruction(spec):
    """A constant Fs/Fd cannot satisfy disjoint required ratio intervals."""
    lo=max(s['ratio'][0] for s in spec['states'])
    hi=min(s['ratio'][1] for s in spec['states'])
    return {'constant_ratio_required_by_model':True,'intersection':[lo,hi],
            'infeasible_for_every_single_constant_ratio_family':lo>hi,
            'assumptions':'Positive dynamic force; common fixed static/dynamic shear coefficients; area superposition.'}
