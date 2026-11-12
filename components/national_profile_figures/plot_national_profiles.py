"""Render readable national profiles without changing any inferential flags."""
from pathlib import Path
import sys,json
from statistics import NormalDist
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator,FixedFormatter,NullLocator
HERE=Path(__file__).resolve().parent
import argparse
_parser=argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--output',type=Path,required=True)
OUT=_parser.parse_args().output.resolve()
if OUT.exists():_parser.error('Choose a new output directory.')
OUT.mkdir(parents=True)
sys.path.insert(0,str(HERE/'qa_tools'))
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8.5,
 'axes.labelsize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':7.5,
 'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none',
 'axes.linewidth':.7,'legend.frameon':False,'savefig.facecolor':'white'})
INK='#38454C';BLUE='#266B8D';FLAG='#A75A28';PURPLE='#77598B';PALE='#B5CED7';GUIDE='#8B949B'
n=pd.read_csv(HERE/'inputs/national_profiles.csv');t=pd.read_csv(HERE/'inputs/target_control_ranges.csv').set_index('airport')
order=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL'];t=t.loc[order]
assert len(n)==1375 and n.E.gt(0).all() and t.E.gt(0).all()
hi=n[n.E>=5];flag=n[n.conditional_flag_998];assert len(hi)==144 and len(flag)==6 and flag.E.ge(5).all()
def panel(ax,letter,title):
    height=ax.get_position().height*ax.figure.get_figheight()*72
    ax.text(0,1+14/height,letter,transform=ax.transAxes,weight='bold',fontsize=10,va='bottom')
    ax.text(.09,1+14/height,title,transform=ax.transAxes,fontsize=8.5,va='bottom')
def log_ticks(ax,axis,values,labels):
    a=ax.xaxis if axis=='x' else ax.yaxis
    a.set_major_locator(FixedLocator(values));a.set_major_formatter(FixedFormatter(labels));a.set_minor_locator(NullLocator())
def export(fig,stem,axes,labels):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=labels,json_out=OUT/(stem+'.alignment.json'),overlay_svg=OUT/(stem+'.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,require_panel_labels=True,strict=True)
    fig.savefig(OUT/(stem+'.pdf'));fig.savefig(OUT/(stem+'.svg'))
    fig.savefig(OUT/(stem+'.png'),dpi=600);fig.savefig(OUT/(stem+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/(stem+'_preview.png'),dpi=300);plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(6.5,5.1))
fig.subplots_adjust(left=.10,right=.975,top=.87,bottom=.30,wspace=.36)
a,b=axs
x=np.geomspace(5,100,300);z=NormalDist().inv_cdf(.999);lower=np.maximum(0,1-z/np.sqrt(x));upper=1+z/np.sqrt(x)
a.plot(x,lower,color=GUIDE,ls=(0,(4,3)),lw=.9);a.plot(x,upper,color=GUIDE,ls=(0,(4,3)),lw=.9)
a.scatter(hi.E,hi.OE,s=11,c=INK,alpha=.75,zorder=3)
a.scatter(flag.E,flag.OE,s=50,facecolors='none',edgecolors=FLAG,lw=1.1,zorder=4)
a.set(xscale='log',xlim=(4.8,100),ylim=(0,2.55),yticks=[0,.5,1,1.5,2,2.5],xlabel='Expected damage E (log scale)',ylabel='Observed / expected damage')
log_ticks(a,'x',[5,10,20,50,100],['5','10','20','50','100']);a.axhline(1,color='#C3C8CB',lw=.7,zorder=0)
panel(a,'A','National profiles with E ≥ 5')
for i,r in enumerate(t.itertuples()):
    b.plot([r.width_lower_count_998/r.E,r.width_upper_count_998/r.E],[i,i],c=PALE,lw=5,solid_capstyle='butt',zorder=1)
    b.plot([r.lower_count_998/r.E,r.upper_count_998/r.E],[i,i],c=INK,lw=1.4,zorder=2)
b.scatter(t.OE,range(8),s=21,c=PURPLE,marker='D',zorder=3)
b.axvline(1,color='#C3C8CB',lw=.7,zorder=0)
b.set(xlim=(0,2.15),xticks=[0,.5,1,1.5,2],ylim=(7.65,-.65),yticks=range(8),yticklabels=[v[1:] for v in order],xlabel='O/E and control ranges')
b.tick_params(axis='y',length=0);panel(b,'B','Separate target predictions')
ha=[Line2D([],[],c=INK,marker='o',lw=0,ms=3,label='National O/E'),Line2D([],[],c=FLAG,marker='o',mfc='none',lw=0,ms=5,label='Exact 99.8% flag'),Line2D([],[],c=GUIDE,ls='--',lw=.9,label='Normal–Poisson guide only')]
hb=[Line2D([],[],c=PURPLE,marker='D',lw=0,ms=4,label='Target O/E'),Line2D([],[],c=INK,lw=1.4,label='Conditional 99.8% range'),Line2D([],[],c=PALE,lw=4,label='Widened range (sensitivity)')]
a.legend(handles=ha,loc='upper left',bbox_to_anchor=(-.02,-.23),borderaxespad=0,handlelength=1.7,labelspacing=.55)
b.legend(handles=hb,loc='upper left',bbox_to_anchor=(-.02,-.23),borderaxespad=0,handlelength=1.7,labelspacing=.55)
fig.text(.10,.035,'144 airports shown in A; all 1,375 national profiles remain in Fig. S3.',fontsize=7.5)
pd.DataFrame({'E':x,'illustrative_lower_998':lower,'illustrative_upper_998':upper}).to_csv(HERE/'inputs/normal_poisson_visual_guide.csv',index=False)
export(fig,'fig02_national_profiles',list(axs),['A','B'])

fig=plt.figure(figsize=(6.5,5.1));gs=fig.add_gridspec(5,2)
fig.subplots_adjust(left=.105,right=.975,top=.87,bottom=.20,wspace=.47,hspace=.27)
a=fig.add_subplot(gs[:4,0]);zero=fig.add_subplot(gs[4,0],sharex=a);b=fig.add_subplot(gs[:,1])
pos=n[n.O>0];zer=n[n.O==0]
assert len(pos)==773 and len(zer)==602 and pos.OE.gt(0).all()
a.scatter(pos.E,pos.OE,s=9,color=INK,alpha=.5,zorder=2)
a.scatter(flag.E,flag.OE,s=48,facecolors='none',edgecolors=FLAG,lw=1.1,zorder=3)
a.set(xscale='log',yscale='log',xlim=(.006,100),ylim=(.025,80),ylabel='O/E (log scale)')
a.axhline(1,color='#BDC3C7',lw=.7);a.axvline(5,color=BLUE,ls=(0,(3,3)),lw=.8)
log_ticks(a,'y',[.1,1,10,50],['0.1','1','10','50']);a.tick_params(axis='x',labelbottom=False)
panel(a,'A','All national airports')
zero.scatter(zer.E,np.zeros(len(zer)),marker='|',s=12,color=INK,alpha=.45)
zero.axvline(5,color=BLUE,ls=(0,(3,3)),lw=.8)
zero.set(xscale='log',ylim=(-.6,.6),yticks=[0],yticklabels=['0'],xlabel='Expected damage E (log scale)')
log_ticks(zero,'x',[.01,.1,1,10,100],['0.01','0.1','1','10','100'])
zero.text(.02,.86,'602 zero-damage airports',transform=zero.transAxes,fontsize=7.5,va='top')
summary=pd.read_csv(HERE/'inputs/national_summary.csv');row=summary.query("display_set=='all' and label==998").iloc[0]
vals=[row.conditional_flags,row.width_flags_phi_all,row.width_flags_phi_expected_ge5,row.width_flags_phi_reports_ge100]
labels=['Conditional','Widened\nAll airports','Widened\nE ≥ 5','Widened\nn ≥ 100']
b.barh(range(4),vals,height=.47,color=[INK,BLUE,BLUE,BLUE])
for y,val in enumerate(vals):b.text(val+.12,y,str(int(val)),va='center',fontsize=8)
b.set(xlim=(0,7),xticks=[0,2,4,6],ylim=(3.7,-.7),yticks=range(4),yticklabels=labels,xlabel='Flagged airports')
b.tick_params(axis='y',length=0);panel(b,'B','Width sensitivity')
fig.text(.105,.08,'A: 773 positive profiles plus 602 zeros; marks may overlap.',fontsize=7.5)
fig.text(.105,.04,'B: all 1,375 airports evaluated; only dispersion estimation sets change.',fontsize=7.5)
# The zero strip belongs to panel A, rather than being a third comparable panel.
# Align the two main panel tops and label anchors; audit the strip width separately.
assert np.isclose(a.get_position().x0,zero.get_position().x0) and np.isclose(a.get_position().width,zero.get_position().width)
export(fig,'figS04_complete_national_profiles',[a,b],['A','B'])
print('Exported Figure 2 and Figure S4 without modifying inferential inputs.')
