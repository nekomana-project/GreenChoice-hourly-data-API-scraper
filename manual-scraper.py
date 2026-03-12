import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import csv
import smtplib
import os
from datetime import datetime, timedelta
from email.message import EmailMessage
from playwright.sync_api import sync_playwright
from tkcalendar import DateEntry
from dotenv import load_dotenv

# Laad de omgevingsvariabelen uit .env
load_dotenv()

class GreenchoiceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Greenchoice Dag-Scraper")
        self.root.geometry("850x950") 
        self.root.configure(padx=20, pady=20)

        self.opgehaalde_data = [] 
        self.start_str = ""
        self.eind_str = ""

        # Wachtrij voor opdrachten naar de achtergrond-browser
        self.scrape_queue = queue.Queue()
        threading.Thread(target=self.browser_worker, daemon=True).start()

        # --- 1. INSTELLINGEN SECTIE ---
        frame_settings = tk.LabelFrame(root, text=" Configuraties (Standaard uit .env) ", padx=10, pady=10)
        frame_settings.pack(fill="x", pady=(0, 15))

        tk.Label(frame_settings, text="GC Email:").grid(row=0, column=0, sticky="w")
        self.ent_gc_email = tk.Entry(frame_settings, width=30)
        self.ent_gc_email.insert(0, os.getenv("GC_EMAIL", ""))
        self.ent_gc_email.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(frame_settings, text="GC Wachtwoord:").grid(row=0, column=2, sticky="w", padx=(10,0))
        self.ent_gc_pass = tk.Entry(frame_settings, width=30, show="*")
        self.ent_gc_pass.insert(0, os.getenv("GC_WACHTWOORD", ""))
        self.ent_gc_pass.grid(row=0, column=3, padx=5, pady=2)

        tk.Label(frame_settings, text="Customer ID:").grid(row=1, column=0, sticky="w")
        self.ent_cust_id = tk.Entry(frame_settings, width=30)
        self.ent_cust_id.insert(0, os.getenv("GC_CUSTOMER_ID", ""))
        self.ent_cust_id.grid(row=1, column=1, padx=5, pady=2)

        tk.Label(frame_settings, text="Agreement ID:").grid(row=1, column=2, sticky="w", padx=(10,0))
        self.ent_agree_id = tk.Entry(frame_settings, width=30)
        self.ent_agree_id.insert(0, os.getenv("GC_AGREEMENT_ID", ""))
        self.ent_agree_id.grid(row=1, column=3, padx=5, pady=2)

        tk.Label(frame_settings, text="Gmail Afzender:").grid(row=2, column=0, sticky="w")
        self.ent_gmail_sender = tk.Entry(frame_settings, width=30)
        self.ent_gmail_sender.insert(0, os.getenv("GMAIL_AFZENDER", ""))
        self.ent_gmail_sender.grid(row=2, column=1, padx=5, pady=2)

        tk.Label(frame_settings, text="Gmail App Pass:").grid(row=2, column=2, sticky="w", padx=(10,0))
        self.ent_gmail_pass = tk.Entry(frame_settings, width=30, show="*")
        self.ent_gmail_pass.insert(0, os.getenv("GMAIL_WACHTWOORD", ""))
        self.ent_gmail_pass.grid(row=2, column=3, padx=5, pady=2)

        tk.Label(frame_settings, text="Mail Ontvanger:").grid(row=3, column=0, sticky="w")
        self.ent_mail_to = tk.Entry(frame_settings, width=30)
        self.ent_mail_to.insert(0, os.getenv("MAIL_ONTVANGER", ""))
        self.ent_mail_to.grid(row=3, column=1, padx=5, pady=2)

        # --- 2. SESSIE EN DATUM SECTIE ---
        frame_top = tk.Frame(root)
        frame_top.pack(fill="x", pady=(0, 15))

        # Datum Controls (Links)
        frame_datum = tk.Frame(frame_top)
        frame_datum.pack(side="left")

        tk.Label(frame_datum, text="Einddatum:", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 5))
        
        self.btn_prev = tk.Button(frame_datum, text="<", font=("Arial", 9, "bold"), command=self.vorige_dag)
        self.btn_prev.pack(side="left")

        gisteren = datetime.now() - timedelta(days=1)
        self.entry_datum = DateEntry(frame_datum, width=12, background='#3498db', foreground='white', 
                                     borderwidth=2, date_pattern='yyyy-mm-dd')
        self.entry_datum.set_date(gisteren)
        self.entry_datum.pack(side="left", padx=5)

        self.btn_next = tk.Button(frame_datum, text=">", font=("Arial", 9, "bold"), command=self.volgende_dag)
        self.btn_next.pack(side="left")

        # Dagen bereik
        tk.Label(frame_datum, text="Aantal dagen:", font=("Arial", 10, "bold")).pack(side="left", padx=(15, 5))
        self.spin_dagen = ttk.Spinbox(frame_datum, from_=1, to=31, width=4) 
        self.spin_dagen.set(1)
        self.spin_dagen.pack(side="left")

        # Sessie Controls (Rechts)
        frame_sessie = tk.Frame(frame_top)
        frame_sessie.pack(side="right")

        self.lbl_sessie = tk.Label(frame_sessie, text="🔴 Offline", font=("Arial", 10, "bold"), fg="#e74c3c")
        self.lbl_sessie.pack(side="left", padx=10)

        self.btn_login = tk.Button(frame_sessie, text="🔑 Login", bg="#9b59b6", fg="white", 
                                   font=("Arial", 9, "bold"), command=self.handmatige_login)
        self.btn_login.pack(side="left")

        # --- 3. KNOPPEN & LAADBALK SECTIE ---
        frame_knoppen = tk.Frame(root)
        frame_knoppen.pack(fill="x", pady=(0, 15))

        self.btn_haal_op = tk.Button(frame_knoppen, text="📥 Haal Data Op", bg="#3498db", fg="white", 
                                     font=("Arial", 10, "bold"), command=self.start_scraping)
        self.btn_haal_op.pack(side="left", padx=5)

        self.btn_save = tk.Button(frame_knoppen, text="💾 Sla CSV op", bg="#f39c12", fg="white", 
                                  font=("Arial", 10, "bold"), command=self.sla_csv_op, state="disabled")
        self.btn_save.pack(side="left", padx=5)

        self.btn_mail = tk.Button(frame_knoppen, text="📧 Mail CSV", bg="#2ecc71", fg="white", 
                                  font=("Arial", 10, "bold"), command=self.stuur_email_thread, state="disabled")
        self.btn_mail.pack(side="left", padx=5)

        self.progress = ttk.Progressbar(frame_knoppen, orient="horizontal", length=150, mode="indeterminate")
        self.progress.pack(side="left", padx=15)

        self.status_label = tk.Label(frame_knoppen, text="Klaar voor actie.", fg="#7f8c8d", font=("Arial", 10, "italic"))
        self.status_label.pack(side="right", padx=5)

        # --- 4. DATATABEL (TREEVIEW) SECTIE ---
        kolommen = ("tijd", "stroom", "terug", "gas")
        self.tree = ttk.Treeview(root, columns=kolommen, show="headings", height=15)
        
        self.tree.heading("tijd", text="Tijdstip")
        self.tree.heading("stroom", text="Stroom in (kWh)")
        self.tree.heading("terug", text="Stroom uit (kWh)")
        self.tree.heading("gas", text="Gas (m³)")

        self.tree.column("tijd", width=150, anchor="center")
        self.tree.column("stroom", width=120, anchor="center")
        self.tree.column("terug", width=120, anchor="center")
        self.tree.column("gas", width=120, anchor="center")

        self.tree.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    # --- DATUM NAVIGATIE FUNCTIES ---
    def vorige_dag(self):
        huidig = self.entry_datum.get_date()
        self.entry_datum.set_date(huidig - timedelta(days=1))

    def volgende_dag(self):
        huidig = self.entry_datum.get_date()
        self.entry_datum.set_date(huidig + timedelta(days=1))

    # --- HULPFUNCTIES ---
    def get_config(self):
        return {
            "gc_email": self.ent_gc_email.get().strip() or os.getenv("GC_EMAIL"),
            "gc_pass": self.ent_gc_pass.get().strip() or os.getenv("GC_WACHTWOORD"),
            "cust_id": self.ent_cust_id.get().strip() or os.getenv("GC_CUSTOMER_ID"),
            "agree_id": self.ent_agree_id.get().strip() or os.getenv("GC_AGREEMENT_ID"),
            "sender": self.ent_gmail_sender.get().strip() or os.getenv("GMAIL_AFZENDER"),
            "sender_pass": self.ent_gmail_pass.get().strip() or os.getenv("GMAIL_WACHTWOORD"),
            "recipient": self.ent_mail_to.get().strip() or os.getenv("MAIL_ONTVANGER")
        }

    def clean_mail_entries(self):
        self.ent_gmail_sender.delete(0, tk.END)
        self.ent_gmail_sender.insert(0, os.getenv("GMAIL_AFZENDER", ""))
        self.ent_gmail_pass.delete(0, tk.END)
        self.ent_gmail_pass.insert(0, os.getenv("GMAIL_WACHTWOORD", ""))
        self.ent_mail_to.delete(0, tk.END)
        self.ent_mail_to.insert(0, os.getenv("MAIL_ONTVANGER", ""))

    def update_status(self, tekst):
        self.root.after(0, lambda: self.status_label.config(text=tekst))

    def set_login_status(self, ingelogd, bezig=False):
        if bezig:
            self.root.after(0, lambda: self.lbl_sessie.config(text="⏳ Bezig met inloggen...", fg="#f39c12"))
            self.root.after(0, lambda: self.btn_login.config(state="disabled"))
        elif ingelogd:
            self.root.after(0, lambda: self.lbl_sessie.config(text="🟢 Ingelogd", fg="#27ae60"))
            self.root.after(0, lambda: self.btn_login.config(state="disabled"))
        else:
            self.root.after(0, lambda: self.lbl_sessie.config(text="🔴 Offline", fg="#e74c3c"))
            self.root.after(0, lambda: self.btn_login.config(state="normal"))

    def reset_ui(self):
        self.root.after(0, lambda: self.progress.stop())
        self.root.after(0, lambda: self.btn_haal_op.config(state="normal"))
        if len(self.opgehaalde_data) > 0:
            self.root.after(0, lambda: self.btn_save.config(state="normal"))
            self.root.after(0, lambda: self.btn_mail.config(state="normal"))

    # --- WERK- EN WACHTRIJ FUNCTIES ---
    def handmatige_login(self):
        self.scrape_queue.put({"action": "login", "conf": self.get_config()})
        self.progress.start(15)

    def start_scraping(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.opgehaalde_data = []
        
        # Bepaal het datumbereik
        eind_obj = self.entry_datum.get_date()
        try:
            aantal_dagen = int(self.spin_dagen.get())
            if aantal_dagen < 1: aantal_dagen = 1
        except ValueError:
            aantal_dagen = 1
            self.spin_dagen.set(1)
            
        start_obj = eind_obj - timedelta(days=aantal_dagen - 1)
        
        self.start_str = start_obj.strftime("%Y-%m-%d")
        self.eind_str = eind_obj.strftime("%Y-%m-%d")
        
        self.btn_haal_op.config(state="disabled")
        self.btn_save.config(state="disabled")
        self.btn_mail.config(state="disabled")
        
        self.progress.start(15)
        self.update_status("Taak in wachtrij plaatsen...")

        self.scrape_queue.put({
            "action": "scrape",
            "start_str": self.start_str,
            "eind_str": self.eind_str,
            "aantal_dagen": aantal_dagen,
            "conf": self.get_config()
        })

    def browser_worker(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            is_logged_in = False

            while True:
                task = self.scrape_queue.get() 
                if task is None: break

                action = task["action"]
                conf = task["conf"]

                try:
                    if action == "login" or (action == "scrape" and not is_logged_in):
                        if not is_logged_in:
                            self.set_login_status(False, bezig=True)
                            self.update_status("Sessie starten bij Greenchoice...")
                            
                            page.goto("https://mijn.greenchoice.nl/inloggen")
                            try: page.get_by_test_id("cookiebar__disagree").click(timeout=3000)
                            except: pass

                            page.get_by_role("textbox", name="E-mailadres").fill(conf["gc_email"])
                            page.locator('input[name="password"]').fill(conf["gc_pass"])
                            page.wait_for_timeout(1000)
                            page.get_by_role("button", name="Inloggen").click() 

                            page.wait_for_timeout(5000)
                            is_logged_in = True
                            self.set_login_status(True)
                            self.update_status("✅ Inloggen succesvol!")

                        if action == "login":
                            self.reset_ui()
                            continue 

                    if action == "scrape":
                        start_str = task["start_str"]
                        aantal_dagen = task["aantal_dagen"]
                        
                        start_obj = datetime.strptime(start_str, "%Y-%m-%d")
                        totaal_uren = 0
                        heeft_fout = False

                        # Loop door het aantal dagen heen
                        for i in range(aantal_dagen):
                            huidige_dag_obj = start_obj + timedelta(days=i)
                            huidige_dag_str = huidige_dag_obj.strftime("%Y-%m-%d")
                            volgende_dag_str = (huidige_dag_obj + timedelta(days=1)).strftime("%Y-%m-%d")

                            self.update_status(f"Data ophalen: {huidige_dag_str} ({i+1}/{aantal_dagen})...")

                            api_url = f"https://mijn.greenchoice.nl/api/v2/customers/{conf['cust_id']}/agreements/{conf['agree_id']}/consumptions?interval=Hour&start={huidige_dag_str}&end={volgende_dag_str}"
                            api_response = page.request.get(api_url)
                            
                            if api_response.status == 200:
                                ruwe_data = api_response.json()
                                for uur in ruwe_data.get("consumptionCosts", []):
                                    if uur.get("hasConsumption"):
                                        elec = uur.get("electricity") or {}
                                        gas = uur.get("gas") or {}
                                        
                                        rij = {
                                            "Timestamp": uur.get("consumedOn"),
                                            "Verbruik stroom": elec.get("totalDeliveryConsumption") or 0,
                                            "Teruglevering stroom": elec.get("totalFeedInConsumption") or 0,
                                            "Gas verbruik": gas.get("totalDeliveryConsumption") or 0
                                        }
                                        self.opgehaalde_data.append(rij)
                                        totaal_uren += 1
                                        
                                        # Stuur naar UI
                                        self.root.after(0, lambda r=rij: self.tree.insert("", "end", values=(
                                            r["Timestamp"].replace("T", " "), 
                                            f"{r['Verbruik stroom']:.3f}", 
                                            f"{r['Teruglevering stroom']:.3f}", 
                                            f"{r['Gas verbruik']:.3f}"
                                        )))
                            elif api_response.status in [401, 403]:
                                self.update_status("❌ Sessie verlopen. Probeer het opnieuw.")
                                is_logged_in = False
                                self.set_login_status(False)
                                heeft_fout = True
                                break # Stop de loop als we niet meer ingelogd zijn
                            else:
                                self.update_status(f"Fout: API gaf code {api_response.status} voor {huidige_dag_str}")
                                heeft_fout = True
                                break
                                
                            # Korte pauze om de API niet te spammen
                            page.wait_for_timeout(300)

                        if not heeft_fout:
                            self.update_status(f"Klaar! {totaal_uren} uren gevonden over {aantal_dagen} dagen.")

                        self.reset_ui()

                except Exception as e:
                    self.update_status("Fout tijdens achtergrond-taak.")
                    print(f"Error: {e}")
                    is_logged_in = False 
                    self.set_login_status(False)
                    self.reset_ui()

    # --- OPSLAAN EN MAILEN ---
    def sla_csv_op(self):
        if not self.opgehaalde_data: return
        
        if self.start_str == self.eind_str:
            bestandsnaam = f"verbruik_{self.start_str}.csv"
        else:
            bestandsnaam = f"verbruik_{self.start_str}_tm_{self.eind_str}.csv"

        try:
            with open(bestandsnaam, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["Timestamp", "Verbruik stroom", "Teruglevering stroom", "Gas verbruik"])
                writer.writeheader()
                writer.writerows(self.opgehaalde_data)
            self.update_status(f"✅ Opgeslagen als {bestandsnaam}")
            messagebox.showinfo("Succes", f"Bestand {bestandsnaam} is succesvol opgeslagen.")
        except Exception as e:
            self.update_status("❌ Fout bij opslaan CSV.")

    def stuur_email_thread(self):
        self.btn_mail.config(state="disabled")
        self.progress.start(15)
        self.update_status("E-mail verzenden...")
        threading.Thread(target=self.verstuur_mail_logica, daemon=True).start()

    def verstuur_mail_logica(self):
        conf = self.get_config()
        
        if self.start_str == self.eind_str:
            bestandsnaam = f"verbruik_{self.start_str}.csv"
            subject = f'📊 Export Greenchoice ({self.start_str})'
            content = f"Hoi!\n\nHierbij de data van {self.start_str}.\n\nGroeten!"
        else:
            bestandsnaam = f"verbruik_{self.start_str}_tm_{self.eind_str}.csv"
            subject = f'📊 Export Greenchoice ({self.start_str} t/m {self.eind_str})'
            content = f"Hoi!\n\nHierbij de data van {self.start_str} tot en met {self.eind_str}.\n\nGroeten!"

        try:
            with open(bestandsnaam, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["Timestamp", "Verbruik stroom", "Teruglevering stroom", "Gas verbruik"])
                writer.writeheader(); writer.writerows(self.opgehaalde_data)

            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = conf["sender"]; msg['To'] = conf["recipient"]
            msg.set_content(content)
            
            with open(bestandsnaam, 'rb') as f:
                msg.add_attachment(f.read(), maintype='text', subtype='csv', filename=bestandsnaam)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(conf["sender"], conf["sender_pass"])
                smtp.send_message(msg)
            
            self.update_status("✅ Succesvol gemaild!")
            self.root.after(0, self.clean_mail_entries)
            if os.path.exists(bestandsnaam): os.remove(bestandsnaam)
        except Exception as e:
            self.update_status("❌ Fout bij verzenden (zie terminal).")
            print(f"Mail error: {e}")
        self.reset_ui()

if __name__ == "__main__":
    app_window = tk.Tk()
    app = GreenchoiceApp(app_window)
    app_window.mainloop()