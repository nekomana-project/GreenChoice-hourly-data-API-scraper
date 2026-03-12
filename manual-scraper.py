import tkinter as tk
from tkinter import ttk, messagebox
import threading
import csv
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from playwright.sync_api import sync_playwright
from tkcalendar import DateEntry
import os
from dotenv import load_dotenv

load_dotenv()

class GreenchoiceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Greenchoice Dag-Scraper")
        self.root.geometry("700x750")
        self.root.configure(padx=20, pady=20)

        self.opgehaalde_data = [] 
        self.huidige_datum = "" # Nu nog maar 1 datum!

        # --- 1. DATUM INPUT SECTIE (Eén enkele datum!) ---
        frame_top = tk.Frame(root)
        frame_top.pack(fill="x", pady=(0, 15))

        gisteren = datetime.now() - timedelta(days=1)

        tk.Label(frame_top, text="Kies een Datum:", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5, sticky="w")
        self.entry_datum = DateEntry(frame_top, width=15, background='#3498db', foreground='white', 
                                     borderwidth=2, date_pattern='yyyy-mm-dd')
        self.entry_datum.set_date(gisteren)
        self.entry_datum.grid(row=0, column=1, padx=5)

        # --- 2. KNOPPEN & LAADBALK SECTIE ---
        frame_knoppen = tk.Frame(root)
        frame_knoppen.pack(fill="x", pady=(0, 15))

        self.btn_haal_op = tk.Button(frame_knoppen, text="📥 Haal Dag Op", bg="#3498db", fg="white", 
                                     font=("Arial", 10, "bold"), command=self.start_scraping)
        self.btn_haal_op.pack(side="left", padx=5)

        self.btn_mail = tk.Button(frame_knoppen, text="📧 Sla op & Mail", bg="#2ecc71", fg="white", 
                                  font=("Arial", 10, "bold"), command=self.stuur_email_thread, state="disabled")
        self.btn_mail.pack(side="left", padx=5)

        self.progress = ttk.Progressbar(frame_knoppen, orient="horizontal", length=150, mode="indeterminate")
        self.progress.pack(side="left", padx=15)

        self.status_label = tk.Label(frame_knoppen, text="Klaar voor actie.", fg="#7f8c8d", font=("Arial", 10, "italic"))
        self.status_label.pack(side="right", padx=5)

        # --- 3. DATATABEL (TREEVIEW) SECTIE ---
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

    # --- FUNCTIES ---
    def update_status(self, tekst):
        self.root.after(0, lambda: self.status_label.config(text=tekst))

    def reset_ui(self):
        self.root.after(0, lambda: self.progress.stop())
        self.root.after(0, lambda: self.btn_haal_op.config(state="normal"))
        if len(self.opgehaalde_data) > 0:
            self.root.after(0, lambda: self.btn_mail.config(state="normal"))

    def start_scraping(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.opgehaalde_data = []
        
        self.btn_haal_op.config(state="disabled")
        self.btn_mail.config(state="disabled")
        
        self.progress.start(15)
        self.update_status("Inloggen en data ophalen...")

        threading.Thread(target=self.scrape_logica, daemon=True).start()

    def scrape_logica(self):
        # We pakken nu maar 1 datum uit de app
        dag_str = self.entry_datum.get()
        self.huidige_datum = dag_str

        try:
            # We berekenen de 'einddatum' voor de API puur op de achtergrond (+1 dag)
            dag_obj = datetime.strptime(dag_str, "%Y-%m-%d")
            dag_eind = (dag_obj + timedelta(days=1)).strftime("%Y-%m-%d")

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.goto("https://mijn.greenchoice.nl/inloggen")
                page.get_by_test_id("cookiebar__disagree").click()
                page.get_by_role("textbox", name="E-mailadres").fill(os.getenv("GC_EMAIL")) 
                page.locator('input[name="password"]').fill(os.getenv("GC_WACHTWOORD"))
                page.wait_for_timeout(1000)
                page.get_by_role("button", name="Inloggen").click() 

                page.wait_for_timeout(5000)
                self.update_status(f"Data ophalen voor {dag_str}...")

                # Geen for-loop meer nodig, we doen precies deze ene dag
                klant_id = os.getenv("GC_CUSTOMER_ID")
                contract_id = os.getenv("GC_AGREEMENT_ID")
                api_url = f"https://mijn.greenchoice.nl/api/v2/customers/{klant_id}/agreements/{contract_id}/consumptions?interval=Hour&start={dag_str}&end={dag_eind}"
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
                            
                            self.root.after(0, lambda r=rij: self.tree.insert("", "end", values=(
                                r["Timestamp"].replace("T", " "), 
                                f"{r['Verbruik stroom']:.3f}", 
                                f"{r['Teruglevering stroom']:.3f}", 
                                f"{r['Gas verbruik']:.3f}"
                            )))

                browser.close()
                self.update_status(f"Klaar! {len(self.opgehaalde_data)} uren gevonden.")
                self.reset_ui()

        except Exception as e:
            self.update_status("Fout tijdens ophalen (zie terminal).")
            print(f"Error: {e}")
            self.reset_ui()

    def stuur_email_thread(self):
        self.btn_mail.config(state="disabled")
        self.progress.start(15)
        self.update_status("CSV maken en e-mailen...")
        threading.Thread(target=self.maak_csv_en_mail, daemon=True).start()

    def maak_csv_en_mail(self):
        dag = self.huidige_datum
        bestandsnaam = f"verbruik_{dag}.csv"
        
        try:
            with open(bestandsnaam, "w", newline="", encoding="utf-8") as csvfile:
                kolomnamen = ["Timestamp", "Verbruik stroom", "Teruglevering stroom", "Gas verbruik"]
                writer = csv.DictWriter(csvfile, fieldnames=kolomnamen)
                writer.writeheader()
                writer.writerows(self.opgehaalde_data)
        except Exception as e:
            self.update_status("Fout bij opslaan CSV.")
            self.reset_ui()
            return

        try:
            afzender_email = os.getenv("GMAIL_AFZENDER")
            afzender_wachtwoord = os.getenv("GMAIL_WACHTWOORD")
            ontvanger_email = os.getenv("MAIL_ONTVANGER") 
            
            msg = EmailMessage()
            msg['Subject'] = f'📊 Handmatige Export Greenchoice ({dag})'
            msg['From'] = afzender_email
            msg['To'] = ontvanger_email
            msg.set_content(f"Hoi!\n\nJe hebt handmatig een export opgevraagd via de app.\nHierbij de data van {dag} ({len(self.opgehaalde_data)} uren).\n\nGroeten!")

            with open(bestandsnaam, 'rb') as f:
                msg.add_attachment(f.read(), maintype='text', subtype='csv', filename=bestandsnaam)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(afzender_email, afzender_wachtwoord)
                smtp.send_message(msg)
            
            self.update_status("✅ Opgeslagen & succesvol gemaild!")
        except Exception as e:
            self.update_status("❌ Fout bij verzenden e-mail.")
            print(e)
            
        self.reset_ui()

if __name__ == "__main__":
    app_window = tk.Tk()
    app = GreenchoiceApp(app_window)
    app_window.mainloop()