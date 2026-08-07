import shutil
import subprocess  # nosec B404 - only used with fixed, developer-supplied argv below, never shell=True
import sys


def _resolve(executable):
    """Resolve an executable to its full path so subprocess isn't started
    with a partial/relative name (bandit B607)."""
    path = shutil.which(executable)
    if path is None:
        print(f"Could not find '{executable}' on PATH. Is it installed?")
        sys.exit(1)
    return path


def run_quality_checks():
    print("Running tests...")

    pytest_path = _resolve("pytest")
    result = subprocess.run(
        [pytest_path, "--cov=.", "--cov-fail-under=85"],
        check=False,
        shell=False,  # nosec B603 - fixed argv, no untrusted/user-controlled input
    )

    if result.returncode != 0:
        print("Tests or coverage failed.")
        sys.exit(1)

    print("Running pylint...")

    pylint_path = _resolve("pylint")
    result = subprocess.run(
        [pylint_path, "--ignore=.venv", "--fail-under=9.5", "."],
        check=False,
        shell=False,  # nosec B603 - fixed argv, no untrusted/user-controlled input
    )

    if result.returncode != 0:
        print("Pylint score is below 9.5.")
        sys.exit(1)