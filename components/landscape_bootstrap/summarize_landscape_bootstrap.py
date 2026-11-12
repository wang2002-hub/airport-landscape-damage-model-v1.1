"""Summarize all 200 recorded landscape bootstrap attempts, preserving failures."""
from pathlib import Path
import argparse,json
import pandas as pd
from run_support import prepare_output
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--records',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
directory=Path(args.records).resolve(strict=True)
paths={str(i):directory/f'bootstrap_{i:03d}.json' for i in range(200)}
if not all(p.is_file() for p in paths.values()):raise ValueError('All 200 attempt records are required, including failed attempts.')
output=prepare_output(args.output,paths,['results'])
values=[];failures=[];selection=[];fits=0
for i,path in paths.items():
 r=json.loads(path.read_text(encoding='utf-8'))
 if r['replicate']!=int(i):raise ValueError('Attempt identifier disagrees with filename.')
 fits+=len(r['fits'])
 if r['success']:
  if len(r['rows'])!=10:raise ValueError('A successful attempt must contain ten collection summaries.')
  keys=[(x['dataset'],x['airport']) for x in r['rows']]
  if len(keys)!=len(set(keys)):raise ValueError('Duplicate collection summary.')
  for row in r['rows']:values.append({'replicate':int(i),**row})
  selection.append({'replicate':int(i),'scale':r['selected']['EBL']})
 else:failures.append({'replicate':int(i),'fit_records':len(r['fits']),'last_fit':r['fits'][-1]['label'] if r['fits'] else None,'error':r.get('error','')})
v=pd.DataFrame(values);rows=[]
if v.empty:raise ValueError('No successful attempt is available.')
for (dataset,airport),group in v.groupby(['dataset','airport'],sort=True):
 if len(group)!=len(selection):raise ValueError('Successful-attempt populations differ between collections.')
 for metric in ['delta_brier','delta_logloss']:
  rows.append({'dataset':dataset,'airport':airport,'metric':metric,'successful_attempts':len(group),'low':group[metric].quantile(.025),'median':group[metric].quantile(.5),'high':group[metric].quantile(.975)})
v.to_csv(output/'results/pipeline_values.csv',index=False);pd.DataFrame(rows).to_csv(output/'results/pipeline_intervals.csv',index=False);pd.DataFrame(selection).to_csv(output/'results/selected_scales.csv',index=False)
(output/'results/failed_attempts.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
summary={'attempts':200,'successes':len(selection),'failures':[x['replicate'] for x in failures],'fit_records':fits,'value_rows':len(v),'interval_rows':len(rows),'uncertainty':'Jointly resampled national airport histories with fixed target reports; conditional on successful development attempts.'}
(output/'results/pipeline_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
