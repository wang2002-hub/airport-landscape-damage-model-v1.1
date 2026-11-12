"""Plot matched landscape comparisons from retained summary data."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audit_panel_alignment import require_matplotlib_panel_alignment
P=Path(__file__).resolve().parent
import argparse
_parser=argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--output',type=Path,required=True)
F=_parser.parse_args().output.resolve()
if F.exists():_parser.error('Choose a new output directory.')
F.mkdir(parents=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans','Arial'],'font.size':10.5,'axes.titlesize':11.5,'pdf.fonttype':42,'svg.fonttype':'none'})
values={};inputs={}
def read(p):
 inputs[p.name]=hashlib.sha256(p.read_bytes()).hexdigest();return pd.read_csv(p)
def save(fig,name):
 fig.canvas.draw()
 require_matplotlib_panel_alignment(fig,json_out=F/(name+'.alignment.json'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(F/f'{name}.pdf',bbox_inches='tight',pad_inches=.1)
 fig.savefig(F/f'{name}.svg',bbox_inches='tight',pad_inches=.1)
 fig.savefig(F/f'{name}.png',dpi=600,bbox_inches='tight',pad_inches=.1)
 im=Image.open(F/f'{name}.png').convert('RGB');im.save(F/f'{name}.tiff',compression='tiff_lzw',dpi=(600,600))
 im.thumbnail((1500,1350));im.save(F/f'{name}_inspection.png');plt.close(fig)

d=read(P/'inputs/landscape_national_verified.csv')
ordering=[(s,f,c) for c in ['E_to_EL','EB_to_EBL'] for s in ['temporal','spatial'] for f in ['glmm','hgb']]
d=d.set_index(['scheme','family','contrast']).loc[ordering].reset_index()
assert len(d)==8
y=np.array([0,1,2,3,5,6,7,8]);labels=[('Temporal' if r.scheme=='temporal' else 'Geographic')+' | '+('Hier.' if r.family=='glmm' else 'Boost.') for r in d.itertuples()]
fig,axs=plt.subplots(1,2,figsize=(8.4,6.1),layout='constrained')
for ax,m,title in zip(axs,['brier','logloss'],['A  Brier loss','B  Log loss']):
 point=d['delta_'+m].to_numpy()*1000;low=d['delta_'+m+'_lo'].to_numpy()*1000;high=d['delta_'+m+'_hi'].to_numpy()*1000
 ax.errorbar(point[:4],y[:4],xerr=[point[:4]-low[:4],high[:4]-point[:4]],fmt='o',c='#267e96',capsize=3)
 ax.errorbar(point[4:],y[4:],xerr=[point[4:]-low[4:],high[4:]-point[4:]],fmt='s',c='#a76a25',capsize=3)
 ax.set(yticks=y,yticklabels=labels if m=='brier' else ['']*8,ylim=(8.9,-1.25),xlabel='Change in loss × 1,000',title=title)
 ax.axvline(0,c='gray',ls='--',lw=.8)
 for j,r in d.iterrows():ax.text(.98,y[j]+.33,f'Base {r["base_"+m]:.6f}',transform=ax.get_yaxis_transform(),ha='right',fontsize=9.5,color='#414a50')
 ax.text(.02,-.85,'Ev → EL',transform=ax.get_yaxis_transform(),color='#267e96',weight='bold',fontsize=10)
 ax.text(.02,4.25,'EB → EBL',transform=ax.get_yaxis_transform(),color='#a76a25',weight='bold',fontsize=10)
values['national_landscape']=d.to_dict('records');save(fig,'figS11_national_landscape')

a=read(P/'inputs/landscape_auxiliary_verified.csv');assert len(a)==8
fig,axs=plt.subplots(2,1,figsize=(8.4,6.2),layout='constrained')
for ax,analysis,title in zip(axs,['seven_field_event_extension','static_2015_canopy'],['A  Landscapes after stronger event information','B  Static 2015 canopy added to landscape models']):
 q=a[a.analysis==analysis].copy().reset_index(drop=True);p=q.delta_brier.to_numpy()*1000;l=q.low.to_numpy()*1000;h=q.high.to_numpy()*1000
 lab=[]
 for r in q.itertuples():
  name='Hierarchical' if r.family=='glmm' else 'Boosting'
  part={'E_to_EL':'Ev → EL','EB_to_EBL':'EB → EBL','annual_landcover':'annual maps','fixed2015_landcover':'2015 maps'}[r.contrast];lab.append(f'{name} | {part}')
 ax.errorbar(p,np.arange(4),xerr=[p-l,h-p],fmt='o',capsize=3,c='#267e96')
 ax.set(yticks=np.arange(4),yticklabels=lab,ylim=(3.6,-.65),xlabel='Change in Brier loss × 1,000',title=title)
 ax.axvline(0,c='gray',ls='--',lw=.8)
 for i,r in q.iterrows():ax.text(.98,i+.28,f'Base {r.base_brier:.6f}',transform=ax.get_yaxis_transform(),ha='right',fontsize=9.5,color='#414a50')
values['auxiliary_landscape']=a.to_dict('records');save(fig,'figS12_additional_landscape')

(P/"plot_values.json").write_text(json.dumps({"inputs":inputs,"values":values},indent=2),encoding="utf-8")
