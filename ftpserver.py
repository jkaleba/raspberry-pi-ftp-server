import os
import socket
from logger import Logger

class FTPServer:
    def __init__(self, username, password, port=21):
        self.port = port
        self.socket = None
        self.username = username
        self.password = password
        self.logged_in = False
        self.pasv_socket = None
        self.pasv_addr = None

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.listen(1)
        Logger.log_info(f"Serwer FTP nasłuchuje na porcie {self.port}")

    def setup_pasv(self):
        # Otwórz socket na losowym porcie >1024
        self.pasv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.pasv_socket.bind(('0.0.0.0', 0))  # 0 = losowy wolny port
        self.pasv_socket.listen(1)
        ip = self.get_local_ip()
        port = self.pasv_socket.getsockname()[1]
        self.pasv_addr = (ip, port)
        # Odpowiedź w formacie FTP: 227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)
        ip_parts = ip.split('.')
        p1 = port // 256
        p2 = port % 256
        response = f"227 Entering Passive Mode ({','.join(ip_parts)},{p1},{p2}).\r\n"
        return response.encode()

    def get_local_ip(self):
        # Spróbuj pobrać IP, domyślnie 127.0.0.1 (na docelowym sprzęcie wpisz prawidłowy IP)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'

    def poll(self):
        try:
            conn, addr = self.socket.accept()
            Logger.log_info(f"Nowe połączenie od {addr}")
            conn.send(b"220 MicroPython FTP Server\r\n")
            self.logged_in = False
            user = None

            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    command = data.decode().strip()
                    Logger.log_info(f"Odebrano komendę: {command}")

                    if command.upper().startswith("USER"):
                        user = command[5:].strip()
                        conn.send(b"331 User name okay, need password.\r\n")

                    elif command.upper().startswith("PASS"):
                        passwd = command[5:].strip()
                        if user == self.username and passwd == self.password:
                            self.logged_in = True
                            conn.send(b"230 User logged in, proceed.\r\n")
                            Logger.log_info(f"Zalogowano użytkownika {user}")
                        else:
                            conn.send(b"530 Login incorrect.\r\n")
                            Logger.log_info(f"Nieudana próba logowania: {user}/{passwd}")

                    elif command.upper().startswith("QUIT"):
                        conn.send(b"221 Bye!\r\n")
                        Logger.log_info("Klient zakończył sesję.")
                        break

                    elif not self.logged_in:
                        conn.send(b"530 Please login with USER and PASS.\r\n")

                    elif command.upper().startswith("PASV"):
                        if self.pasv_socket:
                            self.pasv_socket.close()
                            self.pasv_socket = None
                        response = self.setup_pasv()
                        conn.send(response)
                        Logger.log_info(f"Ustawiono PASV na {self.pasv_addr}")

                    elif command.upper().startswith("LIST"):
                        if not self.pasv_socket:
                            conn.send(b"425 Use PASV first.\r\n")
                            continue
                        conn.send(b"150 Opening data connection.\r\n")
                        data_conn, data_addr = self.pasv_socket.accept()
                        try:
                            files = os.listdir("/sd")
                            listing = "\r\n".join(files) + "\r\n"
                            data_conn.sendall(listing.encode())
                            conn.send(b"226 Directory send OK.\r\n")
                            Logger.log_info("Wysłano listę plików.")
                        except Exception as e:
                            conn.send(b"451 Error reading directory.\r\n")
                            Logger.log_alert(f"Błąd podczas listowania: {e}")
                        finally:
                            data_conn.close()
                            self.pasv_socket.close()
                            self.pasv_socket = None

                    elif command.upper().startswith("RETR"):
                        filename = command[5:].strip()
                        filepath = "/sd/" + filename
                        if not self.pasv_socket:
                            conn.send(b"425 Use PASV first.\r\n")
                            continue
                        if filename in os.listdir("/sd"):
                            conn.send(b"150 Opening data connection.\r\n")
                            data_conn, data_addr = self.pasv_socket.accept()
                            try:
                                with open(filepath, "rb") as f:
                                    while True:
                                        chunk = f.read(512)
                                        if not chunk:
                                            break
                                        data_conn.send(chunk)
                                conn.send(b"226 Transfer complete.\r\n")
                                Logger.log_info(f"Plik pobrany: {filename}")
                            except Exception as e:
                                conn.send(b"451 Error reading file.\r\n")
                                Logger.log_alert(f"Błąd podczas pobierania pliku: {e}")
                            finally:
                                data_conn.close()
                                self.pasv_socket.close()
                                self.pasv_socket = None
                        else:
                            conn.send(b"550 File not found.\r\n")

                    elif command.upper().startswith("STOR"):
                        filename = command[5:].strip()
                        filepath = "/sd/" + filename
                        if not self.pasv_socket:
                            conn.send(b"425 Use PASV first.\r\n")
                            continue
                        conn.send(b"150 Ok to send data.\r\n")
                        data_conn, data_addr = self.pasv_socket.accept()
                        try:
                            with open(filepath, "wb") as f:
                                while True:
                                    data = data_conn.recv(512)
                                    if not data:
                                        break
                                    f.write(data)
                            conn.send(b"226 Transfer complete.\r\n")
                            Logger.log_info(f"Plik zapisany: {filename}")
                        except Exception as e:
                            conn.send(b"451 Error writing file.\r\n")
                            Logger.log_alert(f"Błąd podczas zapisu pliku: {e}")
                        finally:
                            data_conn.close()
                            self.pasv_socket.close()
                            self.pasv_socket = None

                    else:
                        conn.send(b"502 Command not implemented.\r\n")
                        Logger.log_info(f"Nieobsługiwana komenda: {command}")

                except Exception as e:
                    Logger.log_alert(f"Błąd podczas obsługi komendy: {e}")
                    conn.send(b"451 Internal server error.\r\n")
                    # Nie przerywaj pętli – pozwól użytkownikowi próbować dalej

            conn.close()
            Logger.log_info("Połączenie zamknięte.")

        except Exception as e:
            Logger.log_alert(f"Socket error: {e}")
