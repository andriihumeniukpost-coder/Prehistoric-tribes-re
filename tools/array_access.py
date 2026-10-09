
from pathlib import Path
import re
from collections import defaultdict, Counter

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/array_access.txt")

TARGET_OFFSETS = [0, 101, 2828, 2929, 3131, 3232, 4444]
CONTEXT_BEFORE = 5
CONTEXT_AFTER = 7
MAX_EXAMPLES_PER_TYPE = 12


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def parse_method(line):
    stripped = line.strip()

    if not stripped.endswith(");"):
        return None

    if stripped.startswith(("descriptor:", "Signature:", "//")):
        return None

    if " = " in stripped:
        return None

    if not re.match(
        r"^(?:(?:public|private|protected|static|final|"
        r"native|synchronized|abstract|strictfp)\s+)+"
        r".+\);$",
        stripped,
    ):
        return None

    return stripped[:-1]


def constant_value(line):
    patterns = [
        (r"\biconst_m1\b", -1),
        (r"\biconst_([0-5])\b", None),
        (r"\bbipush\s+(-?\d+)\b", None),
        (r"\bsipush\s+(-?\d+)\b", None),
    ]

    for pattern, fixed_value in patterns:
        match = re.search(pattern, line)
        if not match:
            continue

        if fixed_value is not None:
            return fixed_value

        value = match.group(1)

        if pattern.startswith(r"\biconst_"):
            return int(value)

        return int(value)

    return None


def find_accesses(lines):
    accesses = []
    current_method = "(method unknown)"

    for index, line in enumerate(lines):
        parsed = parse_method(line)
        if parsed:
            current_method = parsed

        value = constant_value(line)
        if value not in TARGET_OFFSETS:
            continue

        # A candidate index must use the current record index v.
        window_end = min(len(lines), index + 8)
        window = lines[index:window_end]
        block = "\n".join(window)

        if not re.search(r"Field v:I", block):
            continue

        if not re.search(r"\biadd\b", block):
            continue

        opcode_index = None
        operation = None

        for j in range(index + 1, min(len(lines), index + 10)):
            instruction = lines[j]

            if re.search(r"\bbaload\b", instruction):
                opcode_index = j
                operation = "READ"
                break

            if re.search(r"\bbastore\b", instruction):
                opcode_index = j
                operation = "WRITE"
                break

        if opcode_index is None:
            continue

        start = max(0, index - CONTEXT_BEFORE)
        end = min(len(lines), opcode_index + CONTEXT_AFTER + 1)

        accesses.append({
            "offset": value,
            "operation": operation,
            "method": current_method,
            "line": index + 1,
            "context": lines[start:end],
        })

    return accesses


def main():
    text = read_text(INPUT)
    lines = text.splitlines()
    accesses = find_accesses(lines)

    counts = Counter()
    methods = defaultdict(set)
    examples = defaultdict(list)

    for access in accesses:
        key = (access["offset"], access["operation"])
        counts[key] += 1
        methods[key].add(access["method"])

        if len(examples[key]) < MAX_EXAMPLES_PER_TYPE:
            examples[key].append(access)

    output = [
        "PREHISTORIC TRIBES - ARRAY ACCESS ANALYSIS",
        "Class: c",
        "",
        "Target: a[offset + v] candidate accesses",
        "",
        "IMPORTANT:",
        "These are bytecode-pattern matches, not guaranteed semantic fields.",
        "Each context must be checked before assigning a field meaning.",
        "",
        "=" * 80,
        "SUMMARY",
        "=" * 80,
        "",
        f"TOTAL MATCHES: {len(accesses)}",
        "",
    ]

    for offset in TARGET_OFFSETS:
        output.append("=" * 80)
        output.append(f"OFFSET {offset} + v")
        output.append("=" * 80)
        output.append("")

        for operation in ("READ", "WRITE"):
            key = (offset, operation)
            output.append(f"{operation} MATCHES: {counts[key]}")
            output.append(f"METHODS: {len(methods[key])}")

            for number, access in enumerate(examples[key], start=1):
                output.append("")
                output.append(
                    f"EXAMPLE {number} | "
                    f"{access['method']} | BYTECODE LINE {access['line']}"
                )

                for context_line in access["context"]:
                    output.append(f"    {context_line}")

            output.append("")

    output.extend([
        "=" * 80,
        "ANALYSIS NOTES",
        "=" * 80,
        "",
        "1. baload indicates a byte/boolean array read.",
        "2. bastore indicates a byte/boolean array write.",
        "3. The script searches for target constants near v and iadd.",
        "4. Nearby instructions are included for manual verification.",
        "5. Some matches may be false positives because JVM instructions",
        "   operate on a stack and textual proximity is not proof.",
        "6. Numeric values and offsets do not identify game semantics alone.",
        "",
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(output), encoding="utf-8")

    print(f"Created: {OUTPUT}")
    print(f"Matches: {len(accesses)}")


if __name__ == "__main__":
    main()
