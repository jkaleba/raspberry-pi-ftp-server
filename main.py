import network
import time
import machine
import os
import socket

# -------- KONFIGURACJA ---------
SSID = "HUAWEI-D55F"
PASSWORD = "87859537"
FTP_PORT = 21

MONITORED_FILES = ["document.txt"]  # Lista plików pod ochroną tamper

# -------- TAMPER DETECTION ---------
_file_hashes = {}  # {filename: hash_int}


def _compute_hash(filename):
    """
    Uproszczona suma bajtów pliku (zamiast SHA-256).
    """
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


def log_alert(msg):
    # Alert na UART/konsoli
    print("[ALERT]", msg)
    # (możesz dodać: zapis do pliku lub inną akcję)


# -------- LOGOWANIE ---------
def log_event(msg):
    # Zwykły log na UART/konsoli
    print("[LOG]", msg)
    # (możesz dodać: zapis do pliku logów)


# -------- SERWER FTP ---------
class FTPServer:
    def __init__(self, port=21):
        self.port = port
        self.socket = None
        self.username = "admin"
        self.password = "tajnehaslo"
        self.logged_in = False

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.listen(1)
        log_event(f"Serwer FTP nasłuchuje na porcie {self.port}")

    def poll(self):
        try:
            conn, addr = self.socket.accept()
            log_event(f"Nowe połączenie od {addr}")
            conn.send(b"220 MicroPython FTP Server\r\n")
            self.logged_in = False

            user = None
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                command = data.decode().strip()
                log_event(f"Odebrano komendę: {command}")

                if command.upper().startswith("USER"):
                    user = command[5:].strip()
                    conn.send(b"331 User name okay, need password.\r\n")

                elif command.upper().startswith("PASS"):
                    passwd = command[5:].strip()
                    if user == self.username and passwd == self.password:
                        self.logged_in = True
                        conn.send(b"230 User logged in, proceed.\r\n")
                        log_event(f"Zalogowano użytkownika {user}")
                    else:
                        conn.send(b"530 Login incorrect.\r\n")
                        log_event(f"Nieudana próba logowania: {user}/{passwd}")

                elif command.upper().startswith("QUIT"):
                    conn.send(b"221 Bye!\r\n")
                    log_event("Klient zakończył sesję.")
                    break

                elif not self.logged_in:
                    conn.send(b"530 Please login with USER and PASS.\r\n")

                elif command.upper().startswith("SYST"):
                    conn.send(b"215 UNIX Type: L8\r\n")
                elif command.upper().startswith("NOOP"):
                    conn.send(b"200 OK\r\n")
                elif command.upper().startswith("PWD"):
                    conn.send(b'257 "/" is current directory.\r\n')

                elif command.upper().startswith("LIST"):
                    files = os.listdir()
                    listing = "\r\n".join(files) + "\r\n"
                    conn.send(b"150 Here comes the directory listing.\r\n")
                    conn.send(listing.encode())
                    conn.send(b"226 Directory send OK.\r\n")
                    log_event("Wysłano listę plików.")

                elif command.upper().startswith("RETR"):
                    filename = command[5:].strip()
                    if filename in os.listdir():
                        conn.send(b"150 Opening data connection.\r\n")
                        with open(filename, "rb") as f:
                            while True:
                                chunk = f.read(512)
                                if not chunk:
                                    break
                                conn.send(chunk)
                        conn.send(b"\r\n226 Transfer complete.\r\n")
                        log_event(f"Plik pobrany: {filename}")
                    else:
                        conn.send(b"550 File not found.\r\n")
                        log_event(f"Próba pobrania nieistniejącego pliku: {filename}")

                elif command.upper().startswith("STOR"):
                    filename = command[5:].strip()
                    conn.send(b"150 Ok to send data.\r\n")
                    with open(filename, "wb") as f:
                        while True:
                            data = conn.recv(512)
                            if not data or data.endswith(b"\r\n226 Transfer complete.\r\n"):
                                if data and not data.endswith(b"\r\n226 Transfer complete.\r\n"):
                                    f.write(data)
                                break
                            f.write(data)
                    conn.send(b"226 Transfer complete.\r\n")
                    log_event(f"Plik zapisany: {filename}")
                    # Po STOR zaktualizuj hash dla tego pliku (jeśli monitorowany)
                    if filename in MONITORED_FILES:
                        init_file_hash(filename)

                else:
                    conn.send(b"502 Command not implemented.\r\n")
                    log_event(f"Nieobsługiwana komenda: {command}")

            conn.close()
            log_event("Połączenie zamknięte.")
        except OSError:
            pass


# -------- WIFI ---------
def connect_wifi(ssid, password, timeout_ms=15000):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    log_event("Łączenie z Wi-Fi…")

    t0 = time.ticks_ms()
    while not wlan.isconnected():
        status = wlan.status()
        if status == network.STAT_WRONG_PASSWORD:
            raise RuntimeError("Błędne hasło Wi-Fi")
        if status == network.STAT_NO_AP_FOUND:
            raise RuntimeError("Nie znaleziono sieci Wi-Fi")
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
            raise RuntimeError("Timeout przy łączeniu z Wi-Fi")
        time.sleep(0.2)

    log_event(f"Połączono: {wlan.ifconfig()}")
    return wlan.ifconfig()[0]


# -------- MAIN ---------
def main():
    # Połącz z Wi-Fi
    connect_wifi(SSID, PASSWORD)

    # Utwórz domyślny plik, jeśli go nie ma
    for filename in MONITORED_FILES:
        if filename not in os.listdir():
            with open(filename, "w") as f:
                f.write("Plik chroniony tamper detection!\n")

    # Zapamiętaj hashe
    for filename in MONITORED_FILES:
        init_file_hash(filename)
        log_event(f"Zainicjowano hash dla pliku {filename}")

    # Uruchom FTP
    ftp = FTPServer(port=FTP_PORT)
    ftp.start()
    log_event("Serwer FTP uruchomiony.")

    # Pętla główna
    try:
        while True:
            ftp.poll()
            # Sprawdź zmiany plików co 2 sekundy
            time.sleep(2)
            for filename in MONITORED_FILES:
                check_file_changed(filename)
    except KeyboardInterrupt:
        log_event("Serwer zatrzymany.")

main()
