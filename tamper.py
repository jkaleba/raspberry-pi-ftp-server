# tamper.py
try:
    import hashlib
except ImportError:
    import uhashlib as hashlib
import binascii
import os
from logger import Logger

class FileTamper:
    HASH_DIR = "/sd/"
    
    @staticmethod
    def _ensure_hash_dir():
        try:
            try:
                os.listdir(FileTamper.HASH_DIR)
            except OSError:
                os.mkdir(FileTamper.HASH_DIR)
                Logger.log_info(f"Created hash directory: {FileTamper.HASH_DIR}")
        except Exception as e:
            Logger.log_alert(f"Error ensuring hash directory: {e}")

    @staticmethod
    def _get_hash_filename(original_filename):
        base_name = original_filename.lstrip("/").replace("/", "_")
        return FileTamper.HASH_DIR + base_name + ".hash"

    @staticmethod
    def _compute_hash(filename):
        try:
            try:
                hash_obj = hashlib.md5()
            except AttributeError:
                try:
                    hash_obj = hashlib.sha1()
                except AttributeError:
                    hash_obj = hashlib.sha256()
            
            with open(filename, "rb") as f:
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    hash_obj.update(chunk)
            
            return binascii.hexlify(hash_obj.digest()).decode()
        except Exception as e:
            Logger.log_alert(f"Hash computation error for {filename}: {e}")
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
            Logger.log_info(f"Saved hash for {filename} in {hash_file}")
            return True
        except Exception as e:
            Logger.log_alert(f"Error saving hash for {filename}: {e}")
            return False

    @staticmethod
    def check_file_changed(filename):
        FileTamper._ensure_hash_dir()
        hash_file = FileTamper._get_hash_filename(filename)
        
        try:
            with open(hash_file, "r") as f:
                original_hash = f.read().strip()
        except OSError:
            Logger.log_alert(f"No hash found for {filename}")
            return False
            
        current_hash = FileTamper._compute_hash(filename)
        if current_hash is None:
            return False
            
        if current_hash != original_hash:
            Logger.log_alert(f"FILE '{filename}' HAS BEEN MODIFIED! (MD5: {original_hash} -> {current_hash})")
            return True
            
        return False