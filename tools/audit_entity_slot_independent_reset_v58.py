#!/usr/bin/env python3
"""Reproduce the v58 targeted checks against the bundled javap disassembly."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
checks={
 'c.txt': [r'10: sipush\s+1919', r'15: iconst_0', r'16: bastore', r'82: invokespecial.*Method m:\(I\)V', r'86: invokespecial.*Method m:\(I\)V', r'48: invokespecial.*Method m:\(I\)V'],
 'f.txt': [r'15: putfield.*Field g\.e:\[B'],
 'g.txt': [r'128: invokevirtual.*Method c\.l:\(\)V', r'286: invokevirtual.*Method c\.l:\(\)V', r'417: invokevirtual.*Method c\.m:\(\)V'],
}
for name, patterns in checks.items():
 text=(root/'analysis'/'bytecode'/name).read_text(errors='replace')
 for pattern in patterns:
  if not re.search(pattern,text): raise SystemExit(f'MISSING {name}: {pattern}')
print('v58 targeted disassembly checks: PASS')
