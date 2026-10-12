#!/usr/bin/env python3
"""Regenerate the v57 bytecode context inventories; intentionally heuristic, not a JVM verifier."""
from pathlib import Path
import re,csv
root=Path(__file__).resolve().parents[1]
bc=root/'analysis'/'bytecode'
rows=[]; literal=[]; total=0
for fp in sorted(bc.glob('*.txt')):
    lines=fp.read_text(errors='replace').splitlines(); method='(unknown)'; start=0
    for i,line in enumerate(lines):
        if re.match(r'^\s{2}(?:public|private|protected) .+\);?$',line): method=line.strip(); start=i
        if re.search(r'\bbastore\b',line):
            total+=1; m=re.search(r'^\s*(\d+):',line); off=m.group(1) if m else ''
            ctxlines=lines[max(start,i-10):i+1]
            if any('Field a:[B' in x and '#66' in x for x in ctxlines):
                rows.append([fp.name,method,off,'field #66 in preceding 10 instructions/lines',' | '.join(x.strip() for x in ctxlines[-10:])])
        if re.search(r'\bsipush\s+1919\b',line):
            m=re.search(r'^\s*(\d+):',line); off=m.group(1) if m else ''
            literal.append([fp.name,method,off,' | '.join(x.strip() for x in lines[i:min(i+20,len(lines))] if x.strip())])
for name,header,data in [('entity_slot_computed_index_store_candidates_v57.csv',['class_file','method','bastore_offset','candidate_basis','bytecode_context'],rows),('entity_slot_literal1919_context_v57.csv',['class_file','method','sipush_1919_offset','bytecode_context'],literal)]:
    with (root/'analysis'/name).open('w',newline='') as f:
        w=csv.writer(f); w.writerow(header); w.writerows(data)
print(f'bastore={total}; nearby field-#66 candidates={len(rows)}; literal 1919 refs={len(literal)}')
