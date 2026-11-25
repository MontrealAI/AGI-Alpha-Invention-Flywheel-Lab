"""Bind public remote-sensing catalog claims to acquisition lineage without downloading imagery."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from time import monotonic
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


CMR = 'https://cmr.earthdata.nasa.gov/search/granules.umm_json'
ASF = 'https://api.daac.asf.alaska.edu/services/search/param'
VALIDATED = 'C3622247503-ASF'
OPERA_SENTINEL = 'C3294057315-ASF'
START, END = '2026-10-21T00:00:00Z', '2026-11-24T23:59:59Z'
POINTS = {'montreal': ('-73.5673', '45.5017'), 'quebec-city': ('-71.2080', '46.8139')}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def fetch(url, params, file):
    url = url + '?' + urlencode(params)
    started = datetime.now(timezone.utc).isoformat()
    wall = monotonic()
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Frontier-Omega-catalog-evaluation'})
    with build_opener(NoRedirect()).open(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError(f'Unexpected HTTP availability: {response.status}')
        raw = response.read(2_000_001)
        headers = {key: response.headers.get(key) for key in ('Date', 'CMR-Request-Id')}
    if len(raw) > 2_000_000:
        raise ValueError('Metadata exceeds the prospectively scoped retrieval depth')
    file.write_bytes(raw)
    return json.loads(raw), {'url': url, 'http': 200, 'headers': headers, 'started_utc': started,
                             'bytes': len(raw), 'wall_seconds': round(monotonic() - wall, 3),
                             'sha256': sha256(raw).hexdigest()}


def cmr(collection, point, file):
    data, receipt = fetch(CMR, {'collection_concept_id': collection, 'point': ','.join(point),
                                'temporal': START + ',' + END, 'page_size': 100}, file)
    items = data['items']
    if data['hits'] != len(items) or any(item['meta']['collection-concept-id'] != collection for item in items):
        raise ValueError('Unexpected collection or incomplete CMR page')
    return items, receipt


def asf(point, file):
    data, receipt = fetch(ASF, {'platform': 'NISAR',
                                'intersectsWith': f'POINT({point[0]} {point[1]})', 'start': START, 'end': END,
                                'output': 'json', 'maxResults': 100}, file)
    if len(data) != 1 or len(data[0]) >= 100:
        raise ValueError('Unexpected or truncated ASF GUNW response')
    rows = [row for row in data[0] if row['processingLevel'] == 'GUNW' and
            '_P05036_' in row['granuleName']]
    return rows, receipt


def describe(item):
    metadata = item['umm']
    attr = {entry['Name']: entry['Values'][0] for entry in metadata['AdditionalAttributes']}
    archive = metadata['DataGranule']
    images = [entry for entry in archive['ArchiveAndDistributionInformation'] if entry['Format'] == 'HDF5' and
              entry['Name'] == metadata['GranuleUR'] + '.h5']
    image, = images
    reference = attr['REFERENCE_ZERO_DOPPLER_START_TIME']
    secondary = attr['SECONDARY_ZERO_DOPPLER_START_TIME']
    sources = {}
    for granule in metadata['InputGranules']:
        starts = re.findall(r'_(\d{8}T\d{6})(?=_)', granule)
        if len(starts) != 2 or not granule.startswith('NISAR_L1_PR_RSLC_') or not granule.endswith('.h5'):
            raise ValueError('The product did not supply an exact L1 input identity')
        stamp = datetime.fromisoformat(starts[0] + 'Z')
        if stamp in sources:
            raise ValueError('Conflicting L1 input identities')
        sources[stamp] = granule
    ref_start, sec_start = map(datetime.fromisoformat, (reference, secondary))
    if set(sources) != {ref_start, sec_start} or ref_start >= sec_start:
        raise ValueError('The product inputs do not identify its reference and secondary acquisitions')
    return {'granule': metadata['GranuleUR'], 'concept': item['meta']['concept-id'],
            'revision': item['meta']['revision-id'], 'catalog_revision_utc': item['meta']['revision-date'],
            'provider_insert_utc': next((p['Date'] for p in metadata['ProviderDates'] if p['Type'] == 'Insert'), None),
            'production_utc': archive['ProductionDateTime'], 'stack': attr['STACK_ID'],
            'full_frame': attr['FULL_FRAME'] == 'TRUE', 'reference_utc': reference,
            'secondary_utc': secondary, 'input_granules': [sources[ref_start], sources[sec_start]],
            'frequency': attr['FREQUENCIES'], 'polarization': attr['FREQUENCY_A_POLARIZATION'],
            'bandwidth': attr['FREQUENCY_A_RANGE_BANDWIDTH'], 'pge': metadata['PGEVersionClass']['PGEVersion'],
            'process_version': attr['PRODUCT_VERSION'], 'crid': next(a['Identifier'] for a in archive['Identifiers']
                                                                    if a['IdentifierType'] == 'CRID'),
            'volume_bytes_if_retrieved': image['SizeInBytes'], 'archive_hdf_checksum': image['Checksum']}


def exact_chains(rows):
    paths = defaultdict(dict)
    first, last = map(datetime.fromisoformat, (START, END))
    for row in sorted(rows, key=lambda item: (datetime.fromisoformat(item['reference_utc']), item['granule'])):
        ref_start, sec_start = map(datetime.fromisoformat, (row['reference_utc'], row['secondary_utc']))
        if not row['full_frame'] or ref_start < first or sec_start > last:
            continue
        reference, secondary = row['input_granules']
        if ref_start >= sec_start or reference == secondary:
            raise ValueError('Granule cannot extend an acquisition chain')
        configuration = tuple(row[key] for key in ('stack', 'process_version', 'crid', 'pge',
                                                   'frequency', 'polarization', 'bandwidth'))
        observations = paths[configuration]
        next_path = observations.get((reference, ref_start), []) + [row['concept']]
        node = secondary, sec_start
        if len(next_path) > len(observations.get(node, [])):
            observations[node] = next_path
    return [{'stack': stack, 'process_version': product, 'crid': crid,
             'pge': pge, 'frequency': frequency, 'polarization': polarization, 'bandwidth': bandwidth,
             'same_input_links': max(observations.values(), key=len)}
            for (stack, product, crid, pge, frequency, polarization, bandwidth), observations in sorted(paths.items())]


def compare(base, site, point):
    with ThreadPoolExecutor(max_workers=3) as executor:
        main = executor.submit(cmr, VALIDATED, point, base / f'{site}-nisar-cmr.json')
        mirror = executor.submit(asf, point, base / f'{site}-nisar-asf.json')
        incumbent = executor.submit(cmr, OPERA_SENTINEL, point, base / f'{site}-opera-cmr.json')
        items, source = main.result()
        asf_rows, asf_source = mirror.result()
        control, control_source = incumbent.result()
    rows = [describe(item) for item in items]
    cmr_names = {item['granule'] for item in rows if item['crid'] == 'P05036'}
    asf_names = {item['granuleName'] for item in asf_rows}
    chains = exact_chains(rows)
    return {'point_lon_lat': point, 'nisar_validated_cmr': len(rows), 'nisar_p05036_cmr': len(cmr_names),
            'nisar_p05036_asf': len(asf_rows),
            'catalog_ids_equal': cmr_names == asf_names, 'cmr_only': sorted(cmr_names - asf_names),
            'asf_only': sorted(asf_names - cmr_names), 'pre_window_reference_count': sum(
                row['reference_utc'] < START for row in rows),
            'nisar_validated_rows': rows, 'exact_in_window_acquisition_chains': chains,
            'opera_displacement_control_count': len(control),
            'opera_displacement_control_ids': sorted(item['meta']['concept-id'] for item in control),
            'acquisition_observations': {'nisar_cmr': source, 'nisar_asf': asf_source,
                                         'opera_sentinel_cmr': control_source},
            'scope': 'CATALOG_SOURCED_PLANNING_ONLY', 'numerical_imagery_acquired': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result_directory', type=Path)
    args = parser.parse_args()
    base = args.result_directory
    base.mkdir(parents=True, exist_ok=False)
    results = {'schema': 'frontier/validated-radar-catalog-comparison-v1', 'interval': [START, END],
               'site_results': {site: compare(base, site, point) for site, point in POINTS.items()}}
    (base / 'CATALOG-COMPARISON.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    for site, result in results['site_results'].items():
        keys = ('nisar_validated_cmr', 'nisar_p05036_asf', 'catalog_ids_equal', 'pre_window_reference_count',
                'exact_in_window_acquisition_chains', 'opera_displacement_control_count')
        print(site, {key: result[key] for key in keys})


if __name__ == '__main__':
    main()
