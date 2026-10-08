import re
from pathlib import Path
from collections import defaultdict

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/field_map.txt")

text = INPUT.read_text(encoding="utf-8", errors="ignore")

# Constant-pool Fieldref:
# #6 = Fieldref #1.#444 // c.A:B
# #20 = Fieldref #3.#464 // g.G:Z
fieldrefs = {}

for line in text.splitlines():
    m = re.match(
        r"^\s*#(\d+)\s*=\s*Fieldref\s+#\d+\.\#\d+\s+//\s+"
        r"([^./\s]+)\.([A-Za-z_$][\w$]*):(.+)$",
        line,
    )
    if m:
        index = int(m.group(1))
        owner = m.group(2)
        name = m.group(3)
        descriptor = m.group(4).strip()
        fieldrefs[index] = (owner, name, descriptor)

# Usage of fields belonging to class c.
usage = defaultdict(lambda: {"read": set(), "write": set()})

current_method = "<class>"

method_pattern = re.compile(r"^\s{2}.*\([^;]*\);\s*$")
instruction_pattern = re.compile(
    r"^\s*\d+:\s+(getfield|putfield|getstatic|putstatic)\s+#(\d+)"
)

for line in text.splitlines():
    if method_pattern.match(line):
        declaration = line.strip().rstrip(";")
        m = re.search(
            r"([A-Za-z_$<>][\w$<>]*)\s*\([^)]*\)$",
            declaration,
        )
        if m:
            current_method = m.group(1)
        continue

    m = instruction_pattern.match(line)
    if not m:
        continue

    opcode = m.group(1)
    cp_index = int(m.group(2))

    ref = fieldrefs.get(cp_index)
    if ref is None:
        continue

    owner, name, descriptor = ref

    # Ignore fields belonging to g, d, Object, etc.
    if owner != "c":
        continue

    key = (name, descriptor)

    if opcode in ("getfield", "getstatic"):
        usage[key]["read"].add(current_method)
    else:
        usage[key]["write"].add(current_method)

lines = [
    "PREHISTORIC TRIBES - FIELD MAP: c",
    "=" * 70,
    "",
    "Fields of c.class referenced by c.class bytecode",
    "",
]

for (name, descriptor) in sorted(usage):
    data = usage[(name, descriptor)]

    lines.append(f"FIELD: {name}")
    lines.append(f"TYPE:  {descriptor}")

    reads = sorted(data["read"])
    writes = sorted(data["write"])

    lines.append("READ:  " + (", ".join(reads) if reads else "-"))
    lines.append("WRITE: " + (", ".join(writes) if writes else "-"))
    lines.append("")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text("\n".join(lines), encoding="utf-8")

print(f"Created {OUTPUT}")
print(f"Field references found: {len(usage)}")
