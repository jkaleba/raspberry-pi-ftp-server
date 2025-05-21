import network
import time
import machine
import os
import socket
import sdcard

# -------- KONFIGURACJA ---------
SSID = "HUAWEI-D55F"
PASSWORD = "87859537"
FTP_PORT = 21

MONITORED_FILES = ["/sd/document.txt"]

# -------- TAMPER DETECTION ---------
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


def log_alert(msg):
    print("[ALERT]", msg)


def log_event(msg):
    print("[LOG]", msg)


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
                    conn.send(b'257 "/sd" is current directory.\r\n')

                elif command.upper().startswith("LIST"):
                    files = os.listdir("/sd")
                    listing = "\r\n".join(files) + "\r\n"
                    conn.send(b"150 Here comes the directory listing.\r\n")
                    conn.send(listing.encode())
                    conn.send(b"226 Directory send OK.\r\n")
                    log_event("Wysłano listę plików.")

                elif command.upper().startswith("RETR"):
                    filename = command[5:].strip()
                    filepath = "/sd/" + filename
                    if filename in os.listdir("/sd"):
                        conn.send(b"150 Opening data connection.\r\n")
                        with open(filepath, "rb") as f:
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
                    filepath = "/sd/" + filename
                    conn.send(b"150 Ok to send data.\r\n")
                    with open(filepath, "wb") as f:
                        while True:
                            data = conn.recv(512)
                            if not data or data.endswith(b"\r\n226 Transfer complete.\r\n"):
                                if data and not data.endswith(b"\r\n226 Transfer complete.\r\n"):
                                    f.write(data)
                                break
                            f.write(data)
                    conn.send(b"226 Transfer complete.\r\n")
                    log_event(f"Plik zapisany: {filename}")
                    if filepath in MONITORED_FILES:
                        init_file_hash(filepath)

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


# -------- MONTAŻ SD ---------
def mount_sdcard():
    # Maker Pi Pico: SPI1, SCK=10, MOSI=11, MISO=12, CS=13
    spi = machine.SPI(1,
                      sck=machine.Pin(10),
                      mosi=machine.Pin(11),
                      miso=machine.Pin(12)
                      )
    cs = machine.Pin(13, machine.Pin.OUT)
    try:
        sd = sdcard.SDCard(spi, cs)
        os.mount(sd, "/sd")
        log_event("Karta SD zamontowana.")
        return True
    except Exception as e:
        log_alert(f"Nie wykryto karty SD lub błąd montowania: {e}")
        return False


# -------- MAIN ---------
def main():
    connect_wifi(SSID, PASSWORD)

    if not mount_sdcard():
        return

    for filename in MONITORED_FILES:
        if filename not in ["/sd/" + f for f in os.listdir("/sd")]:
            with open(filename, "w") as f:
                f.write("Plik chroniony tamper detection!\n")

    for filename in MONITORED_FILES:
        init_file_hash(filename)
        log_event(f"Zainicjowano hash dla pliku {filename}")

    ftp = FTPServer(port=FTP_PORT)
    ftp.start()
    log_event("Serwer FTP uruchomiony.")

    try:
        while True:
            ftp.poll()
            time.sleep(2)
            for filename in MONITORED_FILES:
                check_file_changed(filename)
    except KeyboardInterrupt:
        log_event("Serwer zatrzymany.")


main()
