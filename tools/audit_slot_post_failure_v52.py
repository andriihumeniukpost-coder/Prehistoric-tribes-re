#!/usr/bin/env python3
"""Reproduce the bounded textual checks documented in entity_slot_post_failure_path_v52.txt.
Uses only the supplied javap-style disassembly; it is not a full JVM dataflow analyzer.
"""
from pathlib import Path
import csv
root = Path(__file__).resolve().parents[1]
src = root / 'analysis' / 'bytecode' / 'c.txt'
text = src.read_text(errors='replace')
def method_block(header, next_header):
    start = text.find('  ' + header)
    if start < 0:
        raise SystemExit(f'method not found: {header}')
    end = text.find('  ' + next_header, start + 1)
    if end < 0:
        raise SystemExit(f'end method not found: {next_header}')
    return text[start:end]
checks = {
    'c.i()': method_block('private boolean i();', 'private boolean k();'),
    'c.k()': method_block('private boolean k();', 'private void I();'),
    'c.I()': method_block('private void I();', 'private void J();'),
}
print('Source:', src)
for name, block in checks.items():
    print(f'{name}: lines={len(block.splitlines())}, has_1919={"1919" in block}, has_2828={"2828" in block}, has_4444={"4444" in block}, calls_a_IB={"Method a:(IB)V" in block}')
assert 'Method I:()V' in checks['c.i()']
assert 'Method c:(B)V' in checks['c.k()']
assert 'Method a:(IB)V' in checks['c.I()']
assert '1919' not in checks['c.I()'] and '4444' not in checks['c.I()']
print('Bounded checks passed. These checks do not prove absence of transitive side effects.')
