from pathlib import Path
import re
from collections import defaultdict, Counter

INPUT = Path("analysis/bytecode/c.txt")
OUTPUT = Path("analysis/record_fields.txt")


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def method_name_from_line(line):
    """
    Detect javap method declarations.

    Examples:
        private void a();
        final void f();
        public static int b(int);
        private static byte b(int);
    """

    line = line.strip()

    if not line:
        return None

    if line.startswith(("Code:", "descriptor:", "flags:",
                        "LineNumberTable:", "LocalVariableTable:",
                        "StackMapTable:", "Runtime", "Exception",
                        "Signature:", "Deprecated:", "SourceFile:")):
        return None

    if "(" not in line or ")" not in line:
        return None

    if line.startswith(("//", "#")):
        return None

    # javap declarations normally end with ;
    if not line.endswith(";"):
        return None

    # Remove throws clause if present
    line = line.split(" throws ")[0]

    # Take the part before '('
    before = line.split("(", 1)[0].strip()

    if not before:
        return None

    parts = before.split()

    if len(parts) < 2:
        return None

    name = parts[-1]

    # Remove class qualification if present
    if "." in name:
        name = name.split(".")[-1]

    return name


def extract_methods_and_offsets(text):
    """
    Scan c.txt method by method.

    A BASE + v access is recognized from bytecode sequences such as:

        getfield ... v:I
        ...
        iadd
        ...
        getfield ... a:[B

    The actual javap output contains the constant used
    immediately around the v index operation.

    We detect expressions of the form:

        <constant> + v

    from the bytecode context.
    """

    lines = text.splitlines()

    method_offsets = defaultdict(list)

    current_method = "<unknown>"

    # We remember a possible constant seen shortly before v.
    for i, line in enumerate(lines):

        detected_method = method_name_from_line(line)

        if detected_method is not None:
            current_method = detected_method
            continue

        # We only care about bytecode lines mentioning field v:I.
        if "Field v:I" not in line:
            continue

        # Look around the v access.
        start = max(0, i - 12)
        end = min(len(lines), i + 13)

        window = lines[start:end]
        block = "\n".join(window)

        # We need an integer constant somewhere nearby.
        constants = []

        for wline in window:

            m = re.search(
                r"\b(?:bipush|sipush)\s+(-?\d+)",
                wline
            )

            if m:
                constants.append(int(m.group(1)))

            m = re.search(
                r"\biconst_m1\b",
                wline
            )

            if m:
                constants.append(-1)

            for value in range(6):
                if re.search(
                    rf"\biconst_{value}\b",
                    wline
                ):
                    constants.append(value)

        if not constants:
            continue

        # Prefer the constant closest to the v access.
        v_index = i

        best = None
        best_distance = None

        for j in range(start, end):

            distance = abs(j - v_index)

            line_j = lines[j]

            found = []

            m = re.search(
                r"\b(?:bipush|sipush)\s+(-?\d+)",
                line_j
            )

            if m:
                found.append(int(m.group(1)))

            if "iconst_m1" in line_j:
                found.append(-1)

            for value in range(6):
                if f"iconst_{value}" in line_j:
                    found.append(value)

            for value in found:

                if best_distance is None or distance < best_distance:
                    best = value
                    best_distance = distance

        if best is None:
            continue

        # Only keep likely BASE offsets.
        # We deliberately do not assign semantic meaning.
        offset = best

        method_offsets[current_method].append(offset)

    return method_offsets


def extract_real_offsets_from_record_map(text):
    """
    Fallback parser.

    If record_map.txt contains explicit OFFSET lines,
    collect them directly.
    """

    offsets = []

    for line in text.splitlines():

        match = re.search(
            r"OFFSET\s+(-?\d+)\s+\+\s+v",
            line
        )

        if match:
            offsets.append(int(match.group(1)))

    return offsets


def build_offset_methods(method_offsets):
    result = defaultdict(set)

    for method, offsets in method_offsets.items():
        for offset in offsets:
            result[offset].add(method)

    return result


def build_cooccurrence(method_offsets):
    pairs = Counter()

    for offsets in method_offsets.values():

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

    method_offsets = extract_methods_and_offsets(text)

    # Remove duplicates inside each method.
    normalized = {}

    for method, offsets in method_offsets.items():

        normalized[method] = sorted(
            set(offsets)
        )

    method_offsets = normalized

    offset_methods = build_offset_methods(
        method_offsets
    )

    cooccurrence = build_cooccurrence(
        method_offsets
    )

    output = []

    output.append(
        "PREHISTORIC TRIBES - RECORD FIELD ANALYSIS"
    )

    output.append(
        "Class: c"
    )

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

    for offset in sorted(
        offset_methods,
        key=lambda x: (
            -len(offset_methods[x]),
            x
        )
    ):

        methods = sorted(
            offset_methods[offset]
        )

        total = 0

        for method in methods:
            total += method_offsets[method].count(
                offset
            )

        output.append(
            f"OFFSET {offset} + v"
        )

        output.append(
            f"  METHOD COUNT: {len(methods)}"
        )

        output.append(
            f"  DETECTED ACCESS COUNT: {total}"
        )

        output.append(
            "  METHODS:"
        )

        for method in methods:
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

    for method, offsets in sorted(
        method_offsets.items(),
        key=lambda item: (
            -len(item[1]),
            item[0]
        )
    ):

        if not offsets:
            continue

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
        "Pairs are counted when two offsets are "
        "detected inside the same method."
    )

    output.append("")

    for (a, b), count in cooccurrence.most_common():

        output.append(
            f"{a} + v  <->  {b} + v"
        )

        output.append(
            f"  SHARED METHOD COUNT: {count}"
        )

        output.append("")

    # --------------------------------------------------
    # MODULO 101
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("OFFSET GROUPS BY MODULO 101")
    output.append("=" * 80)
    output.append("")

    groups = defaultdict(list)

    for offset in sorted(offset_methods):

        groups[offset % 101].append(
            offset
        )

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
        "1. Offsets are extracted from bytecode analysis."
    )

    output.append(
        "2. Method associations are bytecode-based."
    )

    output.append(
        "3. Co-occurrence means only that offsets "
        "appear in the same detected method."
    )

    output.append(
        "4. Co-occurrence does NOT prove identical "
        "semantic meaning."
    )

    output.append(
        "5. Modulo-101 groups are mathematical groupings only."
    )

    output.append(
        "6. No automatic names such as unit, building, "
        "coordinate or health are assigned."
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

    print(
        f"Created: {OUTPUT}"
    )

    print(
        f"Methods detected: {len(method_offsets)}"
    )

    print(
        f"Unique offsets detected: {len(offset_methods)}"
    )

    print(
        f"Offset pairs: {len(cooccurrence)}"
    )


if __name__ == "__main__":
    main()
