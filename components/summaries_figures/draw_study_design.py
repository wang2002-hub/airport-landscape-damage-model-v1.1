"""Draw the study-design figure from saved evidence with no statistical refitting."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import ScalarFormatter,NullFormatter
from PIL import Image
from artifact_inputs import Inputs
I=Inputs(__doc__);F=I.output/'figures'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'pdf.fonttype':42,'svg.fonttype':'none','axes.titlesize':11})
inputs={};exports={};values={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csv(p):
 inputs[p.name]=sha(p)
 return pd.read_csv(p)
def save(fig,name):
 fig.savefig(F/(name+'.pdf'),bbox_inches='tight',pad_inches=.08)
 fig.savefig(F/(name+'.svg'),bbox_inches='tight',pad_inches=.08)
 fig.savefig(F/(name+'.png'),dpi=600,bbox_inches='tight',pad_inches=.08)
 im=Image.open(F/(name+'.png')).convert('RGB')
 im.save(F/(name+'.tiff'),compression='tiff_lzw',dpi=(600,600))
 preview=im.copy();preview.thumbnail((1450,1300));preview.save(F/(name+'_inspection.png'))
 exports[name]={'pixels':im.size,'dpi':600,'files':{s:sha(F/(name+s)) for s in ['.pdf','.svg','.png','.tiff']}}
 plt.close(fig)
def box(ax,x,y,w,h,title,body,color='#edf3f6'):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.008,rounding_size=0.009',facecolor=color,edgecolor='#627583',lw=.9))
 ax.text(x+.018,y+h-.025,title,weight='bold',va='top',fontsize=9.5)
 ax.text(x+.018,y+h-.075,body,va='top',fontsize=9.2,linespacing=1.35)
def arrow(ax,a,b):ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'-|>','color':'#52636e','lw':1.2})
order=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']
labels=[x[1:] for x in order]

import traceback
try:
 cohort_path=I.path('cohort');inputs[cohort_path.name]=sha(cohort_path)
 cohort=pd.read_parquet(cohort_path)
 assert cohort.event_id.is_unique
 national=cohort[~cohort.target];targets=cohort[cohort.target]
 assert set(targets.airport_id)==set(order)
 train=national[national.year<=2022];calibration=national[national.year==2023];test=national[national.year>=2024]
 recent=targets[targets.year>=2024]
 design=dict(all_n=len(cohort),all_O=int(cohort.damage_binary.sum()),all_airports=cohort.airport_id.nunique(),
  national_n=len(national),national_O=int(national.damage_binary.sum()),national_airports=national.airport_id.nunique(),
  target_n=len(targets),target_O=int(targets.damage_binary.sum()),train_n=len(train),calibration_n=len(calibration),
  test_n=len(test),test_O=int(test.damage_binary.sum()),recent_n=len(recent),recent_O=int(recent.damage_binary.sum()))
 values['derived_design']=design
 
 fig,ax=plt.subplots(figsize=(8.2,6.4));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
 box(ax,.04,.86,.92,.125,'Eligible bird-strike reports, 2015–2025',f"{design['all_n']:,} reports  |  {design['all_O']:,} damage outcomes  |  {design['all_airports']:,} airports")
 box(ax,.04,.63,.50,.16,f"National source: {design['national_airports']:,} airports",f"{design['national_n']:,} reports; {design['national_O']:,} damage outcomes\nTarget airports excluded in every year")
 box(ax,.64,.60,.32,.19,'Eight held-out airports',f"DEN, JFK, MIA, MSP\nBOS, SFO, SAT, STL\n{design['target_n']:,} reports; {design['target_O']:,} damage")
 arrow(ax,(.30,.86),(.30,.80));arrow(ax,(.80,.86),(.80,.80))
 box(ax,.04,.32,.50,.24,'Temporal evaluation',f"Fit: 2015–2022, n = {design['train_n']:,}\nCalibrate: 2023, n = {design['calibration_n']:,}\nTest: 2024–2025, n = {design['test_n']:,}\nTemporal test damage outcomes: {design['test_O']:,}")
 box(ax,.04,.06,.50,.18,'Geographic evaluation',f"Five outer groups; airports kept together\n{design['national_n']:,} outer-test reports\nProfiles at {design['national_airports']:,} airports")
 box(ax,.64,.32,.32,.21,'Target evaluation',f"Frozen temporal model\nAll years: 2015–2025\nRecent subset: 2024–2025\n{design['recent_n']:,} reports; {design['recent_O']:,} damage")
 arrow(ax,(.30,.63),(.30,.57));arrow(ax,(.80,.60),(.80,.54))
 ax.plot([.04,.012,.012],[.71,.71,.15],c='#52636e',lw=1.2);arrow(ax,(.012,.15),(.035,.15))
 arrow(ax,(.55,.44),(.63,.44))
 box(ax,.64,.06,.32,.18,'Local evidence review','Joint uncertainty and losses\nExtent and report composition\nSensitivity to collection choice',color='#f5f2e9')
 arrow(ax,(.80,.32),(.80,.25))
 save(fig,'fig01_study_design')
 
 (I.output/'results/main_figure_build.json').write_text(json.dumps({'input_sha256':inputs,'exports':exports,'displayed_values':values,'new_fits':0,'new_random_draws':0},ensure_ascii=False,indent=2),encoding='utf-8')
 print('Six figures exported as PDF SVG PNG TIFF; saved numerical provenance.')
except Exception:
 (I.output/'logs/main_figure_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
