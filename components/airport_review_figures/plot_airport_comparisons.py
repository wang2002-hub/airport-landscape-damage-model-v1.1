"""Render airport comparisons from frozen, explicitly labelled source tables."""
from pathlib import Path
import argparse,json,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'qa_tools'))
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
 'font.size':8.5,'axes.titlesize':9,'axes.labelsize':8.5,'xtick.labelsize':8,
 'ytick.labelsize':8.5,'legend.fontsize':8,'pdf.fonttype':42,'svg.fonttype':'none',
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,
 'xtick.major.width':.7,'ytick.major.width':.7,'legend.frameon':False,
 'savefig.facecolor':'white','figure.facecolor':'white'})
BLUE='#266B8D';GRAY='#737B82';BROWN='#A96624';INK='#24282B'

def panel(ax,letter,title):
    height_pt=ax.get_position().height*ax.figure.get_figheight()*72
    anchor=1+14/height_pt
    ax.text(0,anchor,letter,transform=ax.transAxes,ha='left',va='bottom',fontweight='bold',fontsize=10)
    ax.text(.09,anchor,title,transform=ax.transAxes,ha='left',va='bottom',fontsize=9)

def subtitle(ax,text):
    height_pt=ax.get_position().height*ax.figure.get_figheight()*72
    ax.text(.09,1+1/height_pt,text,transform=ax.transAxes,va='bottom',fontsize=7.5)

def interval(ax,x,y,lo,hi,color,marker='o',lw=1.1,ms=4):
    x=np.atleast_1d(x);y=np.atleast_1d(y);lo=np.atleast_1d(lo);hi=np.atleast_1d(hi)
    assert np.isfinite(np.r_[x,lo,hi]).all() and (lo<=x).all() and (hi>=x).all()
    return ax.errorbar(x,y,xerr=np.vstack((x-lo,hi-x)),fmt=marker,color=color,
                      ms=ms,elinewidth=lw,capsize=2,capthick=lw,markeredgewidth=.7,zorder=3)

def export(fig,out,stem,axes,ids):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=ids,
       json_out=out/(stem+'.alignment.json'),overlay_svg=out/(stem+'.alignment.svg'),
       tolerance_pt=1.5,gutter_tolerance_pt=1.5,require_panel_labels=True,strict=True)
    # A fixed canvas preserves physical dimensions and the audited axes geometry.
    fig.savefig(out/(stem+'.pdf'))
    fig.savefig(out/(stem+'.svg'))
    fig.savefig(out/(stem+'.png'),dpi=600)
    fig.savefig(out/(stem+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(out/(stem+'_preview.png'),dpi=300)
    plt.close(fig)

def draw_three(data,out):
    d=pd.read_csv(data['airport_comparisons']);p=pd.read_csv(data['pooled_comparison']).iloc[0]
    assert list(d.airport)==['DEN','JFK','MIA','MSP','BOS','SFO','SAT','STL']
    fig,axs=plt.subplots(1,2,figsize=(6.5,4.8))
    fig.subplots_adjust(left=.105,right=.975,top=.88,bottom=.24,wspace=.31)
    y=np.arange(8);offset=.115
    for ax,col in zip(axs,['absolute','relative']):
        columns=[col,col+'_point_low',col+'_point_high',col+'_sim_low',col+'_sim_high']
        assert np.all(d[columns].to_numpy() > 0), 'Log-axis values and interval limits must be positive'
        interval(ax,d[col],y-offset,d[col+'_point_low'],d[col+'_point_high'],GRAY,'o',.9,3.5)
        interval(ax,d[col],y+offset,d[col+'_sim_low'],d[col+'_sim_high'],BLUE,'s',1.2,3.5)
        ax.set_xscale('log');ax.set_xlim(.3,3);ax.set_ylim(8.9,-.65)
        ax.xaxis.set_major_locator(FixedLocator([.3,.5,1,2,3]));ax.xaxis.set_major_formatter(FixedFormatter(['0.3','0.5','1','2','3']))
        ax.xaxis.set_minor_locator(NullLocator());ax.axvline(1,color='#A4AAAE',lw=.8,ls=(0,(3,3)),zorder=0)
        ax.set_yticks(y,d.airport);ax.tick_params(axis='y',length=0,pad=5)
        ax.set_xlabel('O/E (log scale)' if col=='absolute' else 'Airport O/E / pooled O/E (log scale)',labelpad=7)
    interval(axs[0],p.OE,8.45,p.low,p.high,INK,'D',1.1,4.7)
    axs[0].set_yticks(list(y)+[8.45],list(d.airport)+['Pooled'])
    panel(axs[0],'A','National-reference comparison');panel(axs[1],'B','Relative to selected pool')
    # The two interval families are kept distinct despite shared draws.
    handles=[Line2D([],[],color=GRAY,marker='o',lw=.9,ms=3.5,label='Pointwise 95%'),
             Line2D([],[],color=BLUE,marker='s',lw=1.2,ms=3.5,label='Simultaneous 95%'),
             Line2D([],[],color=INK,marker='D',lw=1.1,ms=4,label='Pooled 95% (pointwise)')]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.52,.095),ncol=3,
               handlelength=1.6,columnspacing=1.4,handletextpad=.6)
    fig.text(.105,.045,'JFK relative simultaneous interval: 0.9979–1.6786. Each airport contributes to the pool.',fontsize=7.5)
    export(fig,out,'fig03_airport_comparisons',list(axs),['A','B'])

def draw_five(data,out):
    d=pd.read_csv(data['damage_extent']);p=d[d.airport=='Pooled'].set_index('subtype')
    assert len(d)==18 and d[d.airport!='Pooled'].groupby('airport').size().eq(2).all()
    fig=plt.figure(figsize=(6.5,4.8));gs=fig.add_gridspec(2,2)
    fig.subplots_adjust(left=.14,right=.975,top=.88,bottom=.19,wspace=.43,hspace=.72)
    a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[1,0]);c=fig.add_subplot(gs[:,1])
    obs=[p.loc['undetermined','observed'],p.loc['documented','observed']]
    exp=[p.loc['undetermined','expected'],p.loc['documented','expected']]
    assert sum(obs)==309 and np.isclose(sum(exp),275.6398606949824)
    for yy,values in enumerate([obs,exp]):
        left=0
        for j,(v,color) in enumerate(zip(values,[BROWN,BLUE])):
            a.barh(yy,v,left=left,height=.42,color=color,edgecolor='white',linewidth=.4)
            text=f'{v:.0f}' if yy==0 else f'{v:.1f}'
            a.text(left+v/2,yy,text,ha='center',va='center',color='white',fontsize=8)
            left+=v
    a.set(xlim=(0,325),ylim=(1.65,-.65),yticks=[0,1],yticklabels=['Observed','Expected'],xticks=[0,100,200,300],xlabel='Damage reports')
    a.tick_params(axis='y',length=0);panel(a,'A','Pooled damage composition')
    for yy,(sub,color,marker) in enumerate([('undetermined',BROWN,'o'),('documented',BLUE,'s')]):
        r=p.loc[sub];interval(b,r.ratio,yy,r.point_low,r.point_high,color,marker,1.2,4.5)
    b.set(xlim=(.4,1.6),ylim=(1.65,-.65),yticks=[0,1],yticklabels=['M?','Documented'],xticks=[.4,.8,1.2,1.6],xlabel='Pooled subtype O/E')
    b.axvline(1,color='#A4AAAE',lw=.8,ls=(0,(3,3)),zorder=0);b.tick_params(axis='y',length=0)
    panel(b,'B','Pooled ratios');subtitle(b,'Pointwise 95% intervals')
    order=['DEN','JFK','MIA','MSP','BOS','SFO','SAT','STL'];y=np.arange(8)
    for sub,color,marker,offset in [('undetermined',BROWN,'o',-.14),('documented',BLUE,'s',.14)]:
        g=d[d.subtype==sub].set_index('airport').loc[order]
        interval(c,g.ratio,y+offset,g.sim_low,g.sim_high,color,marker,1.1,4)
    c.set(xlim=(-.07,3.1),ylim=(7.65,-.65),yticks=y,yticklabels=order,xticks=[0,1,2,3],xlabel='Airport subtype O/E')
    c.axvline(1,color='#A4AAAE',lw=.8,ls=(0,(3,3)),zorder=0);c.tick_params(axis='y',length=0)
    panel(c,'C','Local subtype comparisons');subtitle(c,'Simultaneous 95% intervals')
    handles=[Line2D([],[],color=BROWN,marker='o',lw=1.1,ms=4,label='Undetermined extent (M?)'),
             Line2D([],[],color=BLUE,marker='s',lw=1.1,ms=4,label='Documented extent')]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.53,.055),ncol=2,
               handlelength=1.7,columnspacing=2.0,handletextpad=.7)
    export(fig,out,'fig05_damage_extent', [a,b,c],['A','B','C'])

def run(paths,out):
    draw_three(paths,out)
    draw_five(paths,out)

if __name__=='__main__':
    from input_config import execute
    execute(run,['airport_comparisons','pooled_comparison','damage_extent'])
