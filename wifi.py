# wifi.py
import network
import time
from logger import Logger


def connect_wifi(ssid, password, timeout_ms=15000):
    Logger.log_info(f"Aktywuję interfejs Wi-Fi (SSID: {ssid})")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    Logger.log_info("Rozpoczynam łączenie z Wi-Fi...")
    wlan.connect(ssid, password)

    t0 = time.ticks_ms()
    while not wlan.isconnected():
        status = wlan.status()
        Logger.log_info(f"Status Wi-Fi: {status}")
        if status == network.STAT_WRONG_PASSWORD:
            Logger.log_info("Błędne hasło Wi-Fi.")
            raise RuntimeError("Błędne hasło Wi-Fi")
        if status == network.STAT_NO_AP_FOUND:
            Logger.log_info("Nie znaleziono sieci Wi-Fi.")
            raise RuntimeError("Nie znaleziono sieci Wi-Fi")
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
            Logger.log_info("Timeout przy łączeniu z Wi-Fi.")
            raise RuntimeError("Timeout przy łączeniu z Wi-Fi")
        time.sleep(0.2)

    Logger.log_info(f"Połączono: {wlan.ifconfig()}")
    return wlan.ifconfig()[0]
