#!/usr/bin/env python3
"""Reproducibility notes for the v59 static audit.

Reads the supplied javap disassemblies conceptually; this lightweight verifier
checks that the source evidence lines used in the report remain present.
It does not execute or modify the game.
"""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
checks = {
    "analysis/bytecode/c.txt": ["private void m(int);", "final void l();", "final void m();", "sipush        1919"],
    "analysis/bytecode/g.txt": ["private void T();", "Method c.l:()V", "Method c.m:()V", "final void b(int);", "Method T:()V"],
}
failed = []
for rel, needles in checks.items():
    p = root / rel
    data = p.read_text(errors="replace")
    for needle in needles:
        if needle not in data:
            failed.append(f"MISSING {rel}: {needle}")
if failed:
    print("FAIL")
    print("\n".join(failed))
    raise SystemExit(1)
print("PASS: all source anchors for v59 audit are present")
print("Scope: static anchor verification only; reachability claims remain conditional as stated in the report.")
