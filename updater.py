import os
import time
import shutil
import subprocess
import requests
import sys

# Domyślne wartości (jeśli nie podano argumentów)
APPDATA = os.path.join(os.getenv("APPDATA"), "Wyszukiwarka")
DOMYSLNA_NAZWA_EXE = "main.exe"
DOMYSLNY_URL = "https://example.com/main_new.exe"

def czy_program_dziala(nazwa):
    """Sprawdza, czy proces o tej nazwie działa (Windows-only)."""
    try:
        wynik = subprocess.check_output(f'tasklist /FI "IMAGENAME eq {os.path.basename(nazwa)}"', shell=True, text=True)
        return os.path.basename(nazwa) in wynik
    except subprocess.CalledProcessError:
        print("Nie można sprawdzić, czy program działa. Może nie być uruchomiony lub wystąpił błąd.")
        return False

def czekaj_az_program_sie_zamknie(nazwa):
    """Czeka, aż program o podanej nazwie się zamknie."""
    print(f"Czekam, aż program {os.path.basename(nazwa)} się zamknie...")
    while czy_program_dziala(nazwa):
        time.sleep(1)

def pobierz_nowa_wersje(url, nazwa_pliku):
    """Pobiera nową wersję programu z internetu."""
    try:
        print("Pobieram nową wersję...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(nazwa_pliku, "wb") as f:
            f.write(response.content)
        print("Nowa wersja została pobrana.")
    except requests.RequestException as e:
        print(f"Błąd podczas pobierania nowej wersji: {e}")
        raise

def podmien_program(stara_sciezka, nowa_sciezka):
    """Podmienia starą wersję programu na nową."""
    try:
        if os.path.exists(stara_sciezka):
            os.remove(stara_sciezka)
        shutil.move(nowa_sciezka, stara_sciezka)
        print("Program został zaktualizowany.")
    except Exception as e:
        print(f"Błąd podczas podmiany programu: {e}")
        raise

def uruchom_na_nowo(sciezka_programu):
    """Uruchamia zaktualizowany program."""
    try:
        subprocess.Popen([sciezka_programu], shell=True)
        print("Uruchomiono nową wersję programu.")
    except Exception as e:
        print(f"Błąd podczas uruchamiania programu: {e}")
        raise

if __name__ == "__main__":
    try:
        # Obsługa argumentów wiersza poleceń
        if len(sys.argv) == 3:
            nazwa_exe = sys.argv[1]
            url = sys.argv[2]
        else:
            print("Nie podano argumentów, używam domyślnych wartości...")
            nazwa_exe = DOMYSLNA_NAZWA_EXE
            url = DOMYSLNY_URL

        # Ścieżki
        stara_sciezka = os.path.join(APPDATA, nazwa_exe)
        nowa_sciezka = os.path.join(APPDATA, "tmp_update.exe")

        # Tworzenie folderu w APPDATA, jeśli nie istnieje
        if not os.path.exists(APPDATA):
            os.makedirs(APPDATA)

        czekaj_az_program_sie_zamknie(stara_sciezka)
        pobierz_nowa_wersje(url, nowa_sciezka)
        podmien_program(stara_sciezka, nowa_sciezka)
        uruchom_na_nowo(stara_sciezka)
    except Exception as e:
        print(f"Błąd podczas aktualizacji: {e}")
        input("Naciśnij Enter, aby zamknąć...")