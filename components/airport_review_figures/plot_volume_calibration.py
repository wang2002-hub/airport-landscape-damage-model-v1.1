"""Display fixed-reference calibration across tie-preserving report-count groups."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'qa_tools'))
from audit_panel_alignment import require_matplotlib_panel_alignment

def run(paths,OUT):
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':7.5,'legend.fontsize':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'legend.frameon':False})
    d=pd.read_csv(paths['calibration_with_paired_gaps'])
    fig,axs=plt.subplots(2,2,figsize=(6.5,5.6))
    fig.subplots_adjust(left=.095,right=.985,bottom=.16,top=.88,wspace=.27,hspace=.65)
    colors=['#235B83','#B36331'];markers=['o','s'];titles=['Geographic 2015–2025','Temporal test 2024–2025']
    for j,evaluation in enumerate(['geographic','temporal_test']):
     for i,weight in enumerate(['airport_equal','report_weighted']):
      ax=axs[i,j];g=d[(d.evaluation==evaluation)&(d.weighting==weight)].sort_values('min_reports')
      assert len(g)==6 and g.airports.sum()==(1375 if j==0 else 803)
      x=np.arange(6)
      for k,metric in enumerate(['observed','predicted']):
       center=g[metric].to_numpy()*100;low=g[metric+'_low'].to_numpy()*100;high=g[metric+'_high'].to_numpy()*100
       assert (low<=center).all() and (high>=center).all()
       ax.errorbar(x+(-.12 if k==0 else .12),center,yerr=np.vstack([center-low,high-center]),fmt=markers[k],color=colors[k],ms=3.8,lw=.8,capsize=2,zorder=3)
      ax.set(xlim=(-.5,5.5),ylim=(0,40),yticks=[0,10,20,30,40],xticks=x,xticklabels=[f'{int(a)}–{int(b)}' for a,b in zip(g.min_reports,g.max_reports)],xlabel='Eligible reports per airport')
      ax.grid(axis='y',color='#E4E7E9',lw=.6);ax.set_axisbelow(True)
      if j==0:ax.set_ylabel('Damage proportion (%)')
      letter=['A','B','C','D'][i*2+j]
      ax.text(0,1.08,letter,transform=ax.transAxes,fontsize=10,weight='bold',va='bottom')
      ax.text(.10,1.08,'Airport-equal' if i==0 else 'Report-weighted',transform=ax.transAxes,fontsize=8.5,va='bottom')
    for j,title in enumerate(titles):
     ax=axs[0,j];b=ax.get_position();fig.text(b.x0+b.width/2,.965,title,ha='center',fontsize=9,weight='bold')
    fig.legend(handles=[Line2D([],[],color=colors[0],marker='o',lw=0,ms=4,label='Observed'),Line2D([],[],color=colors[1],marker='s',lw=0,ms=4,label='Predicted')],loc='lower center',bbox_to_anchor=(.5,.025),ncol=2)
    fig.canvas.draw()
    stem=OUT/'figS03_report_volume_calibration'
    require_matplotlib_panel_alignment(fig,axes=list(axs.ravel()),panel_ids=['A','B','C','D'],json_out=stem.with_suffix('.alignment.json'),overlay_svg=stem.with_suffix('.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,require_panel_labels=True,strict=True)
    fig.savefig(stem.with_suffix('.pdf'));fig.savefig(stem.with_suffix('.svg'))
    fig.savefig(stem.with_suffix('.png'),dpi=600);fig.savefig(stem.with_suffix('.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/'preview.png',dpi=300);plt.close(fig)
    print('Exported four aligned panels with all 24 observed and predicted group summaries.')

if __name__=='__main__':
    from input_config import execute
    execute(run,['calibration_with_paired_gaps'])
