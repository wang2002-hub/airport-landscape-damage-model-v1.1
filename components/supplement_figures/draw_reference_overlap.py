"""Reconstruct overlap sets from saved bounds and render the complete comparison."""
from pathlib import Path
import sys,json,hashlib,itertools
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from plot_inputs import Inputs
I=Inputs(__doc__);F=I.output/'figures'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs={}
def load(p):
 p=Path(p);inputs[p.name]=sha(p);return pd.read_csv(p)
import traceback
try:
 base=load(I.path('national_funnel_limit_audit'))
 wide=load(I.path('national_funnel_width_sensitivity'))
 factors=load(I.path('funnel_dispersion_factors'))
 saved=load(I.path('reference_flag_overlap_sensitivity'))
 models=['ordinary_EB','glmm_EB','glmm_EBL','hgb_EB','hgb_EBL'];labels=['O-EB','H-EB','H-EBL','G-EB','G-EBL']
 controls=['conditional','all','expected_ge5','reports_ge100']
 allids=set(base.airport);common=set(base[(base.model=='glmm_EBL')&(base.E>=5)].airport)
 assert len(allids)==1375 and len(common)==144
 assert not allids.intersection({'KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL'})
 sets={};rows=[];members=[];factor_error=[];bound_error=[]
 for m in models:
  q=base[base.model==m].set_index('airport');assert set(q.index)==allids and q.n.sum()==46167 and q.O.sum()==3096
  assert (q.O==0).sum()==602
  flag=(q.O<q.lower_count_998-1e-9)|(q.O>q.upper_count_998+1e-9)
  assert np.array_equal(flag,q.conditional_flag_998)
  sets['conditional',m]=set(q.index[flag])
  for c in controls[1:]:
   selected=q if c=='all' else q[q.E>=5] if c=='expected_ge5' else q[q.n>=100]
   phi=max(1,float((selected.z**2).mean()))
   f=factors[(factors.model==m)&(factors.estimation_set==c)].iloc[0]
   assert len(selected)==f.estimation_airports;factor_error.append(abs(phi-f.phi))
   low=np.maximum(0,q.E+np.sqrt(phi)*(np.minimum(q.lower_count_998,q.E)-q.E))
   high=np.minimum(q.n,q.E+np.sqrt(phi)*(np.maximum(q.upper_count_998,q.E)-q.E))
   z=wide[(wide.model==m)&(wide.estimation_set==c)&(wide.label.astype(str)=='998')].set_index('airport').loc[q.index]
   bound_error.extend(np.abs(z.lower_count-low).tolist());bound_error.extend(np.abs(z.upper_count-high).tolist())
   flags=(q.O<low-1e-9)|(q.O>high+1e-9)
   assert np.array_equal(flags,z.flag)
   sets[c,m]=set(q.index[flags])
 assert max(factor_error)<1e-12 and max(bound_error)<1e-10
 for c in controls:
  for pop,ids in [('all',allids),('primary_expected_ge5',common)]:
   for m in models:
    for a in sorted(sets[c,m]&ids):members.append(dict(control=c,population=pop,model=m,airport=a))
   for a,b in itertools.combinations(sorted(models),2):
    sa=sets[c,a]&ids;sb=sets[c,b]&ids;inter=sa&sb;union=sa|sb
    r=dict(control=c,population=pop,model_a=a,model_b=b,flags_a=len(sa),flags_b=len(sb),intersection=len(inter),union=len(union),jaccard=len(inter)/len(union) if union else np.nan)
    old=saved[(saved.control==c)&(saved.population==pop)&(saved.model_a==a)&(saved.model_b==b)]
    assert len(old)==1
    for field in ['flags_a','flags_b','intersection','union','jaccard']:assert np.isclose(r[field],old.iloc[0][field],equal_nan=True,rtol=1e-12,atol=1e-14)
    rows.append(r)
 assert len(rows)==len(saved)==80
 assert all(sets[c,m]<=common for c in controls for m in models)
 checks=pd.DataFrame(rows);checks.to_csv(F/'reference_overlap_verified.csv',index=False)
 pd.DataFrame(members).to_csv(F/'reference_exceedance_membership.csv',index=False)
 pd.DataFrame({'airport':sorted(common)}).to_csv(F/'common_evaluation_airports.csv',index=False)
 
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':9.5,'pdf.fonttype':42,'svg.fonttype':'none'})
 fig,axes=plt.subplots(2,2,figsize=(6.5,6.0))
 fig.subplots_adjust(left=.105,right=.97,top=.94,bottom=.18,wspace=.34,hspace=.34)
 titles=['A  Conditional 99.8% limits','B  Factor from all airports','C  Factor from E ≥ 5','D  Factor from n ≥ 100']
 for ax,c,title in zip(axes.flat,controls,titles):
  mat=np.full((5,5),np.nan)
  for i in range(5):
   for k in range(i+1,5):
    a=sets[c,models[i]];b=sets[c,models[k]];u=len(a|b);inter=len(a&b)
    val=inter/u if u else np.nan;mat[i,k]=val
  cmap=plt.get_cmap('Blues').copy();cmap.set_bad('white')
  ax.imshow(np.ma.masked_invalid(mat),vmin=0,vmax=1,cmap=cmap)
  for i in range(5):
   ax.add_patch(plt.Rectangle((i-.5,i-.5),1,1,color='#e9ecef',ec='white',lw=1))
   ax.text(i,i,f'k={len(sets[c,models[i]])}',ha='center',va='center',fontsize=7.7)
   for k in range(i+1,5):
    a=sets[c,models[i]];b=sets[c,models[k]];u=len(a|b);inter=len(a&b)
    ax.text(k,i,f'{inter}/{u}\n{inter/u:.3f}' if u else '0/0\nNA',ha='center',va='center',fontsize=7.1,color='white' if u and inter/u>.6 else 'black')
  ax.set_xticks(range(5),labels,rotation=35,ha='right',fontsize=7.7)
  ax.set_yticks(range(5),labels,fontsize=7.7);ax.set_title(title,loc='left',pad=8)
  ax.spines[['top','right','bottom','left']].set_visible(False);ax.tick_params(length=0)
 cax=fig.add_axes([.29,.075,.46,.02]);cb=fig.colorbar(ScalarMappable(norm=Normalize(0,1),cmap='Blues'),cax=cax,orientation='horizontal')
 cb.set_ticks([0,.5,1]);cb.set_label('Jaccard overlap',fontsize=8);cb.ax.tick_params(labelsize=8)
 stem='figS08_reference_limit_overlap'
 for ext in ['pdf','svg','png','tiff']:
  kw={'dpi':600}
  if ext=='tiff':kw['pil_kwargs']={'compression':'tiff_lzw'}
  fig.savefig(F/f'{stem}.{ext}',**kw)
 fig.savefig(F/f'{stem}_inspection.png',dpi=160);plt.close(fig)
 build={'input_sha256':inputs,'figure_numbers':[7],'new_fits':0,'new_random_draws':0,'reference_models':5,'control_rules':4,'pairwise_comparisons_verified':80,'pairwise_comparisons_displayed':40,'evaluation_populations':{'all':1375,'common_primary_expected_ge5':144},'all_exceedances_within_common_subset':True,'maximum_factor_error':max(factor_error),'maximum_widened_bound_error':max(bound_error),'exceedance_counts':{c:{m:len(sets[c,m]) for m in models} for c in controls},'overlap_ranges':{c:[float(checks[(checks.control==c)&(checks.population=='all')].jaccard.min()),float(checks[(checks.control==c)&(checks.population=='all')].jaccard.max())] for c in controls},'exports':{p.name:sha(p) for p in F.iterdir() if p.is_file()}}
 (I.output/'results/reference_overlap_figure_build.json').write_text(json.dumps(build,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in build.items() if k not in ['input_sha256','exports']},ensure_ascii=False,indent=2))
except Exception:
 (I.output/'logs/reference_overlap_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
