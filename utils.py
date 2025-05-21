# utils.py

def log_event(msg):
    print("[LOG]", msg)


def log_alert(msg):
    print("[ALERT]", msg)


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
        log_alert(".env file not found! Using default values.")
    return env
