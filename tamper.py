# tamper.py
from utils import log_alert, log_event
import hashlib
import os


class FileTamper:
    HASH_DIR = "/sd/hashes/"
    
    @staticmethod
    def _ensure_hash_dir():
        if not os.path.exists(FileTamper.HASH_DIR):
            os.mkdir(FileTamper.HASH_DIR)
            log_event(f"Utworzono katalog hashów: {FileTamper.HASH_DIR}")

    @staticmethod
    def _get_hash_filename(original_filename):
        base_name = original_filename.lstrip("/").replace("/", "_")
        return f"{FileTamper.HASH_DIR}{base_name}.hash"

    @staticmethod
    def _compute_hash(filename):
        try:
            hash_md5 = hashlib.md5()
            with open(filename, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except OSError as e:
            log_alert(f"Błąd obliczania hash dla {filename}: {e}")
            return None

    @staticmethod
    def init_file_hash(filename):
        FileTamper._ensure_hash_dir()
        current_hash = FileTamper._compute_hash(filename)
        if current_hash is None:
            return False
            
        hash_file = FileTamper._get_hash_filename(filename)
        try:
            with open(hash_file, "w") as f:
                f.write(current_hash)
            log_event(f"Zapisano hash dla {filename} w {hash_file}")
            return True
        except OSError as e:
            log_alert(f"Błąd zapisu hash dla {filename}: {e}")
            return False

    @staticmethod
    def check_file_changed(filename):
        FileTamper._ensure_hash_dir()
        hash_file = FileTamper._get_hash_filename(filename)
        
        if not os.path.exists(hash_file):
            log_alert(f"Brak zapisanego hash dla {filename}")
            return False
            
        try:
            with open(hash_file, "r") as f:
                original_hash = f.read().strip()
        except OSError as e:
            log_alert(f"Błąd odczytu hash dla {filename}: {e}")
            return False
            
        current_hash = FileTamper._compute_hash(filename)
        if current_hash is None:
            return False
            
        if current_hash != original_hash:
            log_alert(f"PLIK '{filename}' ZOSTAŁ ZMIENIONY! (MD5: {original_hash} -> {current_hash})")
            return True
            
        return False