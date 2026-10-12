
#!/usr/bin/env python3

import subprocess
import zipfile
from pathlib import Path

JAR = Path("original/prehistoric-tribes-0.1.38.jar")
OUTPUT_DIR = Path("analysis/bytecode")

# Основные классы игры и вспомогательные классы.
CLASSES = [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "tribes",
]


def main():
    if not JAR.is_file():
        raise SystemExit(f"ERROR: JAR not found: {JAR}")

    with zipfile.ZipFile(JAR, "r") as jar:
        entries = set(jar.namelist())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success = []
    missing = []
    errors = []

    for class_name in CLASSES:
        entry = f"{class_name}.class"

        if entry not in entries:
            missing.append(class_name)
            print(f"SKIP: {entry} not found in JAR")
            continue

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
            errors.append(class_name)
            print(f"ERROR: javap failed for {class_name}")
            print(result.stderr)
            continue

        output = result.stdout

        if not output.strip() or "Code:" not in output:
            errors.append(class_name)
            print(f"ERROR: No bytecode found for {class_name}")
            continue

        output_file = OUTPUT_DIR / f"{class_name}.txt"
        output_file.write_text(output, encoding="utf-8")

        success.append(class_name)
        print(
            f"OK: {output_file} "
            f"({len(output)} characters)"
        )

    print("\n=== BYTECODE DUMP SUMMARY ===")
    print(f"Successful: {len(success)}")
    print(f"Missing: {len(missing)}")
    print(f"Errors: {len(errors)}")

    if missing:
        print("Missing classes:", ", ".join(missing))

    if errors:
        print("Failed classes:", ", ".join(errors))
        raise SystemExit(1)

    if not success:
        raise SystemExit("ERROR: No classes were dumped")

    print("Bytecode extraction completed.")


if __name__ == "__main__":
    main()
