#!/usr/bin/env python3
"""Strictly trace byte-array accesses indexed by CONSTANT + field v:I.

Scans analysis/bytecode/*.txt and writes:
    analysis/array_field_trace.txt

This is a bytecode-pattern analyzer, not a full JVM stack simulator.
It only accepts a narrow instruction sequence immediately before
baload/bastore and reports ambiguous cases separately by omission.
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
FIELD_RE = re.compile(r"//\s*Field\s+([A-Za-z_$][\w$]*):([^\s]+)")


def parse_field(instruction):
    match = FIELD_RE.search(instruction["text"])
    return (match.group(1), match.group(2)) if match else None


def pushed_integer(instruction):
    opcode = instruction["opcode"]
    operand = instruction["operand"].strip()

    if opcode.startswith("iconst_"):
        suffix = opcode[len("iconst_"):]
        if suffix == "m1":
            return -1
        if suffix.isdigit():
            return int(suffix)

    if opcode in ("bipush", "sipush"):
        match = re.match(r"^-?\d+\b", operand)
        if match:
            return int(match.group(0))

    if opcode in ("ldc", "ldc_w"):
        match = re.match(r"^#\d+\s+//\s+int\s+(-?\d+)\b", operand)
        if match:
            return int(match.group(1))

    return None


def parse_report(path):
    methods = []
    current_method = None

    # javap reports contain declarations followed by instruction lines.
    method_re = re.compile(r"^\s*(?:public|protected|private|static|final|synchronized|native|abstract).*\([^;]*\);\s*$")

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()

            if method_re.match(line) and not stripped.startswith("//"):
                current_method = {
                    "file": path.name,
                    "signature": stripped,
                    "instructions": [],
                }
                methods.append(current_method)
                continue

            match = INSTRUCTION_RE.match(line)
            if match and current_method is not None:
                current_method["instructions"].append({
                    "offset": int(match.group(1)),
                    "opcode": match.group(2),
                    "operand": match.group(3).strip(),
                    "text": stripped,
                })

    return methods


def is_array_field(instruction):
    return parse_field(instruction) == ("a", "[B")


def match_access(instructions, pos):
    """Accept only a narrow, ordered stack-building pattern.

    Expected core sequence:
        getfield a:[B
        integer constant
        aload_0
        getfield v:I
        iadd
        baload/bastore

    Small harmless stack instructions are not allowed here. This avoids
    matching an earlier expression or a different array's access.
    """
    access = instructions[pos]
    opcode = access["opcode"]

    if opcode not in ("baload", "bastore"):
        return None

    # Index and array must be built by the immediately preceding
    # instructions in this exact order.
    if pos < 4:
        return None

    array_instruction = instructions[pos - 5] if pos >= 5 else None
    constant_instruction = instructions[pos - 4]
    receiver_instruction = instructions[pos - 3]
    field_instruction = instructions[pos - 2]
    add_instruction = instructions[pos - 1]

    if array_instruction is None or not is_array_field(array_instruction):
        return None

    base = pushed_integer(constant_instruction)
    if base is None:
        return None

    if receiver_instruction["opcode"] != "aload_0":
        return None

    if parse_field(field_instruction) != ("v", "I"):
        return None

    if add_instruction["opcode"] != "iadd":
        return None

    # Ensure these instructions are contiguous in bytecode.
    core = instructions[pos - 5:pos + 1]
    for left, right in zip(core, core[1:]):
        if left["offset"] >= right["offset"]:
            return None

    return {
        "base": base,
        "operation": "READ" if opcode == "baload" else "WRITE",
        "offset": access["offset"],
        "context": instructions[max(0, pos - 5):min(len(instructions), pos + 2)],
    }


def analyze_method(method):
    events = []
    instructions = method["instructions"]

    for pos in range(len(instructions)):
        result = match_access(instructions, pos)
        if result is None:
            continue

        events.append({
            "file": method["file"],
            "method": method["signature"],
            **result,
        })

    return events


def main():
    if not INPUT_DIR.exists():
        raise SystemExit(f"Input directory not found: {INPUT_DIR}")

    reports = sorted(INPUT_DIR.glob("*.txt"))
    if not reports:
        raise SystemExit(f"No bytecode reports found in {INPUT_DIR}")

    methods = []
    for report in reports:
        methods.extend(parse_report(report))

    events = []
    for method in methods:
        events.extend(analyze_method(method))

    counts = Counter()
    methods_by_base = defaultdict(set)

    for event in events:
        base = event["base"]
        counts[(base, event["operation"])] += 1
        methods_by_base[base].add((event["file"], event["method"]))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        out.write("STRICT ARRAY FIELD TRACE REPORT\n")
        out.write("=" * 72 + "\n")
        out.write(f"Input reports scanned: {len(reports)}\n")
        out.write(f"Methods parsed: {len(methods)}\n")
        out.write(f"Strict pattern matches: {len(events)}\n")
        out.write("Pattern: a:[B, CONSTANT, aload_0, getfield v:I, iadd, access\n")
        out.write("This narrow matcher may miss valid patterns with other bytecode forms.\n\n")

        out.write("1. SUMMARY BY BASE OFFSET\n")
        out.write("-" * 72 + "\n")

        for base in sorted(methods_by_base):
            out.write(
                f"{base:>6} + v:I  "
                f"reads={counts[(base, 'READ')]:>4} "
                f"writes={counts[(base, 'WRITE')]:>4} "
                f"methods={len(methods_by_base[base]):>3}\n"
            )

        if not events:
            out.write("No strict matches found.\n")

        out.write("\n2. ACCESS DETAILS\n")
        out.write("-" * 72 + "\n")

        for number, event in enumerate(events, start=1):
            out.write(
                f"\n[{number}] {event['file']} | {event['method']}\n"
            )
            out.write(
                f"Candidate: a[{event['base']} + v] | "
                f"{event['operation']} | bytecode offset {event['offset']}\n"
            )
            out.write("Context:\n")
            for instruction in event["context"]:
                marker = ">> " if instruction["offset"] == event["offset"] else "   "
                out.write(
                    f"  {marker}{instruction['offset']:>5}: "
                    f"{instruction['opcode']:<12} {instruction['operand']}\n"
                )

        out.write("\n3. LIMITATIONS\n")
        out.write("-" * 72 + "\n")
        out.write(
            "- This is a strict pattern matcher, not a complete JVM stack analysis.\n"
            "- It intentionally rejects patterns that do not match the exact sequence.\n"
            "- A match confirms only a bytecode shape, not the meaning of the field.\n"
            "- Compare results with record_map.txt and paired_regions.txt.\n"
        )

    print(f"Reports scanned: {len(reports)}")
    print(f"Methods parsed: {len(methods)}")
    print(f"Strict pattern matches: {len(events)}")
    print(f"Output: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
