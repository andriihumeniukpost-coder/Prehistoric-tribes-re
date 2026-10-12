from pathlib import Path
from collections import defaultdict, Counter

INPUT = Path("analysis/record_fields.txt")
OUTPUT = Path("analysis/record_clusters.txt")


def read_text(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def parse_method_summary(text):
    """
    Read METHOD SUMMARY from record_fields.txt.

    Returns:

        {
            "method_name": {
                offset1,
                offset2,
                ...
            }
        }
    """

    methods = defaultdict(set)

    in_method_summary = False
    current_method = None

    for line in text.splitlines():

        line = line.rstrip()

        if line == "METHOD SUMMARY":
            in_method_summary = True
            current_method = None
            continue

        if not in_method_summary:
            continue

        if line.startswith("="):
            continue

        if line.startswith("METHOD "):
            current_method = line[
                len("METHOD "):
            ].strip()

            methods[current_method] = set()
            continue

        if current_method is None:
            continue

        line = line.strip()

        if line.endswith("+ v"):

            try:
                offset = int(
                    line[:-3].strip()
                )

                methods[current_method].add(
                    offset
                )

            except ValueError:
                pass

    return dict(methods)


def build_cooccurrence(methods):
    """
    Count how many methods contain each pair.
    """

    pairs = Counter()

    for offsets in methods.values():

        values = sorted(offsets)

        for i in range(len(values)):

            for j in range(i + 1, len(values)):

                pair = (
                    values[i],
                    values[j]
                )

                pairs[pair] += 1

    return pairs


def build_offset_frequency(methods):
    frequency = Counter()

    for offsets in methods.values():

        for offset in offsets:
            frequency[offset] += 1

    return frequency


def build_clusters(offsets, pairs, threshold):
    """
    Build connected components.

    Two offsets belong to the same cluster when
    they share at least 'threshold' methods.

    Transitive connections are allowed.
    """

    graph = defaultdict(set)

    for (a, b), count in pairs.items():

        if count >= threshold:

            graph[a].add(b)
            graph[b].add(a)

    visited = set()
    clusters = []

    for offset in sorted(offsets):

        if offset in visited:
            continue

        stack = [offset]
        cluster = set()

        while stack:

            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)
            cluster.add(current)

            for neighbor in graph[current]:

                if neighbor not in visited:
                    stack.append(neighbor)

        clusters.append(
            sorted(cluster)
        )

    clusters.sort(
        key=lambda x: (
            -len(x),
            x
        )
    )

    return clusters


def cluster_score(cluster, pairs):
    """
    Average pair co-occurrence inside cluster.
    """

    if len(cluster) < 2:
        return 0.0

    values = []

    for i in range(len(cluster)):

        for j in range(i + 1, len(cluster)):

            pair = (
                cluster[i],
                cluster[j]
            )

            values.append(
                pairs.get(pair, 0)
            )

    if not values:
        return 0.0

    return sum(values) / len(values)


def main():

    text = read_text(INPUT)

    methods = parse_method_summary(text)

    if not methods:
        raise SystemExit(
            "No methods found in record_fields.txt"
        )

    pairs = build_cooccurrence(methods)
    frequency = build_offset_frequency(methods)

    all_offsets = set(frequency)

    output = []

    output.append(
        "PREHISTORIC TRIBES - RECORD CLUSTER ANALYSIS"
    )

    output.append(
        "Class: c"
    )

    output.append("")

    output.append(
        "This report groups BASE + v offsets according "
        "to their bytecode-derived co-occurrence."
    )

    output.append("")

    output.append(
        "IMPORTANT: A cluster does NOT automatically "
        "represent a game object or semantic record."
    )

    output.append(
        "It only represents offsets that frequently "
        "appear together in detected methods."
    )

    output.append("")

    # --------------------------------------------------
    # GENERAL STATISTICS
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("STATISTICS")
    output.append("=" * 80)
    output.append("")

    output.append(
        f"METHODS: {len(methods)}"
    )

    output.append(
        f"UNIQUE OFFSETS: {len(all_offsets)}"
    )

    output.append(
        f"OFFSET PAIRS: {len(pairs)}"
    )

    output.append("")

    # --------------------------------------------------
    # MOST CONNECTED OFFSETS
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("MOST CONNECTED OFFSETS")
    output.append("=" * 80)
    output.append("")

    for offset, count in frequency.most_common():

        output.append(
            f"{offset} + v"
        )

        output.append(
            f"  METHOD COUNT: {count}"
        )

        connected = []

        for (a, b), pair_count in pairs.items():

            if a == offset:
                connected.append(
                    (pair_count, b)
                )

            elif b == offset:
                connected.append(
                    (pair_count, a)
                )

        connected.sort(
            key=lambda x: (
                -x[0],
                x[1]
            )
        )

        output.append(
            "  STRONGEST CONNECTIONS:"
        )

        for pair_count, other in connected[:10]:

            output.append(
                f"    {other} + v"
                f"  -> {pair_count} shared methods"
            )

        output.append("")

    # --------------------------------------------------
    # CLUSTERS THRESHOLD 20
    # --------------------------------------------------

    for threshold in [20, 15, 10, 5]:

        clusters = build_clusters(
            all_offsets,
            pairs,
            threshold
        )

        output.append("=" * 80)

        output.append(
            f"CLUSTERS - CO-OCCURRENCE >= {threshold}"
        )

        output.append("=" * 80)

        output.append("")

        cluster_number = 0

        for cluster in clusters:

            # Ignore singletons for this section.
            if len(cluster) < 2:
                continue

            cluster_number += 1

            score = cluster_score(
                cluster,
                pairs
            )

            output.append(
                f"CLUSTER {cluster_number}"
            )

            output.append(
                f"  SIZE: {len(cluster)}"
            )

            output.append(
                f"  AVERAGE PAIR SCORE: {score:.2f}"
            )

            output.append(
                "  OFFSETS:"
            )

            for offset in cluster:

                output.append(
                    f"    {offset} + v"
                    f"  ({frequency[offset]} methods)"
                )

            output.append("")

        if cluster_number == 0:

            output.append(
                "No multi-offset clusters found."
            )

            output.append("")

    # --------------------------------------------------
    # IMPORTANT PAIRS
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("STRONGEST OFFSET PAIRS")
    output.append("=" * 80)
    output.append("")

    for (a, b), count in pairs.most_common(100):

        output.append(
            f"{a} + v  <->  {b} + v"
        )

        output.append(
            f"  SHARED METHODS: {count}"
        )

        output.append("")

    # --------------------------------------------------
    # SPECIAL REGULAR OFFSETS
    # --------------------------------------------------

    output.append("=" * 80)
    output.append("REGULAR 101-STEP OFFSETS")
    output.append("=" * 80)
    output.append("")

    regular = sorted(
        offset
        for offset in all_offsets
        if offset >= 0
        and offset % 101 == 0
    )

    for offset in regular:

        output.append(
            f"{offset} + v"
            f"  ({frequency[offset]} methods)"
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
        "1. Input comes from record_fields.txt."
    )

    output.append(
        "2. Two offsets are connected when they occur "
        "in the same detected method."
    )

    output.append(
        "3. Cluster thresholds are based on shared "
        "method counts."
    )

    output.append(
        "4. Clusters are mathematical/structural "
        "observations only."
    )

    output.append(
        "5. A cluster is NOT automatically a unit, "
        "building, character, map tile or other object."
    )

    output.append(
        "6. The 101-step section is reported because "
        "many offsets follow this numerical pattern."
    )

    output.append(
        "7. Further bytecode analysis is required "
        "to assign semantic field names."
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
        f"Methods: {len(methods)}"
    )

    print(
        f"Unique offsets: {len(all_offsets)}"
    )

    print(
        f"Pairs: {len(pairs)}"
    )


if __name__ == "__main__":
    main()
