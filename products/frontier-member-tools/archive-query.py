"""Run the pinned NOAA archive query from an extracted capability package."""
from pathlib import Path
from runpy import run_path
import sys


if __name__ == '__main__':
    source = Path(__file__).resolve().parent / 'products/frontier-omega-alpha/research/archive_point'
    sys.path.insert(0, str(source))
    run_path(str(source / 'query.py'), run_name='__main__')
