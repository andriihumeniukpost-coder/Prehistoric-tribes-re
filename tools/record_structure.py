from pathlib import Path
import re

INPUT_BYTECODE = Path("analysis/bytecode/c.txt")
INPUT_RECORDS = Path("analysis/record_map.txt")
OUTPUT = Path("analysis/record_structure.txt")


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def extract_offsets(text):
    """
    Extract all BASE + v offsets from record_map.txt.
    """

    offsets = set()

    pattern = re.compile(
        r"^OFFSET\s+(-?\d+)\s+\+\s+v",
        re.MULTILINE
    )

    for match in pattern.finditer(text):
        offsets.add(int(match.group(1)))

    return sorted(offsets)


def find_u_v_relations(text):
    """
    Find bytecode patterns involving:

        u * 50
        u * 50 + 1
        (u + 1) * 50
        assignments into v

    This is evidence collection only.
    It does not assign semantic meaning.
    """

    lines = text.splitlines()

    results = []

    for index, line in enumerate(lines):

        window = lines[
            max(0, index - 8):
            min(len(lines), index + 12)
        ]

        block = "\n".join(window)

        has_u = (
            "Field u:I" in block
        )

        has_v = (
            "Field v:I" in block
        )

        has_50 = (
            "bipush        50" in block
            or "bipush 50" in block
            or "sipush        50" in block
            or "sipush 50" in block
        )

        if not (has_u and has_v and has_50):
            continue

        results.append({
            "line": index + 1,
            "context": window,
        })

    return results


def find_exact_formulas(text):
    """
    Search for bytecode sequences corresponding to:

        v = u * 50 + 1

    and nearby variants.
    """

    lines = text.splitlines()

    results = []

    for index in range(len(lines)):

        window = lines[
            index:
            min(len(lines), index + 20)
        ]

        block = "\n".join(window)

        if (
            "Field u:I" in block
            and "Field v:I" in block
            and "bipush        50" in block
            and "imul" in block
            and "putfield" in block
        ):
            results.append({
                "line": index + 1,
                "context": window,
            })

    return results


def make_offset_groups(offsets):
    """
    Group offsets by their relationship to 101.

    Many offsets in this class look like:

        0
        101
        202
        303
        ...

    We only report the mathematical grouping.
    """

    groups = {}

    for offset in offsets:

        quotient, remainder = divmod(
            offset,
            101
        )

        groups.setdefault(
            remainder,
            []
        ).append(
            (quotient, offset)
        )

    return groups


def main():

    bytecode = read_text(
        INPUT_BYTECODE
    )

    record_map = read_text(
        INPUT_RECORDS
    )

    offsets = extract_offsets(
        record_map
    )

    relations = find_u_v_relations(
        bytecode
    )

    formulas = find_exact_formulas(
        bytecode
    )

    groups = make_offset_groups(
        offsets
    )

    output = []

    output.append(
        "PREHISTORIC TRIBES - RECORD STRUCTURE ANALYSIS"
    )

    output.append(
        "Class: c"
    )

    output.append("")

    output.append(
        "This report collects mathematical relationships"
    )

    output.append(
        "between u, v, 50-sized loops and BASE + v offsets."
    )

    output.append("")

    output.append(
        "IMPORTANT: No semantic meaning is assigned automatically."
    )

    output.append(
        "For example, a block is NOT automatically assumed to be"
    )

    output.append(
        "a unit, character, building or other game object."
    )

    output.append("")

    # -------------------------------------------------
    # OFFSET SUMMARY
    # -------------------------------------------------

    output.append("=" * 80)
    output.append("BASE + v OFFSETS")
    output.append("=" * 80)
    output.append("")

    output.append(
        f"TOTAL UNIQUE OFFSETS: {len(offsets)}"
    )

    output.append("")

    for offset in offsets:

        output.append(
            f"{offset:5d} + v"
        )

    output.append("")

    # -------------------------------------------------
    # 101 GROUPS
    # -------------------------------------------------

    output.append("=" * 80)
    output.append("OFFSET GROUPS MODULO 101")
    output.append("=" * 80)
    output.append("")

    output.append(
        "Offsets are grouped mathematically by offset % 101."
    )

    output.append("")

    for remainder in sorted(groups):

        values = sorted(
            groups[remainder]
        )

        output.append(
            f"REMAINDER {remainder}"
        )

        output.append(
            "  " +
            ", ".join(
                str(offset)
                for _, offset in values
            )
        )

        output.append("")

    # -------------------------------------------------
    # u/v RELATIONSHIPS
    # -------------------------------------------------

    output.append("=" * 80)
    output.append("u / v / 50 RELATIONSHIPS")
    output.append("=" * 80)
    output.append("")

    output.append(
        f"WINDOWS FOUND: {len(relations)}"
    )

    output.append("")

    for number, item in enumerate(
        relations,
        start=1
    ):

        output.append(
            f"RELATIONSHIP #{number}"
        )

        output.append(
            f"BYTECODE LINE: {item['line']}"
        )

        output.append("")

        for line in item["context"]:
            output.append(
                f"    {line}"
            )

        output.append("")

    # -------------------------------------------------
    # EXACT FORMULAS
    # -------------------------------------------------

    output.append("=" * 80)
    output.append("POSSIBLE u * 50 -> v ASSIGNMENTS")
    output.append("=" * 80)
    output.append("")

    output.append(
        f"WINDOWS FOUND: {len(formulas)}"
    )

    output.append("")

    for number, item in enumerate(
        formulas,
        start=1
    ):

        output.append(
            f"FORMULA CANDIDATE #{number}"
        )

        output.append(
            f"BYTECODE LINE: {item['line']}"
        )

        output.append("")

        for line in item["context"]:
            output.append(
                f"    {line}"
            )

        output.append("")

    # -------------------------------------------------
    # CONCLUSION
    # -------------------------------------------------

    output.append("=" * 80)
    output.append("ANALYSIS NOTES")
    output.append("=" * 80)
    output.append("")

    output.append(
        "1. BASE + v offsets are direct observations from bytecode."
    )

    output.append(
        "2. 50-sized relationships are reported when detected."
    )

    output.append(
        "3. Modulo-101 groups are mathematical groupings only."
    )

    output.append(
        "4. No field/object semantics are inferred automatically."
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
        f"Unique offsets: {len(offsets)}"
    )

    print(
        f"u/v/50 windows: {len(relations)}"
    )

    print(
        f"Formula candidates: {len(formulas)}"
    )


if __name__ == "__main__":
    main()
