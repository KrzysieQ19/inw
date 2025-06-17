import os
import sys
import shutil
import sqlite3
import threading
import requests
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import pandas as pd
from rapidfuzz import fuzz
import subprocess
import logging
import json

# --- STAŁE I ŚCIEŻKI ---
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), "Wyszukiwarka")
os.makedirs(APPDATA_DIR, exist_ok=True)

NAZWA_PLIKU_ODS = "data.ods"
NAZWA_BAZY = "baza.sqlite"
NAZWA_LOGU = "log.txt"
NAZWA_EKSPORTU = "wyniki.txt"
NAZWA_BACKUP = "backup.ods"
NAZWA_PROGRAMU = "main.exe"
NAZWA_UPDATERA = "updater.exe"
DATA_AKTUALIZACJI = os.path.join(APPDATA_DIR, "data_aktualizacji.txt")

ŚCIEŻKA_PLIKU_ODS = os.path.join(APPDATA_DIR, NAZWA_PLIKU_ODS)
ŚCIEŻKA_BAZY = os.path.join(APPDATA_DIR, NAZWA_BAZY)
ŚCIEŻKA_LOGU = os.path.join(APPDATA_DIR, NAZWA_LOGU)
ŚCIEŻKA_UPDATERA = os.path.join(APPDATA_DIR, NAZWA_UPDATERA)

# --- KONFIGURACJA ---
VERSION_JSON_URL = "https://github.com/KrzysieQ19/inw/releases/latest/download/version.json"
AKTUALNA_WERSJA = "1.0.0"
ODSWIEZ_CO_DNI = 14
PODOBIENSTWO = 80
ZACHOWANE_BACKUPY = 10

# --- LOGOWANIE ---
logging.basicConfig(
    filename=ŚCIEŻKA_LOGU,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()
logger.info(f"Program start, wersja {AKTUALNA_WERSJA}")

# --- POBIERANIE URL-i Z version.json ---
def pobierz_version_json():
    try:
        r = requests.get(VERSION_JSON_URL, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Błąd pobierania version.json: {e}")
        messagebox.showerror("Błąd", f"Nie udało się pobrać version.json: {e}")
        return None

def get_url_from_version_json(nazwa_pliku):
    data = pobierz_version_json()
    if not data:
        return None
    url = data.get("files", {}).get(nazwa_pliku)
    if not url:
        logger.error(f"Brak URL do pliku {nazwa_pliku} w version.json")
        messagebox.showerror("Błąd", f"Brak URL do pliku {nazwa_pliku} w version.json")
    return url

def get_version_from_version_json():
    data = pobierz_version_json()
    if not data:
        return None
    return data.get("version")

# --- BACKUP .ODS I SQLITE ---
def backup_file(path, prefix):
    try:
        backup_dir = os.path.join(APPDATA_DIR, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(path)[1]
        backup_path = os.path.join(backup_dir, f"{prefix}_{timestamp}{ext}")
        shutil.copy2(path, backup_path)
        logger.info(f"Backup utworzony: {backup_path}")
        backup_old_files(prefix)
    except Exception as e:
        logger.error(f"Błąd backupu {prefix}: {e}")

def backup_old_files(prefix):
    backup_dir = os.path.join(APPDATA_DIR, "backup")
    files = sorted([f for f in os.listdir(backup_dir) if f.startswith(prefix)],
                   key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)))
    while len(files) >= ZACHOWANE_BACKUPY:
        os.remove(os.path.join(backup_dir, files.pop(0)))
    logger.debug(f"Backupy po czyszczeniu: {files}")

# --- POBIERANIE PLIKÓW ---
def pobierz_plik(url, sciezka_docelowa):
    try:
        logger.info(f"Pobieranie pliku z: {url}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(sciezka_docelowa, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Pobrano i zapisano plik do: {sciezka_docelowa}")
        return True
    except Exception as e:
        logger.error(f"Błąd pobierania pliku: {e}")
        messagebox.showerror("Błąd", f"Nie udało się pobrać pliku: {e}")
        return False

# --- AKTUALIZACJA BAZY ---
def aktualizuj_baze():
    if os.path.exists(ŚCIEŻKA_PLIKU_ODS):
        backup_file(ŚCIEŻKA_PLIKU_ODS, "ods")
    else:
        messagebox.showerror("Błąd", "Plik danych nie istnieje.")
        return

    try:
        dane = pd.read_excel(ŚCIEŻKA_PLIKU_ODS, engine="odf")
        if os.path.exists(ŚCIEŻKA_BAZY):
            backup_file(ŚCIEŻKA_BAZY, "sqlite")
        conn = sqlite3.connect(ŚCIEŻKA_BAZY)
        dane.to_sql("dane", conn, if_exists="replace", index=False)
        conn.close()
        zapisz_date_aktualizacji()
        logger.info("Baza danych została zaktualizowana.")
        messagebox.showinfo("Sukces", "Baza danych została zaktualizowana.")
    except Exception as e:
        logger.error(f"Błąd aktualizacji bazy danych: {e}")
        messagebox.showerror("Błąd", f"Nie udało się zaktualizować bazy danych: {e}")

def refresh_data():
    url = get_url_from_version_json(NAZWA_PLIKU_ODS)
    if not url:
        return
    if pobierz_plik(url, ŚCIEŻKA_PLIKU_ODS):
        aktualizuj_baze()

def zapisz_date_aktualizacji():
    with open(DATA_AKTUALIZACJI, "w") as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S"))

def odczytaj_date_aktualizacji():
    if os.path.exists(DATA_AKTUALIZACJI):
        with open(DATA_AKTUALIZACJI, "r") as f:
            return f.read().strip()
    return "Brak danych"

def czy_aktualizacja_wymagana():
    ostatnia_aktualizacja = odczytaj_date_aktualizacji()
    if not ostatnia_aktualizacja or ostatnia_aktualizacja == "Brak danych":
        return True
    try:
        dt = datetime.datetime.strptime(ostatnia_aktualizacja, "%Y-%m-%d-%H:%M:%S")
        return (datetime.datetime.now() - dt).days >= ODSWIEZ_CO_DNI
    except Exception:
        return True

# --- BAZA DANYCH ---
class Database:
    def __init__(self, path): self.path = path
    def connect(self): return sqlite3.connect(self.path)
    def update_from_ods(self, ods_path):
        backup_file(ods_path, "ods")
        dane = pd.read_excel(ods_path, engine="odf")
        with self.connect() as conn:
            dane.to_sql("dane", conn, if_exists="replace", index=False)
        zapisz_date_aktualizacji()
        logger.info("Baza zaktualizowana")
        return True

    def search(self, fraza, kolumna):
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                if fraza.isnumeric() or len(fraza)==1:
                    cursor.execute(f"SELECT rowid, * FROM dane WHERE {kolumna} = ?", (fraza,))
                    wyniki = [(r, 100) for r in cursor.fetchall()]
                else:
                    pattern = f"%{fraza}%"
                    cursor.execute(f"SELECT rowid, * FROM dane WHERE lower({kolumna}) LIKE ?", (pattern.lower(),))
                    fetched = cursor.fetchall()
                    wyniki = []
                    col_names = [desc[0] for desc in cursor.description]
                    col_idx = col_names.index(kolumna)
                    for r in fetched:
                        val = str(r[col_idx]).lower()
                        score = fuzz.ratio(fraza.lower(), val)
                        if score >= PODOBIENSTWO:
                            wyniki.append((r, score))
                wyniki.sort(key=lambda x: x[1], reverse=True)
                cols = [d[0] for d in cursor.description]
                return wyniki, cols
        except Exception as e:
            logger.error(f"Błąd wyszukiwania: {e}")
            messagebox.showerror("Błąd", f"Nie udało się wyszukać danych: {e}")
            return [], []

# --- EKSPORT WYNIKÓW ---
def export_results(results, columns):
    try:
        export_dir = os.path.join(APPDATA_DIR, "eksport")
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(export_dir, f"wyniki_{timestamp}.txt")
        with open(export_path, 'w', encoding='utf-8') as f:
            for row, score in results:
                row_data = dict(zip(columns, row))
                f.write(f"Wiersz {row[0]} (trafność {score}%): {row_data}\n")
        logger.info(f"Wyniki wyeksportowano do {export_path}")
        messagebox.showinfo("Sukces", f"Wyniki wyeksportowano do {export_path}")
    except Exception as e:
        logger.error(f"Błąd eksportu wyników: {e}")
        messagebox.showerror("Błąd", f"Nie udało się wyeksportować wyników: {e}")

# --- AKTUALIZACJA PROGRAMU ---
def sprawdz_i_aktualizuj_program():
    try:
        nowa_wersja = get_version_from_version_json()
        if not nowa_wersja:
            return
        if nowa_wersja != AKTUALNA_WERSJA:
            logger.info(f"Znaleziono nową wersję: {nowa_wersja}")
            url_updater = get_url_from_version_json(NAZWA_UPDATERA)
            if not url_updater:
                return
            if not os.path.exists(ŚCIEŻKA_UPDATERA) or not file_is_latest(ŚCIEŻKA_UPDATERA, url_updater):
                pobierz_plik(url_updater, ŚCIEŻKA_UPDATERA)
            subprocess.Popen([ŚCIEŻKA_UPDATERA, NAZWA_PROGRAMU], shell=True)
            messagebox.showinfo("Aktualizacja", "Znaleziono nową wersję programu. Program zostanie zaktualizowany.")
            sys.exit()
    except Exception as e:
        logger.error(f"Błąd sprawdzania nowej wersji: {e}")

def file_is_latest(local_path, url):
    # Proste sprawdzenie po rozmiarze pliku
    try:
        r = requests.head(url, timeout=10)
        remote_size = int(r.headers.get('Content-Length', 0))
        local_size = os.path.getsize(local_path)
        return local_size == remote_size
    except Exception:
        return False

# --- GUI ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Wyszukiwarka - wersja {AKTUALNA_WERSJA}")
        self.geometry("1100x600")
        self.db = Database(ŚCIEŻKA_BAZY)
        self.results, self.columns = [], []
        self.create_widgets()
        self.load_columns()
        self.update_label()
        self.after(1000, self.periodic_tasks)
        self.bind("<Return>", lambda event: self.on_search_thread())

    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(pady=10, padx=10, fill=tk.X)
        
        ttk.Label(frame, text="Wybierz kolumnę:").grid(row=0, column=0, sticky="w")
        self.column_cb = ttk.Combobox(frame, state='readonly', width=30)
        self.column_cb.grid(row=0, column=1, padx=5)

        ttk.Label(frame, text="Fraza:").grid(row=1, column=0, sticky="w")
        self.search_entry = ttk.Entry(frame, width=30)
        self.search_entry.grid(row=1, column=1, padx=5)

        self.search_button = ttk.Button(frame, text="Szukaj", command=self.on_search_thread)
        self.search_button.grid(row=0, column=2, rowspan=2, padx=10, pady=2)

        self.refresh_button = ttk.Button(frame, text="Odśwież dane", command=self.on_refresh_thread)
        self.refresh_button.grid(row=0, column=3, rowspan=2, padx=10, pady=2)

        self.export_button = ttk.Button(frame, text="Eksportuj wyniki", command=self.on_export_thread)
        self.export_button.grid(row=0, column=4, rowspan=2, padx=10, pady=2)

        self.update_button = ttk.Button(frame, text="Aktualizuj program", command=self.on_update_program_thread)
        self.update_button.grid(row=0, column=5, rowspan=2, padx=10, pady=2)

        self.update_db_button = ttk.Button(frame, text="Aktualizuj bazę", command=self.on_update_db_thread)
        self.update_db_button.grid(row=0, column=6, rowspan=2, padx=10, pady=2)

        self.open_logs_button = ttk.Button(frame, text="Otwórz folder logów", command=self.open_logs_folder)
        self.open_logs_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=2)

        self.open_exports_button = ttk.Button(frame, text="Otwórz folder eksportów", command=self.open_exports_folder)
        self.open_exports_button.grid(row=2, column=2, columnspan=2, sticky="ew", pady=2)

        self.last_update_var = tk.StringVar()
        self.label_update = ttk.Label(self, textvariable=self.last_update_var)
        self.label_update.pack(pady=2)

        self.results_box = ScrolledText(self, height=25, width=100)
        self.results_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def open_logs_folder(self):
        folder = APPDATA_DIR
        subprocess.Popen(f'explorer "{folder}"')

    def open_exports_folder(self):
        folder = os.path.join(APPDATA_DIR, "eksport")
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')
    
    def load_columns(self):
        try:
            conn = sqlite3.connect(ŚCIEŻKA_BAZY)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dane LIMIT 1")
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            self.column_cb['values'] = columns
            if columns:
                self.column_cb.current(0)
            self.current_columns = columns
        except Exception as e:
            logger.error(f"Błąd ładowania kolumn: {e}")
            self.column_cb['values'] = []
            self.current_columns = []

    def update_label(self):
        self.last_update_var.set(f"Ostatnia aktualizacja: {odczytaj_date_aktualizacji()}")

    def on_search_thread(self):
        threading.Thread(target=self.on_search, daemon=True).start()

    def on_search(self):
        query = self.search_entry.get().strip()
        col = self.column_cb.get()
        if not query or not col:
            messagebox.showwarning("Uwaga", "Brak frazy lub kolumny. Wprowadź tekst do wyszukania.")
            return
        results, columns = self.db.search(query, col)
        self.results = results
        self.columns = columns
        self.display_results(results, columns)

    def display_results(self, results, columns):
        self.results_box.delete('1.0', tk.END)
        if not results:
            self.results_box.insert(tk.END, "Brak wyników.\n")
            return
        for row, score in results:
            row_data = dict(zip(columns, row))
            self.results_box.insert(tk.END, f"Wiersz {row[0]} (trafność {score}%): {row_data}\n")

    def on_export_thread(self):
        threading.Thread(target=self.on_export, daemon=True).start()

    def on_export(self):
        if not self.results:
            messagebox.showinfo("Info", "Brak wyników")
            return
        export_results(self.results, self.columns)

    def on_refresh_thread(self):
        threading.Thread(target=self._refresh_thread, daemon=True).start()

    def _refresh_thread(self):
        self.results_box.insert(tk.END, "Aktualizacja danych...\n")
        refresh_data()
        self.load_columns()
        self.update_label()
        self.results_box.insert(tk.END, "Zakończono aktualizację.\n")

    def on_update_db_thread(self):
        threading.Thread(target=self._update_db_thread, daemon=True).start()

    def _update_db_thread(self):
        self.results_box.insert(tk.END, "Aktualizacja bazy...\n")
        aktualizuj_baze()
        self.load_columns()
        self.update_label()
        self.results_box.insert(tk.END, "Zakończono aktualizację bazy.\n")

    def on_update_program_thread(self):
        threading.Thread(target=sprawdz_i_aktualizuj_program, daemon=True).start()

    def periodic_tasks(self):
        # Automatyczna aktualizacja bazy co X dni
        if czy_aktualizacja_wymagana():
            self.on_refresh_thread()
        # Automatyczne sprawdzanie nowej wersji programu
        threading.Thread(target=sprawdz_i_aktualizuj_program, daemon=True).start()
        self.after(60 * 60 * 1000, self.periodic_tasks)  # co godzinę

if __name__=="__main__":
    if not os.path.exists(ŚCIEŻKA_BAZY) or not os.path.exists(DATA_AKTUALIZACJI):
        refresh_data()
    app = App()
    app.mainloop()