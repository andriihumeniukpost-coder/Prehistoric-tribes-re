
#!/usr/bin/env python3
"""Analyze reads and writes of selected fields in javap bytecode reports."""

from collections import Counter, defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BYTECODE_DIR = ROOT / "analysis" / "bytecode"
OUTPUT = ROOT / "analysis" / "field_semantics.txt"

TARGET_NAMES = {"l", "m", "v", "w"}
CONTEXT_RADIUS = 5

# Example: // Field l:B
# Example: // Field v:I
FIELD_RE = re.compile(
    r"\bField\s+(?:[\w$./]*\.)?"
    r"([A-Za-z_$][\w$]*):([^\s]+)"
)

# Example: 414: getfield #123 // Field l:B
INSTRUCTION_RE = re.compile(
    r"^\s*\d+:\s+([a-z][a-z0-9_]*)\b"
)

METHOD_END_RE = re.compile(r"\([^;]*\);$")


def is_method_header(line):
    """Identify javap method declarations."""
    stripped = line.strip()

    return (
        "(" in stripped
        and METHOD_END_RE.search(stripped) is not None
        and not stripped.startswith(
            ("//", "descriptor:", "Signature:")
        )
        and not INSTRUCTION_RE.match(line)
    )


def get_opcode(line):
    """Extract the instruction after the bytecode offset."""
    match = INSTRUCTION_RE.match(line)
    return match.group(1) if match else None


def classify_access(line):
    """Classify a field instruction as READ or WRITE."""
    opcode = get_opcode(line)

    if opcode in {"getfield", "getstatic"}:
        return "READ"

    if opcode in {"putfield", "putstatic"}:
        return "WRITE"

    return None


def parse_report(path):
    """Parse field accesses and retain their enclosing methods."""
    lines = path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    methods = []
    current_method = "<unknown method>"
    current_class = path.stem
    current_record = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("public final class "):
            current_class = stripped
        elif stripped.startswith("public class "):
            current_class = stripped
        elif stripped.startswith("class "):
            current_class = stripped

        if is_method_header(line):
            current_method = stripped
            current_record = {
                "class": current_class,
                "method": current_method,
                "file": path.name,
                "lines": [],
                "events": [],
            }
            methods.append(current_record)

        if current_record is None:
            continue

        current_record["lines"].append(line)

        access = classify_access(line)
        if access is None:
            continue

        match = FIELD_RE.search(line)
        if not match:
            continue

        name, descriptor = match.groups()

        if name not in TARGET_NAMES:
            continue

        event = {
            "class": current_class,
            "method": current_method,
            "file": path.name,
            "name": name,
            "descriptor": descriptor,
            "field": f"{name}:{descriptor}",
            "access": access,
            "line": line.strip(),
            "index": len(current_record["lines"]) - 1,
            "body": current_record["lines"],
        }

        current_record["events"].append(event)

    events = [
        event
        for method in methods
        for event in method["events"]
    ]

    return events, methods


def main():
    if not BYTECODE_DIR.exists():
        raise SystemExit(
            f"Missing directory: {BYTECODE_DIR}\n"
            "Run the bytecode analysis workflow first."
        )

    report_files = sorted(BYTECODE_DIR.glob("*.txt"))

    if not report_files:
        raise SystemExit(
            f"No bytecode reports found in {BYTECODE_DIR}"
        )

    all_events = []
    all_methods = []

    for path in report_files:
        events, methods = parse_report(path)
        all_events.extend(events)
        all_methods.extend(methods)

    counts = Counter()
    access_by_field = defaultdict(Counter)
    methods_by_field = defaultdict(set)
    fields_by_method = defaultdict(set)

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

    output_lines = [
        "FIELD SEMANTICS REPORT",
        "=" * 72,
        f"Bytecode report files scanned: {len(report_files)}",
        f"Methods parsed: {len(all_methods)}",
        f"Target field references found: {len(all_events)}",
        "",
        "Target fields: l, m, v, w",
        "Fields are identified by both name and descriptor.",
        "READ means getfield/getstatic; WRITE means putfield/putstatic.",
        "Field names alone do not prove gameplay meaning.",
        "",
        "1. SUMMARY BY FIELD",
        "-" * 72,
    ]

    if not counts:
        output_lines.append(
            "No matching field accesses found."
        )
        output_lines.append(
            "Check that javap reports contain comments such as "
            "'// Field l:B'."
        )

    for field in sorted(counts):
        reads = access_by_field[field]["READ"]
        writes = access_by_field[field]["WRITE"]
        method_count = len(methods_by_field[field])

        output_lines.append(
            f"{field:8} references={counts[field]:4} "
            f"reads={reads:4} writes={writes:4} "
            f"methods={method_count:3}"
        )

    output_lines.extend([
        "",
        "2. METHODS USING MULTIPLE TARGET FIELDS",
        "-" * 72,
    ])

    multi_field_methods = [
        (key, sorted(fields))
        for key, fields in fields_by_method.items()
        if len(fields) > 1
    ]

    multi_field_methods.sort(
        key=lambda item: (item[0][0], item[0][2])
    )

    if not multi_field_methods:
        output_lines.append(
            "No methods using multiple target fields were found."
        )

    for (filename, class_name, method_name), fields in multi_field_methods:
        output_lines.append(
            f"{filename} | {class_name} | {method_name}"
        )
        output_lines.append(
            f"  Fields: {', '.join(fields)}"
        )

    output_lines.extend([
        "",
        "3. READ/WRITE CONTEXTS",
        "-" * 72,
    ])

    for number, event in enumerate(all_events, start=1):
        output_lines.extend([
            "",
            f"[{number}] {event['file']} | {event['method']}",
            f"Field: {event['field']} | Access: {event['access']}",
        ])

        body = event["body"]
        start = max(0, event["index"] - CONTEXT_RADIUS)
        end = min(
            len(body),
            event["index"] + CONTEXT_RADIUS + 1,
        )

        for index in range(start, end):
            marker = ">>" if index == event["index"] else "  "
            output_lines.append(f"{marker} {body[index]}")

    output_lines.extend([
        "",
        "4. INTERPRETATION NOTES",
        "-" * 72,
        "Compare READ and WRITE contexts for each field.",
        "Follow callers and array accesses before assigning meanings.",
        "Treat nearby conditions as clues, not definitive proof.",
        "Do not assume fields are coordinates, health, or animation "
        "without supporting evidence.",
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "\n".join(output_lines) + "\n",
        encoding="utf-8",
    )

    print(f"Scanned {len(report_files)} bytecode reports.")
    print(f"Parsed {len(all_methods)} methods.")
    print(f"Found {len(all_events)} target field accesses.")
    print(f"Report: {OUTPUT.relative_to(ROOT)}")
    print()

    for field in sorted(counts):
        print(
            f"{field}: {counts[field]} references; "
            f"{access_by_field[field]['READ']['READ'] if False else access_by_field[field]['READ']} reads; "
            f"{access_by_field[field]['WRITE']} writes; "
            f"{len(methods_by_field[field])} methods"
        )


if __name__ == "__main__":
    main()
