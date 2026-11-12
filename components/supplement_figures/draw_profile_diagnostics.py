"""Render saved calibration, limit sensitivity and rank results without fitting."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter,NullFormatter
from plot_inputs import Inputs
I=Inputs(__doc__);F=I.output/'figures'
inputs={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 p=Path(p);inputs[p.name]=sha(p)
 return json.loads(p.read_text(encoding='utf-8')) if p.suffix=='.json' else pd.read_csv(p)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,'axes.labelsize':9,'pdf.fonttype':42,'svg.fonttype':'none'})
BLUE='#245f83';RED='#b34b35';TEAL='#247b72';GRAY='#7e8790'
order=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']
display={}
def save(fig,stem):
 for ext in ['pdf','svg','png','tiff']:
  kwargs={'dpi':600}
  if ext=='tiff':kwargs['pil_kwargs']={'compression':'tiff_lzw'}
  fig.savefig(F/f'{stem}.{ext}',**kwargs)
 fig.savefig(F/f'{stem}_inspection.png',dpi=160);plt.close(fig)

# S2: separate calibration populations from descriptive standardization.
import traceback
try:
 c=read(I.path('national_calibration_deciles'))
 s=read(I.path('case_mix_standardization')).set_index('airport').loc[[a[1:] for a in order]]
 assert len(c)==20 and set(c.family)=={'glmm','hgb'}
 for _,q in c.groupby('family'):
  assert len(q)==10 and q.n.sum()==11124 and q.damage.sum()==669
  assert np.allclose(q.observed,q.damage/q.n)
  assert ((q.low<=q.observed)&(q.observed<=q.high)).all()
 assert s.target_n.sum()==5936 and (s.supported_n+s.unsupported_n==s.target_n).all()
 assert np.allclose(s.support_pct,100*s.supported_n/s.target_n)
 fig=plt.figure(figsize=(6.5,5.6),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1,1.1])
 for k,(fam,title) in enumerate([('glmm','A  Hierarchical EBL'),('hgb','B  Boosting EBL')]):
  ax=fig.add_subplot(gs[0,k]);q=c[c.family==fam].sort_values('decile')
  ax.errorbar(q.predicted*100,q.observed*100,yerr=[100*(q.observed-q.low),100*(q.high-q.observed)],fmt='o-',ms=3,lw=.8,capsize=2,color=BLUE)
  limit=np.ceil(max(c.predicted.max(),c.high.max())*100/5)*5
  ax.plot([0,limit],[0,limit],ls='--',color=GRAY,lw=.8);ax.set(xlim=(0,limit),ylim=(0,limit),xlabel='Mean predicted damage (%)',ylabel='Observed damage (%)',title=title)
  ax.grid(alpha=.12)
 ax=fig.add_subplot(gs[1,:]);yy=np.arange(8)
 ax.hlines(yy,s.standardized_reference_pct,s.supported_target_observed_pct,color=GRAY,lw=1.2)
 ax.scatter(s.standardized_reference_pct,yy,c=BLUE,s=27,label='Reweighted national proportion',zorder=3)
 ax.scatter(s.supported_target_observed_pct,yy,c=RED,s=27,marker='s',label='Supported target proportion',zorder=3)
 ax.axvline(s.national_observed_pct.iloc[0],c=GRAY,ls='--',lw=.8,label='Crude national proportion')
 ax.set(yticks=yy,yticklabels=s.index,ylim=(7.6,-.6),xlim=(2.2,11.3),xlabel='Recorded damage in the stated population (%)')
 ax.set_title('C  Composition standardization',loc='left')
 ax.set_xticks([3,4,5,6,7,8]);ax.grid(axis='x',alpha=.12)
 for i,r in enumerate(s.itertuples()):ax.text(9.05,i,f'{r.supported_n:,}/{r.target_n:,} ({r.support_pct:.1f}%)',va='center',fontsize=7.3)
 ax.text(9.05,-.95,'Supported / all reports',fontsize=7.3)
 ax.legend(loc='lower center',bbox_to_anchor=(.5,-.49),fontsize=7.5,ncol=1,frameon=False)
 save(fig,'figS02_calibration_and_composition')
 display['calibration']=c.to_dict('records');display['standardization']=s.reset_index().to_dict('records')
 
 d=read(I.path('airport_partial_pooling'));fit=read(I.path('partial_pooling_fit'));t=d.set_index('airport').loc[order]
 assert len(d)==1383 and d.n.sum()==52103 and d.target.sum()==8
 assert (d.rank_low<=d.rank_high).all() and (d.low_b<d.high_b).all()
 assert np.allclose(d.conditional_odds_multiplier,np.exp(d.conditional_mean_b))
 assert np.isclose(np.median(d.rank_high-d.rank_low),fit['median_rank_width'])
 fig=plt.figure(figsize=(6.5,5.6),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1.1,1])
 a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[0,1]);c=fig.add_subplot(gs[1,:]);y=np.arange(8)
 a.errorbar(t.conditional_mean_b,y,xerr=[t.conditional_mean_b-t.low_b,t.high_b-t.conditional_mean_b],fmt='o',ms=4,color=BLUE,capsize=2)
 a.axvline(0,c=GRAY,lw=.8,ls='--');a.set(xlabel='Conditional log-odds effect',title='A  Target airport effects')
 b.errorbar(t.rank_mean,y,xerr=[t.rank_mean-t.rank_low,t.rank_high-t.rank_mean],fmt='o',ms=4,color=BLUE,capsize=2)
 b.set(xlabel='Rank among 1,383 airports',title='B  Conditional target ranks',xlim=(0,1384),xticks=[1,500,1000,1383])
 for ax in [a,b]:ax.set_yticks(y,[x[1:] for x in order]);ax.invert_yaxis();ax.grid(axis='x',alpha=.12)
 rest=d[~d.target];c.scatter(rest.n,rest.rank_high-rest.rank_low,s=9,alpha=.22,color=BLUE,rasterized=True,label='National source airports')
 c.scatter(t.n,t.rank_high-t.rank_low,s=25,color=RED,marker='D',label='Eight targets',zorder=3)
 c.axhline(fit['median_rank_width'],c=GRAY,lw=.8,ls='--',label=f'Median width: {fit["median_rank_width"]:,.0f}')
 c.set(xscale='log',xlabel='Eligible reports per airport',ylabel='95% rank interval width',title='C  Rank uncertainty across all 1,383 airports',ylim=(0,1400))
 c.legend(fontsize=7.5,loc='lower left',frameon=False);c.grid(alpha=.12)
 save(fig,'figS05_conditional_airport_ranks')
 display['conditional_target_effects']=t.reset_index().to_dict('records')
 d.to_csv(F/'all_airport_conditional_effects_and_ranks.csv',index=False)
 (I.output/'results/profile_diagnostic_display_values.json').write_text(json.dumps(display,ensure_ascii=False,indent=2),encoding='utf-8')
 record={'input_sha256':inputs,'figure_numbers':[2,3,4],'new_fits':0,'new_random_draws':0,'calibration_groups':20,'composition_airports':8,'national_references':5,'national_evaluation_airports':1375,'national_zero_damage_airports':602,'conditional_rank_airports':1383,'rank_draws_reused':fit['posterior_draws'],'median_rank_interval_width':fit['median_rank_width']}
 (I.output/'results/profile_diagnostic_figure_build.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(record,ensure_ascii=False,indent=2))
except Exception:
 (I.output/'logs/profile_diagnostics_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
