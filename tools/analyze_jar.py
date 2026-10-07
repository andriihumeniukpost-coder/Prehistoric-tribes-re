#!/usr/bin/env python3

import zipfile
from pathlib import Path
from collections import Counter

JAR = Path("original/prehistoric-tribes-0.1.38.jar")
REPORT = Path("analysis/jar_report.txt")


def main():
    if not JAR.exists():
        print(f"ERROR: JAR not found: {JAR}")
        return

    REPORT.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(JAR, "r") as jar:
        files = jar.infolist()

        classes = []
        resources = []

        for f in files:
            if f.is_dir():
                continue

            if f.filename.endswith(".class"):
                classes.append(f)
            else:
                resources.append(f)

        with REPORT.open("w", encoding="utf-8") as out:
            out.write("PREHISTORIC TRIBES - JAR ANALYSIS\n")
            out.write("=" * 50 + "\n\n")

            out.write(f"JAR: {JAR}\n")
            out.write(f"Total files: {len(files)}\n")
            out.write(f"Class files: {len(classes)}\n")
            out.write(f"Other files: {len(resources)}\n\n")

            out.write("=== CLASS FILES ===\n\n")

            for f in sorted(classes, key=lambda x: x.filename):
                out.write(
                    f"{f.filename:<40} {f.file_size:>10} bytes\n"
                )

            out.write("\n=== RESOURCES ===\n\n")

            for f in sorted(resources, key=lambda x: x.filename):
                out.write(
                    f"{f.filename:<40} {f.file_size:>10} bytes\n"
                )

            out.write("\n=== FILE TYPES ===\n\n")

            extensions = Counter()

            for f in files:
                if f.is_dir():
                    continue

                suffix = Path(f.filename).suffix.lower()

                if not suffix:
                    suffix = "[no extension]"

                extensions[suffix] += 1

            for ext, count in sorted(extensions.items()):
                out.write(f"{ext:<20} {count}\n")

            out.write("\n=== MANIFEST ===\n\n")

            try:
                manifest = jar.read("META-INF/MANIFEST.MF").decode(
                    "utf-8", errors="replace"
                )
                out.write(manifest)
            except KeyError:
                out.write("MANIFEST.MF not found.\n")

    print(f"Report created: {REPORT}")


if __name__ == "__main__":
    main()
