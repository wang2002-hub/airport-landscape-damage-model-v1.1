"""Extract annual landscape measurements from explicit raster and geometry inputs."""
from pathlib import Path
import argparse,json,os,time,sys,threading,traceback
from urllib.parse import quote
from run_support import prepare_output

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
import numpy as np,pandas as pd
import pyogrio.raw
from shapely import from_wkb
from shapely.geometry import Polygon
from shapely.ops import transform
from pyproj import CRS,Transformer,Geod

manifest=args.inputs.resolve(strict=True);config=json.loads(manifest.read_text(encoding='utf-8'))
def resolve(value):return (manifest.parent/Path(value)).resolve(strict=True)
paths={k:resolve(v) for k,v in config['paths'].items()};library=resolve(config['gdal_library']);RASTERS=config['rasters'];SELECTED=config['airports']
expected={('D02',y) for y in range(2015,2026)}|{('D03',y) for y in range(2015,2026)}|{('D04',y) for y in [2015,2020,2025]}|{('D05',2025)}
if len(RASTERS)!=26 or {(x['source'],x['year']) for x in RASTERS}!=expected:raise ValueError('Missing or duplicate raster product-year.')
if not SELECTED or len(SELECTED)!=len(set(SELECTED)):raise ValueError('Empty or duplicate airport selection.')
for x in RASTERS:x['resolved']=resolve(x['path'])
if len({x['resolved'] for x in RASTERS})!=26:raise ValueError('Duplicate raster file.')
OUT=prepare_output(args.output,{'bindings':manifest,**paths,'gdal_library':library,**{x['source']+'_'+str(x['year']):x['resolved'] for x in RASTERS}},['cache','processed','logs'])
record=json.loads((OUT/'run_inputs.json').read_text(encoding='utf-8'))
for x in RASTERS:
 if record['inputs'][x['source']+'_'+str(x['year'])]['sha256']!=x['sha256']:raise ValueError('Raster input hash mismatch.')
os.environ['BIRDSTRIKE_GDAL_LIBRARY']=str(library)
from raster_core import *
W=OUT;O=OUT
ZONES=['r00_03','r03_08','r08_13','b03','b08','b13']
PAIRS=[(y-1,y) for y in range(2016,2026)]+[(2015,2020),(2020,2025)]
SFIELDS=['valid_n','shdi','edge_density_km_km2','lpi_water_wetland_pct','lpi_cropland_pct','largest_water_wetland_pixels','largest_cropland_pixels']
LOCAL=threading.local()
def initialize():
    LOCAL.sets={}
    for source in RASTERS:
        LOCAL.sets[source['source'],source['year']]=Raster(source['resolved'])

def hist(a,masks):
    return np.stack([np.bincount(a[m].ravel(),minlength=256) for m in masks]).astype(np.int32)

def extract(job):
    SETS=LOCAL.sets
    airport,wbks=job; path=W/'cache'/f'{quote(airport,safe="")}.npz'
    if path.exists():raise ValueError('Refusing to reuse an existing cache.')
    t=time.time();polys=[from_wkb(b) for b in wbks];base=SETS['D02',2015]
    win=base.window(polys[-1].bounds);gt=base.window_gt(win);shape=(win[3],win[2])
    cum=[mask_polygon(p,gt,shape) for p in polys[3:]]
    masks=[cum[0],cum[1]&~cum[0],cum[2]&~cum[1]]+cum
    touches=[mask_polygon(p,gt,shape,True) for p in polys]
    assert not np.any(masks[0]&masks[1]) and not np.any(masks[1]&masks[2])
    assert np.array_equal(masks[0]|masks[1]|masks[2],masks[5])
    land={year:SETS['D02',year].read(*win) for year in range(2015,2026)}
    imperv={year:SETS['D03',year].read(*win) for year in range(2015,2026)}
    lc=np.stack([hist(land[y],masks) for y in range(2015,2026)])
    lc_touch=np.stack([hist(land[y],touches) for y in range(2015,2026)])
    imp=np.stack([hist(imperv[y],masks) for y in range(2015,2026)])
    imp_touch=np.stack([hist(imperv[y],touches) for y in range(2015,2026)])
    struct=np.empty((11,3,len(SFIELDS)),dtype=float)
    for yi,y in enumerate(range(2015,2026)):
        for zi,m in enumerate(cum):
            rr,cc=np.nonzero(m);sl=(slice(rr.min(),rr.max()+1),slice(cc.min(),cc.max()+1))
            out=structure(land[y][sl],m[sl]);struct[yi,zi]=[out.get(k,np.nan) for k in SFIELDS]
    transitions=np.zeros((len(PAIRS),6,16,16),dtype=np.int32)
    imp_common=np.zeros((len(PAIRS),6,4),dtype=float)
    classindex=np.full(256,-1,dtype=np.int16);classindex[CLASSES]=np.arange(16)
    for pi,(y0,y1) in enumerate(PAIRS):
        a=land[y0];b=land[y1];valid=LUT[a]&LUT[b]
        ac=classindex[a];bc=classindex[b]
        ia=imperv[y0];ib=imperv[y1];iv=(ia<=100)&(ib<=100)
        for zi,m in enumerate(masks):
            keep=m&valid
            count=np.bincount((ac[keep]*16+bc[keep]).ravel(),minlength=256).reshape(16,16)
            assert np.array_equal(count.sum(1),np.bincount(ac[keep],minlength=16))
            assert np.array_equal(count.sum(0),np.bincount(bc[keep],minlength=16))
            transitions[pi,zi]=count
            km=m&iv;imp_common[pi,zi]=[km.sum(),ia[km].sum(dtype=np.float64),ib[km].sum(dtype=np.float64),np.count_nonzero(ia[km]!=ib[km])]
    canopy=[];canopy_touch=[];canopy_n=[];canopy_touch_n=[]
    for y in [2015,2020,2025]:
        r=SETS['D04',y]; cw=r.window(polys[-1].bounds); cg=r.window_gt(cw);a=r.read(*cw)
        cm=[mask_polygon(p,cg,a.shape) for p in polys];ct=[mask_polygon(p,cg,a.shape,True) for p in polys]
        canopy.append(hist(a,cm));canopy_touch.append(hist(a,ct));canopy_n.append([m.sum() for m in cm]);canopy_touch_n.append([m.sum() for m in ct])
    a=land[2024];b=land[2025];ch=SETS['D05',2025].read(*win)
    common=LUT[a]&LUT[b];expect=np.where(a==b,a,a.astype(np.uint16)*100+b)
    changecheck=[]
    for m in masks:
        good=m&common;dg=good&(ch!=9999)
        changecheck.append([good.sum(),dg.sum(),np.count_nonzero(ch[dg]!=expect[dg]),np.count_nonzero(good&(ch==9999)),np.count_nonzero(m&~common&(ch!=9999))])
    np.savez_compressed(path,airport_id=np.array(airport),years=np.arange(2015,2026),zones=np.array(ZONES),pairs=np.array(PAIRS),lc=lc,lc_touch=lc_touch,imp=imp,imp_touch=imp_touch,canopy=np.array(canopy),canopy_touch=np.array(canopy_touch),canopy_n=np.array(canopy_n),canopy_touch_n=np.array(canopy_touch_n),mask_n=np.array([m.sum() for m in masks]),touch_n=np.array([m.sum() for m in touches]),areas_km2=np.array([p.area/1e6 for p in polys]),structure=struct,structure_fields=np.array(SFIELDS),transitions=transitions,impervious_common=imp_common,changecheck=np.array(changecheck),window=np.array(win),window_gt=np.array(gt),transition_marginals_verified=np.array(True))
    if airport in ['KDEN','KDEN_ALT']:
        for y in [2015,2020,2025]:
            write_tif(W/'cache'/f'{airport}_landcover_{y}.tif',land[y],gt,base.wkt)
    return airport,'computed',time.time()-t

def tests():
    from shapely.geometry import box
    a=np.array([[11,82],[82,11]],dtype='uint8');m=np.ones_like(a,dtype=bool)
    v=structure(a,m,30)
    assert abs(v['shdi']-np.log(2))<1e-12
    assert v['largest_water_wetland_pixels']==2 and v['largest_cropland_pixels']==2
    assert abs(v['edge_density_km_km2']-0.12/0.0036)<1e-9
    assert v['lpi_water_wetland_pct']==50
    aa=np.array([[11,250],[82,11]],dtype='uint8');v2=structure(aa,m,30)
    assert v2['valid_n']==3 and abs(v2['edge_density_km_km2']-.06/.0027)<1e-9
    gt=[0,30,0,60,0,-30]; p=box(5,5,35,55)
    center=mask_polygon(p,gt,(2,2));touch=mask_polygon(p,gt,(2,2),True)
    assert center.sum()==2 and touch.sum()==4
    dump(O/'logs/synthetic_raster_unit_checks.json',{'checkerboard_shdi':v['shdi'],'diagonal_8_neighbour_connected':True,'edge_once_and_outer_excluded':True,'nodata_edges_excluded':True,'centre_mask_expected_2':int(center.sum()),'all_touched_expected_4':int(touch.sum()),'passed':True})

def geometry_table(path):
    meta,_,wkb,cols=pyogrio.raw.read(path)
    frame=pd.DataFrame(dict(zip(meta['fields'],cols)));frame['geometry']=from_wkb(wkb)
    return frame,CRS.from_user_input(meta['crs'])

def jobs():
    b,bcrs=geometry_table(paths['buffers']);r,rcrs=geometry_table(paths['rings'])
    if not bcrs.equals(rcrs):raise ValueError('Buffer and ring coordinate systems differ.')
    b=b.sort_values(['airport_id','radius_km']);r=r.sort_values(['airport_id','outer_km'])
    if b.duplicated(['airport_id','radius_km']).any() or r.duplicated(['airport_id','outer_km']).any():raise ValueError('Duplicate geometry key.')
    available=set(b.airport_id)&set(r.airport_id)
    if not set(SELECTED)<=(available|{'KDEN_ALT'}):raise ValueError('Unknown airport selection.')
    result=[]
    for airport in SELECTED:
        if airport=='KDEN_ALT':continue
        br=b[b.airport_id==airport];rr=r[r.airport_id==airport]
        if br.radius_km.tolist()!=[3,8,13] or rr.outer_km.tolist()!=[3,8,13]:raise ValueError('Incomplete geometry radii.')
        polys=list(rr.geometry)+list(br.geometry)
        if not all(p.is_valid and not p.is_empty for p in polys):raise ValueError('Invalid input geometry.')
        result.append((airport,[p.wkb for p in polys]))
    if 'KDEN_ALT' in SELECTED:
        alternatives=pd.read_csv(paths['den_alternatives'])
        if len(alternatives)<2:raise ValueError('Missing DEN alternative reference.')
        a=alternatives.iloc[1];geod=Geod(ellps='WGS84');az=np.arange(0,360,.5);trans=Transformer.from_crs(4326,bcrs,always_xy=True)
        ps=[]
        for rad in [3000,8000,13000]:
            x,y,_=geod.fwd(np.full(720,a.longitude),np.full(720,a.latitude),az,np.full(720,rad));ps.append(transform(trans.transform,Polygon(zip(x,y))))
        polys=[ps[0],ps[1].difference(ps[0]),ps[2].difference(ps[1])]+ps
        result.append(('KDEN_ALT',[p.wkb for p in polys]))
        dump(OUT/'processed/den_alternative_geometry.json',{'crs':bcrs.to_wkt(),'zones':[{'zone':z,'wkb_hex':p.wkb_hex} for z,p in zip(ZONES,polys)]})
    return result,bcrs

if __name__=='__main__':
    try:
        tests();alljobs,geometry_crs=jobs();initialize();base=LOCAL.sets['D02',2015];raster_info=[]
        for key,raster in LOCAL.sets.items():
            if not CRS.from_wkt(raster.wkt).equals(geometry_crs):raise ValueError('Raster and geometry CRS mismatch.')
            if key[0] in ['D02','D03','D05'] and (raster.gt!=base.gt or raster.w!=base.w or raster.h!=base.h):raise ValueError('Annual raster grids differ.')
            raster_info.append({'product':key[0],'year':key[1],'width':raster.w,'height':raster.h,'transform':raster.gt,'dtype':str(np.dtype(raster.dtype)),'nodata':raster.nodata})
        if base.gt[1]!=30 or base.gt[5]!=-30:raise ValueError('Landscape structure requires the retained 30 m grid.')
        dump(OUT/'logs/raster_metadata.json',raster_info)
        start=time.time();results=[]
        for job in alljobs:
            item=extract(job);results.append(item);print('EXTRACTED',item,flush=True)
        pd.DataFrame(results,columns=['airport_id','status','seconds']).to_csv(OUT/'logs/extraction_log.csv',index=False)
        dump(OUT/'logs/extraction_scope.json',{'airports':[x[0] for x in alljobs],'rasters':len(RASTERS),'seconds':time.time()-start,'workers':1,'cache_reuse':False,'gdal_version':pyogrio.__gdal_version_string__})
    except Exception:
        (OUT/'logs/failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
    finally:
        for raster in getattr(LOCAL,'sets',{}).values():raster.release()
