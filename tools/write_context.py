
from pathlib import Path
import re

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/write_context.txt")

TARGET_OFFSETS = [2828, 2929, 3131, 3232, 4444]

BEFORE = 14
AFTER = 18

INSTRUCTION_RE = re.compile(
    r"^\s*(\d+):\s+([a-z][a-z0-9_]*)\s*(.*?)\s*$"
)
FIELD_RE = re.compile(r"// Field ([^:]+):([^\s]+)")


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    return path.read_text(encoding="utf-8", errors="replace")


def parse_methods(text):
    methods = []
    current_name = "(unknown method)"
    current_lines = []
    current_instructions = []

    for line in text.splitlines():
        stripped = line.strip()

        # A javap method declaration is followed by its Code section.
        if (
            stripped.endswith(";")
            and "(" in stripped
            and not stripped.startswith(
                ("//", "descriptor:", "Signature:")
            )
            and not INSTRUCTION_RE.match(line)
        ):
            if current_instructions:
                methods.append({
                    "name": current_name,
                    "lines": current_lines,
                    "instructions": current_instructions,
                })

            current_name = stripped
            current_lines = [line]
            current_instructions = []
            continue

        current_lines.append(line)

        match = INSTRUCTION_RE.match(line)
        if match:
            current_instructions.append({
                "pc": int(match.group(1)),
                "op": match.group(2),
                "arg": match.group(3),
                "raw": line.rstrip(),
                "line": len(current_lines) - 1,
            })

    if current_instructions:
        methods.append({
            "name": current_name,
            "lines": current_lines,
            "instructions": current_instructions,
        })

    return methods


def const_value(op, arg):
    if op == "iconst_m1":
        return -1

    if re.fullmatch(r"iconst_[0-5]", op):
        return int(op[-1])

    if op in ("bipush", "sipush"):
        match = re.match(r"-?\d+", arg)
        if match:
            return int(match.group())

    return None


def get_field(arg):
    match = FIELD_RE.search(arg)
    if not match:
        return None

    return f"{match.group(1)}:{match.group(2)}"


def find_write_candidates(instructions):
    candidates = []

    # This intentionally identifies address-building candidates,
    # then retains the entire method context for manual verification.
    for index, ins in enumerate(instructions):
        if ins["op"] != "bastore":
            continue

        start = max(0, index - 12)
        window = instructions[start:index + 1]

        fields = set()
        constants = []

        for item in window:
            field = get_field(item["arg"])

            if field:
                fields.add(field)

            value = const_value(item["op"], item["arg"])

            if value is not None:
                constants.append(value)

        if "a:[B" not in fields or "v:I" not in fields:
            continue

        possible_offsets = [
            value for value in constants
            if value in TARGET_OFFSETS
        ]

        if not possible_offsets:
            continue

        candidates.append({
            "instruction_index": index,
            "pc": ins["pc"],
            "offsets": possible_offsets,
        })

    return candidates


def render_method(method, candidate, number):
    instructions = method["instructions"]
    index = candidate["instruction_index"]

    start = max(0, index - BEFORE)
    end = min(len(instructions), index + AFTER + 1)

    output = [
        "-" * 80,
        f"EXAMPLE {number}",
        f"METHOD: {method['name']}",
        f"WRITE BYTECODE OFFSET: {candidate['pc']}",
        "POSSIBLE TARGET OFFSETS: "
        + ", ".join(map(str, candidate["offsets"])),
        "",
        "CONTEXT:",
    ]

    for i in range(start, end):
        marker = " >>> " if i == index else "     "
        output.append(marker + instructions[i]["raw"])

    output.extend([
        "",
        "NOTE: This is a candidate, not a proven address match.",
        "Inspect stack order and the exact index expression manually.",
        "",
    ])

    return output


def main():
    methods = parse_methods(read_text(INPUT))
    output = [
        "PREHISTORIC TRIBES - WRITE CONTEXT REPORT",
        "Class: c",
        "",
        "Purpose: inspect bytecode around bastore instructions",
        "that may write to selected a[offset + v] regions.",
        "",
        "WARNING:",
        "Nearby constants and fields do not prove the exact address.",
        "Each candidate must be checked against JVM stack order.",
        "",
    ]

    total = 0

    for base in TARGET_OFFSETS:
        output.extend([
            "=" * 80,
            f"TARGET OFFSET {base} + v",
            "=" * 80,
            "",
        ])

        found_for_base = 0

        for method in methods:
            candidates = find_write_candidates(
                method["instructions"]
            )

            for candidate in candidates:
                if base not in candidate["offsets"]:
                    continue

                total += 1
                found_for_base += 1

                output.extend(
                    render_method(method, candidate, total)
                )

        output.append(
            f"CANDIDATES FOR {base} + v: {found_for_base}"
        )
        output.append("")

    output.extend([
        "=" * 80,
        "SUMMARY",
        "=" * 80,
        f"PARSED METHODS: {len(methods)}",
        f"WRITE CANDIDATES: {total}",
        "",
        "This report is intended for manual bytecode inspection.",
        "It does not assign semantic names to any array region.",
        "",
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(output) + "\n", encoding="utf-8")

    print(f"Created: {OUTPUT}")
    print(f"Parsed methods: {len(methods)}")
    print(f"Write candidates: {total}")


if __name__ == "__main__":
    main()
