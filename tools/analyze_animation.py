
#!/usr/bin/env python3
"""Collect animation-related evidence from the Prehistoric Tribes analysis files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
OUTPUT = ANALYSIS / "animation_report.txt"

TARGETS = (
    "frame_index_trace.txt",
    "frame_methods.txt",
    "field_usage.txt",
    "record_fields.txt",
    "record_map.txt",
    "record_structure.txt",
    "record_clusters.txt",
)

PATTERNS = (
    re.compile(r"\b(?:o|q|ai)\s*:\s*[BISZ]"),
    re.compile(r"\ba\s*\[\s*aS?\s*\[\s*154\s*\]"),
    re.compile(r"\b(?:154|7587|pi8|pi9|pi0)\b", re.I),
    re.compile(r"Image\.createImage|drawRegion|drawImage"),
    re.compile(r"\b(?:frame|animation|sprite|record|offset)\b", re.I),
)

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"[READ ERROR: {exc}]"

def section(title: str, content: str) -> str:
    return f"\n{'=' * 78}\n{title}\n{'=' * 78}\n{content.rstrip()}\n"

def find_context(path: Path, terms: list[str], radius: int = 3,
                 max_hits: int = 80) -> str:
    if not path.is_file():
        return f"[NOT FOUND] {path.relative_to(ROOT)}"

    lines = read_text(path).splitlines()
    hits = []
    for i, line in enumerate(lines):
        if any(term.lower() in line.lower() for term in terms):
            start = max(0, i - radius)
            end = min(len(lines), i + radius + 1)
            hits.append((start, end))

    merged = []
    for start, end in hits:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    out = []
    for start, end in merged[:max_hits]:
        out.append(f"\n--- lines {start + 1}-{end} ---")
        out.extend(f"{i + 1}: {lines[i]}" for i in range(start, end))

    omitted = max(0, len(merged) - max_hits)
    if omitted:
        out.append(f"\n[Omitted {omitted} additional matching blocks]")
    return "\n".join(out) if out else "[No matching lines]"

def inspect_json(path: Path) -> str:
    if not path.is_file():
        return f"[NOT FOUND] {path.relative_to(ROOT)}"

    raw = read_text(path)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"File exists but is not valid JSON: {exc}\nFirst 2000 chars:\n{raw[:2000]}"

    lines = [
        f"File: {path.relative_to(ROOT)}",
        f"Root type: {type(obj).__name__}",
    ]

    if isinstance(obj, dict):
        lines.append("Top-level keys: " + ", ".join(map(str, list(obj)[:100])))
        for key, value in obj.items():
            if isinstance(value, list):
                lines.append(f"{key}: list, {len(value)} items")
            elif isinstance(value, dict):
                lines.append(f"{key}: object, {len(value)} keys")
            else:
                lines.append(f"{key}: {type(value).__name__} = {str(value)[:160]}")
    elif isinstance(obj, list):
        lines.append(f"List length: {len(obj)}")
        for item in obj[:5]:
            lines.append(json.dumps(item, ensure_ascii=False)[:1000])

    return "\n".join(lines)

def inspect_csv(path: Path) -> str:
    if not path.is_file():
        return f"[NOT FOUND] {path.relative_to(ROOT)}"

    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
            reader = csv.DictReader(handle, dialect=dialect)
            rows = list(reader)
        out = [
            f"File: {path.relative_to(ROOT)}",
            f"Rows: {len(rows)}",
            f"Columns: {reader.fieldnames}",
        ]
        for row in rows[:8]:
            out.append(json.dumps(row, ensure_ascii=False))
        return "\n".join(out)
    except Exception as exc:
        return f"CSV inspection failed: {exc}"

def inventory() -> str:
    roots = [
        ANALYSIS / "a_dump",
        ANALYSIS / "pd0_tables",
        ANALYSIS / "bytecode",
        ROOT / "tools",
    ]
    out = []
    for folder in roots:
        out.append(f"\n{folder.relative_to(ROOT)}/")
        if not folder.exists():
            out.append("  [directory missing]")
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                try:
                    size = path.stat().st_size
                except OSError:
                    size = -1
                out.append(f"  {path.relative_to(ROOT)} ({size} bytes)")
    return "\n".join(out)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a single report of animation and sprite evidence."
    )
    parser.add_argument(
        "--output", default=str(OUTPUT),
        help="Report path (default: analysis/animation_report.txt)",
    )
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output

    parts = [
        "PREHISTORIC TRIBES — ANIMATION RESEARCH REPORT",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Repository root: {ROOT}",
        "\nThis report gathers evidence; it does not modify game code or source dumps.",
        section("1. PROJECT FILE INVENTORY", inventory()),
    ]

    for name in TARGETS:
        path = ANALYSIS / name
        parts.append(section(
            f"2. EVIDENCE: {name}",
            find_context(
                path,
                ["154", "7587", "pi8", "pi9", "pi0",
                 "Field o:B", "Field q:B", "Field ai:B",
                 "drawRegion", "drawImage", "createImage"],
            ),
        ))

    g_path = ANALYSIS / "bytecode" / "g.txt"
    parts.append(section(
        "3. MAIN GAME CLASS — ANIMATION AND DRAWING",
        find_context(
            g_path,
            ["private void U()", "final void b(int)",
             "private void c(byte)", "drawRegion", "drawImage",
             "Field o:B", "Field q:B", "Field ai:B"],
            radius=5,
            max_hits=100,
        ),
    ))

    dump_json = ANALYSIS / "a_dump" / "a_dump.json"
    parts.append(section("4. RESOURCE /a JSON STRUCTURE", inspect_json(dump_json)))

    records_csv = ANALYSIS / "a_dump" / "a_records.csv"
    parts.append(section("5. RESOURCE /a RECORDS CSV", inspect_csv(records_csv)))

    csv_dir = ANALYSIS / "pd0_tables"
    if csv_dir.exists():
        for path in sorted(csv_dir.glob("j_*.csv")):
            parts.append(section(
                f"6. SPRITE TABLE: {path.name}",
                inspect_csv(path),
            ))

    # Search the repository's text/CSV/JSON files for the most relevant clues.
    matches = []
    excluded_parts = {".git", ".venv", "__pycache__", "node_modules"}
    candidate_files = (
        p for p in ROOT.rglob("*")
        if p.is_file()
        and not excluded_parts.intersection(p.parts)
        and p.suffix.lower() in {".txt", ".csv", ".json", ".py", ".md"}
        and p != output
    )

    for path in candidate_files:
        try:
            if path.stat().st_size > 5_000_000:
                continue
            text = read_text(path)
        except OSError:
            continue

        for number, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in PATTERNS):
                matches.append(
                    f"{path.relative_to(ROOT)}:{number}: {line.strip()[:350]}"
                )

    counts = Counter(line.split(":", 1)[0] for line in matches)
    summary = [
        f"Matching lines found: {len(matches)}",
        "Files with most matches:",
    ]
    summary.extend(f"  {name}: {count}" for name, count in counts.most_common(30))
    summary.append("\nMatching lines:")
    summary.extend(matches[:1500])
    if len(matches) > 1500:
        summary.append(f"\n[Truncated: {len(matches) - 1500} more matching lines]")

    parts.append(section("7. CROSS-REPOSITORY SEARCH", "\n".join(summary)))
    parts.append(section(
        "8. NEXT INVESTIGATION CHECKLIST",
        "\n".join([
            "- Confirm the exact resource /a record at index 154.",
            "- Separate byte-array offsets from short-array offsets.",
            "- Trace every write to fields o, q, and ai.",
            "- Identify callers of c(byte) and the selected pi8 record.",
            "- Compare runtime frame selection with resource record lengths.",
            "- Do not infer animation order from CSV row order alone.",
        ]),
    ))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Report written: {output}")
    print(f"Size: {output.stat().st_size:,} bytes")
    print("No game source files were changed.")

if __name__ == "__main__":
    main()
