import re
from pathlib import Path
from collections import defaultdict

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/field_map.txt")

text = INPUT.read_text(encoding="utf-8", errors="ignore")

# ------------------------------------------------------------
# 1. Read Constant Pool Fieldref entries
#
# Example:
# #6 = Fieldref #1.#444 // c.A:B
# #20 = Fieldref #3.#464 // g.G:Z
# ------------------------------------------------------------

fieldrefs = {}

fieldref_pattern = re.compile(
    r"^\s*#(\d+)\s*=\s*Fieldref\s+#\d+\.\#\d+\s+//\s+"
    r"([^./\s]+)\.([A-Za-z_$][\w$]*):(.+)$"
)

for line in text.splitlines():
    m = fieldref_pattern.match(line)

    if not m:
        continue

    index = int(m.group(1))
    owner = m.group(2)
    name = m.group(3)
    desc = m.group(4).strip()

    fieldrefs[index] = (owner, name, desc)


# ------------------------------------------------------------
# 2. Find field accesses inside methods
# ------------------------------------------------------------

usage = defaultdict(
    lambda: {
        "read": set(),
        "write": set(),
    }
)

current_method = "UNKNOWN"

# Method declaration looks like:
#
#   private void A();
#   final boolean b(byte);
#   public c(g);
#
# Fields do not contain "(" so this is safe enough for javap output.

method_pattern = re.compile(
    r"^\s{2}.*$begin:math:text$\[\^\;\]\*$end:math:text$;\s*$"
)

instruction_pattern = re.compile(
    r"^\s*\d+:\s+"
    r"(getfield|putfield|getstatic|putstatic)"
    r"\s+#(\d+)"
)

for line in text.splitlines():

    # Detect method declaration
    if method_pattern.match(line):

        declaration = line.strip()

        # Remove trailing semicolon
        declaration = declaration[:-1]

        # Extract method name
        name_match = re.search(
            r"([A-Za-z_$<>][\w$<>]*)\s*$begin:math:text$\[\^\)\]\*$end:math:text$$",
            declaration
        )

        if name_match:
            current_method = name_match.group(1)

        continue

    # Detect field access instruction
    m = instruction_pattern.match(line)

    if not m:
        continue

    opcode = m.group(1)
    cp_index = int(m.group(2))

    if cp_index not in fieldrefs:
        continue

    owner, field_name, descriptor = fieldrefs[cp_index]

    # We only want fields belonging to c.class.
    if owner != "c":
        continue

    key = (field_name, descriptor)

    if opcode in ("getfield", "getstatic"):
        usage[key]["read"].add(current_method)

    elif opcode in ("putfield", "putstatic"):
        usage[key]["write"].add(current_method)


# ------------------------------------------------------------
# 3. Write report
# ------------------------------------------------------------

lines = []

lines.append("PREHISTORIC TRIBES - FIELD MAP: c")
lines.append("=" * 70)
lines.append("")
lines.append("Fields of c.class referenced by c.class bytecode")
lines.append("")

for (name, descriptor) in sorted(
    usage.keys(),
    key=lambda x: (x[0], x[1])
):

    data = usage[(name, descriptor)]

    lines.append(f"FIELD: {name}")
    lines.append(f"TYPE:  {descriptor}")

    reads = sorted(data["read"])
    writes = sorted(data["write"])

    lines.append(
        "READ:  " +
        (", ".join(reads) if reads else "-")
    )

    lines.append(
        "WRITE: " +
        (", ".join(writes) if writes else "-")
    )

    lines.append("")


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    "\n".join(lines),
    encoding="utf-8"
)

print(f"Created {OUTPUT}")
print(f"Field references found: {len(usage)}")
