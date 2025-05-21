# ftpserver.py
import os
import socket
from utils import log_event, log_alert


class FTPServer:
    def __init__(self, username, password, port=21):
        self.port = port
        self.socket = None
        self.username = username
        self.password = password
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
                else:
                    conn.send(b"502 Command not implemented.\r\n")
                    log_event(f"Nieobsługiwana komenda: {command}")

            conn.close()
            log_event("Połączenie zamknięte.")
        except OSError:
            pass
