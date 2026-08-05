import subprocess
import sys

def run_quality_checks():
    print("Running tests...")

    result = subprocess.run(
        ["pytest", "--cov=.", "--cov-fail-under=85"],
        check=False,
    )

    if result.returncode != 0:
        print("Tests or coverage failed.")
        sys.exit(1)

    print("Running pylint...")

    result = subprocess.run(
        ["pylint", "--ignore=.venv", "--fail-under=9.5", "."],
        check=False,
    )

    if result.returncode != 0:
        print("Pylint score is below 9.5.")
        sys.exit(1)
