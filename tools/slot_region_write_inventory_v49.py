#!/usr/bin/env python3
"""Conservative inventory of bastore instructions near slot-state base constants 2828/4444."""
import re, csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/entity_slot_region_write_candidates_v49.csv'
rows=[]
for p in sorted((ROOT/'analysis/bytecode').glob('*.txt')):
    lines=p.read_text(errors='replace').splitlines(); method='(unknown)'; block=[]
    def scan(method, block):
        ins=[]
        for i,line in enumerate(block):
            m=re.match(r'\s*(\d+):\s+(\S+)(.*)',line)
            if m: ins.append((int(m.group(1)),m.group(2),m.group(3).strip()))
        for j,(off,op,arg) in enumerate(ins):
            if op!='bastore': continue
            recent=ins[max(0,j-16):j]
            bases=[(k,int(re.match(r'(-?\d+)',a).group(1))) for k,(o,op2,a) in enumerate(recent) if op2=='sipush' and re.match(r'(-?\d+)',a) and int(re.match(r'(-?\d+)',a).group(1)) in (2828,4444)]
            if not bases: continue
            base=bases[-1][1]
            rows.append([p.name,method,off,base,'; '.join(f'{o}:{op2} {a}' for o,op2,a in ins[max(0,j-16):j+1])])
    for line in lines:
        if line.startswith('  ') and '(' in line and line.rstrip().endswith(');') and not re.match(r'\s*\d+:',line): scan(method,block); method=line.strip(); block=[line]
        else: block.append(line)
    scan(method,block)
with OUT.open('w',newline='') as f:
    w=csv.writer(f); w.writerow(['class_file','method','bastore_offset','candidate_base','nearby_bytecode']); w.writerows(rows)
print(f'wrote {len(rows)} candidates to {OUT}')
