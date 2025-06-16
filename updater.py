import os
import time
import shutil
import subprocess
import requests
import sys
import logging
import json

APPDATA = os.path.join(os.getenv("APPDATA"), "Wyszukiwarka")
TMP_NAME = "tmp_update.exe"
LOG = os.path.join(APPDATA, "updater.log")
VERSION_URL = "https://github.com/w47k3r201800/my-app/releases/latest/download/version.json"
logging.basicConfig(
    filename=LOG,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()
logger.info("Starter updatera")

def is_running(exe):
    try:
        out = subprocess.check_output(
            f'tasklist /FI "IMAGENAME eq {os.path.basename(exe)}"',
            shell=True, text=True
        )
        return os.path.basename(exe) in out
    except Exception as e:
        logger.warning(f"Nie sprawdzono procesu: {e}")
        print("Nie można sprawdzić, czy program działa. Może nie być uruchomiony lub wystąpił błąd.")
        return False

def wait_for_close(exe, timeout=30):
    t0 = time.time()
    print(f"Czekam, aż program {os.path.basename(exe)} się zamknie...")
    while is_running(exe):
        if time.time() - t0 > timeout:
            logger.error("Timeout oczekiwania na zamkniecie")
            print("Przekroczono czas oczekiwania na zamknięcie programu!")
            break
        time.sleep(1)

def pobierz_version_json():
    try:
        r = requests.get(VERSION_URL, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Błąd pobierania version.json: {e}")
        print(f"Błąd podczas pobierania version.json: {e}")
        return None

def get_url_and_version(nazwa_pliku):
    data = pobierz_version_json()
    if not data:
        return None, None
    url = data.get("files", {}).get(nazwa_pliku)
    wersja = data.get("version")
    if not url:
        logger.error(f"Brak URL do pliku {nazwa_pliku} w version.json")
        print(f"Brak URL do pliku {nazwa_pliku} w version.json")
    return url, wersja

def download(url, dest):
    logger.info(f"Pobieram {url}")
    print("Pobieram nową wersję programu...")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        logger.info("Pobrano")
        print("Nowa wersja została pobrana.")
    except Exception as e:
        logger.error(f"Błąd pobierania: {e}")
        print(f"Błąd podczas pobierania nowej wersji: {e}")
        raise

def replace(old, tmp):
    try:
        if os.path.exists(old):
            os.remove(old)
        shutil.move(tmp, old)
        logger.info("Podmieniono plik")
        print("Program został zaktualizowany.")
    except Exception as e:
        logger.error(f"Błąd podmiany pliku: {e}")
        print(f"Błąd podczas podmiany programu: {e}")
        raise

def start_new(exe):
    try:
        subprocess.Popen([exe], shell=False)
        logger.info("Uruchomiono nowy program")
        print("Uruchomiono nową wersję programu.")
    except Exception as e:
        logger.error(f"Błąd uruchamiania programu: {e}")
        print(f"Błąd podczas uruchamiania programu: {e}")
        raise

def get_local_version(exe_path):
    # Zakładamy, że wersja jest w pliku version.txt obok exe lub w logu
    version_file = os.path.join(APPDATA, "version.txt")
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            return f.read().strip()
    return None

def main():
    try:
        exe = sys.argv[1] if len(sys.argv) >= 2 else "main.exe"
        old = os.path.join(APPDATA, exe)
        tmp = os.path.join(APPDATA, TMP_NAME)
        os.makedirs(APPDATA, exist_ok=True)
        wait_for_close(old)

        url, wersja_zdalna = get_url_and_version(exe)
        if not url or not wersja_zdalna:
            print("Nie udało się pobrać informacji o wersji.")
            return

        wersja_lokalna = get_local_version(old)
        if wersja_lokalna == wersja_zdalna:
            print("Program jest już w najnowszej wersji.")
            logger.info("Brak potrzeby aktualizacji.")
            return

        download(url, tmp)
        replace(old, tmp)
        # Zapisz nową wersję
        with open(os.path.join(APPDATA, "version.txt"), "w") as f:
            f.write(wersja_zdalna)
        start_new(old)
        print("Aktualizacja zakończona pomyślnie.")
    except Exception as e:
        logger.error(f"Błąd updatera: {e}")
        print(f"Błąd podczas aktualizacji: {e}")
        input("Naciśnij Enter, aby zamknąć...")
        sys.exit(1)

if __name__ == "__main__":
    main()
