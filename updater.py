import os
import time
import shutil
import subprocess
import requests
import sys
import logging

# --- STAŁE ---
APPDATA = os.path.join(os.getenv("APPDATA"), "Wyszukiwarka")
TMP_NAME = "tmp_update.exe"
LOG = os.path.join(APPDATA, "updater.log")
VERSION_URL = "https://example.com/version.json"
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

def get_url_from_version_json(nazwa_pliku):
    try:
        print("Pobieram informacje o wersji z serwera...")
        r = requests.get(VERSION_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        url = data.get("files", {}).get(nazwa_pliku)
        if not url:
            raise ValueError(f"Brak URL do pliku {nazwa_pliku} w version.json")
        logger.info(f"URL z version.json: {url}")
        print(f"Znaleziono URL do nowej wersji: {url}")
        return url
    except Exception as e:
        logger.error(f"Błąd odczytu version.json: {e}")
        print(f"Błąd podczas pobierania informacji o wersji: {e}")
        raise

def main():
    try:
        exe = sys.argv[1] if len(sys.argv) >= 2 else "main.exe"
        url_arg = sys.argv[2] if len(sys.argv) >= 3 else None
        old = os.path.join(APPDATA, exe)
        tmp = os.path.join(APPDATA, TMP_NAME)

        os.makedirs(APPDATA, exist_ok=True)
        wait_for_close(old)

        if url_arg:
            url = url_arg
            print(f"Używam podanego URL: {url}")
        else:
            url = get_url_from_version_json(exe)

        download(url, tmp)
        replace(old, tmp)
        start_new(old)
        print("Aktualizacja zakończona pomyślnie.")
    except Exception as e:
        logger.error(f"Błąd updatera: {e}")
        print(f"Błąd podczas aktualizacji: {e}")
        input("Naciśnij Enter, aby zamknąć...")
        sys.exit(1)

if __name__ == "__main__":
    main()
