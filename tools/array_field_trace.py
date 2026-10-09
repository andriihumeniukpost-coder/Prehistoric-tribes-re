
#!/usr/bin/env python3
"""Trace byte-array accesses indexed by CONSTANT + field v:I.

Input:
    analysis/bytecode/*.txt

Output:
    analysis/array_field_trace.txt

This is a heuristic bytecode analyzer. Results are candidates for manual
verification, not proof of gameplay semantics.
"""

from collections import Counter, defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "analysis" / "bytecode"
OUTPUT_FILE = ROOT / "analysis" / "array_field_trace.txt"

INSTRUCTION_RE = re.compile(
    r"^\s*(\d+):\s+([a-z][a-z0-9_]*)\b(.*?)\s*$"
)
FIELD_RE = re.compile(
    r"//\s*Field\s+([A-Za-z_$][\w$]*):([^\s]+)"
)

# Match ordinary javap method declarations such as:
# private void h(int);
# public final void a(java.lang.String);
METHOD_RE = re.compile(r"^\s*.+\([^;]*\);\s*$")


def parse_field(instruction):
    """Return (field_name, descriptor), or None."""
    match = FIELD_RE.search(instruction["text"])
    if not match:
        return None
    return match.group(1), match.group(2)


def pushed_integer(instruction):
    """Read an integer pushed by iconst, bipush, sipush, or ldc."""
    opcode = instruction["opcode"]
    operand = instruction["operand"].strip()

    if opcode.startswith("iconst_"):
        suffix = opcode[len("iconst_"):]
        if suffix == "m1":
            return -1
        if suffix.isdigit():
            return int(suffix)

    if opcode in ("bipush", "sipush", "ldc", "ldc_w"):
        # For ldc, accept only a plain integer constant.
        match = re.match(r"^-?\d+\b", operand)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                pass

    return None


def find_index_pattern(instructions, access_position):
    """Find a:[B, integer constant, v:I, iadd before baload/bastore."""
    start = max(0, access_position - 14)
    window = instructions[start:access_position]

    # Search backwards so the closest plausible index expression wins.
    for add_pos in range(len(window) - 1, -1, -1):
        if window[add_pos]["opcode"] != "iadd":
            continue

        v_pos = None
        for pos in range(add_pos - 1, max(-1, add_pos - 6), -1):
            field = parse_field(window[pos])
            if field == ("v", "I"):
                v_pos = pos
                break

        if v_pos is None:
            continue

        constant_pos = None
        constant_value = None
        for pos in range(v_pos - 1, max(-1, v_pos - 6), -1):
            value = pushed_integer(window[pos])
            if value is not None:
                constant_pos = pos
                constant_value = value
                break

        if constant_pos is None:
            continue

        array_pos = None
        for pos in range(constant_pos - 1, max(-1, constant_pos - 6), -1):
            if parse_field(window[pos]) == ("a", "[B"):
                array_pos = pos
                break

        if array_pos is None:
            continue

        return {
            "base": constant_value,
            "array_field": "a:[B",
            "index_field": "v:I",
            "sequence": window[array_pos:add_pos + 1],
        }

    return None


def parse_report(path):
    """Parse methods and bytecode instructions from one javap report."""
    methods = []
    current_method = None
    current_class = path.stem

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()

            if stripped.startswith("public ") and " class " in stripped:
                current_class = stripped

            if (
                METHOD_RE.match(line)
                and "(" in line
                and not stripped.startswith("//")
            ):
                current_method = {
                    "file": path.name,
                    "class": current_class,
                    "signature": stripped,
                    "instructions": [],
                }
                methods.append(current_method)
                continue

            match = INSTRUCTION_RE.match(line)
            if match and current_method is not None:
                offset = int(match.group(1))
                opcode = match.group(2)
                operand = match.group(3).strip()

                current_method["instructions"].append({
                    "offset": offset,
                    "opcode": opcode,
                    "operand": operand,
                    "text": stripped,
                })

    return methods


def analyze_method(method):
    """Return array-access events that match the candidate index pattern."""
    instructions = method["instructions"]
    events = []

    for position, instruction in enumerate(instructions):
        opcode = instruction["opcode"]
        if opcode not in ("baload", "bastore"):
            continue

        pattern = find_index_pattern(instructions, position)
        if pattern is None:
            continue

        # Include nearby instructions so a person can verify the match.
        context_start = max(0, position - 6)
        context_end = min(len(instructions), position + 2)

        events.append({
            "file": method["file"],
            "class": method["class"],
            "method": method["signature"],
            "operation": "READ" if opcode == "baload" else "WRITE",
            "base": pattern["base"],
            "offset": instruction["offset"],
            "context": instructions[context_start:context_end],
        })

    return events


def main():
    if not INPUT_DIR.exists():
        raise SystemExit(
            f"Input directory not found: {INPUT_DIR}\n"
            "Run the bytecode extraction workflow first."
        )

    report_files = sorted(INPUT_DIR.glob("*.txt"))
    if not report_files:
        raise SystemExit(
            f"No .txt reports found in {INPUT_DIR}\n"
            "Run the bytecode extraction workflow first."
        )

    all_methods = []
    for report in report_files:
        all_methods.extend(parse_report(report))

    all_events = []
    for method in all_methods:
        all_events.extend(analyze_method(method))

    counts = Counter()
    methods_by_base = defaultdict(set)

    for event in all_events:
        counts[(event["base"], event["operation"])] += 1
        methods_by_base[event["base"]].add(
            (event["file"], event["method"])
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        out.write("ARRAY FIELD TRACE REPORT\n")
        out.write("=" * 72 + "\n")
        out.write(f"Input reports scanned: {len(report_files)}\n")
        out.write(f"Methods parsed: {len(all_methods)}\n")
        out.write(f"Candidate array accesses: {len(all_events)}\n")
        out.write(
            "Pattern sought: a:[B indexed by CONSTANT + v:I\n"
        )
        out.write(
            "READ = baload; WRITE = bastore. Matches are heuristic.\n\n"
        )

        out.write("1. SUMMARY BY BASE OFFSET\n")
        out.write("-" * 72 + "\n")

        if not counts:
            out.write(
                "No candidate accesses found. Check the javap report "
                "format and input directory.\n"
            )
        else:
            for base in sorted(methods_by_base):
                reads = counts[(base, "READ")]
                writes = counts[(base, "WRITE")]
                method_count = len(methods_by_base[base])
                out.write(
                    f"{base:>6} + v:I  reads={reads:>4} "
                    f"writes={writes:>4} methods={method_count:>3}\n"
                )

        out.write("\n2. ACCESS DETAILS\n")
        out.write("-" * 72 + "\n")

        for number, event in enumerate(all_events, start=1):
            out.write(
                f"\n[{number}] {event['file']} | "
                f"{event['method']}\n"
            )
            out.write(
                f"Class: {event['class']}\n"
                f"Candidate: a[{event['base']} + v] | "
                f"{event['operation']} | "
                f"instruction offset {event['offset']}\n"
            )
            out.write("Context:\n")
            for instruction in event["context"]:
                marker = (
                    ">> " if instruction["offset"] == event["offset"]
                    else "   "
                )
                out.write(
                    f"  {marker}{instruction['offset']:>5}: "
                    f"{instruction['opcode']:<12} "
                    f"{instruction['operand']}\n"
                )

        out.write("\n3. INTERPRETATION NOTES\n")
        out.write("-" * 72 + "\n")
        out.write(
            "- A repeated base offset suggests a recurring data region, "
            "but does not prove its meaning.\n"
            "- READ/WRITE counts are counts of matched bytecode "
            "instructions, not gameplay events.\n"
            "- Inspect the surrounding method before assigning a "
            "semantic name to any field.\n"
        )

    print(f"Reports scanned: {len(report_files)}")
    print(f"Methods parsed: {len(all_methods)}")
    print(f"Candidate accesses: {len(all_events)}")
    print(f"Output written to: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
