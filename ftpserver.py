import os
import socket
from logger import Logger
from tamper import FileTamper

class FTPServer:
    def __init__(self, username, password, port=21):
        self.port = port
        self.server_socket = None
        self.username = username
        self.password = password
        self.logged_in = False
        self.pasv_socket = None
        self.pasv_addr = None

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)
        Logger.log_info(f"Serwer FTP nasłuchuje na porcie {self.port}")

    def setup_pasv(self, conn):
        if self.pasv_socket:
            try:
                self.pasv_socket.close()
            except:
                pass
            self.pasv_socket = None
    
        self.pasv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.pasv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        pasv_port = 50000 
        
        try:
            self.pasv_socket.bind(('0.0.0.0', pasv_port))
            self.pasv_socket.listen(1)
            ip = self.get_local_ip()
            
            if ip == '127.0.0.1':
                Logger.log_alert("Warning: Using localhost IP - remote connections will fail!")
                
            self.pasv_addr = (ip, pasv_port)
            ip_parts = ip.split('.')
            p1 = pasv_port // 256
            p2 = pasv_port % 256
            response = f"227 Entering Passive Mode ({','.join(ip_parts)},{p1},{p2}).\r\n"
            conn.send(response.encode())
            return response
        except Exception as e:
            Logger.log_alert(f"PASV setup failed: {e}")
            raise

    def get_local_ip(self):
        import network
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.active():
            sta_if.active(True)
        if sta_if.isconnected():
            return sta_if.ifconfig()[0]
        Logger.log_alert("WiFi not connected! Falling back to 127.0.0.1")
        return '127.0.0.1'  
    
    def poll(self):
        try:
            conn, addr = self.server_socket.accept()
            Logger.log_info(f"Nowe połączenie od {addr}")
            conn.send(b"220 MicroPython FTP Server\r\n")
            self.logged_in = False
            user = None

            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    command = data.decode('ascii', 'ignore').strip()
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
                    
                    # FileZilla commands
                    elif command.upper().startswith("PWD"):
                        conn.send(b'257 "/" is the current directory.\r\n')

                    elif command.upper().startswith("TYPE"):
                        type_code = command[5:].strip().upper()
                        if type_code in ['A', 'I', 'L 8']:
                            conn.send(f"200 Type set to {type_code}.\r\n".encode())
                            Logger.log_info(f"Ustawiono typ transferu: {type_code}")
                        else:
                            conn.send(b"504 Type not supported.\r\n")


                    elif command.upper().startswith("PASV"):
                        if self.pasv_socket:
                            self.pasv_socket.close()
                            self.pasv_socket = None
                        response = self.setup_pasv(conn)
                        Logger.log_info(f"Ustawiono PASV na {self.pasv_addr}")

                    elif command.upper().startswith("LIST") or command.upper().startswith("NLST"):
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

                    elif command.upper().startswith("SIZE"):
                        if not self.pasv_socket:
                            conn.send(b"425 Use PASV first.\r\n")
                            continue
                        filename = command[5:].strip().lstrip('/')
                        filepath = "/sd/" + filename
                        try:
                            if filename in os.listdir("/sd"):
                                file_size = os.stat(filepath)[6]
                                response = f"213 {file_size}\r\n"
                                conn.send(response.encode())
                            else:
                                conn.send(b"550 File not found.\r\n")
                        except Exception as e:
                            conn.send(b"550 Error retrieving file size.\r\n")

                    elif command.upper().startswith("RETR"):
                        filename = command[5:].strip().lstrip('/')
                        filepath = "/sd/" + filename
                        if not self.pasv_socket:
                            conn.send(b"425 Use PASV first.\r\n")
                            continue

                        if filename not in os.listdir("/sd"):
                            conn.send(b"550 File not found.\r\n")
                            continue
                            
                        if FileTamper.check_file_changed(filepath):
                            conn.send(b"550 File verification failed - possible tampering detected.\r\n")
                            Logger.log_alert(f"Próba pobrania zmodyfikowanego pliku: {filename}")
                            continue
                            
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

                    elif command.upper().startswith("MDTM"):
                        filename = command[5:].strip().lstrip('/')
                        filepath = "/sd/" + filename
                        try:
                            if filename in os.listdir("/sd"):
                                mtime = os.stat(filepath)[8]
                                import time
                                timestamp = time.localtime(mtime)
                                formatted_time = time.strftime("%Y%m%d%H%M%S", timestamp)
                                response = f"213 {formatted_time}\r\n"
                                conn.send(response.encode())
                            else:
                                conn.send(b"550 File not found.\r\n")
                        except Exception as e:
                            conn.send(b"550 Error retrieving modification time.\r\n")

                    elif command.upper().startswith("CWD"):
                        path = command[4:].strip()
                        if path in ["/", "/sd", ""]:
                            conn.send(b"250 Directory successfully changed.\r\n")
                        else:
                            conn.send(b"550 Failed to change directory.\r\n")


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
                            
                            if FileTamper.init_file_hash(filepath):
                                Logger.log_info(f"Plik zapisany i hash utworzony: {filename}")
                            else:
                                Logger.log_alert(f"Plik zapisany, ale nie udało się utworzyć hash: {filename}")
                            
                            conn.send(b"226 Transfer complete.\r\n")
                        except Exception as e:
                            conn.send(b"451 Error writing file.\r\n")
                            Logger.log_alert(f"Błąd podczas zapisu pliku: {e}")
                        finally:
                            data_conn.close()
                            self.pasv_socket.close()
                            self.pasv_socket = None

                    elif command.upper().startswith("SYST"):
                        conn.send(b"215 UNIX Type: L8\r\n")
                    elif command.upper().startswith("FEAT"):
                        conn.send(b"211 No features\r\n")
                    elif command.upper() == "AUTH TLS" or command.upper() == "AUTH SSL":
                        conn.send(b"502 SSL/TLS not supported\r\n")
                        
                    else:
                        conn.send(b"502 Command not implemented.\r\n")
                        Logger.log_info(f"Nieobsługiwana komenda: {command}")

                except Exception as e:
                    Logger.log_alert(f"Błąd podczas obsługi komendy: {e}")
                    conn.send(b"451 Internal server error.\r\n")
                    # Nie przerywaj pętli – pozwól użytkownikowi próbować dalej

        except Exception as e:
            Logger.log_alert(f"Socket error: {e}")

        finally:
            conn.close()
            Logger.log_info("Połączenie zamknięte.")