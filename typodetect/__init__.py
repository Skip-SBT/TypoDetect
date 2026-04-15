"""TypoDetect – a lightweight background tool that detects word typos and flashes a visual warning."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("typodetect")
except PackageNotFoundError:
    # Package is not installed (e.g. running from source without pip install)
    __version__ = "unknown"
