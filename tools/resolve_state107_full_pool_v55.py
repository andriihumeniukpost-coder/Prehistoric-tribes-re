#!/usr/bin/env python3
"""Reproduce the v55 state-107 transition lookup from the target JAR resource /a."""
from pathlib import Path
import zipfile
import sys
jar = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("original/prehistoric-tribes-0.1.38.jar")
with zipfile.ZipFile(jar) as z:
    data = z.read("a")
pos = 0
records = []
offsets = [0]
for i in range(312):
    n = data[pos] | (data[pos + 1] << 8)
    pos += 2
    record = data[pos:pos+n]
    if len(record) != n:
        raise ValueError(f"record {i} truncated")
    pos += n
    records.append(record)
    offsets.append(offsets[-1] + n)
assert offsets[-1] == 17770
# Consume and validate the five trailing short tables as the loader does.
lengths = []
for _ in range(5):
    n = data[pos] | (data[pos + 1] << 8)
    pos += 2
    lengths.append(n)
    pos += 2*n
assert pos == len(data)
assert lengths == [122, 121, 6, 24, 12]
print(f"/a bytes={len(data)} payload={offsets[-1]} table_lengths={lengths}")
print(f"record27 offset={offsets[27]} len={len(records[27])} state107_flag={records[27][107]}")
print(f"record31 offset={offsets[31]} len={len(records[31])} selector={records[31][107]}")
print(f"record160 offset={offsets[160]} len={len(records[160])} state107->{records[160][107]} state69->{records[160][69]}")
assert records[160][107] == 69 and records[160][69] == 69
assert records[27][107] == 49 and records[31][107] == 13
