import json
import os
import smtplib
from dotenv import load_dotenv
from datetime import datetime, timedelta
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

# Laad de geheime variabelen in
load_dotenv()

vandaag = datetime.now()
globale_start = (vandaag - timedelta(days=7)).strftime("%Y-%m-%d")
globale_eind = (vandaag - timedelta(days=1)).strftime("%Y-%m-%d")

GEHEUGEN_BESTAND = "gemiste_dagen.json"

def genereer_js_bestand(alle_data, var_name, bestandsnaam):
    """Generieke functie om JS arrays te maken voor Greenchoice"""
    if not alle_data: return None

    def format_num(num):
        if num == 0: return "0"
        s = f"{num:.2f}".rstrip('0').rstrip('.')
        return s if s else "0"

    data_per_dag = {}
    for rij in alle_data:
        dt = datetime.strptime(rij["Timestamp"][:19], "%Y-%m-%dT%H:%M:%S")
        dag_str = dt.strftime("%Y-%m-%d")
        
        if dag_str not in data_per_dag:
            data_per_dag[dag_str] = {'uren': [], 'totaal_in': 0.0, 'totaal_uit': 0.0, 'totaal_gas': 0.0}
            
        stroom_in = float(rij["Verbruik stroom"])
        stroom_uit = abs(float(rij["Teruglevering stroom"]))
        gas_verbruik = float(rij.get("Gas verbruik", 0)) 
        
        data_per_dag[dag_str]['totaal_in'] += stroom_in
        data_per_dag[dag_str]['totaal_uit'] += stroom_uit
        data_per_dag[dag_str]['totaal_gas'] += gas_verbruik
        data_per_dag[dag_str]['uren'].append((dt.hour, stroom_in, stroom_uit, gas_verbruik)) 

    lijnen = [f"const {var_name} = ["]
    for dag_str in sorted(data_per_dag.keys()):
        dag_data = data_per_dag[dag_str]
        dt = datetime.strptime(dag_str, "%Y-%m-%d")
        
        t_in = dag_data['totaal_in']
        t_uit = dag_data['totaal_uit']
        t_gas = dag_data['totaal_gas'] 
        t_netto = t_in - t_uit
        
        t_uit_str = f"-{format_num(t_uit)}" if t_uit > 0 else "0"
        
        lijnen.append(f'"verbruik/uur op {dt.day}-{dt.month}: {format_num(t_in)}/{t_uit_str}/{format_num(t_netto)}/{format_num(t_gas)}",')
        
        for uur, s_in, s_uit, s_gas in sorted(dag_data['uren'], key=lambda x: x[0]):
            lijnen.append(f'"{uur}/{format_num(s_in)}/{format_num(s_uit)}/{format_num(s_gas)}",')
            
    lijnen.append("];")
    
    with open(bestandsnaam, "w", encoding="utf-8") as f:
        f.write("\n".join(lijnen))
        
    return bestandsnaam

def stuur_email(normaal_bestand, inhaal_bestand, normale_samenvattingen, inhaal_samenvattingen):
    print("E-mail klaarmaken voor verzending via Gmail...")
    
    afzender_email = os.getenv("GMAIL_AFZENDER")
    afzender_wachtwoord = os.getenv("GMAIL_WACHTWOORD")
    ontvangers_raw = os.getenv("MAIL_ONTVANGER", "")
    ontvanger_lijst = [e.strip() for e in ontvangers_raw.split(",") if e.strip()]
    
    if not ontvanger_lijst:
        print("❌ Geen ontvangers gevonden in MAIL_ONTVANGER!")
        return False, []
    
    msg = EmailMessage()
    
    verwachte_uren = len(normale_samenvattingen) * 24
    aantal_geldige_uren = sum(dag['geldige_uren'] for dag in normale_samenvattingen)
    laatste_dag = normale_samenvattingen[-1] if normale_samenvattingen else None

    if aantal_geldige_uren == verwachte_uren:
        msg['Subject'] = f'⚡ Greenchoice Verbruik ({globale_start} tot {globale_eind})'
        waarschuwing_tekst = ""
    elif laatste_dag and aantal_geldige_uren == (verwachte_uren - 24) and laatste_dag['geldige_uren'] == 0:
        msg['Subject'] = f'⏳ Vertraagde data ({aantal_geldige_uren}/{verwachte_uren}) - Greenchoice'
        waarschuwing_tekst = f"\nℹ️ INFO: De data van gisteren ({laatste_dag['datum']}) is nog niet verwerkt door de netbeheerder. We proberen het de volgende keer opnieuw!\n"
    else:
        msg['Subject'] = f'⚠️ LET OP: Afwijkende data ({aantal_geldige_uren}/{verwachte_uren}) - Greenchoice'
        waarschuwing_tekst = f"\n🚨 WAARSCHUWING: Er ontbreken data-punten in de afgelopen 7 dagen!\nNormaal verwachten we {verwachte_uren} uren, maar we hebben er nu {aantal_geldige_uren}.\n"

    msg['From'] = afzender_email
    msg['To'] = ", ".join(ontvanger_lijst)
    
    # 1. Normale week opbouwen
    overzicht_tekst = "📅 Afgelopen 7 Dagen:\n"
    overzicht_tekst += "-" * 75 + "\n"
    for dag in normale_samenvattingen:
        if dag['geldige_uren'] == 24:
            overzicht_tekst += f"• {dag['datum']} -> ✅ 24/24 uren | ⚡ {dag['stroom']:.2f} kWh | 🔄 {abs(dag['terug']):.2f} kWh | 🔥 {dag['gas']:.2f} m³\n"
        elif dag['geldige_uren'] == 0:
            overzicht_tekst += f"• {dag['datum']} -> ⏳  0/24 uren | (Wordt onthouden voor volgende keer)\n"
        else:
            overzicht_tekst += f"• {dag['datum']} -> ⚠️ {dag['geldige_uren']:>2}/24 uren | ⚡ {dag['stroom']:.2f} kWh | 🔄 {abs(dag['terug']):.2f} kWh | 🔥 {dag['gas']:.2f} m³\n"
    overzicht_tekst += "-" * 75 + "\n"

    # 2. Inhaaldagen toevoegen aan DEZELFDE mail
    if inhaal_samenvattingen:
        overzicht_tekst += "\n🕰️ Ingehaalde Oude Dagen:\n"
        overzicht_tekst += "-" * 75 + "\n"
        for dag in inhaal_samenvattingen:
            if dag['geldige_uren'] > 0:
                overzicht_tekst += f"• {dag['datum']} -> ✅ Succesvol ingehaald! | ⚡ {dag['stroom']:.2f} kWh | 🔄 {abs(dag['terug']):.2f} kWh | 🔥 {dag['gas']:.2f} m³\n"
            else:
                overzicht_tekst += f"• {dag['datum']} -> ❌ Nog steeds geen data. Blijft in het geheugen.\n"
        overzicht_tekst += "-" * 75 + "\n"
        waarschuwing_tekst += "\n(P.S. Ik heb ook data van eerder gemiste dagen gevonden en in een apart tekstbestand in de bijlage gezet!)\n"

    bericht = f"""Hoi!

Hier is je automatische Greenchoice-update in het nieuwe wekelijkse formaat!
{waarschuwing_tekst}
{overzicht_tekst}
Kijk in de bijlage(n) voor de exacte data per uur in JavaScript formaat.

Groeten van je eigen Python Bot 🤖
"""
    msg.set_content(bericht)

    bestanden_om_te_verwijderen = []
    
    if normaal_bestand and os.path.exists(normaal_bestand):
        with open(normaal_bestand, 'rb') as f:
            msg.add_attachment(f.read(), maintype='text', subtype='plain', filename=normaal_bestand)
            bestanden_om_te_verwijderen.append(normaal_bestand)
            
    if inhaal_bestand and os.path.exists(inhaal_bestand):
        with open(inhaal_bestand, 'rb') as f:
            msg.add_attachment(f.read(), maintype='text', subtype='plain', filename=inhaal_bestand)
            bestanden_om_te_verwijderen.append(inhaal_bestand)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(afzender_email, afzender_wachtwoord)
            smtp.send_message(msg)
        print("✅ E-mail succesvol verzonden!")
        return True, bestanden_om_te_verwijderen
    except Exception as e:
        print(f"❌ Fout bij verzenden van e-mail: {e}")
        return False, []

def scrape_greenchoice():
    with sync_playwright() as p:
        # Bepaal de 'normale' dagen
        normale_dagen = [(vandaag - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, 0, -1)]
        normale_dagen.sort()

        gemiste_dagen_lijst = []
        if os.path.exists(GEHEUGEN_BESTAND):
            with open(GEHEUGEN_BESTAND, "r") as f:
                gemiste_dagen_lijst = json.load(f)
                print(f"Geheugen geladen! Ik moet deze oude dagen nog inhalen: {gemiste_dagen_lijst}")

        # Filter inhaaldagen
        inhaal_dagen = [d for d in gemiste_dagen_lijst if d not in normale_dagen]
        inhaal_dagen.sort()

        dagen_om_te_scrapen = normale_dagen + inhaal_dagen
        dagen_om_te_scrapen.sort() 

        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()

        print("Inloggen bij Greenchoice...")
        page.goto("https://mijn.greenchoice.nl/inloggen")
        page.get_by_test_id("cookiebar__disagree").click()
        page.get_by_role("textbox", name="E-mailadres").fill(os.getenv("GC_EMAIL")) 
        page.locator('input[name="password"]').fill(os.getenv("GC_WACHTWOORD"))
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Inloggen").click() 

        page.wait_for_timeout(5000)
        print(f"Ingelogd! We gaan in totaal {len(dagen_om_te_scrapen)} dagen ophalen...")

        normale_samenvattingen = []
        inhaal_samenvattingen = []
        nieuwe_gemiste_dagen = [] 
        normale_data = [] 
        inhaal_data = []
        
        for dag_start in dagen_om_te_scrapen:
            start_obj = datetime.strptime(dag_start, "%Y-%m-%d")
            dag_eind = (start_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            is_normaal = dag_start in normale_dagen
            
            print(f"-> Data ophalen voor {dag_start}...")
            
            klant_id = os.getenv("GC_CUSTOMER_ID")
            contract_id = os.getenv("GC_AGREEMENT_ID")
            api_url = f"https://mijn.greenchoice.nl/api/v2/customers/{klant_id}/agreements/{contract_id}/consumptions?interval=Hour&start={dag_start}&end={dag_eind}"
            api_response = page.request.get(api_url)
            
            if api_response.status == 200:
                ruwe_data = api_response.json() 
                
                dag_totaal_stroom = 0
                dag_totaal_terug = 0
                dag_totaal_gas = 0
                dag_geldige_uren = 0 
                
                for uur in ruwe_data.get("consumptionCosts", []):
                    if uur.get("hasConsumption") == True:
                        dag_geldige_uren += 1 

                    elec = uur.get("electricity") or {}
                    gas = uur.get("gas") or {}

                    stroom_in = elec.get("totalDeliveryConsumption") or 0
                    stroom_uit = elec.get("totalFeedInConsumption") or 0
                    gas_verbruik = gas.get("totalDeliveryConsumption") or 0

                    dag_totaal_stroom += stroom_in
                    dag_totaal_terug += stroom_uit
                    dag_totaal_gas += gas_verbruik

                    if uur.get("hasConsumption"):
                        rij = {
                            "Timestamp": uur.get("consumedOn"),
                            "Verbruik stroom": stroom_in,
                            "Teruglevering stroom": stroom_uit,
                            "Gas verbruik": gas_verbruik
                        }
                        if is_normaal:
                            normale_data.append(rij)
                        else:
                            inhaal_data.append(rij)
                
                samenvatting = {
                    "datum": dag_start,
                    "stroom": dag_totaal_stroom,
                    "terug": dag_totaal_terug,
                    "gas": dag_totaal_gas,
                    "geldige_uren": dag_geldige_uren
                }
                
                if is_normaal:
                    normale_samenvattingen.append(samenvatting)
                else:
                    inhaal_samenvattingen.append(samenvatting)
                
                if dag_geldige_uren == 0:
                    print(f"   [!] Geen data gevonden voor {dag_start}. Ik onthoud deze voor de volgende keer!")
                    nieuwe_gemiste_dagen.append(dag_start)
                
            else:
                print(f"⚠️ Fout bij ophalen van {dag_start}: API gaf code {api_response.status}")
                nieuwe_gemiste_dagen.append(dag_start)
                samenvatting = {"datum": dag_start, "stroom": 0, "terug": 0, "gas": 0, "geldige_uren": 0}
                if is_normaal: normale_samenvattingen.append(samenvatting)
                else: inhaal_samenvattingen.append(samenvatting)
                
            page.wait_for_timeout(1000)
            
        # Sla gemiste dagen op
        with open(GEHEUGEN_BESTAND, "w") as f:
            json.dump(nieuwe_gemiste_dagen, f)
        
        # --- Genereer Bestanden ---
        normaal_bestand = None
        inhaal_bestand = None

        if normale_data:
            start_dt = datetime.strptime(normale_dagen[0], "%Y-%m-%d")
            week_nummer = start_dt.isocalendar()[1]
            var_naam = f"meting_w{week_nummer:02d}_{start_dt.year}"
            bestandsnaam = f"GreenChoice_kWh_{start_dt.year}_week{week_nummer:02d}_uur_dag.txt"
            normaal_bestand = genereer_js_bestand(normale_data, var_naam, bestandsnaam)

        if inhaal_data:
            var_naam = "meting_inhaaldata"
            bestandsnaam = "GreenChoice_Inhaaldata.txt"
            inhaal_bestand = genereer_js_bestand(inhaal_data, var_naam, bestandsnaam)
        
        # --- Email Versturen ---
        email_is_gelukt, te_verwijderen = stuur_email(normaal_bestand, inhaal_bestand, normale_samenvattingen, inhaal_samenvattingen)
        
        if email_is_gelukt:
            print("\n🧹 E-mail is verzonden. Bestanden opruimen...")
            for bestand in te_verwijderen:
                try:
                    os.remove(bestand)
                    print(f"   🗑️ Verwijderd: {bestand}")
                except Exception as e:
                    print(f"   ⚠️ Kon {bestand} niet verwijderen: {e}")
            print("✨ Opruimen voltooid! De map is weer netjes.")
        else:
            print("\n⚠️ E-mail is NIET verzonden. Bestanden lokaal bewaard.")

        browser.close()

if __name__ == "__main__":
    scrape_greenchoice()