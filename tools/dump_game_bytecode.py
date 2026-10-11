
#!/usr/bin/env python3

import subprocess
import zipfile
from pathlib import Path

JAR = Path("original/prehistoric-tribes-0.1.38.jar")
OUTPUT_DIR = Path("analysis/bytecode")

# Пока выгружаем только основной класс игры.
CLASSES = ["g"]


def main():
    if not JAR.is_file():
        raise SystemExit(f"ERROR: JAR not found: {JAR}")

    with zipfile.ZipFile(JAR, "r") as jar:
        entries = set(jar.namelist())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for class_name in CLASSES:
        entry = f"{class_name}.class"

        if entry not in entries:
            raise SystemExit(
                f"ERROR: {entry} not found inside {JAR}"
            )

        command = [
            "javap",
            "-classpath",
            str(JAR),
            "-c",
            "-p",
            "-s",
            class_name,
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode != 0:
            raise SystemExit(
                f"ERROR: javap failed for {class_name}:\n"
                f"{result.stderr}"
            )

        output = result.stdout

        if not output.strip():
            raise SystemExit(
                f"ERROR: javap returned empty output for {class_name}"
            )

        if "Code:" not in output:
            raise SystemExit(
                f"ERROR: No bytecode instructions found for {class_name}"
            )

        output_file = OUTPUT_DIR / f"{class_name}.txt"
        output_file.write_text(output, encoding="utf-8")

        print(f"Created: {output_file}")
        print(f"Output size: {len(output)} characters")

    print("Bytecode extraction completed successfully.")


if __name__ == "__main__":
    main()
