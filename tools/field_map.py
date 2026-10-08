import re
from pathlib import Path
from collections import defaultdict

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/field_map.txt")

text = INPUT.read_text(encoding="utf-8", errors="ignore")

# Все обращения к полям c.class
field_usage = defaultdict(lambda: {
    "read": set(),
    "write": set()
})

# Разбиваем bytecode на методы
method_blocks = re.split(
    r"\n(?=(?:public|private|protected|static|final|native|synchronized|abstract|\s{2,})"
    r".*\n\s+(?:descriptor:|Code:))",
    text
)

current_method = "UNKNOWN"

for block in method_blocks:
    # Пытаемся определить имя метода
    m = re.search(
        r"\n\s*(?:public|private|protected|static|final|native|synchronized|abstract|\s)+"
        r"([A-Za-z_$][\w$]*)\([^;]*\);",
        block
    )

    if m:
        current_method = m.group(1)

    # getfield = чтение
    for m in re.finditer(
        r"getfield\s+#\d+\s+// Field ([A-Za-z_$][\w$]*):([^\s]+)",
        block
    ):
        name, desc = m.groups()
        field_usage[(name, desc)]["read"].add(current_method)

    # putfield = запись
    for m in re.finditer(
        r"putfield\s+#\d+\s+// Field ([A-Za-z_$][\w$]*):([^\s]+)",
        block
    ):
        name, desc = m.groups()
        field_usage[(name, desc)]["write"].add(current_method)

    # static fields
    for m in re.finditer(
        r"getstatic\s+#\d+\s+// Field ([A-Za-z_$][\w$]*):([^\s]+)",
        block
    ):
        name, desc = m.groups()
        field_usage[(name, desc)]["read"].add(current_method)

    for m in re.finditer(
        r"putstatic\s+#\d+\s+// Field ([A-Za-z_$][\w$]*):([^\s]+)",
        block
    ):
        name, desc = m.groups()
        field_usage[(name, desc)]["write"].add(current_method)


lines = []
lines.append("PREHISTORIC TRIBES - FIELD MAP: c")
lines.append("=" * 70)
lines.append("")
lines.append("Fields referenced by c.class bytecode")
lines.append("")

for (name, desc), usage in sorted(field_usage.items()):
    lines.append(f"FIELD: {name}")
    lines.append(f"TYPE:  {desc}")

    reads = sorted(usage["read"])
    writes = sorted(usage["write"])

    lines.append(
        "READ:  " + (", ".join(reads) if reads else "-")
    )
    lines.append(
        "WRITE: " + (", ".join(writes) if writes else "-")
    )

    lines.append("")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text("\n".join(lines), encoding="utf-8")

print(f"Created {OUTPUT}")
print(f"Fields found: {len(field_usage)}")
