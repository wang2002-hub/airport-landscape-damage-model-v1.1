from pathlib import Path
import csv,json,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator,FixedFormatter,NullLocator
sys.path.insert(0,str(Path(__file__).resolve().parent/'qa_tools'))
from audit_panel_alignment import require_matplotlib_panel_alignment
def save(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def run(paths,O):
    points,intervals,dispersion,funnel=[paths[k] for k in ['points', 'intervals', 'dispersion', 'funnel']]
    pool=next(x for x in rows(points) if x['scheme']=='year' and x['airport']=='Pooled')
    ivals={x['metric']:x for x in rows(intervals) if x['scheme']=='year' and x['airport']=='Pooled'}
    national=next(x for x in rows(dispersion) if x['endpoint']=='documented_damage' and x['subset']=='all_available')
    f=next(x for x in rows(funnel) if x['model']=='glmm_EBL' and x['display_set']=='all' and x['label']=='998')
    counts=[int(f['conditional_flags']),int(f['width_flags_phi_all'])]
    assert counts==[6,2] and int(national['airports'])==1375
    assert float(pool['n'])==5936 and float(pool['O'])==309
    assert all(float(ivals[k]['low'])<1<float(ivals[k]['high']) for k in ['OE','OE_undetermined','OE_documented'])
    source=[]
    for lab,val in zip(['Conditional national flags','Dispersion-widened national flags'],counts):source.append({'panel':'a','quantity':lab,'estimate':val,'lower':'','upper':''})
    for panel,k,lab in [('b','OE','Pooled any damage'),('c','OE_undetermined','Pooled undetermined extent'),('c','OE_documented','Pooled documented extent')]:
     x=ivals[k];source.append({'panel':panel,'quantity':lab,'estimate':float(x['estimate']),'lower':float(x['low']),'upper':float(x['high'])})
    source.append({'panel':'c','quantity':'National documented-extent Pearson dispersion','estimate':float(national['factor_max_one']),'lower':'','upper':''})
    with (O/'source_data.csv').open('w',encoding='utf-8',newline='') as f:
     writer=csv.DictWriter(f,fieldnames=['panel','quantity','estimate','lower','upper']);writer.writeheader();writer.writerows(source)

    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7,'pdf.fonttype':42,'svg.fonttype':'none','axes.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'xtick.labelsize':6.5,'ytick.labelsize':6.5})
    fig=plt.figure(figsize=(13/2.54,10.7/2.54),facecolor='white')
    ink='#172E3A';blue='#216C86';amber='#B45D28';muted='#536570';light='#D4DEE2'
    def label(x,y,t,size=7,weight='normal',color=ink,ha='left'):
     return fig.text(x,y,t,fontsize=size,fontweight=weight,color=color,ha=ha,va='top',linespacing=1.2)
    label(.045,.975,'Interpreting airport bird-strike damage reports',9,'bold')
    label(.045,.922,'52,103 eligible reports | 2015–2025',7.5)
    label(.045,.880,'Primary hierarchical event–bird–landscape reference',6.8,color=muted)
    label(.045,.817,'a  National profiles',8,'bold')
    label(.555,.817,'b  Eight held-out airports',8,'bold')
    label(.045,.775,'1,375 airports · 99.8% count limits',6.7)
    label(.555,.775,f"Pooled O/E  {float(pool['OE']):.2f}",7.5,'bold',blue)
    aa=fig.add_axes([.085,.587,.35,.145],label='a')
    aa.patch.set_visible(False)
    aa.bar([0,1],counts,width=.48,color=[blue,amber],zorder=2)
    aa.set(xlim=(-.6,1.6),ylim=(0,7.6),yticks=[])
    aa.set_xticks([0,1],['Conditional','Widened']);aa.tick_params(length=0,pad=4)
    for sp in ['left','right','top']:aa.spines[sp].set_visible(False)
    aa.spines['bottom'].set_color(light)
    for j,v in enumerate(counts):aa.text(j,v+.6,str(v),ha='center',va='bottom',fontsize=9,fontweight='bold',color=ink)
    label(.045,.523,'Flags depend on the\ndispersion specification.',6.7)
    bb=fig.add_axes([.595,.587,.35,.145],label='b')
    def ratio_axis(ax,xlim,ticks,labels):
     assert min(xlim)>0 and min(ticks)>0
     ax.patch.set_visible(False)
     ax.set_xscale('log');ax.set_xlim(*xlim);ax.set_yticks([])
     ax.axvline(1,color=muted,ls=(0,(3,3)),lw=.65,zorder=0)
     ax.xaxis.set_major_locator(FixedLocator(ticks));ax.xaxis.set_major_formatter(FixedFormatter(labels));ax.xaxis.set_minor_locator(NullLocator());ax.tick_params(length=2,pad=3)
     for sp in ['left','right','top']:ax.spines[sp].set_visible(False)
     ax.spines['bottom'].set_color(light)
    def point(ax,x,y,color,marker='o'):
     v,lo,hi=[float(x[k]) for k in ['estimate','low','high']]
     assert 0 < lo <= v <= hi, 'Log-axis intervals must be positive and ordered'
     ax.errorbar(v,y,xerr=[[v-lo],[hi-v]],fmt=marker,ms=4.5,color=color,elinewidth=1.3,capsize=3,capthick=.9)
    ratio_axis(bb,(.8,1.5),[.8,1,1.5],['0.8','1','1.5']);bb.set_ylim(0,1);point(bb,ivals['OE'],.5,blue)
    label(.555,.523,'Joint 95% interval  0.91–1.31\n5,936 reports · 309 damage outcomes',6.7)

    label(.045,.440,'c  Pooled damage-extent decomposition',8,'bold')
    label(.045,.400,'Annual national extent proportions · unchanged report collection',6.5)
    cc=fig.add_axes([.55,.245,.395,.12],label='c')
    ratio_axis(cc,(.4,1.6),[.5,1,1.5],['0.5','1','1.5']);cc.set_ylim(-.6,1.6)
    point(cc,ivals['OE_undetermined'],1,amber,'o');point(cc,ivals['OE_documented'],0,blue,'s')
    for y,key,txt,col in [(1,'OE_undetermined','Undetermined extent (252)',amber),(0,'OE_documented','Documented extent (57)',blue)]:
     yy=.245+.12*(y+.6)/2.2
     label(.06,yy+.017,txt,6.7,color=col)
     label(.06,yy-.009,f"O/E  {float(ivals[key]['estimate']):.2f}",6.5,color=muted)
    label(.045,.201,'Both joint 95% subtype intervals include 1.',6.7)
    label(.045,.164,f"National documented-extent dispersion persists (Pearson factor {float(national['factor_max_one']):.2f}).",6.3)
    label(.045,.117,'Check uncertainty and documentation before\nassigning an operational explanation.',7.4,'bold')
    label(.045,.047,'O/E: observed / expected damage, log axes. Joint intervals include\nmodel development and year uncertainty; they are not simultaneous.',6.3,color=muted)
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,axes=[aa,bb],panel_ids=['a','b'],row_groups=[['a','b']],json_out=O/'alignment.json',overlay_svg=O/'alignment.svg',strict=True)
    save(O/'alignment_scope.json',{'included':['a','b'],'excluded':['c'],'reason':'C is an intentional full-width decomposition panel with a larger direct-label region; only the two top-row plot areas are comparable.'})
    fig.savefig(O/'graphical_abstract.pdf');fig.savefig(O/'graphical_abstract.svg')
    fig.savefig(O/'graphical_abstract.png',dpi=600)
    fig.savefig(O/'graphical_abstract.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(O/'preview.png',dpi=300)
    save(O/'rendered_labels.json',[x.get_text() for x in fig.texts])
    plt.close(fig)

if __name__=='__main__':
 from input_config import execute
 execute(run,['points', 'intervals', 'dispersion', 'funnel'])
