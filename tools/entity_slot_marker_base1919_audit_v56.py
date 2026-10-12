#!/usr/bin/env python3
"""Inventory literal 1919 marker-base references in supplied javap text."""
from pathlib import Path
import re,csv
root=Path(__file__).resolve().parents[1]
bc=root/'analysis'/'bytecode'; out=root/'analysis'/'entity_slot_marker_base1919_audit_v56.csv'
rows=[]
for fp in sorted(bc.glob('*.txt')):
 lines=fp.read_text(errors='replace').splitlines(); method='(method header not inferred)'
 for i,line in enumerate(lines):
  if re.match(r'^\s{2}(?:public|private|protected) .+\);?$',line): method=line.strip()
  if re.search(r'\bsipush\s+1919\b',line):
   off=re.search(r'^\s*(\d+):',line); ctx=' | '.join(x.strip() for x in lines[i:min(i+18,len(lines))] if x.strip())
   rows.append([fp.name,method,off.group(1) if off else '',str(bool(re.search(r'\bbastore\b','\n'.join(lines[i:min(i+18,len(lines))]))),ctx])
with out.open('w',newline='') as f:
 w=csv.writer(f); w.writerow(['class_file','method_header_nearest','sipush_1919_offset','bastore_within_next_18_lines','bytecode_context']); w.writerows(rows)
print(f'Wrote {len(rows)} references to {out}')
