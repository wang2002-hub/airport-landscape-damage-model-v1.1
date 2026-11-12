"""Add a switchable year specification to every copy of model_core.py (round-4 item D1).

After patching, the environment variable BIRDSTRIKE_YEAR_SPEC selects:
  linear       (default)  original single linear term (year - 2020) / 5  -> results unchanged
  period                   linear term + categorical coding period {2015, 2016, 2017+}
                           estimable in the temporal scheme (training 2015-2022) and
                           applicable to 2023-2025 (all fall in 2017+)
  categorical              one level per incident year (encoder reference = most frequent training year);
                           GEOGRAPHIC scheme only - the temporal model never sees 2023-2025,
                           and unseen levels would silently fall back to the reference.
The linear column is kept (set to 0 under 'categorical') so that the encoder's
landscape screening, which starts at numeric column 3, is unaffected.
Usage: python apply_year_spec_patch.py REPO_ROOT    (idempotent; prints patched files)
"""
import sys
from pathlib import Path

root = Path(sys.argv[1])
OLD_NUM = "num=pd.DataFrame(index=d.index);num['year']=(d.year.to_numpy(float)-2020)/5;"
NEW_NUM = ("num=pd.DataFrame(index=d.index);_spec=os.environ.get('BIRDSTRIKE_YEAR_SPEC','linear');"
           "assert _spec in ('linear','period','categorical'),_spec;"
           "num['year']=(d.year.to_numpy(float)-2020)/5 if _spec!='categorical' else np.zeros(len(d));")
OLD_CAT = "    cats=['aircraft_mass_class','phase']+"
NEW_CAT = ("    d=d.assign(coding_period=np.where(d.year<=2015,'2015',np.where(d.year==2016,'2016','2017+')),year_level=d.year.astype(int).astype(str))\r\n"
           "    cats=(['coding_period'] if _spec=='period' else ['year_level'] if _spec=='categorical' else [])+['aircraft_mass_class','phase']+")
done = []
for f in sorted(root.glob('components/*/model_core.py')):
    s = f.read_text(encoding='utf-8')
    if 'BIRDSTRIKE_YEAR_SPEC' in s:
        continue
    assert s.count(OLD_NUM) == 1 and s.count(OLD_CAT) == 1, f
    s = s.replace(OLD_NUM, NEW_NUM).replace(OLD_CAT, NEW_CAT)
    if not s.startswith('import os') and '\nimport os' not in s:
        s = 'import os\r\n' + s
    f.write_text(s, encoding='utf-8'); done.append(str(f))
print('patched:', *done, sep='\n  ')
