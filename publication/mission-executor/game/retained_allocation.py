"""Load the exact allocation components shipped in the preceding release."""

from hashlib import sha256
from importlib import import_module
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "universal" / "game-theory"
SOURCE_COMMIT = "8944f51db7b8e7fce8630503046c2a257cf62e44"
SOURCE_SHA256 = {
    "verify": "57d4f4281df204ac1d9f9290f72240df9dedf7ea78844a7009dad4a3aced9121",
    "solve": "abf3eeab97637c2491597788d0fa8802ee5ba3e33ea38860080e8e9be52f2413",
    "baselines": "94a5894906cba6962e812fb3582a432351246bd7de902b48fa2d8ad6e61bf64a",
}


def load(name):
    source = ROOT / f"{name}.py"
    if sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256[name]:
        raise ValueError(f"Retained allocation source changed: {source.name}")
    sys.path.insert(0, str(ROOT))
    try:
        module = import_module(name)
    finally:
        sys.path.pop(0)
    if Path(module.__file__).resolve() != source:
        raise ImportError(f"Conflicting loaded module: {name}")
    return module
