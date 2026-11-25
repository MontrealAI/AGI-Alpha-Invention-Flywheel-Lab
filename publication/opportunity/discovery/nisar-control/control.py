"""Independently replay the public NISAR/OPERA catalog planning decision."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from time import monotonic_ns

from capture import COLLECTIONS, SITES, utc_now

EARLIEST = datetime(2026, 10, 21, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2026, 11, 25, tzinfo=timezone.utc)


def in_window(stamp):
    return EARLIEST <= datetime.fromisoformat(stamp) < END_EXCLUSIVE


def open_capture(name, receipt):
    raw = (Path('raw') / (name + '.json')).read_bytes()
    if sha256(raw).hexdigest() != receipt['sha256'] or len(raw) != receipt['bytes']:
        raise ValueError(f'Source receipt mismatch: {name}')
    document = json.loads(raw)
    if document['hits'] != receipt['hits'] or len(document['items']) != receipt['hits']:
        raise ValueError(f'Incomplete CMR denominator: {name}')
    return document['items']


def native_record(item, family):
    meta, umm = item['meta'], item['umm']
    attributes = {att['Name']: att['Values'][0] for att in umm['AdditionalAttributes']}
    ref = attributes['REFERENCE_ZERO_DOPPLER_START_TIME']
    sec = attributes['SECONDARY_ZERO_DOPPLER_START_TIME']
    granule = umm['GranuleUR']
    assert meta['collection-concept-id'] == COLLECTIONS[family]
    assert datetime.fromisoformat(ref) < datetime.fromisoformat(sec)
    lineage = {}
    source_ids = umm.get('InputGranules', [])
    if family == 'nisar':
        assert attributes['PROCESSING_LEVEL'] == 'L2' and attributes['PRODUCT_TYPE'] == 'GUNW'
        assert len(source_ids) == 2 and len(set(source_ids)) == 2
        for source in source_ids:
            starts = re.findall(r'_(\d{8}T\d{6})(?=_)', source)
            assert len(starts) == 2 and source.startswith('NISAR_L1_PR_RSLC_') and source.endswith('.h5')
            stamp = datetime.fromisoformat(starts[0] + 'Z')
            if stamp == datetime.fromisoformat(ref):
                assert 'ref_source' not in lineage
                lineage['ref_source'] = source
            elif stamp == datetime.fromisoformat(sec):
                assert 'sec_source' not in lineage
                lineage['sec_source'] = source
        assert set(lineage) == {'ref_source', 'sec_source'}
    else:
        assert attributes['PROCESSING_TYPE'] == 'DISP-S1'
    provider_dates = {row['Type']: row['Date'] for row in umm['ProviderDates']}
    return {'concept': meta['concept-id'], 'product': granule, 'stack': attributes['STACK_ID'],
            'version': attributes['PRODUCT_VERSION'], 'pge': umm['PGEVersionClass']['PGEVersion'],
            'frequency': attributes.get('FREQUENCIES'),
            'polarization': attributes.get('FREQUENCY_A_POLARIZATION', attributes.get('POLARIZATION')),
            'bandwidth': attributes.get('FREQUENCY_A_RANGE_BANDWIDTH'),
            'full_frame': attributes.get('FULL_FRAME') == 'TRUE', 'ref': ref, 'sec': sec,
            'reference_before_window': datetime.fromisoformat(ref) < EARLIEST,
            'both_acquisition_starts_in_window': in_window(ref) and in_window(sec),
            'processing_metadata_revision': meta['revision-date'], 'catalog_insert': provider_dates['Insert'],
            'exact_input_granule_count': len(source_ids), **lineage}


def linked_pairs(records):
    """Find a minimum useful linked chain of two products and three exact L1 acquisitions."""
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE edges (concept TEXT PRIMARY KEY, stack TEXT, version TEXT, pge TEXT, '
                   'frequency TEXT, polarization TEXT, bandwidth TEXT, ref_source TEXT, sec_source TEXT, ref TEXT, sec TEXT)')
        keys = ('concept', 'stack', 'version', 'pge', 'frequency', 'polarization', 'bandwidth',
                'ref_source', 'sec_source', 'ref', 'sec')
        db.executemany('INSERT INTO edges VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            [tuple(record[key] for key in keys) for record in records
             if record['full_frame'] and record['both_acquisition_starts_in_window']])
        result = db.execute('''
            SELECT lhs.stack, lhs.version, lhs.pge, lhs.frequency, lhs.polarization, lhs.bandwidth,
                   lhs.concept, rhs.concept, lhs.ref, lhs.sec, rhs.sec,
                   lhs.ref_source, lhs.sec_source, rhs.sec_source
            FROM edges AS lhs JOIN edges AS rhs
              ON lhs.sec_source = rhs.ref_source AND lhs.sec = rhs.ref
              AND lhs.stack = rhs.stack AND lhs.version = rhs.version AND lhs.pge = rhs.pge
              AND lhs.frequency = rhs.frequency AND lhs.polarization = rhs.polarization
              AND lhs.bandwidth = rhs.bandwidth
            WHERE lhs.concept != rhs.concept AND lhs.ref < lhs.sec AND lhs.sec < rhs.sec
            ORDER BY lhs.stack, lhs.ref
        ''').fetchall()
        if {row[7] for row in result} & {row[6] for row in result}:
            raise ValueError('The pair result needs concatenation for longer chains')
    return [{'stack': stack, 'version': version, 'pge': pge, 'frequency': frequency,
             'polarization': pol, 'bandwidth_mhz': bw, 'product_concepts': [left, right],
             'acquisition_starts': [start, middle, end], 'exact_input_granules': [ref, shared, sec]}
            for stack, version, pge, frequency, pol, bw, left, right, start, middle, end, ref, shared, sec in result]


def main():
    capture_raw = Path('CAPTURES.json').read_bytes()
    captures = json.loads(capture_raw)
    collection_raw = Path('COLLECTION-ACCESS.json').read_bytes()
    supplemental = json.loads(collection_raw)
    for family,data in supplemental['collection_metadata'].items():
        items=open_capture(family+'-collection',data)
        assert items[0]['umm']['EntryTitle']==data['entry_title'] and items[0]['meta']['concept-id']==COLLECTIONS[family]
        assert 'validated' in data['entry_title'].casefold()
    began_at = utc_now()
    began_ns = monotonic_ns()
    sites = {}
    for site, point in SITES.items():
        rows = {}
        for family in COLLECTIONS:
            name = f'{site}-{family}'
            rows[family] = [native_record(item, family) for item in open_capture(name, captures[name])]
            assert len({record['concept'] for record in rows[family]}) == len(rows[family])
        reports = {}
        for family, records in rows.items():
            reports[family] = {'query_hits': len(records),
                'reference_before_window': sum(row['reference_before_window'] for row in records),
                'both_acquisition_starts_in_window': sum(row['both_acquisition_starts_in_window'] for row in records),
                'secondary_acquisition_in_window': sum(in_window(row['sec']) for row in records),
                'latest_revision_by_cutoff': sum(datetime.fromisoformat(row['processing_metadata_revision'])<END_EXCLUSIVE for row in records),
                'rows': records}
        reports['nisar']['full_frame_by_metadata'] = sum(row['full_frame'] for row in rows['nisar'])
        reports['nisar']['two_product_full_frame_within_window_chains'] = linked_pairs(rows['nisar'])
        reports['opera']['exact_input_granule_links_exposed'] = sum(row['exact_input_granule_count'] for row in rows['opera'])
        reports['opera']['qualified_same_window_chain'] = False
        sites[site] = {'point_lon_lat': point, **reports}
    end_at = utc_now()
    elapsed_ns = monotonic_ns() - began_ns
    start_at = Path('READY-AT.txt').read_text().strip()
    overlap = {row['concept'] for row in sites['montreal']['nisar']['rows']} & {row['concept'] for row in sites['quebec-city']['nisar']['rows']}
    result = {'schema':'frontier/nisar-ordinary-source-control-v1','ready_at':start_at,'frozen_at':end_at,
              'utc_window_inclusive_days':['2026-10-21','2026-11-24'],'sites':sites,
              'shared_nisar_product_concepts_between_sites':sorted(overlap),'primary_capture_receipt_sha256':sha256(capture_raw).hexdigest(),
              'collection_and_access_receipt_sha256':sha256(collection_raw).hexdigest(),
              'analysis_ns':elapsed_ns,'whole_work_to_frozen_seconds':(datetime.fromisoformat(end_at)-datetime.fromisoformat(start_at)).total_seconds(),
              'catalog_requests':len(captures),'catalog_bytes':sum(row['bytes'] for row in captures.values()),
              'catalog_request_elapsed_ns':sum(row['elapsed_ns'] for row in captures.values()),
              'supplemental_requests':3,'supplemental_catalog_bytes':sum(row['bytes'] for row in supplemental['collection_metadata'].values()),
              'scope':'CMR point intersection and native catalog product/input granule metadata. Two in-window L2 GUNW products with full frame flags, exactly equal shared L1 RSLC identity and common stack, product/PGE version, polarization and frequency constitute a planning candidate only.',
              'decision':'NISAR exact-input chains provide an actionable retrieval shortlist for both points. OPERA supplied one exact-window overlap product per point. Evaluate OPERA in its usual wider historical context for real site work.',
              'data_access':supplemental['representative_hdf5_access'],
              'verified_site_displacement_or_safety':False,'observed_operator_time':None,'provider_cost_accounting':None,
              'source_documentation':['https://nisar-docs.asf.alaska.edu/gunw/','https://nisar-docs.asf.alaska.edu/access-overview/',
                                      'https://doi.org/10.5067/SNWG/OPL3DISPS1-V1']}
    encoded=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode()
    with Path('RESULTS.json').open('xb') as stream: stream.write(encoded)
    print(sha256(encoded).hexdigest())
    for site, rows in sites.items():
        print(site, rows['nisar']['query_hits'], rows['nisar']['reference_before_window'],
              rows['nisar']['both_acquisition_starts_in_window'],
              [chain['stack'] for chain in rows['nisar']['two_product_full_frame_within_window_chains']], rows['opera']['query_hits'])


if __name__=='__main__':
    main()
