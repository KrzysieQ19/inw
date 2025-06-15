import os
import sys
import shutil
import sqlite3
import threading
import requests
import datetime
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import pandas as pd
from rapidfuzz import process
import subprocess
import logging
import json

# --- STAŁE I ŚCIEŻKI ---
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), "Wyszukiwarka")
os.makedirs(APPDATA_DIR, exist_ok=True)

URL = "https://example.com/dane.ods"
URL_WERSJA_TXT = "https://example.com/wersja.txt"
URL_UPDATER = "https://example.com/updater.exe"
URL_VERSION_JSON = "https://example.com/version.json"  # NOWE

AKTUALNA_WERSJA = "1.0.0"
ODSWIEZ_CO_DNI = 14
PODOBIENSTWO = 80
NAZWA_PLIKU_ODS = "dane.ods"
NAZWA_BAZY = "baza.sqlite"
NAZWA_LOGU = "log.txt"
ŚCIEŻKA_PLIKU_ODS = os.path.join(APPDATA_DIR, NAZWA_PLIKU_ODS)
ŚCIEŻKA_BAZY = os.path.join(APPDATA_DIR, NAZWA_BAZY)
DATA_AKTUALIZACJI = os.path.join(APPDATA_DIR, "data_aktualizacji.txt")
ŚCIEŻKA_UPDATERA = os.path.join(APPDATA_DIR, "updater.exe")

# --- LOGOWANIE ---
logging.basicConfig(
    filename=os.path.join(APPDATA_DIR, NAZWA_LOGU),
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()
logger.info(f"Program start, wersja {AKTUALNA_WERSJA}")

# --- UTYLTY ---
def backup_old_ods(dirname=APPDATA_DIR, keep=5):
    bdir = os.path.join(dirname, "backup")
    os.makedirs(bdir, exist_ok=True)
    files = sorted([f for f in os.listdir(bdir) if f.startswith(NAZWA_PLIKU_ODS)],
                   key=lambda x: os.path.getmtime(os.path.join(bdir, x)))
    while len(files) >= keep:
        os.remove(os.path.join(bdir, files.pop(0)))
    logger.debug(f"Backupy po czyszczeniu: {files}")

def backup_file(path):
    try:
        bdir = os.path.join(APPDATA_DIR, "backup")
        os.makedirs(bdir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(bdir, f"{NAZWA_PLIKU_ODS}_{timestamp}")
        shutil.copy2(path, dst)
        logger.info(f"Backup utworzony: {dst}")
        backup_old_ods()
    except Exception as e:
        logger.error(f"Błąd backupu: {e}")

def pobierz_plik(url, sciezka):
    try:
        logger.info(f"Pobieranie: {url}")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        with open(sciezka, "wb") as f:
            f.write(resp.content)
        logger.info(f"Pobrano do: {sciezka}")
        return True
    except Exception as e:
        logger.error(f"Błąd pobierania: {e}")
        messagebox.showerror("Błąd", f"Nie udało się pobrać pliku: {e}")
        return False

def zapisz_date():
    with open(DATA_AKTUALIZACJI, "w") as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def odczytaj_date():
    if os.path.exists(DATA_AKTUALIZACJI):
        return open(DATA_AKTUALIZACJI).read().strip()
    return "Brak danych"

def czy_trzeba_odswiezyc():
    d = odczytaj_date()
    if d == "Brak danych": return True
    dt = datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
    return (datetime.datetime.now() - dt).days >= ODSWIEZ_CO_DNI

# --- BAZA DANYCH ---
class Database:
    def __init__(self, path): self.path = path
    def connect(self): return sqlite3.connect(self.path)
    def update_from_ods(self, ods_path):
        backup_file(ods_path)
        dane = pd.read_excel(ods_path, engine="odf")
        with self.connect() as conn:
            dane.to_sql("dane", conn, if_exists="replace", index=False)
        zapisz_date()
        logger.info("Baza zaktualizowana")
        return True

    def search(self, fraza, kolumna):
        with self.connect() as conn:
            c = conn.cursor()
            if fraza.isnumeric() or len(fraza)==1:
                c.execute(f"SELECT rowid, * FROM dane WHERE {kolumna} = ?", (fraza,))
                rows = [(r, 100) for r in c.fetchall()]
            else:
                pattern = f"%{fraza}%"
                c.execute(f"SELECT rowid, * FROM dane WHERE lower({kolumna}) LIKE ?", (pattern.lower(),))
                fetched = c.fetchall()
                rows = []
                for r in fetched:
                    val = str(r[c.description.index((kolumna,))]).lower()
                    score = process.extractOne(fraza.lower(), [val])[1]
                    if score >= PODOBIENSTWO:
                        rows.append((r, score))
            rows.sort(key=lambda x: x[1], reverse=True)
            cols = [d[0] for d in c.description]
            return rows, cols

# --- AKTUALIZACJA ---
def update_data():
    if pobierz_plik(URL, ŚCIEŻKA_PLIKU_ODS):
        Database(ŚCIEŻKA_BAZY).update_from_ods(ŚCIEŻKA_PLIKU_ODS)

def run_updater_if_needed():
    try:
        r = requests.get(URL_VERSION_JSON, timeout=10)
        r.raise_for_status()
        wersje = r.json()
        wersja_online = wersje.get("version", "")
        if wersja_online != AKTUALNA_WERSJA:
            logger.info(f"Nowa wersja {wersja_online}, uruchamiam updater")

            for nazwa, url in wersje.get("files", {}).items():
                local_path = os.path.join(APPDATA_DIR, nazwa)
                if not pobierz_plik(url, local_path):
                    logger.warning(f"Nie udało się pobrać {nazwa}")
                    return

            subprocess.Popen([ŚCIEŻKA_UPDATERA], shell=False)
            sys.exit()
    except Exception as e:
        logger.warning(f"Nie udało się sprawdzić wersji z GitHub: {e}")

# --- GUI ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Wyszukiwarka {AKTUALNA_WERSJA}")
        self.geometry("800x600")
        self.db = Database(ŚCIEŻKA_BAZY)
        self.results, self.columns = [], []
        self.create_widgets()
        self.load_columns()
        self.update_label()
        self.after(1000, self.periodic_tasks)

    def create_widgets(self):
        frame = ttk.Frame(self); frame.pack(padx=10, pady=10, fill=tk.X)
        ttk.Label(frame,text="Kolumna:").grid(row=0,col=0,sticky="w")
        self.col_cb = ttk.Combobox(frame, state='readonly', width=30)
        self.col_cb.grid(row=0,col=1,padx=5)
        ttk.Label(frame,text="Fraza:").grid(row=1,col=0,sticky="w")
        self.entry = ttk.Entry(frame, width=30); self.entry.grid(row=1,col=1,padx=5)
        ttk.Button(frame,text="Szukaj",command=self.threaded(self.on_search)).grid(row=0,col=2,rowspan=2,padx=5)
        ttk.Button(frame,text="Odśwież dane",command=self.threaded(self.on_refresh)).grid(row=0,col=3,rowspan=2,padx=5)
        ttk.Button(frame,text="Eksportuj",command=self.on_export).grid(row=0,col=4,rowspan=2,padx=5)
        ttk.Button(frame,text="Aktualizuj program",command=run_updater_if_needed).grid(row=0,col=5,rowspan=2,padx=5)
        ttk.Button(frame,text="Aktualizuj bazę",command=self.threaded(self.on_update_db)).grid(row=0,col=6,rowspan=2,padx=5)
        self.last_var = tk.StringVar()
        ttk.Label(self, textvariable=self.last_var).pack()
        self.text = ScrolledText(self, height=25); self.text.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)

    def load_columns(self):
        try:
            with self.db.connect() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM dane LIMIT 1")
                cols = [d[0] for d in c.description]
            self.col_cb['values'] = cols
            if cols: self.col_cb.current(0)
            self.columns = cols
        except Exception as e:
            logger.error(f"Błąd ładowania kolumn: {e}")
            self.columns = []

    def update_label(self): self.last_var.set(f"Ostatnia aktualizacja: {odczytaj_date()}")

    def threaded(self, fn):
        def wrapper():
            threading.Thread(target=fn, daemon=True).start()
        return wrapper

    def on_search(self):
        q=self.entry.get().strip(); col=self.col_cb.get()
        if not q or not col:
            messagebox.showwarning("Uwaga","Brak frazy lub kolumny")
            return
        res, cols = self.db.search(q, col)
        self.results, self.columns = res, cols
        self.after(0, self.display)

    def display(self):
        self.text.delete('1.0', tk.END)
        if not self.results:
            self.text.insert(tk.END,"Brak wyników\n"); return
        for row, score in self.results:
            data=dict(zip(self.columns, row))
            self.text.insert(tk.END,f"Wiersz {row[0]} (trafność {score}%): {data}\n")

    def on_export(self):
        if not self.results: messagebox.showinfo("Info","Brak wyników"); return
        fdir=os.path.join(APPDATA_DIR,"eksport"); os.makedirs(fdir,exist_ok=True)
        fn=os.path.join(fdir,f"wyniki_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(fn, 'w', encoding='utf-8') as f:
            for r,s in self.results:
                d=dict(zip(self.columns,r))
                f.write(f"Wiersz {r[0]} (trafność {s}%): {d}\n")
        logger.info(f"Wyniki zapisane w {fn}")
        messagebox.showinfo("Sukces",f"Zapisano: {fn}")

    def on_refresh(self):
        self.text.insert(tk.END,"Aktualizacja danych...\n")
        update_data()
        self.after(0, self.load_columns); self.after(0,self.update_label)
        self.text.insert(tk.END,"Gotowe.\n")

    def on_update_db(self):
        self.text.insert(tk.END,"Aktualizacja bazy...\n")
        if os.path.exists(ŚCIEŻKA_PLIKU_ODS):
            self.db.update_from_ods(ŚCIEŻKA_PLIKU_ODS)
            self.after(0,self.load_columns); self.after(0,self.update_label)
        else:
            messagebox.showwarning("Uwaga","Brak pliku ods")
        self.text.insert(tk.END,"Gotowe.\n")

    def periodic_tasks(self):
        if czy_trzeba_odswiezyc():
            self.on_refresh()
        run_updater_if_needed()
        self.after(3600000, self.periodic_tasks)

if __name__=="__main__":
    if not os.path.exists(ŚCIEŻKA_BAZY) or not os.path.exists(DATA_AKTUALIZACJI):
        update_data()
    app = App()
    app.mainloop()
