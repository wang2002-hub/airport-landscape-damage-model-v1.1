from pathlib import Path
import itertools
import numpy as np,pandas as pd
from scipy.stats import spearmanr

def run(paths,O):
    I=O
    source=[paths[k] for k in ['national_profiles','rank_concordance','flag_overlap']]
    n=pd.read_csv(source[0]);r=pd.read_csv(source[1]);f=pd.read_csv(source[2])
    models=['ordinary_EB','glmm_EB','glmm_EBL','hgb_EB','hgb_EBL'];labels=['O-EB','H-EB','H-EBL','G-EB','G-EBL']
    assert n.model.nunique()==5 and n.groupby('model').size().eq(1375).all()
    wide=n.pivot(index='airport',columns='model',values='OE')[models]
    ids=n.query("model=='glmm_EBL' and E>=5").airport
    x=wide.loc[ids];assert len(x)==144 and x.gt(0).all().all()
    n.to_csv(I/'national_profiles.csv',index=False);r.to_csv(I/'saved_rank_concordance.csv',index=False);f.to_csv(I/'saved_flag_overlap.csv',index=False)
    members=[];sets={};flags={};rows=[]
    for model in models:
     q=x[model];k=int(np.ceil(len(q)*.1));threshold=q.nlargest(k).min();sets[model]=set(q.index[q>=threshold]);flags[model]=set(n.loc[(n.model==model)&n.conditional_flag_998,'airport'])&set(ids)
     for airport in ids:members.append({'airport':airport,'model':model,'OE':float(x.loc[airport,model]),'top_decile':airport in sets[model],'conditional_flag_998':airport in flags[model],'decile_cutoff':threshold})
    for ma,mb in itertools.combinations(models,2):
     row={'model_a':ma,'model_b':mb,'label':labels[models.index(ma)]+' / '+labels[models.index(mb)],'airports':144,'spearman':float(spearmanr(x[ma],x[mb]).statistic)}
     for name,groups in [('top',sets),('flag',flags)]:
      sa,sb=groups[ma],groups[mb];row.update({name+'_a':len(sa),name+'_b':len(sb),name+'_intersection':len(sa&sb),name+'_union':len(sa|sb),name+'_jaccard':len(sa&sb)/len(sa|sb)})
     saved=r[(r.subset=='primary_expected_ge5')&(((r.model_a==ma)&(r.model_b==mb))|((r.model_a==mb)&(r.model_b==ma)))].iloc[0]
     assert np.allclose([row['spearman'],row['top_jaccard'],row['flag_jaccard']],[saved.spearman,saved.top_decile_jaccard,saved.flag_jaccard])
     rows.append(row)
    pd.DataFrame(rows).to_csv(I/'paired_set_comparisons.csv',index=False);pd.DataFrame(members).to_csv(I/'subset_membership.csv',index=False)
    scatter=x[['ordinary_EB','glmm_EBL']].copy();scatter['different_top_membership']=[a in (sets['ordinary_EB']^sets['glmm_EBL']) for a in scatter.index]
    scatter.reset_index().to_csv(I/'paired_profiles.csv',index=False)
    matrix=wide.corr(method='spearman');matrix.to_csv(I/'full_population_spearman_matrix.csv')

if __name__=='__main__':
    from input_config import execute
    execute(run,['national_profiles','rank_concordance','flag_overlap'])
