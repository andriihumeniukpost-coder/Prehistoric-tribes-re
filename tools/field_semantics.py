
#!/usr/bin/env python3
"""Analyze reads and writes of selected obfuscated fields in javap reports."""

from collections import Counter, defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BYTECODE_DIR = ROOT / "analysis" / "bytecode"
OUTPUT = ROOT / "analysis" / "field_semantics.txt"

TARGET_NAMES = {"l", "m", "v", "w"}
CONTEXT_RADIUS = 4

# Matches javap comments such as:
# // Field l:B
# // Field v:I
# // Field some/Class.w:B
FIELD_RE = re.compile(
    r"\bField\s+(?:(?:[\w$]+/)*[\w$]+\.)?"
    r"([A-Za-z_$][\w$]*):([^\s]+)"
)

INSTRUCTION_RE = re.compile(r"^\s*\d+:\s")
METHOD_END_RE = re.compile(r"\([^;]*\);$")


def is_method_header(line):
    """Recognize javap method declarations, not bytecode instructions."""
    stripped = line.strip()
    return (
        "(" in stripped
        and METHOD_END_RE.search(stripped) is not None
        and not stripped.startswith(("//", "descriptor:", "Signature:"))
        and not INSTRUCTION_RE.match(line)
    )


def classify_access(line):
    """Return READ, WRITE, or OTHER for a field instruction."""
    instruction = line.strip().split()
    if not instruction:
        return "OTHER"

    opcode = instruction[0].rstrip(":")
    if opcode in {"getfield", "getstatic"}:
        return "READ"
    if opcode in {"putfield", "putstatic"}:
        return "WRITE"
    return "OTHER"


def parse_report(path):
    """Extract target-field references grouped by method."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    methods = []
    current_method = "<class initialization or unknown method>"
    current_class = path.stem

    for line in lines:
        stripped = line.strip()

        if stripped.startswith(("public class ", "class ", "final class ")):
            current_class = stripped

        if is_method_header(line):
            current_method = stripped
            methods.append({
                "class": current_class,
                "method": current_method,
                "file": path.name,
                "lines": [],
                "events": [],
            })

        if not methods or methods[-1]["method"] != current_method:
            methods.append({
                "class": current_class,
                "method": current_method,
                "file": path.name,
                "lines": [],
                "events": [],
            })

        methods[-1]["lines"].append(line)

    events = []
    method_records = []

    for method in methods:
        body = method["lines"]
        for index, line in enumerate(body):
            match = FIELD_RE.search(line)
            if not match:
                continue

            name, descriptor = match.groups()
            if name not in TARGET_NAMES:
                continue

            access = classify_access(line)
            if access == "OTHER":
                continue

            event = {
                "class": method["class"],
                "method": method["method"],
                "file": method["file"],
                "name": name,
                "descriptor": descriptor,
                "field": f"{name}:{descriptor}",
                "access": access,
                "line": line.strip(),
                "index": index,
                "body": body,
            }
            events.append(event)
            method_records.append(method)
            method["events"].append(event)

    return events, methods


def main():
    if not BYTECODE_DIR.exists():
        raise SystemExit(
            f"Missing directory: {BYTECODE_DIR}\n"
            "Run the bytecode analysis workflow first."
        )

    report_files = sorted(
        path for path in BYTECODE_DIR.glob("*.txt")
        if path.is_file()
    )

    if not report_files:
        raise SystemExit(f"No javap reports found in {BYTECODE_DIR}")

    all_events = []
    all_methods = []

    for path in report_files:
        events, methods = parse_report(path)
        all_events.extend(events)
        all_methods.extend(methods)

    counts = Counter()
    methods_by_field = defaultdict(set)
    fields_by_method = defaultdict(set)
    access_by_field = defaultdict(Counter)

    for event in all_events:
        field = event["field"]
        method_key = (
            event["file"],
            event["class"],
            event["method"],
        )
        counts[field] += 1
        access_by_field[field][event["access"]] += 1
        methods_by_field[field].add(method_key)
        fields_by_method[method_key].add(field)

    lines = []
    lines.append("FIELD SEMANTICS REPORT")
    lines.append("=" * 72)
    lines.append(f"Bytecode report files scanned: {len(report_files)}")
    lines.append(f"Target field references found: {len(all_events)}")
    lines.append("")
    lines.append("IMPORTANT:")
    lines.append("- Names are obfuscated; meanings are not proven by names alone.")
    lines.append("- Fields with different descriptors are treated separately.")
    lines.append("- Context windows are evidence for manual inspection, not")
    lines.append("  proof of the field's gameplay meaning.")
    lines.append("")

    lines.append("1. SUMMARY BY FIELD")
    lines.append("-" * 72)
    if not counts:
        lines.append("No matching field accesses found.")
    else:
        for field in sorted(counts):
            reads = access_by_field[field]["READ"]
            writes = access_by_field[field]["WRITE"]
            method_count = len(methods_by_field[field])
            lines.append(
                f"{field:8} references={counts[field]:4} "
                f"reads={reads:4} writes={writes:4} "
                f"methods={method_count:3}"
            )

    lines.append("")
    lines.append("2. METHODS USING MORE THAN ONE TARGET FIELD")
    lines.append("-" * 72)
    multi_field_methods = [
        (key, sorted(fields))
        for key, fields in fields_by_method.items()
        if len(fields) > 1
    ]
    multi_field_methods.sort(key=lambda item: (item[0][0], item[0][2]))

    if not multi_field_methods:
        lines.append("No methods with multiple target fields were found.")
    else:
        for (filename, class_name, method_name), fields in multi_field_methods:
            lines.append(f"{filename} | {method_name}")
            lines.append(f"  Fields: {', '.join(fields)}")

    lines.append("")
    lines.append("3. ACCESS CONTEXTS")
    lines.append("-" * 72)

    if not all_events:
        lines.append("No target field accesses found.")
    else:
        for number, event in enumerate(all_events, start=1):
            lines.append("")
            lines.append(
                f"[{number}] {event['file']} | {event['method']}"
            )
            lines.append(
                f"Field: {event['field']} | Access: {event['access']}"
            )

            body = event["body"]
            start = max(0, event["index"] - CONTEXT_RADIUS)
            end = min(len(body), event["index"] + CONTEXT_RADIUS + 1)

            for context_index in range(start, end):
                marker = ">>" if context_index == event["index"] else "  "
                lines.append(f"{marker} {body[context_index]}")

    lines.append("")
    lines.append("4. NEXT INVESTIGATION TARGETS")
    lines.append("-" * 72)
    lines.append(
        "Inspect methods that read and write the same field, then follow "
        "the values through their callers and array accesses."
    )
    lines.append(
        "Do not assign meanings such as position, health, animation, or "
        "resource count until conditions and call sites support them."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Scanned {len(report_files)} bytecode report files.")
    print(f"Found {len(all_events)} target field accesses.")
    print(f"Report written to: {OUTPUT.relative_to(ROOT)}")
    print("")
    print("Field summary:")
    for field in sorted(counts):
        print(
            f"  {field}: {counts[field]} references, "
            f"{len(methods_by_field[field])} methods"
        )


if __name__ == "__main__":
    main()
