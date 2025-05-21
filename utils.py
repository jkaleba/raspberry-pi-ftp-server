# utils.py
from logger import Logger

def load_env(filepath=".env"):
    env = {}
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
    except OSError:
        Logger.log_alert(".env file not found! Using default values.")
    return env
