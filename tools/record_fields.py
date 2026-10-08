from pathlib import Path
import re
from collections import defaultdict, Counter

INPUT = Path("analysis/record_map.txt")
OUTPUT = Path("analysis/record_fields.txt")


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def parse_record_map(text):
    """
    Parse record_map.txt.

    Expected blocks contain:
        METHOD <name>
        OFFSET <number> + v

    The parser keeps all offsets associated with each method.
    """

    methods = defaultdict(list)
    current_method = None

    for line in text.splitlines():

        method_match = re.match(
            r"^\s*METHOD\s+(.+?)\s*$",
            line
        )

        if method_match:
            current_method = method_match.group(1).strip()
            continue

        offset_match = re.match(
            r"^\s*OFFSET\s+(-?\d+)\s+\+\s+v",
            line
        )

        if offset_match and current_method is not None:
            offset = int(offset_match.group(1))
            methods[current_method].append(offset)

    return methods


def normalize_methods(methods):
    result = {}

    for method, offsets in methods.items():
        result[method] = sorted(set(offsets))

    return result


def build_offset_methods(methods):
    result = defaultdict(set)

    for method, offsets in methods.items():
        for offset in offsets:
            result[offset].add(method)

    return result


def build_offset_counts(text):
    counts = Counter()

    for line in text.splitlines():

        match = re.match(
            r"^\s*OFFSET\s+(-?\d+)\s+\+\s+v",
            line
        )

        if match:
            counts[int(match.group(1))] += 1

    return counts


def build_cooccurrence(methods):
    """
    Count how often two offsets appear in the same method.
    """

    pairs = Counter()

    for offsets in methods.values():

        unique_offsets = sorted(set(offsets))

        for i in range(len(unique_offsets)):
            for j in range(i + 1, len(unique_offsets)):

                pair = (
                    unique_offsets[i],
                    unique_offsets[j]
                )

                pairs[pair] += 1

    return pairs


def main():

    text = read_text(INPUT)

    methods = parse_record_map(text)
    methods = normalize_methods(methods)

    offset_methods = build_offset_methods(methods)
    offset_counts = build_offset_counts(text)
    cooccurrence = build_cooccurrence(methods)

    output = []

    output.append(
        "PREHISTORIC TRIBES - RECORD FIELD ANALYSIS"
    )

    output.append("Class: c")
    output.append("")

    output.append(
        "This report connects BASE + v offsets "
        "with methods that access them."
    )

    output.append("")

    output.append(
        "IMPORTANT: Offsets are bytecode observations."
    )

    output.append(
        "No semantic meaning is assigned automatically."
    )

    output.append("")

    # --------------------------------------------------
    # OFFSET SUMMARY
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("OFFSET SUMMARY")
    output.append("=" * 80)
    output.append("")

    output.append(
        f"UNIQUE OFFSETS: {len(offset_methods)}"
    )

    output.append("")

    sorted_offsets = sorted(
        offset_methods.keys(),
        key=lambda x: (-offset_counts[x], x)
    )

    for offset in sorted_offsets:

        methods_for_offset = sorted(
            offset_methods[offset]
        )

        output.append(
            f"OFFSET {offset} + v"
        )

        output.append(
            f"  ACCESS COUNT: {offset_counts[offset]}"
        )

        output.append(
            f"  METHOD COUNT: {len(methods_for_offset)}"
        )

        output.append(
            "  METHODS:"
        )

        for method in methods_for_offset:
            output.append(
                f"    {method}"
            )

        output.append("")

    # --------------------------------------------------
    # METHOD SUMMARY
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("METHOD SUMMARY")
    output.append("=" * 80)
    output.append("")

    method_order = sorted(
        methods.items(),
        key=lambda item: (
            -len(item[1]),
            item[0]
        )
    )

    for method, offsets in method_order:

        output.append(
            f"METHOD {method}"
        )

        output.append(
            f"  UNIQUE OFFSET COUNT: {len(offsets)}"
        )

        output.append(
            "  OFFSETS:"
        )

        for offset in offsets:
            output.append(
                f"    {offset} + v"
            )

        output.append("")

    # --------------------------------------------------
    # CO-OCCURRENCE
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("OFFSET CO-OCCURRENCE")
    output.append("=" * 80)
    output.append("")

    output.append(
        "Pairs are counted when two offsets are used "
        "by the same method."
    )

    output.append("")

    for (a, b), count in cooccurrence.most_common():

        output.append(
            f"{a} + v  <->  {b} + v"
        )

        output.append(
            f"  SHARED METHOD COUNT: {count}"
        )

        shared_methods = []

        for method, offsets in methods.items():

            offset_set = set(offsets)

            if a in offset_set and b in offset_set:
                shared_methods.append(method)

        output.append(
            "  METHODS:"
        )

        for method in sorted(shared_methods):
            output.append(
                f"    {method}"
            )

        output.append("")

    # --------------------------------------------------
    # MATHEMATICAL GROUPS
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("OFFSET GROUPS BY MODULO 101")
    output.append("=" * 80)
    output.append("")

    groups = defaultdict(list)

    for offset in sorted(offset_methods):
        groups[offset % 101].append(offset)

    for remainder in sorted(groups):

        values = groups[remainder]

        output.append(
            f"REMAINDER {remainder}"
        )

        output.append(
            "  " +
            ", ".join(
                f"{value}+v"
                for value in values
            )
        )

        output.append("")

    # --------------------------------------------------
    # NOTES
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("ANALYSIS NOTES")
    output.append("=" * 80)
    output.append("")

    output.append(
        "1. OFFSET + v entries come directly from record_map.txt."
    )

    output.append(
        "2. METHOD associations are based on the generated "
        "bytecode record map."
    )

    output.append(
        "3. Co-occurrence means only that two offsets are "
        "used in the same method."
    )

    output.append(
        "4. Co-occurrence does NOT prove that two fields have "
        "the same semantic meaning."
    )

    output.append(
        "5. Modulo-101 groups are mathematical groupings only."
    )

    output.append(
        "6. Further bytecode inspection is required before "
        "assigning names such as unit, building, coordinate, etc."
    )

    output.append("")

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    print(f"Created: {OUTPUT}")
    print(
        f"Unique offsets: {len(offset_methods)}"
    )
    print(
        f"Methods: {len(methods)}"
    )
    print(
        f"Offset pairs: {len(cooccurrence)}"
    )


if __name__ == "__main__":
    main()
