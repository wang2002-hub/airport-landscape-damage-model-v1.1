"""Verify saved uncertainty summaries and render two supplementary figures."""
from pathlib import Path
import sys,json,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter,NullFormatter
from plot_inputs import Inputs
I=Inputs(__doc__);F=I.output/'figures'
inputs={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 p=Path(p);inputs[p.name]=sha(p)
 if p.suffix=='.json':return json.loads(p.read_text(encoding='utf-8'))
 if p.suffix=='.parquet':return pd.read_parquet(p)
 return pd.read_csv(p)
import traceback
try:
 interval=load(I.path('local_absolute_intervals'))
 draws=load(I.path('local_bootstrap_values'))
 meta=load(I.path('bootstrap_summary'))
 primary=load(I.path('primary_joint_intervals'))
 deletion=load(I.path('leave_one_year_out'))
 summary=load(I.path('leave_one_year_out_summary'))
 annual=load(I.path('local_annual_predictions'))
 pred=load(I.path('temporal_0_glmm_EBL_predictions'))
 pred=pred[pred.dataset=='target'].copy()
 order=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']
 scopes=['fixed_iid_year','fixed_block2','development_only','joint_iid_year','joint_block2']
 assert set(interval.scope)==set(draws.scope)==set(scopes)
 assert len(pred)==5936 and pred.damage_binary.sum()==309 and set(pred.airport_id)==set(order)
 assert meta['successful']==498 and meta['attempts']==500 and meta['failures']==[224,336]
 counts={'fixed_iid_year':2000,'fixed_block2':2000,'development_only':498,'joint_iid_year':9960,'joint_block2':9960}
 quantile_errors=[];point_errors=[]
 for r in interval.itertuples():
  g=draws[(draws.scope==r.scope)&(draws.airport==r.airport)]
  assert len(g)==counts[r.scope]==r.draws
  if r.scope.startswith(('joint','development')):
   assert g.replicate.nunique()==498 and r.development_fits==498
   assert g.groupby('replicate').size().eq(1 if r.scope=='development_only' else 20).all()
  else:assert r.development_fits==0
  lo,hi=np.quantile(g[r.measure],[.025,.975]);quantile_errors.extend([abs(lo-r.low),abs(hi-r.high)])
  q=pred[pred.airport_id==r.airport];o=q.damage_binary.sum();e=q.p_calibrated.sum();n=len(q)
  values={'predicted':e/n,'bias_pp':100*(e-o)/n,'oe':o/e,'observed_minus_expected':o-e}
  point_errors.append(abs(values[r.measure]-r.estimate))
 assert max(quantile_errors)<1e-10 and max(point_errors)<1e-10
 for r in primary.itertuples():
  z=interval[(interval.airport==r.airport)&(interval.measure==r.measure)&(interval.scope=='joint_iid_year')].iloc[0]
  assert np.allclose([r.estimate,r.low,r.high],[z.estimate,z.low,z.high],rtol=1e-12,atol=1e-12)
 
 # Independent deterministic reconstruction of all annual deletion values.
 assert len(deletion)==88 and len(annual)==88 and len(summary)==8
 deletion_errors=[];annual_errors=[]
 for r in deletion.itertuples():
  q=pred[(pred.airport_id=='K'+r.airport)&(pred.year!=r.omitted_year)]
  n=len(q);o=q.damage_binary.sum();e=q.p_calibrated.sum()
  assert n==r.retained_n and o==r.retained_damage
  deletion_errors.extend([abs(100*(e-o)/n-r.bias_pp),abs(o/e-r.oe)])
 for r in annual.itertuples():
  q=pred[(pred.airport_id=='K'+r.airport)&(pred.year==r.year)]
  assert len(q)==r.reports and q.damage_binary.sum()==r.damage
  annual_errors.extend([abs(q.p_calibrated.mean()*100-r.predicted_pct),abs(q.damage_binary.mean()*100-r.observed_pct)])
 for r in summary.itertuples():
  g=deletion[deletion.airport==r.airport]
  assert set(g.omitted_year)==set(range(2015,2026))
  assert np.allclose([r.bias_min_pp,r.bias_max_pp,r.oe_min,r.oe_max],[g.bias_pp.min(),g.bias_pp.max(),g.oe.min(),g.oe.max()],atol=1e-12,rtol=1e-12)
 assert max(deletion_errors)<1e-10 and max(annual_errors)<1e-10
 
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,'axes.labelsize':9,'pdf.fonttype':42,'svg.fonttype':'none'})
 colors=['#8d969e','#a15a3c','#765a90','#236783','#287f71'];markers=['o','s','^','D','v']
 labels=['Fixed model + years','Fixed model + 2-year blocks','Development only','Development + years (primary)','Development + 2-year blocks']
 def save(fig,stem):
  for ext in ['pdf','svg','png','tiff']:
   kwargs={'dpi':600}
   if ext=='tiff':kwargs['pil_kwargs']={'compression':'tiff_lzw'}
   fig.savefig(F/f'{stem}.{ext}',**kwargs)
  fig.savefig(F/f'{stem}_inspection.png',dpi=160);plt.close(fig)
 
 # S5: common estimates, five separately identified uncertainty procedures.
 fig,axs=plt.subplots(1,2,figsize=(6.5,5.9),sharey=True)
 fig.subplots_adjust(left=.10,right=.98,top=.93,bottom=.22,wspace=.20)
 y=np.arange(8)
 for ax,measure,title in zip(axs,['bias_pp','oe'],['A  Mean probability difference','B  Observed to expected ratio']):
  for k,(scope,color,marker,label) in enumerate(zip(scopes,colors,markers,labels)):
   d=interval[(interval.scope==scope)&(interval.measure==measure)].set_index('airport').loc[order]
   yy=y+(k-2)*.12
   ax.hlines(yy,d.low,d.high,color=color,lw=1.2 if scope=='joint_iid_year' else .8)
   ax.scatter(d.estimate,yy,color=color,marker=marker,s=17 if scope=='joint_iid_year' else 12,label=label,zorder=3)
  ax.set(yticks=y,yticklabels=[a[1:] for a in order],ylim=(7.6,-.6),title=title)
  ax.grid(axis='x',alpha=.15)
  if measure=='oe':
   ax.set_xscale('log');ax.axvline(1,c='#444444',ls='--',lw=.8);ax.set_xlabel('O/E (log scale)')
   ax.set_xticks([.4,.6,1,1.5,2]);ax.xaxis.set_major_formatter(ScalarFormatter());ax.xaxis.set_minor_formatter(NullFormatter())
  else:ax.axvline(0,c='#444444',ls='--',lw=.8);ax.set_xlabel('Predicted minus observed (pp)')
 handles,legendlabels=axs[0].get_legend_handles_labels()
 fig.legend(handles,legendlabels,loc='lower center',bbox_to_anchor=(.5,.018),ncol=2,frameon=False,fontsize=8,columnspacing=1.2,handletextpad=.5)
 save(fig,'figS06_local_uncertainty_sources')
 
 # S6: every deletion value plus its min-max range and the complete-period estimate.
 fig,axs=plt.subplots(1,2,figsize=(6.5,5.3),sharey=True)
 fig.subplots_adjust(left=.10,right=.98,top=.92,bottom=.21,wspace=.20)
 full=primary[primary.measure.isin(['bias_pp','oe'])]
 for ax,measure,title in zip(axs,['bias_pp','oe'],['A  Mean probability difference','B  Observed to expected ratio']):
  for i,a in enumerate(order):
   d=deletion[deletion.airport==a[1:]].sort_values('omitted_year');point=full[(full.airport==a)&(full.measure==measure)].estimate.iloc[0]
   ax.plot([d[measure].min(),d[measure].max()],[i,i],color='#9cabb5',lw=2,label='Deletion range' if i==0 else None,zorder=1)
   offsets=(d.omitted_year.to_numpy()-2020)*.028
   ax.scatter(d[measure],i+offsets,color='#236783',s=14,alpha=.8,label='One omitted year' if i==0 else None,zorder=2)
   ax.scatter([point],[i],color='#b34b35',marker='D',s=25,label='Complete 2015–2025' if i==0 else None,zorder=3)
  ax.set(yticks=y,yticklabels=[a[1:] for a in order],ylim=(7.5,-.5),title=title);ax.grid(axis='x',alpha=.15)
  if measure=='oe':
   ax.set_xscale('log');ax.axvline(1,c='#444444',ls='--',lw=.8);ax.set_xlabel('O/E (log scale)')
   ax.set_xticks([.8,1,1.2,1.5]);ax.xaxis.set_major_formatter(ScalarFormatter());ax.xaxis.set_minor_formatter(NullFormatter())
  else:ax.axvline(0,c='#444444',ls='--',lw=.8);ax.set_xlabel('Predicted minus observed (pp)')
 handles,legendlabels=axs[0].get_legend_handles_labels()
 fig.legend(handles,legendlabels,loc='lower center',bbox_to_anchor=(.5,.045),ncol=3,frameon=False,fontsize=8,columnspacing=.9)
 save(fig,'figS07_annual_deletion_influence')
 interval.to_csv(F/'local_interval_values.csv',index=False)
 deletion.to_csv(F/'annual_deletion_values.csv',index=False)
 record={'input_sha256':inputs,'figure_numbers':[5,6],'new_fits':0,'new_random_draws':0,'target_airports':8,'target_reports':5936,'target_damage':309,'interval_procedures':5,'displayed_interval_rows':80,'verified_interval_rows':len(interval),'verified_interval_endpoints':len(quantile_errors),'successful_development_fits':498,'attempted_development_fits':500,'saved_draws_per_airport':counts,'annual_deletion_rows':88,'reconstructed_annual_rows':88,'maximum_saved_quantile_error':max(quantile_errors),'maximum_point_error':max(point_errors),'maximum_deletion_error':max(deletion_errors),'maximum_annual_error':max(annual_errors),'JFK_deletion_oe_range':summary[summary.airport=='JFK'][['oe_min','oe_max']].iloc[0].tolist(), 'exports':{p.name:sha(p) for p in F.iterdir() if p.is_file()}}
 (I.output/'results/local_uncertainty_figure_build.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in record.items() if k not in ['input_sha256','exports']},ensure_ascii=False,indent=2))
except Exception:
 (I.output/'logs/local_uncertainty_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
