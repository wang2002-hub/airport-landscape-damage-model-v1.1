"""Retrospective wetland, source-vintage and runway geometry context."""
from pathlib import Path
import argparse,json,traceback,importlib.metadata
from run_support import prepare_output
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
import numpy as np,pandas as pd,pyogrio,pyogrio.raw
from pyproj import CRS,Transformer,Geod
from shapely.geometry import Point,shape,mapping,Polygon
from shapely.ops import transform,unary_union
from shapely import from_wkb,make_valid
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from shapely.geometry.polygon import orient
from matplotlib.collections import PatchCollection

manifest=Path(args.inputs).resolve(strict=True);config=json.loads(manifest.read_text(encoding='utf-8'))
paths={k:(manifest.parent/Path(v)).resolve(strict=True) for k,v in config['paths'].items()}
inventory=config['layers'];expected={'DEN','JFK','MIA','MSP','BOS','SFO','SAT','STL'}
if len(inventory)!=8 or {x['airport'] for x in inventory}!=expected:raise ValueError('Airport layer inventory must identify each target exactly once.')
refs=pd.read_csv(paths['airport_reference']);refs=refs[refs.target].copy()
if refs.airport_id.duplicated().any() or set(refs.airport_id)!={'K'+x for x in expected}:raise ValueError('Duplicate or incomplete target reference.')
if not refs.longitude.between(-180,180).all() or not refs.latitude.between(-90,90).all():raise ValueError('Invalid reference coordinates.')
refs=refs.set_index('airport_id');e=pd.read_parquet(paths['environment']);e=e[e.year.eq(2025)].copy()
if e.airport_id.duplicated().any():raise ValueError('Duplicate 2025 environmental key.')
e=e.set_index('airport_id');vectors=json.loads(paths['runway_vectors'].read_text(encoding='utf-8'))
if len(vectors)!=8 or {x['airport'] for x in vectors}!=expected:raise ValueError('Invalid runway inventory.')
for item in inventory:
 item['gpkg']=str((manifest.parent/Path(item['gpkg'])).resolve(strict=True));layers=item['layers']
 if len(layers)!=2 or len({x['layer_name'] for x in layers})!=2:raise ValueError('Duplicate or missing layer definition.')
 wet=[x for x in layers if x['layer_name'].lower().endswith('_wetlands')];project=[x for x in layers if x['layer_name'].lower().endswith('wetlands_project_metadata')]
 if len(wet)!=1 or len(project)!=1:raise ValueError('Wetland and project layers must be explicitly identified.')
 for layer in layers:
  actual=pyogrio.read_info(item['gpkg'],layer=layer['layer_name'])
  if not CRS.from_user_input(actual['crs']).equals(CRS.from_user_input(layer['crs'])):raise ValueError('Configured CRS disagrees with source layer.')
 if not CRS.from_user_input(wet[0]['crs']).equals(CRS.from_user_input(project[0]['crs'])):raise ValueError('Wetland and metadata CRS differ.')
D=prepare_output(args.output,{'bindings':manifest,**paths,**{'geopackage_'+x['airport']:x['gpkg'] for x in inventory}},['results','processed','figures','logs'])
(D/'spatial_runtime.json').write_text(json.dumps({'packages':{x:importlib.metadata.version(x) for x in ['pyogrio','shapely','pyproj','matplotlib','Pillow']},'gdal':pyogrio.__gdal_version__},indent=2),encoding='utf-8')
try:
 summary=[];types=[];dates=[];meta_features=[];vector_rows=[];polygon_vintages=[];fig,axes=plt.subplots(2,4,figsize=(12,6.6));order=['DEN','JFK','MIA','MSP','BOS','SFO','SAT','STL']
 def raw(path,layer,bounds):
  meta,fid,geom,values=pyogrio.raw.read(str(path),layer=layer,bbox=bounds,return_fids=True);return meta,pd.DataFrame(dict(zip(meta['fields'],values))),from_wkb(geom)
 def parts(g):
  if g.geom_type=='Polygon':return [g]
  if hasattr(g,'geoms'):return [p for x in g.geoms for p in parts(x)]
  return []
 for index,a in enumerate(order):
  p=next(x for x in inventory if x['airport'].endswith(a));lon,lat=refs.loc['K'+a,['longitude','latitude']];local=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m');to_local=Transformer.from_crs(4326,local,always_xy=True).transform;inv_local=Transformer.from_crs(local,4326,always_xy=True).transform;circle=Point(0,0).buffer(13000,quad_segs=180)
  wet=next(x for x in p['layers'] if x['layer_name'].lower().endswith('_wetlands'));to_src=Transformer.from_crs(local,wet['crs'],always_xy=True).transform;from_src=Transformer.from_crs(wet['crs'],local,always_xy=True).transform;bounds=transform(to_src,circle).bounds
  meta,attrs,geoms=raw(p['gpkg'],wet['layer_name'],bounds);clips=[];kept=[];repairs=0
  for i,g in enumerate(geoms):
   if not g.is_valid:g=make_valid(g);repairs+=1
   g=transform(from_src,g).intersection(circle)
   if not g.is_empty and g.area>0:clips.append(g);kept.append(i)
  attrs=attrs.iloc[kept].reset_index(drop=True);union=unary_union(clips);r=dict(airport=a,polygons=len(clips),repaired_input_polygons=repairs,nwi_all_classes_pct=100*union.area/circle.area,nlcd2025_wetland_pct=100*e.loc['K'+a,'wetland_fraction__b13'],nlcd2025_water_pct=100*e.loc['K'+a,'water_fraction__b13'])
  # Join source project footprints spatially; do not infer a single date from the download year.
  ml=next(x for x in p['layers'] if x['layer_name'].lower().endswith('wetlands_project_metadata'));mm,ma,mg=raw(p['gpkg'],ml['layer_name'],bounds);footprints=[];labels=[];wetdated=[]
  for j,g in enumerate(mg):
   g=transform(from_src,make_valid(g)).intersection(circle)
   if g.is_empty or g.area==0:continue
   footprints.append(g);label=str(ma.iloc[j].get('IMAGE_YR',''));labels.append(label);over=union.intersection(g);wetdated.append(over)
   row={k:str(v) for k,v in ma.iloc[j].items()};row.update(airport=a,buffer_coverage_pct=100*g.area/circle.area,nwi_area_overlap_km2=over.area/1e6);dates.append(row)
   meta_features.append({'type':'Feature','properties':row,'geometry':mapping(transform(inv_local,g))})
  r['source_image_years']='; '.join(sorted(set(labels)));r['project_coverage_pct']=min(100,100*unary_union(footprints).area/circle.area) if footprints else 0;r['nwi_area_with_project_metadata_pct']=min(100,100*unary_union(wetdated).area/union.area) if union.area else np.nan
  for i,g in enumerate(clips):
   overlaps=[(label,g.intersection(poly).area) for label,poly in zip(labels,footprints) if g.intersects(poly)]
   # Keep even small overlaps in the audit, with areas, so slivers are visible rather than silently treated as dominant dates.
   for label,area in overlaps:
    if area>0:polygon_vintages.append(dict(airport=a,nwi_id=str(attrs.iloc[i].get('NWI_ID',i)),attribute=str(attrs.iloc[i].get('ATTRIBUTE','')),wetland_type=str(attrs.iloc[i].get('WETLAND_TYPE','')),clipped_area_m2=g.area,source_image_year=label,overlap_m2=area,overlap_fraction=area/g.area))
  # Full area within supplied polygons is descriptive; classification systems and vintages differ.
  for typ in sorted(attrs.WETLAND_TYPE.dropna().unique()):
   gs=[g for g,k in zip(clips,attrs.WETLAND_TYPE) if k==typ];area=unary_union(gs).area;types.append(dict(airport=a,wetland_type=typ,area_km2=area/1e6,buffer_pct=100*area/circle.area,polygons=len(gs)))
  summary.append(r);ax=axes.flat[index];patches=[]
  for g in clips:
   for poly in parts(g):
    poly=orient(poly,sign=1.0);verts=[];codes=[]
    for ring in [poly.exterior]+list(poly.interiors):
     xy=np.asarray(ring.coords)/1000;verts.extend(xy);codes.extend([MplPath.MOVETO]+[MplPath.LINETO]*(len(xy)-2)+[MplPath.CLOSEPOLY])
    patches.append(PathPatch(MplPath(np.asarray(verts),codes)))
  ax.add_collection(PatchCollection(patches,facecolor='#a8cbd2',edgecolor='none',alpha=.85))
  v=next(x for x in vectors if x['airport']==a);run=[]
  for f in v['runways']:
   g=transform(to_local,shape(f['geometry']));run.append(g)
   def draw(g):
    if g.geom_type in ['LineString','LinearRing']:
     xy=np.array(g.coords)/1000;ax.plot(xy[:,0],xy[:,1],color='#253847',lw=1)
    elif g.geom_type=='Polygon':draw(g.exterior)
    elif hasattr(g,'geoms'):
     for x in g.geoms:draw(x)
   draw(g)
  for radius,ls in [(3,':'),(8,'--'),(13,'-')]:ax.add_patch(plt.Circle((0,0),radius,fill=False,color='#5b6670',linestyle=ls,lw=.8))
  ax.plot(0,0,'+',color='#a84032',ms=7);ax.set(xlim=(-14,14),ylim=(-14,14),aspect='equal',xticks=[-10,0,10],yticks=[-10,0,10],title=a);ax.tick_params(labelsize=8);ax.set_xlabel('East (km)',fontsize=8)
  if index%4==0:ax.set_ylabel('North (km)',fontsize=8)
  vector_rows.append(dict(airport=a,runway_tagged_geometries=len(run),max_distance_from_reference_km=max(max(np.hypot(*xy)) for g in run for poly in ([g] if g.geom_type=='LineString' else parts(g)) for xy in [np.array(poly.coords if poly.geom_type=='LineString' else poly.exterior.coords).T])/1000))
  print('SPATIAL',r,flush=True)
 plt.subplots_adjust(left=.06,right=.99,top=.94,bottom=.13,wspace=.2,hspace=.3);fig.text(.5,.025,'Shaded: NWI wetland/deepwater snapshot; dark lines: runway-tagged geometry; circles: 3, 8 and 13 km.\nLocal equidistant coordinates. Source dates differ; features do not represent historical runway use.',ha='center',fontsize=9)
 fig.savefig(D/'figures/spatial_context_diagnostic.png',dpi=300);fig.savefig(D/'figures/spatial_context_diagnostic.pdf');plt.close(fig)
 for name,rows in [('wetland_summary.csv',summary),('wetland_types.csv',types),('source_projects.csv',dates),('polygon_vintage_overlaps.csv',polygon_vintages),('runway_geometry.csv',vector_rows)]:pd.DataFrame(rows).to_csv(D/'results'/name,index=False,encoding='utf-8-sig')
 (D/'processed/local_nwi_project_footprints.geojson').write_text(json.dumps({'type':'FeatureCollection','features':meta_features},ensure_ascii=False),encoding='utf-8')
except Exception:
 (D/'logs/failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
