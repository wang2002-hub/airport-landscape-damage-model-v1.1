"""Verify reporting denominators and saved coding predictions; render S8 and S9."""
from pathlib import Path
import json,sys,hashlib
import pandas as pd,numpy as np
from scipy.special import expit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plot_inputs import Inputs
I=Inputs(__doc__);F=I.output/'figures'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs={}
def load(p):
 p=Path(p);inputs[p.name]=sha(p)
 if p.suffix=='.json':return json.loads(p.read_text(encoding='utf-8'))
 if p.suffix=='.parquet':return pd.read_parquet(p)
 return pd.read_csv(p)
import traceback
try:
 near=load(I.path('near_reports'))
 final=load(I.path('analysis_events'))
 audit=load(I.path('airport_year_audit'))
 quality=load(I.path('airport_year_quality'))
 annual=load(I.path('annual_coding_composition'))
 scores=load(I.path('coding_model_benchmarks'))
 fit=load(I.path('coding_model_fit'))
 saved_predictions=load(I.path('coding_target_predictions_private'))
 A=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL'];years=list(range(2015,2026))
 assert len(near)==65254 and near.known.sum()==54919 and len(final)==52103
 assert not near.event_id.duplicated().any() and not final.event_id.duplicated().any()
 assert set(final.event_id)<=set(near.loc[near.known,'event_id'])
 assert near.known.eq(near.DAMAGE_LEVEL.isin(['N','M','M?','S','D'])).all()
 near_target=near[near.airport_id.isin(A)];final_target=final[final.airport_id.isin(A)]
 rows=[]
 for a in A:
  for year in years:
   n=near_target[(near_target.airport_id==a)&(near_target.year==year)]
   f=final_target[(final_target.airport_id==a)&(final_target.year==year)]
   q=audit[(audit.airport_id==a)&(audit.year==year)].iloc[0]
   z=quality[(quality.airport_id==a)&(quality.year==year)].iloc[0]
   assert len(n)>0 and len(f)>0
   assert len(n)==q.near==z.n and n.known.sum()==q.known==z.known
   assert len(f)==q.n and f.damage_binary.sum()==q.damage
   assert np.isclose(n.known.mean(),q.label_completeness)
   rows.append(dict(airport=a,year=year,near_reports=len(n),known_labels=int(n.known.sum()),unknown_labels=int((~n.known).sum()),known_pct=100*n.known.mean(),final_reports=len(f),final_damage=int(f.damage_binary.sum())))
 annual_targets=pd.DataFrame(rows);assert len(annual_targets)==88
 assert annual_targets.final_reports.sum()==5936 and annual_targets.final_damage.sum()==309
 annual_targets.to_csv(F/'target_annual_reporting_values.csv',index=False)
 # Rebuild annual coding counts from final records, including all targets.
 damage=final[final.damage_binary==1].copy();damage['undetermined']=damage.DAMAGE_LEVEL.eq('M?').astype(int)
 annual_errors=[]
 for r in annual.itertuples():
  g=damage[(damage.target==r.target)&(damage.year==r.year)]
  assert len(g)==r.damage and g.undetermined.sum()==r.undetermined
  annual_errors.append(abs(g.undetermined.mean()-r.proportion))
 assert len(annual)==22 and max(annual_errors)<1e-12
 assert annual[~annual.target].damage.sum()==3096 and annual[annual.target].damage.sum()==309
 assert annual[~annual.target].undetermined.sum()==2303 and annual[annual.target].undetermined.sum()==252
 # Apply saved preprocessing metadata directly, avoiding any refit.
 e=fit['encoder'];beta=np.array(fit['beta']);cal=np.array(fit['calibrator'])
 assert e['scale'] is None and e['geography'] is False and e['bird_adjustment']==1
 assert e['numeric']==['year','month_sin','month_cos']
 def predict(v):
  num=pd.DataFrame({'year':(v.year.to_numpy(float)-2020)/5,'month_sin':v.month_sin.to_numpy(float),'month_cos':v.month_cos.to_numpy(float)},index=v.index)
  arr=[np.ones((len(v),1)),((num.fillna(pd.Series(e['medians']))-pd.Series(e['means']))/pd.Series(e['standard_deviations'])).to_numpy(float)]
  if e['missing_indicators']:arr.append(num[e['missing_indicators']].isna().to_numpy(float))
  names=['Intercept']+e['numeric']+[c+'_missing' for c in e['missing_indicators']]
  for col,levels in e['categories'].items():
   values=v[col].astype('string').fillna('Unknown')
   mapped=values.where(values.isin(e['retained_raw_categories'][col]),'Other')
   mapped=mapped.where(values.isin(e['observed_raw_categories'][col]),'__UNSEEN__')
   mapped=mapped.where(~mapped.eq('Other')|('Other' in levels),e['reference_categories'][col])
   for level in levels[1:]:arr.append((mapped==level).to_numpy(float)[:,None]);names.append(col+'='+level)
  X=np.hstack(arr);assert names==e['feature_names'] and X.shape[1]==len(beta) and np.isfinite(X).all()
  z=X@beta;return expit(z),expit(cal[0]+cal[1]*z)
 nat2023=damage[(~damage.target)&(damage.year==2023)];baseline=nat2023.undetermined.mean()
 assert len(nat2023)==287 and nat2023.undetermined.sum()==236
 score_errors=[];score_rows=[]
 for pop,v in [('national_test',damage[(~damage.target)&(damage.year>=2024)]),('target_damaged',damage[damage.target])]:
  raw,calibrated=predict(v);y=v.undetermined.to_numpy(float)
  for model,prediction in [('calibrated_EB',calibrated),('uncalibrated_EB',raw),('constant_national_2023',np.full(len(v),baseline))]:
   r=scores[(scores.population==pop)&(scores.model==model)].iloc[0]
   assert len(v)==r.n and y.sum()==r.undetermined
   expected=prediction.sum();brier=np.mean((prediction-y)**2);logloss=-np.mean(y*np.log(prediction)+(1-y)*np.log1p(-prediction))
   score_errors.extend([abs(expected-r.expected),abs(brier-r.brier),abs(logloss-r.logloss)])
   score_rows.append(dict(population=pop,model=model,n=len(v),undetermined=int(y.sum()),expected=expected,brier=brier,logloss=logloss))
 assert max(score_errors)<1e-10
 alltarget=final_target.set_index('event_id').loc[saved_predictions.event_id]
 _,predicted=predict(alltarget);prediction_error=float(np.max(np.abs(predicted-saved_predictions.q_undetermined.to_numpy())))
 assert prediction_error<1e-12
 pd.DataFrame(score_rows).to_csv(F/'coding_model_loss_values.csv',index=False)
 annual.to_csv(F/'annual_coding_values.csv',index=False)
 
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,'pdf.fonttype':42,'svg.fonttype':'none'})
 def save(fig,stem):
  for ext in ['pdf','svg','png','tiff']:
   kw={'dpi':600}
   if ext=='tiff':kw['pil_kwargs']={'compression':'tiff_lzw'}
   fig.savefig(F/f'{stem}.{ext}',**kw)
  fig.savefig(F/f'{stem}_inspection.png',dpi=160);plt.close(fig)
 
 # S8: complete 8 by 11 matrices, with the differing populations named.
 fig,axs=plt.subplots(2,1,figsize=(6.5,5.9));fig.subplots_adjust(left=.075,right=.89,top=.94,bottom=.065,hspace=.30)
 for k,(ax,field,title,cmap,vmin,vmax) in enumerate(zip(axs,['final_damage','known_pct'],['A  Final-cohort damage reports','B  Known labels before environmental screening'],['Blues','YlGnBu'],[0,0],[annual_targets.final_damage.max(),100])):
  mat=annual_targets.pivot(index='airport',columns='year',values=field).loc[A,years].to_numpy()
  im=ax.imshow(mat,cmap=cmap,vmin=vmin,vmax=vmax,aspect='auto')
  ax.set_xticks(range(11),[str(y)[2:] for y in years],fontsize=8);ax.set_yticks(range(8),[a[1:] for a in A],fontsize=8)
  ax.set_title(title,loc='left');ax.tick_params(length=0)
  for i,a in enumerate(A):
   for j,year in enumerate(years):
    r=annual_targets[(annual_targets.airport==a)&(annual_targets.year==year)].iloc[0]
    txt=f'{int(r.final_damage)}' if k==0 else f'{r.known_pct:.1f}%\n{int(r.known_labels)}/{int(r.near_reports)}'
    ax.text(j,i,txt,ha='center',va='center',fontsize=8 if k==0 else 6.3,color='white' if mat[i,j]>.59*vmax else 'black')
  ax.set_xlabel('Incident year (20xx)',fontsize=8)
  box=ax.get_position();cax=fig.add_axes([.91,box.y0,.018,box.height]);cb=fig.colorbar(im,cax=cax)
  cb.ax.tick_params(labelsize=7);cb.set_label('Reports' if k==0 else 'Known labels (%)',fontsize=8)
 save(fig,'figS10_annual_reporting')
 
 # S9: report coding trajectory and all saved probability-loss benchmarks.
 fig=plt.figure(figsize=(6.5,5.8));gs=fig.add_gridspec(2,2,left=.18,right=.98,top=.93,bottom=.14,hspace=.52,wspace=.35)
 ax=fig.add_subplot(gs[0,:])
 for target,color,label in [(False,'#236783','National source'),(True,'#b34b35','Eight targets')]:
  g=annual[annual.target==target].sort_values('year');ax.plot(g.year,100*g.proportion,'o-',color=color,label=label,lw=1,ms=3)
 ax.set(ylim=(0,105),xticks=years,xlabel='Incident year (20xx)',ylabel='M? among damage (%)',title='A  Annual extent coding in the final cohort')
 ax.set_xticklabels([str(y)[2:] for y in years]);ax.grid(alpha=.12);ax.legend(fontsize=8,frameon=False,loc='lower right')
 models=['calibrated_EB','uncalibrated_EB','constant_national_2023'];labels=['Calibrated','Uncalibrated','2023 constant']
 for k,(metric,title) in enumerate([('brier','B  Conditional coding Brier loss'),('logloss','C  Conditional coding log loss')]):
  ax=fig.add_subplot(gs[1,k]);yy=np.arange(3)
  for offset,pop,color,label in [(-.14,'national_test','#236783','National test (n = 669)'),(.14,'target_damaged','#b34b35','Targets (n = 309)')]:
   z=scores[scores.population==pop].set_index('model').loc[models]
   ax.barh(yy+offset,z[metric],height=.24,color=color,label=label)
   for i,r in enumerate(z.itertuples()):ax.text(getattr(r,metric)+(.004 if metric=='brier' else .012),i+offset,f'{getattr(r,metric):.3f}',va='center',fontsize=7)
  ax.set(yticks=yy,yticklabels=labels,xlabel='Loss in original units',title=title,xlim=(0,.33 if metric=='brier' else 1.02),ylim=(2.5,-.5));ax.tick_params(axis='y',labelsize=8);ax.grid(axis='x',alpha=.12)
  if k==1:ax.set_yticklabels([])
  if k==0:handles,legendlabels=ax.get_legend_handles_labels()
 fig.legend(handles,legendlabels,loc='lower center',bbox_to_anchor=(.5,.015),ncol=2,fontsize=8,frameon=False)
 save(fig,'figS09_coding_diagnostics')
 build={'input_sha256':inputs,'figure_numbers':[8,9],'new_model_fits':0,'new_preprocessing_fits':0,'new_random_draws':0,'annual_target_cells':88,'final_target_reports':int(annual_targets.final_reports.sum()),'final_target_damage':int(annual_targets.final_damage.sum()),'near_target_reports':int(annual_targets.near_reports.sum()),'near_target_known_labels':int(annual_targets.known_labels.sum()),'annual_coding_rows':22,'loss_comparisons':6,'loss_values':12,'maximum_annual_proportion_error':max(annual_errors),'maximum_score_error':max(score_errors),'maximum_saved_prediction_error':prediction_error,'constant_coding_probability':baseline,'exports':{p.name:sha(p) for p in F.iterdir() if p.is_file()}}
 (I.output/'results/reporting_coding_figure_build.json').write_text(json.dumps(build,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in build.items() if k not in ['input_sha256','exports']},ensure_ascii=False,indent=2))
except Exception:
 (I.output/'logs/reporting_coding_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
