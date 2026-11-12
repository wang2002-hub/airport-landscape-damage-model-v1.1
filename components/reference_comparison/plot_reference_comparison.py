"""Plot paired fixed-prediction profiles and complete reference-pair overlaps."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator,FixedFormatter,NullLocator
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'qa_tools'))
from audit_panel_alignment import require_matplotlib_panel_alignment

def run(paths,OUT):
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':8.5,'axes.labelsize':8.5,
     'xtick.labelsize':8,'ytick.labelsize':7.5,'legend.fontsize':7.5,'legend.frameon':False,
     'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
    INK='#4F5D64';BLUE='#266B8D';ORANGE='#A75A28'
    d=pd.read_csv(paths['paired_profiles']);p=pd.read_csv(paths['paired_set_comparisons'])
    assert len(d)==144 and d[['ordinary_EB','glmm_EBL']].gt(0).all().all()
    assert len(p)==10 and p[['top_jaccard','flag_jaccard']].ge(0).all().all() and p[['top_jaccard','flag_jaccard']].le(1).all().all()
    assert round(d.ordinary_EB.corr(d.glmm_EBL,method='spearman'),4)==0.9878
    assert len(d[d.different_top_membership])==4
    assert d[['ordinary_EB','glmm_EBL']].ge(.13).all().all() and d[['ordinary_EB','glmm_EBL']].le(2.3).all().all()
    fig,axs=plt.subplots(1,2,figsize=(6.5,4.6));fig.subplots_adjust(left=.105,right=.975,top=.85,bottom=.33,wspace=.65)
    a,b=axs
    for ax in axs:ax.set_box_aspect(1)
    a.plot([.13,2.3],[.13,2.3],color='#A6AFB4',lw=.8,ls=(0,(4,3)),zorder=0)
    a.scatter(d.ordinary_EB,d.glmm_EBL,c=INK,s=13,alpha=.75,zorder=2)
    diff=d[d.different_top_membership]
    a.scatter(diff.ordinary_EB,diff.glmm_EBL,facecolors='none',edgecolors=ORANGE,s=52,marker='s',lw=1.1,zorder=3)
    a.set(xscale='log',yscale='log',xlim=(.13,2.3),ylim=(.13,2.3),xlabel='O/E: ordinary logistic EB\n(log scale)',ylabel='O/E: hierarchical EBL (log scale)')
    for axis in [a.xaxis,a.yaxis]:
     axis.set_major_locator(FixedLocator([.2,.5,1,2]));axis.set_major_formatter(FixedFormatter(['0.2','0.5','1','2']));axis.set_minor_locator(NullLocator())
    a.text(.04,.95,'144 airports\nSpearman = 0.9878',transform=a.transAxes,va='top',fontsize=7.5,linespacing=1.3)
    y=np.arange(10)
    b.scatter(p.top_jaccard,y-.13,c=BLUE,s=17,marker='o',zorder=3)
    b.scatter(p.flag_jaccard,y+.13,c=ORANGE,s=19,marker='D',zorder=3)
    b.set(xlim=(0,1.06),xticks=[0,.25,.5,.75,1],yticks=y,yticklabels=p.label,ylim=(9.7,-.7),xlabel='Jaccard overlap')
    b.tick_params(axis='y',length=0,pad=4);b.grid(axis='x',color='#E0E4E6',lw=.6);b.set_axisbelow(True)
    # Layout is settled before physical panel-label anchors are computed.
    fig.canvas.draw()
    for ax,letter,title in zip(axs,['A','B'],['Paired O/E values','Membership overlap']):
     h=ax.get_position().height*fig.get_figheight()*72
     ax.text(0,1+14/h,letter,transform=ax.transAxes,weight='bold',fontsize=10,va='bottom')
     ax.text(.10,1+14/h,title,transform=ax.transAxes,fontsize=8.5,va='bottom')
    a.legend(handles=[Line2D([],[],marker='o',color=INK,lw=0,ms=3,label='Airport profile'),Line2D([],[],marker='s',color=ORANGE,mfc='none',lw=0,ms=5,label='Top decile in one reference')],loc='upper left',bbox_to_anchor=(-.03,-.36),borderaxespad=0,handlelength=1.3,labelspacing=.7)
    b.legend(handles=[Line2D([],[],marker='o',color=BLUE,lw=0,ms=4,label='Highest decile'),Line2D([],[],marker='D',color=ORANGE,lw=0,ms=4,label='Conditional 99.8% flags')],loc='upper left',bbox_to_anchor=(-.03,-.36),borderaxespad=0,handlelength=1.3,labelspacing=.7)
    fig.text(.105,.05,'O: ordinary logistic; H: hierarchical logistic; G: gradient boosting.',fontsize=7.5)
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,axes=list(axs),panel_ids=['A','B'],json_out=OUT/'fig04_paired_profiles_and_overlap.alignment.json',overlay_svg=OUT/'fig04_paired_profiles_and_overlap.alignment.svg',tolerance_pt=1.5,gutter_tolerance_pt=1.5,require_panel_labels=True,strict=True)
    stem=OUT/'fig04_paired_profiles_and_overlap'
    fig.savefig(stem.with_suffix('.pdf'));fig.savefig(stem.with_suffix('.svg'))
    fig.savefig(stem.with_suffix('.png'),dpi=600);fig.savefig(stem.with_suffix('.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/'fig04_paired_profiles_and_overlap_preview.png',dpi=300)
    plt.close(fig)
    print('Figure 4 exported with all 144 paired profiles and ten reference pairs.')

if __name__=='__main__':
    from input_config import execute
    execute(run,['paired_profiles','paired_set_comparisons'])
