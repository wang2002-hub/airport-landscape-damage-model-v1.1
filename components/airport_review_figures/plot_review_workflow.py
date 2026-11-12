"""Draw a proposed review workflow with conditional, compatible follow-up paths."""
from pathlib import Path
import json,re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,FancyArrowPatch

HERE=Path(__file__).resolve().parent

def run(paths,OUT):
    import pandas as pd
    comparison=pd.read_csv(paths['airport_comparisons']).set_index('airport').loc['JFK']
    extent=pd.read_csv(paths['damage_extent'])
    jfk=extent[(extent.airport=='JFK') & (extent.subtype=='undetermined')]
    assert len(jfk)==1 and int(jfk.observed.iloc[0])==58
    assert comparison.absolute_sim_low<=1<=comparison.absolute_sim_high
    assert comparison.relative_sim_low<=1<=comparison.relative_sim_high
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],
     'font.size':8.5,'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
    # v1.1: box 3-4 gains a second detail line (report-volume calibration, coding period);
    # its height grows by DY points and everything below shifts down by DY.
    DY=12;H=410.4+DY
    fig=plt.figure(figsize=(6.5,5.7*H/410.4));ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,468),ylim=(H,0));ax.axis('off')
    INK='#24282B';EDGE='#78858B';PALE='#F4F6F7';ACCENT='#E7F0F4'
    boxes=[];texts=[]
    def box(key,x,y,w,h,fill=PALE):
        r=Rectangle((x,y),w,h,facecolor=fill,edgecolor=EDGE,linewidth=.7);r.set_gid('node-'+key);ax.add_patch(r)
        boxes.append((key,x,y,w,h));return r
    def txt(key,x,y,text,size=8.5,weight='normal',ha='center'):
        t=ax.text(x,y,text,fontsize=size,color=INK,weight=weight,ha=ha,va='center',linespacing=1.3)
        t.set_gid('label-'+key);texts.append(t);return t
    def arrow(key,start,end):
        a=FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=8,lw=.85,color=EDGE,shrinkA=0,shrinkB=0)
        a.set_gid('edge-'+key);ax.add_patch(a)

    preparation=[
     ('collection',14,'1–2  Define the collection and inspect extent','Eligibility, known and unresolved labels; M? remains known damage.'),
     ('comparison',74,'3–4  Assess the reference and compare','Report-volume calibration and coding period; matched probability losses;\nabsolute and relative simultaneous intervals.'),
     ('sensitivity',134+DY,'5  Check why the comparison changes','Same-report extent partition; period and reference sensitivity.')]
    for key,y,title,detail in preparation:
        h=43+(DY if key=='comparison' else 0)
        box(key,18,y,432,h);txt(key+'-title',234,y+13,title,9)
        txt(key+'-detail',234,y+(36 if key=='comparison' else 30),detail,8.2)
    arrow('collection-comparison',(234,57),(234,74))
    arrow('comparison-sensitivity',(234,117+DY),(234,134+DY))
    txt('follow-up',234,195+DY,'6  Choose follow-up from the evidence; actions may overlap',9)

    branches=[
     ('A',18,'A  Hazard investigation','Stable elevation across\noutcomes and references;\nsimultaneous intervals\nsupport elevation, with\noperational corroboration.','Investigate hazards and\nplausible mechanisms.',PALE),
     ('B',165,'B  Documentation audit','Extent remains unresolved\nor the profile changes with\nreport composition.\nUnderlying records may\nclarify the documentation.','Check extent evidence\nand coding provenance.',ACCENT),
     ('C',312,'C  Routine monitoring','Local excess unresolved:\nsimultaneous intervals\ninclude 1, or sensitivity\nchecks change the\ninterpretation.','Continue monitoring;\nexamine shared shifts.',PALE)]
    for key,x,title,condition,action,fill in branches:
        box('branch-'+key,x,226+DY,138,124,fill)
        txt(key+'-title',x+69,240+DY,title,8.5)
        txt(key+'-condition',x+69,281+DY,condition,8.2)
        txt(key+'-action',x+69,331+DY,action,8.5)
        arrow('dispatch-'+key,(x+69,213+DY),(x+69,226+DY))
    ax.plot([87,381],[213+DY,213+DY],color=EDGE,lw=.85)
    ax.plot([234,234],[205+DY,213+DY],color=EDGE,lw=.85)
    ax.plot(234,213+DY,'o',color=EDGE,ms=2)
    txt('JFK',234,372+DY,'JFK: B + C — 58 M? reports; both primary airport intervals include 1.',8.5)
    txt('boundary',234,395+DY,'Proposed retrospective workflow; prospective effects remain to be evaluated.',8.2)

    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    layout=[]
    for t in texts:
        bb=t.get_window_extent(renderer).transformed(ax.transData.inverted())
        # The y axis runs downward, so bounds are sorted for geometric checking.
        bounds=[float(bb.x0),float(min(bb.y0,bb.y1)),float(bb.x1),float(max(bb.y0,bb.y1))]
        assert 0<=bounds[0]<bounds[2]<=468 and 0<=bounds[1]<bounds[3]<=H
        layout.append({'id':t.get_gid(),'text':t.get_text(),'bounds_pt':bounds})
    for i,a in enumerate(layout):
        for b in layout[i+1:]:
            aa=a['bounds_pt'];bb=b['bounds_pt']
            assert min(aa[2],bb[2])-max(aa[0],bb[0])<=0 or min(aa[3],bb[3])-max(aa[1],bb[1])<=0, (a['id'],b['id'])
    for key,x,y,w,h in boxes:
        names=[key+'-title',key+'-detail'] if not key.startswith('branch-') else [key[-1]+'-title',key[-1]+'-condition',key[-1]+'-action']
        for name in names:
            b=next(r['bounds_pt'] for r in layout if r['id']=='label-'+name)
            assert b[0]>=x+3 and b[2]<=x+w-3 and b[1]>=y+3 and b[3]<=y+h-3,(key,name,b)
    (OUT/'fig06_review_protocol.geometry.json').write_text(json.dumps({'passed':True,'canvas_pt':[468,H],'font_floor_pt':8.2,'comparable_branch_boxes':boxes[-3:],'text_boxes':layout,'layout_type':'One workflow; branch cards have identical width, height and top alignment. No quantitative panels.'},indent=2),encoding='utf-8')
    stem=OUT/'fig06_review_protocol'
    fig.savefig(stem.with_suffix('.pdf'));fig.savefig(stem.with_suffix('.svg'))
    # The drawing is self-contained; remove the optional external SVG 1.1 DTD.
    svg=stem.with_suffix('.svg')
    svg_text=re.sub(r'<!DOCTYPE[^>]*>\s*','',svg.read_text(encoding='utf-8'))
    # Express font sizes as SVG user-unit presentation attributes. One user unit
    # equals one physical point on this canvas; geometry and live text are unchanged.
    svg_text=re.sub(r'<text style="font-size: ([\d.]+)px; ',r'<text font-size="\1" style="',svg_text)
    svg.write_text(svg_text,encoding='utf-8')
    fig.savefig(stem.with_suffix('.png'),dpi=600)
    fig.savefig(stem.with_suffix('.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/'fig06_review_protocol_preview.png',dpi=300)
    plt.close(fig)
    print('Exported the conditional review workflow.')

if __name__=='__main__':
    from input_config import execute
    execute(run,['airport_comparisons','damage_extent'])
