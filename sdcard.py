"""
MicroPython SDCard driver (SPI mode) + DEBUG LOGS.
"""

from micropython import const
import time

_CMD_TIMEOUT = const(100)
_R1_IDLE_STATE = const(1 << 0)
_R1_ILLEGAL_COMMAND = const(1 << 2)
_TOKEN_CMD25 = const(0xFC)
_TOKEN_STOP_TRAN = const(0xFD)
_TOKEN_DATA = const(0xFE)

class SDCard:
    def __init__(self, spi, cs, baudrate=1320000):
        self.spi = spi
        self.cs = cs
        self.cmdbuf = bytearray(6)
        self.dummybuf = bytearray(512)
        self.tokenbuf = bytearray(1)
        for i in range(512):
            self.dummybuf[i] = 0xFF
        self.dummybuf_memoryview = memoryview(self.dummybuf)
        # initialise the card
        print("[SD] Inicjalizacja SDCard (SPI)")
        self.init_card(baudrate)

    def init_spi(self, baudrate):
        try:
            master = self.spi.MASTER
        except AttributeError:
            self.spi.init(baudrate=baudrate, phase=0, polarity=0)
        else:
            self.spi.init(master, baudrate=baudrate, phase=0, polarity=0)

    def init_card(self, baudrate):
        print("[SD] Inicjalizuję CS pin...")
        self.cs.init(self.cs.OUT, value=1)
        print("[SD] Init SPI na niskim baudrate...")
        self.init_spi(100000)
        print("[SD] Wysyłam 100 cykli clocka z CS high...")
        for i in range(16):
            self.spi.write(b"\xff")
        print("[SD] CMD0: próbuję 5 razy...")
        for attempt in range(5):
            res = self.cmd(0, 0, 0x95)
            print(f"[SD] CMD0 próba {attempt+1}: odpowiedź {res}")
            if res == _R1_IDLE_STATE:
                break
        else:
            print("[SD] Brak odpowiedzi z SD card (CMD0)")
            raise OSError("no SD card")

        print("[SD] CMD8: sprawdzam wersję karty...")
        r = self.cmd(8, 0x01AA, 0x87, 4)
        print(f"[SD] CMD8 odpowiedź: {r}")
        if r == _R1_IDLE_STATE:
            print("[SD] Detekcja v2")
            self.init_card_v2()
        elif r == (_R1_IDLE_STATE | _R1_ILLEGAL_COMMAND):
            print("[SD] Detekcja v1")
            self.init_card_v1()
        else:
            print("[SD] Nieznana odpowiedź wersji SD: ", r)
            raise OSError("couldn't determine SD card version")

        print("[SD] CMD9: pobieram CSD")
        if self.cmd(9, 0, 0, 0, False) != 0:
            print("[SD] Brak odpowiedzi od SD (CMD9)")
            raise OSError("no response from SD card")
        csd = bytearray(16)
        self.readinto(csd)
        print("[SD] CSD: ", [hex(b) for b in csd])
        if csd[0] & 0xC0 == 0x40:  # CSD version 2.0
            self.sectors = ((csd[8] << 8 | csd[9]) + 1) * 1024
        elif csd[0] & 0xC0 == 0x00:  # CSD version 1.0
            c_size = (csd[6] & 0b11) << 10 | csd[7] << 2 | csd[8] >> 6
            c_size_mult = (csd[9] & 0b11) << 1 | csd[10] >> 7
            read_bl_len = csd[5] & 0b1111
            capacity = (c_size + 1) * (2 ** (c_size_mult + 2)) * (2**read_bl_len)
            self.sectors = capacity // 512
        else:
            print("[SD] Nieobsługiwany format CSD.")
            raise OSError("SD card CSD format not supported")

        print(f"[SD] Liczba sektorów: {self.sectors}")
        print("[SD] CMD16: ustawiam blok 512 bajtów...")
        if self.cmd(16, 512, 0) != 0:
            print("[SD] Nie można ustawić bloku 512 bajtów!")
            raise OSError("can't set 512 block size")
        print("[SD] Ustawiam szybki SPI")
        self.init_spi(baudrate)
        print("[SD] Karta SD zainicjalizowana pomyślnie!")

    def init_card_v1(self):
        print("[SD] Inicjalizacja SD v1")
        for i in range(_CMD_TIMEOUT):
            time.sleep_ms(50)
            self.cmd(55, 0, 0)
            if self.cmd(41, 0, 0) == 0:
                self.cdv = 512
                print("[SD] v1: karta zainicjalizowana")
                return
        print("[SD] Timeout SD v1")
        raise OSError("timeout waiting for v1 card")

    def init_card_v2(self):
        print("[SD] Inicjalizacja SD v2")
        for i in range(_CMD_TIMEOUT):
            time.sleep_ms(50)
            self.cmd(58, 0, 0, 4)
            self.cmd(55, 0, 0)
            if self.cmd(41, 0x40000000, 0) == 0:
                self.cmd(58, 0, 0, -4)
                ocr = self.tokenbuf[0]
                if not ocr & 0x40:
                    self.cdv = 512
                    print("[SD] v2: SDSC (byte addressing)")
                else:
                    self.cdv = 1
                    print("[SD] v2: SDHC/SDXC (block addressing)")
                print("[SD] v2: karta zainicjalizowana")
                return
        print("[SD] Timeout SD v2")
        raise OSError("timeout waiting for v2 card")

    def cmd(self, cmd, arg, crc, final=0, release=True, skip1=False):
        self.cs(0)
        buf = self.cmdbuf
        buf[0] = 0x40 | cmd
        buf[1] = arg >> 24
        buf[2] = arg >> 16
        buf[3] = arg >> 8
        buf[4] = arg
        buf[5] = crc
        self.spi.write(buf)
        if skip1:
            self.spi.readinto(self.tokenbuf, 0xFF)
        for i in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            response = self.tokenbuf[0]
            if not (response & 0x80):
                if final < 0:
                    self.spi.readinto(self.tokenbuf, 0xFF)
                    final = -1 - final
                for j in range(final):
                    self.spi.write(b"\xff")
                if release:
                    self.cs(1)
                    self.spi.write(b"\xff")
                return response
        self.cs(1)
        self.spi.write(b"\xff")
        return -1

    def readinto(self, buf):
        self.cs(0)
        for i in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == _TOKEN_DATA:
                break
            time.sleep_ms(1)
        else:
            self.cs(1)
            print("[SD] Timeout oczekiwania na odpowiedź DATA")
            raise OSError("timeout waiting for response")
        mv = self.dummybuf_memoryview
        if len(buf) != len(mv):
            mv = mv[: len(buf)]
        self.spi.write_readinto(mv, buf)
        self.spi.write(b"\xff")
        self.spi.write(b"\xff")
        self.cs(1)
        self.spi.write(b"\xff")

    def write(self, token, buf):
        self.cs(0)
        self.spi.read(1, token)
        self.spi.write(buf)
        self.spi.write(b"\xff")
        self.spi.write(b"\xff")
        if (self.spi.read(1, 0xFF)[0] & 0x1F) != 0x05:
            self.cs(1)
            self.spi.write(b"\xff")
            return
        while self.spi.read(1, 0xFF)[0] == 0:
            pass
        self.cs(1)
        self.spi.write(b"\xff")

    def write_token(self, token):
        self.cs(0)
        self.spi.read(1, token)
        self.spi.write(b"\xff")
        while self.spi.read(1, 0xFF)[0] == 0x00:
            pass
        self.cs(1)
        self.spi.write(b"\xff")

    def readblocks(self, block_num, buf):
        self.spi.write(b"\xff")
        nblocks = len(buf) // 512
        assert nblocks and not len(buf) % 512, "Buffer length is invalid"
        if nblocks == 1:
            if self.cmd(17, block_num * self.cdv, 0, release=False) != 0:
                self.cs(1)
                raise OSError(5)  # EIO
            self.readinto(buf)
        else:
            if self.cmd(18, block_num * self.cdv, 0, release=False) != 0:
                self.cs(1)
                raise OSError(5)  # EIO
            offset = 0
            mv = memoryview(buf)
            while nblocks:
                self.readinto(mv[offset : offset + 512])
                offset += 512
                nblocks -= 1
            if self.cmd(12, 0, 0xFF, skip1=True):
                raise OSError(5)  # EIO

    def writeblocks(self, block_num, buf):
        self.spi.write(b"\xff")
        nblocks, err = divmod(len(buf), 512)
        assert nblocks and not err, "Buffer length is invalid"
        if nblocks == 1:
            if self.cmd(24, block_num * self.cdv, 0) != 0:
                raise OSError(5)  # EIO
            self.write(_TOKEN_DATA, buf)
        else:
            if self.cmd(25, block_num * self.cdv, 0) != 0:
                raise OSError(5)  # EIO
            offset = 0
            mv = memoryview(buf)
            while nblocks:
                self.write(_TOKEN_CMD25, mv[offset : offset + 512])
                offset += 512
                nblocks -= 1
            self.write_token(_TOKEN_STOP_TRAN)

    def ioctl(self, op, arg):
        if op == 4:  # get number of blocks
            return self.sectors
        if op == 5:  # get block size in bytes
            return 512
