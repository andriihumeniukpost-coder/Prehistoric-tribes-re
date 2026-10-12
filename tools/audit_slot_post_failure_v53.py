#!/usr/bin/env python3
"""Reproduce selected bounded checks for v53 post-failure audit.
This is a textual bytecode audit, not a full JVM verifier/dataflow engine.
"""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
c = (root / 'analysis' / 'bytecode' / 'c.txt').read_text(errors='replace')
g = (root / 'analysis' / 'bytecode' / 'g.txt').read_text(errors='replace')
def block(src, start, end):
    a = src.find('  ' + start)
    b = src.find('  ' + end, a + 1)
    if a < 0 or b < 0:
        raise SystemExit(f'could not isolate {start} -> {end}')
    return src[a:b]
C = block(c, 'private void C();', 'private void a(byte);')
setter = block(c, 'private void a(int, byte);', 'private void b(int, int);')
retry = block(c, 'private void c(byte);', 'private void j(int);')
k = block(c, 'private boolean k();', 'private void I();')
i = block(c, 'private boolean i();', 'private boolean k();')
I = block(c, 'private void I();', 'private void J();')
assert 'invoke' not in '\n'.join(line for line in C.splitlines() if 'invoke' in line)
assert 'sipush        1919' not in C and 'sipush        4444' not in C
assert 'Method C:()V' in setter
assert 'sipush        1919' in retry and 'sipush        4444' in retry
assert 'Method c:(B)V' in k
assert 'Method I:()V' in i and 'Method k:()Z' in i
assert 'Method a:(IB)V' in I
print('v53 bounded checks passed')
print('c.C(): lines', len(C.splitlines()), 'direct invoke instructions', sum('invoke' in x for x in C.splitlines()))
print('c.c(byte): full-group return offset 429 present:', '429: return' in retry)
print('c.k(): state-107 dispatch and later return paths present:', 'Method c:(B)V' in k and '732: ireturn' in k)
print('Scope: textual checks only; does not resolve runtime table values or all computed-index stores.')
