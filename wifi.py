# wifi.py
import network
import time
from utils import log_event


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
