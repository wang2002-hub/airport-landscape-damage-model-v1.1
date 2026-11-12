"""Measure classifier confidence and audit auxiliary-source coverage."""
from pathlib import Path
import argparse,json,zipfile,io,traceback,importlib.metadata
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from run_support import prepare_output,file_hash

AIRPORTS={'DEN','JFK','MIA','MSP','BOS','SFO','SAT','STL'}

def resolve(base,value):
    p=Path(value)
    return (p if p.is_absolute() else base/p).resolve(strict=True)

def bindings(path):
    cfg=json.loads(path.read_text(encoding='utf-8-sig'))
    if cfg['study_years']!=[2015,2025] or cfg['confidence_year']!=2025:
        raise ValueError('The audit requires the specified 2015-2025 window and 2025 confidence product.')
    files={k:resolve(path.parent,v) for k,v in cfg['paths'].items()}
    for key,count in [('sentinel',13),('forecasts',19),('precipitation',88)]:
        entries=cfg[key]
        if len(entries)!=count or {x['airport'] for x in entries}!=AIRPORTS:
            raise ValueError('Incomplete source inventory: '+key)
        seen=set()
        for i,x in enumerate(entries):
            x['resolved']=resolve(path.parent,x['path'])
            if x['resolved'] in seen:raise ValueError('Duplicate source file: '+key)
            seen.add(x['resolved']);files[f'{key}_{i:03d}']=x['resolved']
    for airport in AIRPORTS:
        if sum(x['airport']==airport and x['primary_export'] for x in cfg['forecasts'])!=1:
            raise ValueError('Each airport needs one primary forecast export.')
    refs=pd.read_csv(files['airport_reference'])
    if str(refs.target.dtype)!='bool':raise ValueError('Target flags must be Boolean.')
    refs=refs[refs.target]
    if len(refs)!=8 or not refs.airport_id.is_unique or set(refs.airport_id)!={'K'+x for x in AIRPORTS}:
        raise ValueError('Duplicate or incomplete target reference.')
    if not refs.latitude.between(-90,90).all() or not refs.longitude.between(-180,180).all():
        raise ValueError('Invalid reference coordinates.')
    if file_hash(files['activity_source'])!=cfg['activity_expected_sha256']:
        raise ValueError('Activity source hash mismatch.')
    with zipfile.ZipFile(files['confidence_archive']) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.tif')]
        if len(names)!=1 or '2025' not in names[0]:raise ValueError('Ambiguous or wrong-year confidence raster.')
    return cfg,files,refs,names[0]

def confidence(refs,p,member):
    rows=[]
    with rasterio.open('/vsizip/'+str(p).replace('\\','/')+'/'+member) as ds:
        if ds.crs is None:raise ValueError('Missing raster coordinate system.')
        metadata={'member':member,'crs':ds.crs.to_wkt(),'nodata':ds.nodata,'width':ds.width,'height':ds.height,'gdal':rasterio.__gdal_version__}
        for a in refs.itertuples():
            local=CRS.from_proj4(f'+proj=aeqd +lat_0={a.latitude} +lon_0={a.longitude} +datum=WGS84 +units=m');trans=Transformer.from_crs(local,ds.crs,always_xy=True).transform
            outer=transform(trans,Point(0,0).buffer(13000,quad_segs=180));arr,aff=mask(ds,[mapping(outer)],crop=True,filled=False,all_touched=False);arr=arr[0]
            for radius in [3,8,13]:
                inside=geometry_mask([mapping(transform(trans,Point(0,0).buffer(radius*1000,quad_segs=180)))],out_shape=arr.shape,transform=aff,invert=True,all_touched=False);valid=inside&~np.ma.getmaskarray(arr)&(arr.data>=1)&(arr.data<=100);v=arr.data[valid]
                if not len(v):raise ValueError('No valid confidence pixels: '+a.airport_id)
                rows.append(dict(airport=a.airport_id,radius_km=radius,buffer_cells=int(inside.sum()),valid_cells=len(v),valid_pct=100*len(v)/inside.sum(),mean_confidence=float(v.mean()),median_confidence=float(np.median(v)),p10_confidence=float(np.quantile(v,.1)),below50_pct=100*(v<50).mean()))
            print('Confidence',a.airport_id,flush=True)
    return pd.DataFrame(rows),metadata

def sentinel(entries):
    rows=[];members=[]
    for x in entries:
        with zipfile.ZipFile(x['resolved']) as z:
            names=[n for n in z.namelist() if n.endswith('/MTD_MSIL2A.xml')]
            if len(names)!=1:raise ValueError('Ambiguous Sentinel metadata.')
            n=names[0];payload=z.read(n)
            root=ET.fromstring(payload);tags={v.tag.split('}')[-1]:v.text for v in root.iter() if v.text and v.text.strip()}
            rows.append(dict(airport=x['airport'],path=x['source_label'],sensing_start=tags.get('PRODUCT_START_TIME'),sensing_stop=tags.get('PRODUCT_STOP_TIME'),cloud_pct=tags.get('Cloud_Coverage_Assessment'),processing_baseline=tags.get('PROCESSING_BASELINE'),metadata_member=n))
            import hashlib
            members.append({'airport':x['airport'],'member':n,'sha256':hashlib.sha256(payload).hexdigest()})
    return pd.DataFrame(rows),members

def workbooks(entries,kind):
    rows=[];keys={};primary={}
    for x in entries:
        wb=openpyxl.load_workbook(x['resolved'],read_only=True,data_only=True)
        found=0
        try:
            for sh in wb:
                it=sh.iter_rows(values_only=True);head=next(it,())
                if kind=='forecast':
                    if not {'station','obtime','ftime'}.issubset(head):continue
                    ids=[head.index(k) for k in ['station','obtime','ftime']]
                    vals=[[row[k] for k in ids] for row in it if row and row[0] is not None]
                    data=pd.DataFrame(vals,columns=['station','obtime','ftime'])
                    ot=pd.to_datetime(data.obtime,errors='coerce',format='mixed');ft=pd.to_datetime(data.ftime,errors='coerce',format='mixed')
                    rows.append(dict(airport=x['airport'],path=x['source_label'],rows=len(data),stations=';'.join(sorted(data.station.astype(str).unique())),first_forecast=str(ft.min()),last_forecast=str(ft.max()),negative_lead_rows=int(ft.lt(ot).sum()),lead_hours=sorted(((ft-ot).dt.total_seconds()/3600).dropna().unique().tolist()),duplicate_forecast_keys=int(data.duplicated(['station','obtime','ftime']).sum()),available_fields=';'.join(str(k) for k in head)))
                    keys[x['source_label']]=set(map(tuple,data.astype(str).itertuples(index=False,name=None)))
                    if x['primary_export']:primary[x['airport']]=x['source_label']
                else:
                    if not {'valid','precip_in'}.issubset(head):continue
                    data=pd.DataFrame(list(it),columns=head).dropna(how='all')
                    t=pd.to_datetime(data['valid'],errors='coerce',format='mixed');v=pd.to_numeric(data.precip_in,errors='coerce')
                    rows.append(dict(airport=x['airport'],path=x['source_label'],rows=len(data),first=str(t.min()),last=str(t.max()),station=';'.join(sorted(data.station.dropna().astype(str).unique())),invalid_time=int(t.isna().sum()),missing_values=int(v.isna().sum()),negative_values=int(v.lt(0).sum()),duplicate_station_times=int(data.duplicated(['station','valid']).sum())))
                found+=1
            if found!=1:raise ValueError('Expected one audited data sheet: '+x['source_label'])
        finally:wb.close()
        print(kind,x['airport'],x['resolved'].name,flush=True)
    overlaps=[]
    if kind=='forecast':
        for x in entries:
            if not x['primary_export']:
                a=keys[x['source_label']];b=keys[primary[x['airport']]]
                overlaps.append({'airport':x['airport'],'source':x['source_label'],'primary_source':primary[x['airport']],'unique_keys':len(a),'shared_primary_keys':len(a&b),'keys_outside_primary':len(a-b)})
    return pd.DataFrame(rows),overlaps

def activity(path):
    tables=pd.read_html(io.StringIO(path.read_text(encoding='utf-8',errors='replace')),flavor='lxml')
    if len(tables)!=1:raise ValueError('Expected one activity table.')
    t=tables[0];original_columns=list(map(str,t.columns));t.columns=[str(c[-1]) if isinstance(c,tuple) else str(c) for c in t.columns]
    airports=t['Airport'].dropna().astype(str).unique().tolist()
    dates=t['Date'].astype('string').str.strip()
    detail=dates.str.fullmatch(r'(0[1-9]|1[0-2])/20\d{2}',na=False)
    subtotal=dates.str.startswith('Sub-Total for ',na=False);total=dates.eq('Total:').fillna(False)
    if not (detail|subtotal|total).all():raise ValueError('Unclassified activity table rows.')
    detail_airports=sorted(t.loc[detail,'Airport'].dropna().astype(str).unique())
    if detail_airports!=['DEN'] or t.loc[detail,'Airport'].isna().any():raise ValueError('Activity airport coverage changed.')
    months=pd.to_datetime(dates[detail],format='%m/%Y')
    if not months.dt.year.between(2015,2025).all():raise ValueError('Activity period changed.')
    return {'actual_format':'HTML table with XLS extension','sha256':file_hash(path),'tables':[{'shape':list(t.shape),'columns':original_columns}],'date_values_preview':t['Date'].dropna().astype(str).unique()[:15].tolist(),'airport_values':airports,'date_unique':int(t['Date'].nunique()),'detail_airports':detail_airports,'detail_rows':int(detail.sum()),'subtotal_rows':int(subtotal.sum()),'grand_total_rows':int(total.sum()),'distinct_detail_months':int(months.nunique()),'first_detail_month':str(months.min().date()),'last_detail_month':str(months.max().date()),'rows_missing_airport':int(t.Airport.isna().sum()),'conclusion':'DEN-only activity collection; no common eight-target activity denominator. Detail rows are monthly classifications; subtotals and the grand total are separate. Table rows are not individual flights or incidents.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    global rasterio,openpyxl,mask,geometry_mask,CRS,Transformer,Point,mapping,transform
    import rasterio
    import openpyxl
    from rasterio.mask import mask
    from rasterio.features import geometry_mask
    from pyproj import CRS,Transformer
    from shapely.geometry import Point,mapping
    from shapely.ops import transform
    # Reject protected output before expensive file hashing or raster access.
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):raise ValueError('Use a new or empty output directory; previous runs are preserved.')
    cfg,files,refs,member=bindings(args.inputs.resolve());out=prepare_output(args.output,{'bindings':args.inputs,**files},['results','logs'])
    def save(name,obj):(out/'results'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        conf,rastermeta=confidence(refs,files['confidence_archive'],member);conf.to_csv(out/'results/confidence_2025.csv',index=False);save('confidence_raster.json',rastermeta)
        sent,metahash=sentinel(cfg['sentinel']);sent.to_csv(out/'results/sentinel_dates.csv',index=False);save('sentinel_metadata_hashes.json',metahash)
        fd,overlaps=workbooks(cfg['forecasts'],'forecast');fd.to_csv(out/'results/forecast_scope.csv',index=False);save('forecast_export_overlap.json',overlaps)
        precip,_=workbooks(cfg['precipitation'],'precipitation');precip.to_csv(out/'results/precipitation_scope.csv',index=False)
        tf=activity(files['activity_source']);save('activity_scope.json',tf)
        dates=pd.to_datetime(sent.sensing_start,utc=True,errors='raise');in_period=dates.dt.year.between(*cfg['study_years'])
        if in_period.any():raise ValueError('Contemporaneous Sentinel acquisitions require a separate eligibility review.')
        decisions=[
            dict(source='2026 Sentinel-2',records=len(sent),decision='Out-of-period background only; no image classification performed',reason='Acquisitions fall after the 2015-2025 outcome window.'),
            dict(source='2025 Annual NLCD LndCnf',records=len(conf),decision='Eight-airport, three-radius classifier-confidence summaries',reason='Values 1-100 describe classifier confidence, not externally validated accuracy or land-cover change. These measurements are separate from damage prediction.'),
            dict(source='FD',records=len(fd),decision='Forecast scope and duplicate-key diagnostics',reason='Reference times, valid times and altitude levels differ from observed surface conditions. Supplemental exports are not concatenated into the primary export.'),
            dict(source='TFMSC',records=tf['tables'][0]['shape'][0],decision='DEN-only activity coverage; separate from the conditional-damage denominator',reason='A common eight-airport incidence analysis would require comparable activity data. Source totals are not extra observations.'),
            dict(source='Standalone hourly precipitation XLSX',records=len(precip),decision='Source coverage audit; separate from incident matching',reason='Timezone provenance remains unresolved and yearly boundaries are incomplete. Surface-record precipitation uses its separately verified UTC matching rule.')]
        save('source_roles.json',decisions);save('audit_runtime.json',{p:importlib.metadata.version(p) for p in ['rasterio','shapely','pyproj','openpyxl','lxml']})
        print('Source audit completed',flush=True)
    except Exception:
        (out/'logs/failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise

if __name__=='__main__':main()
