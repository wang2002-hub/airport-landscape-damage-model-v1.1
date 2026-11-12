"""Plot source-audited geography and saved landscape evidence without refitting."""
from pathlib import Path
import sys,json,hashlib,io,zipfile
from plot_inputs import Inputs
I=Inputs(__doc__);F=I.output/'figures'
import pandas as pd,numpy as np,shapefile
import pyproj
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.titlesize':11.5,'pdf.fonttype':42,'svg.fonttype':'none'})
inputs={};exports={};values={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 inputs[p.name]=sha(p);return pd.read_csv(p)
def save(fig,name):
 for ext in ['pdf','svg']:fig.savefig(F/f'{name}.{ext}',bbox_inches='tight',pad_inches=.1)
 fig.savefig(F/f'{name}.png',dpi=600,bbox_inches='tight',pad_inches=.1)
 im=Image.open(F/f'{name}.png').convert('RGB');im.save(F/f'{name}.tiff',compression='tiff_lzw',dpi=(600,600))
 preview=im.copy();preview.thumbnail((1500,1350));preview.save(F/f'{name}_inspection.png')
 exports[name]={'pixels':list(im.size),'dpi':600,'files':{'.'+s:sha(F/f'{name}.{s}') for s in ['pdf','svg','png','tiff']}}
 plt.close(fig)

import traceback
try:
 air=read(I.path('map_airports'));summary=read(I.path('airport_summary'))
 assert len(air)==1383 and air.airport_id.nunique()==1383 and air.target.sum()==8
 assert set(air.airport_id)==set(summary.airport_id)
 assert air.reports.sum()==52103
 merged=air.merge(summary[['airport_id','n','region']],on='airport_id',suffixes=('','_summary'),validate='one_to_one')
 assert (merged.reports==merged.n).all() and (merged.region==merged.region_summary).all()
 assert air.longitude.between(-125,-66).all() and air.latitude.between(24,50).all()
 zip_path=I.path('ne_50m_admin_1_states_provinces');inputs[zip_path.name]=sha(zip_path)
 with zipfile.ZipFile(zip_path) as z:
  stem='ne_50m_admin_1_states_provinces'
  reader=shapefile.Reader(shp=io.BytesIO(z.read(stem+'.shp')),shx=io.BytesIO(z.read(stem+'.shx')),dbf=io.BytesIO(z.read(stem+'.dbf')))
  source_crs=pyproj.CRS.from_wkt(z.read(stem+'.prj').decode());version=z.read(stem+'.VERSION.txt').decode().strip()
  members={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
 assert version=='5.1.1' and source_crs.to_epsg()==4326
 transform=pyproj.Transformer.from_crs(source_crs,5070,always_xy=True)
 fig,ax=plt.subplots(figsize=(8.4,5.4),layout='constrained');state_names=[];allcoords=[]
 for sr in reader.iterShapeRecords():
  r=sr.record.as_dict()
  if r['admin']!='United States of America' or r['postal'] in ['AK','HI']:continue
  state_names.append(r['name']);points=np.array(sr.shape.points);x,y=transform.transform(points[:,0],points[:,1]);coords=np.column_stack([x,y]);allcoords.append(coords)
  parts=list(sr.shape.parts)+[len(points)];vertices=[];codes=[]
  for i,j in zip(parts[:-1],parts[1:]):
   vertices.extend(coords[i:j]);codes.extend([MPath.MOVETO]+[MPath.LINETO]*(j-i-2)+[MPath.CLOSEPOLY])
  ax.add_patch(PathPatch(MPath(np.array(vertices),codes),facecolor='#eef1f2',edgecolor='#939fa5',lw=.45,zorder=1))
 assert len(state_names)==49
 x,y=transform.transform(air.longitude.to_numpy(),air.latitude.to_numpy());air['map_x']=x;air['map_y']=y
 national=air[~air.target];target=air[air.target]
 ax.scatter(national.map_x,national.map_y,s=5,c='#667d8b',alpha=.6,lw=0,label='National source: 1,375 airports',zorder=2)
 ax.scatter(target.map_x,target.map_y,s=58,marker='*',c='#af4b28',edgecolors='white',lw=.45,label='Eight jointly excluded targets',zorder=4)
 offset={'KDEN':(8,-16),'KJFK':(27,-18),'KMIA':(16,-10),'KMSP':(-20,17),'KBOS':(22,15),'KSFO':(-8,-22),'KSAT':(-30,-20),'KSTL':(12,-14)}
 for r in target.itertuples():
  dx,dy=offset[r.airport_id];ax.annotate(f'{r.airport_id[1:]} ({r.region})',(r.map_x,r.map_y),xytext=(dx,dy),textcoords='offset points',fontsize=10,weight='bold',ha='left' if dx>=0 else 'right',arrowprops={'arrowstyle':'-','lw':.6,'color':'#555'},bbox={'boxstyle':'round,pad=.15','fc':'white','ec':'none','alpha':.85},zorder=5)
 coords=np.concatenate(allcoords);ax.set_xlim(coords[:,0].min()-250000,coords[:,0].max()+400000);ax.set_ylim(coords[:,1].min()-180000,coords[:,1].max()+180000)
 ax.set_aspect('equal');ax.axis('off');ax.legend(loc='lower left',frameon=False,fontsize=10)
 geod=pyproj.Geod(ellps='WGS84');lo,la=-122.5,29;lon2,lat2,_=geod.fwd(lo,la,90,1000000);sx,sy=transform.transform([lo,lon2],[la,lat2])
 ax.plot(sx,sy,c='#333',lw=2);ax.text(np.mean(sx),np.mean(sy)+60000,'1,000 km',fontsize=9,ha='center')
 nx,ny=transform.transform([-68,-68],[44,46]);ax.annotate('N',xy=(nx[1],ny[1]),xytext=(nx[0],ny[0]),ha='center',fontsize=10,arrowprops={'arrowstyle':'-|>','color':'#333'})
 ax.text(.99,.01,'CONUS Albers equal-area projection\nMade with Natural Earth',transform=ax.transAxes,ha='right',fontsize=8.5,color='#555')
 values['map']={'airports':len(air),'national_airports':len(national),'target_airports':len(target),'reports':int(air.reports.sum()),'states_plus_dc':len(state_names),'source_epsg':4326,'display_epsg':5070,'target_records':target.to_dict('records')}
 save(fig,'figS01_airport_distribution')
 source_info={'name':'Natural Earth Admin 1 states and provinces','version':version,'scale':'1:50,000,000','zip_sha256':sha(zip_path),'download_url':'https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_1_states_provinces.zip','source_page':'https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-1-states-provinces/','terms_url':'https://www.naturalearthdata.com/about/terms-of-use/','license':'Public domain per official Natural Earth terms','access_date':'2026-11-02','source_crs':source_crs.to_string(),'display_crs':'EPSG:5070','retained_geographies':state_names,'members':members,'scope':'Background only; no model inputs or sample selection changed'}
 (I.output/'results/basemap_source.json').write_text(json.dumps(source_info,ensure_ascii=False,indent=2),encoding='utf-8')
 air.to_csv(F/'airport_plot_coordinates.csv',index=False)
 
 (I.output/'results/geographic_landscape_figure_build.json').write_text(json.dumps({'input_sha256':inputs,'exports':exports,'displayed_values':values,'basemap_source':source_info,'new_fits':0,'new_random_draws':0},ensure_ascii=False,indent=2),encoding='utf-8')
 print('Airport distribution exported.')
except Exception:
 (I.output/'logs/geography_landscape_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
