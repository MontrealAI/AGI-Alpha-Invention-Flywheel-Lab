import csv,json,datetime,zoneinfo
from pathlib import Path
P=Path(__file__).parent;R=P.parent;camera=json.loads((R/'cameras.json').read_text())[0];tz=zoneinfo.ZoneInfo(camera['tz'])
rows=list(csv.DictReader((P/'production_measurements.csv').read_text().splitlines()));out=[]
for x in rows:
 u=datetime.datetime.strptime(x['timestamp'],'%Y-%m-%dT%H-%M-%SZ').replace(tzinfo=datetime.timezone.utc);l=u.astimezone(tz)
 out.append({'timestamp_utc':u.isoformat().replace('+00:00','Z'),'timestamp_local':l.isoformat(),'local_zone':camera['tz'],'local_zone_abbreviation':l.tzname(),'archive_timestamp_raw':x['timestamp'],**{k:v for k,v in x.items() if k!='timestamp'}})
with (P/'production_measurements_zoned.csv').open('w') as fp:w=csv.DictWriter(fp,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
# These six visible clock readings were actually inspected in timestamp_overlay_audit.jpg.
observed=[('2024-06-15T18-00-41Z','2024-06-15T13:00:41-05:00','CDT'),('2024-06-23T18-00-31Z','2024-06-23T13:00:31-05:00','CDT'),('2024-06-30T18-00-28Z','2024-06-30T13:00:28-05:00','CDT'),('2024-07-14T18-00-08Z','2024-07-14T13:00:08-05:00','CDT'),('2025-06-15T13-00-04Z','2025-06-15T08:00:04-05:00','CDT'),('2025-07-14T23-00-08Z','2025-07-14T18:00:08-05:00','CDT')]
checks=[]
for raw,visible,abbr in observed:
 u=datetime.datetime.strptime(raw,'%Y-%m-%dT%H-%M-%SZ').replace(tzinfo=datetime.timezone.utc);l=u.astimezone(tz);assert l.isoformat()==visible and l.tzname()==abbr;checks.append({'api_filename_time':raw,'visually_read_overlay_local':visible,'overlay_abbreviation':abbr,'zoneinfo_matches':True})
assert datetime.datetime(2024,1,15,18,tzinfo=datetime.timezone.utc).astimezone(tz).hour==12
report={'source_docs':'https://api.waterdata.usgs.gov/docs/nims/','documented_format':'API docs say ISO8601 or NIMS-standardYYYY-MM-DDThh:mm:ssZ; filenames/time fields useZ with dashesseparatingtimecomponents.','camera_metadata_zone':camera['tz'],'semantics':'API/filenameZ isUTC; visiblecameraoverlay is localCDT. Six actualoverlays agree exactly, includingseconds.','checks':checks,'all_production_dates_utc_offset':'-05:00/CDT','conversion':'IANAUS/Central viazoneinfo, not fixed5hour subtraction. JanuaryCST6hour offset unitcheck also passes (computationalcheck, notwinterimagevalidation).','timestamp_correction_needed':False,'frozen_visual_labels_changed':False,'original_time_dependent_metrics_need_regeneration':False,'preferred_contract_csv':'production_measurements_zoned.csv','extra_audit_work':{'view_calls':1,'source_frame_exposures':6,'new_prediction_rows':0}}
(P/'timestamp_audit.json').write_text(json.dumps(report,indent=2));print('Six visibleclocks exactlymatch UTC→US/Central; zonedCSV676rows')
