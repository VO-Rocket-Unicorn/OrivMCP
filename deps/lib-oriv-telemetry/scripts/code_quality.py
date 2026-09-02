import subprocess
import sys

from lib_oriv_telemetry._internal import paths as path_helpers


SOURCE_DIR = path_helpers.get_package_name()


def lint():
    subprocess.run([sys.executable, "-m", "flake8", SOURCE_DIR], check=True)


def format():
    subprocess.run([sys.executable, "-m", "black", SOURCE_DIR], check=True)
