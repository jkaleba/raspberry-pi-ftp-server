# tamper.py
from utils import log_alert

_file_hashes = {}

def _compute_hash(filename):
    h = 0
    try:
        with open(filename, "rb") as f:
            while True:
                chunk = f.read(256)
                if not chunk:
                    break
                for b in chunk:
                    h += b
    except OSError:
        return None
    return h & 0xFFFFFFFF

def init_file_hash(filename):
    _file_hashes[filename] = _compute_hash(filename)

def check_file_changed(filename):
    original = _file_hashes.get(filename)
    if original is None:
        return False
    current = _compute_hash(filename)
    if current != original:
        log_alert(f"PLIK '{filename}' ZOSTAŁ ZMIENIONY! ({original} -> {current})")
        return True
    return False
