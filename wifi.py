# wifi.py
import network
import time
from logger import Logger


def connect_wifi(ssid, password, timeout_ms=15000):
    log_event(f"Aktywuję interfejs Wi-Fi (SSID: {ssid})")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    log_event("Rozpoczynam łączenie z Wi-Fi...")
    wlan.connect(ssid, password)
<<<<<<< Updated upstream
=======
    Logger.log_event("Łączenie z Wi-Fi…")
>>>>>>> Stashed changes

    t0 = time.ticks_ms()
    while not wlan.isconnected():
        status = wlan.status()
        log_event(f"Status Wi-Fi: {status}")
        if status == network.STAT_WRONG_PASSWORD:
            log_event("Błędne hasło Wi-Fi.")
            raise RuntimeError("Błędne hasło Wi-Fi")
        if status == network.STAT_NO_AP_FOUND:
            log_event("Nie znaleziono sieci Wi-Fi.")
            raise RuntimeError("Nie znaleziono sieci Wi-Fi")
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
            log_event("Timeout przy łączeniu z Wi-Fi.")
            raise RuntimeError("Timeout przy łączeniu z Wi-Fi")
        time.sleep(0.2)

    Logger.log_event(f"Połączono: {wlan.ifconfig()}")
    return wlan.ifconfig()[0]
