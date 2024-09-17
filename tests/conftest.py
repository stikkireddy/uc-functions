import os
import sys
from pathlib import Path


def add_samples_to_path():
    samples_dir = str(Path(__file__).parent / "samples")

    if samples_dir not in sys.path:
        sys.path.append(samples_dir)

    if "PYTHONPATH" in os.environ:
        os.environ["PYTHONPATH"] = f"{os.environ['PYTHONPATH']}:{samples_dir}"
    else:
        os.environ["PYTHONPATH"] = samples_dir


def pytest_sessionstart(session):
    add_samples_to_path()
