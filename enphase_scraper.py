import json
import os
import smtplib
from dotenv import load_dotenv
from datetime import datetime, timedelta
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

load_dotenv()

vandaag = datetime.now()
globale_start = (vandaag - timedelta(days=7)).strftime("%Y-%m-%d")
globale_eind = (vandaag - timedelta(days=1)).strftime("%Y-%m-%d")

GEHEUGEN_BESTAND = "enphase_gemiste_dagen.json"

def genereer_js_bestand(data_dict, var_name, bestandsnaam):
    if not data_dict: return None

    def format_num(num):
        if num == 0: return "0"
        s = f"{num:.2f}".rstrip('0').rstrip('.')
        return s if s else "0"

    lijnen = [f"const {var_name} = ["]
    
    for dag_str in sorted(data_dict.keys()):
        dag_data = data_dict[dag_str]
        dt = datetime.strptime(dag_str, "%Y-%m-%d")
        
        t_prod = dag_data.get('tot_prod', 0)
        t_verb = dag_data.get('tot_verb', 0)
        t_exp = dag_data.get('tot_exp', 0)
        
        lijnen.append(f'"enphase/uur op {dt.day}-{dt.month}: {format_num(t_prod)}/{format_num(t_verb)}/{format_num(t_exp)}",')
        
        for uur_data in sorted(dag_data.get('uren', []), key=lambda x: x[0]):
            uur = uur_data[0]
            s_prod = uur_data[1]
            s_verb = uur_data[2]
            s_exp = uur_data[3]
            lijnen.append(f'"{uur}/{format_num(s_prod)}/{format_num(s_verb)}/{format_num(s_exp)}",')
            
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
        msg['Subject'] = f'☀️ Enphase Energie ({globale_start} tot {globale_eind})'
        waarschuwing_tekst = ""
    elif laatste_dag and aantal_geldige_uren == (verwachte_uren - 24) and laatste_dag['geldige_uren'] == 0:
        msg['Subject'] = f'⏳ Vertraagde data ({aantal_geldige_uren}/{verwachte_uren}) - Enphase'
        waarschuwing_tekst = f"\nℹ️ INFO: De data van gisteren ({laatste_dag['datum']}) is nog niet verwerkt door Enphase. We proberen het de volgende keer opnieuw!\n"
    else:
        msg['Subject'] = f'⚠️ LET OP: Afwijkende data ({aantal_geldige_uren}/{verwachte_uren}) - Enphase'
        waarschuwing_tekst = f"\n🚨 WAARSCHUWING: Er ontbreken data-punten in de afgelopen 7 dagen!\nNormaal verwachten we {verwachte_uren} uren, maar we hebben er nu {aantal_geldige_uren}.\n"

    msg['From'] = afzender_email
    msg['To'] = ", ".join(ontvanger_lijst)
    
    # 1. Normale week opbouwen
    overzicht_tekst = "📅 Afgelopen 7 Dagen:\n"
    overzicht_tekst += "-" * 75 + "\n"
    for dag in normale_samenvattingen:
        if dag['geldige_uren'] == 24:
            overzicht_tekst += f"• {dag['datum']} -> ✅ 24/24 uren | ☀️ {dag['opgewekt']:.2f} kWh | 🏠 {dag['verbruikt']:.2f} kWh | ⚡ {dag['export']:.2f} kWh\n"
        elif dag['geldige_uren'] == 0:
            overzicht_tekst += f"• {dag['datum']} -> ⏳  0/24 uren | (Wordt onthouden voor volgende keer)\n"
        else:
            overzicht_tekst += f"• {dag['datum']} -> ⚠️ {dag['geldige_uren']:>2}/24 uren | ☀️ {dag['opgewekt']:.2f} kWh | 🏠 {dag['verbruikt']:.2f} kWh | ⚡ {dag['export']:.2f} kWh\n"
    overzicht_tekst += "-" * 75 + "\n"

    # 2. Inhaaldagen toevoegen aan DEZELFDE mail
    if inhaal_samenvattingen:
        overzicht_tekst += "\n🕰️ Ingehaalde Oude Dagen:\n"
        overzicht_tekst += "-" * 75 + "\n"
        for dag in inhaal_samenvattingen:
            if dag['geldige_uren'] > 0:
                overzicht_tekst += f"• {dag['datum']} -> ✅ Succesvol ingehaald! | ☀️ {dag['opgewekt']:.2f} kWh | 🏠 {dag['verbruikt']:.2f} kWh\n"
            else:
                overzicht_tekst += f"• {dag['datum']} -> ❌ Nog steeds geen data. Blijft in het geheugen.\n"
        overzicht_tekst += "-" * 75 + "\n"
        waarschuwing_tekst += "\n(P.S. Ik heb ook data van eerder gemiste dagen gevonden en in een apart tekstbestand in de bijlage gezet!)\n"

    bericht = f"""Hoi!

Hier is je automatische Enphase-update in het wekelijkse formaat!
{waarschuwing_tekst}
{overzicht_tekst}
Kijk in de bijlage(n) voor de exacte data per uur.

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

def scrape_enphase():
    with sync_playwright() as p:
        # Bepaal de 'normale' dagen
        normale_dagen = [(vandaag - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, 0, -1)]
        normale_dagen.sort()

        # Geheugen ophalen
        gemiste_dagen_lijst = []
        if os.path.exists(GEHEUGEN_BESTAND):
            with open(GEHEUGEN_BESTAND, "r") as f:
                gemiste_dagen_lijst = json.load(f)
                print(f"Geheugen geladen! Oude dagen om in te halen: {gemiste_dagen_lijst}")

        inhaal_dagen = [d for d in gemiste_dagen_lijst if d not in normale_dagen]
        inhaal_dagen.sort()

        alle_benodigde_dagen = normale_dagen + inhaal_dagen
        alle_benodigde_dagen.sort()

        # --- DE OPLOSSING: Splits de benodigde dagen op per MAAND ---
        # Bijv: 2026-02-11 en 2026-03-01 resulteert in ['2026-02-01', '2026-03-01']
        benodigde_maanden = list(set([d[:7] + "-01" for d in alle_benodigde_dagen]))
        benodigde_maanden.sort()

        browser = p.chromium.launch(headless=True) 
        context = browser.new_context()
        page = context.new_page()

        print("Inloggen bij Enphase...")
        page.goto("https://enlighten.enphaseenergy.com/login")
        
        try:
            page.get_by_role("button", name="Accept All Cookies").click(timeout=3000)
        except Exception:
            pass

        print("Gegevens invullen...")
        page.locator('input[name="user[email]"]').press_sequentially(os.getenv("ENPHASE_EMAIL"), delay=100)
        page.locator('input[name="user[password]"]').press_sequentially(os.getenv("ENPHASE_WACHTWOORD"), delay=100)
        page.get_by_role("button", name="Sign In").click() 

        print("Wachten op login...")
        page.wait_for_timeout(15000) 

        site_id = os.getenv("ENPHASE_SITE_ID")
        
        # Verzamelbak voor álle data uit de verschillende maanden
        alle_opgehaalde_dagen_data = {}

        # Haal elke benodigde maand op bij Enphase
        for maand_start in benodigde_maanden:
            api_url = f"https://enlighten.enphaseenergy.com/pv/systems/{site_id}/daily_energy?start_date={maand_start}"
            print(f"-> Maand-chunk ophalen vanaf {maand_start}...")
            
            response = page.request.get(api_url)
            if response.status == 200:
                ruwe_data = response.json()
                stats = ruwe_data.get("stats", [])
                if not stats:
                    continue
                    
                api_start_dt = datetime.strptime(ruwe_data.get("start_date"), "%Y-%m-%d")
                
                # Sla elke dag uit deze maand op in onze grote verzamelbak
                for index, dag_data in enumerate(stats):
                    huidige_dag = api_start_dt + timedelta(days=index)
                    datum_str = huidige_dag.strftime("%Y-%m-%d")
                    alle_opgehaalde_dagen_data[datum_str] = dag_data
            else:
                print(f"⚠️ Fout bij ophalen API voor maand {maand_start}: Code {response.status}")
                
            page.wait_for_timeout(1500) # Klein wachtmomentje tussen API calls

        # --- Data filteren & ordenen ---
        normale_data_per_dag = {}
        inhaal_data_per_dag = {}
        normale_samenvattingen = []
        inhaal_samenvattingen = []
        nieuwe_gemiste_dagen = []

        for datum_str in alle_benodigde_dagen:
            is_normaal = datum_str in normale_dagen
            dag_data = alle_opgehaalde_dagen_data.get(datum_str)

            # Als we de dag überhaupt niet hebben teruggekregen van de API
            if not dag_data:
                print(f"   [!] Geen data gevonden voor {datum_str}.")
                nieuwe_gemiste_dagen.append(datum_str)
                samenvatting = {"datum": datum_str, "opgewekt": 0, "verbruikt": 0, "export": 0, "geldige_uren": 0}
                if is_normaal: normale_samenvattingen.append(samenvatting)
                else: inhaal_samenvattingen.append(samenvatting)
                continue

            productie = dag_data.get("production", [])
            verbruik = dag_data.get("consumption", [])
            export = dag_data.get("export", [])
            totals = dag_data.get("totals", {})

            dag_geldige_uren = 0

            # Als de dag er is, maar Enphase heeft nog 0 waarden
            if not totals or (not productie and not verbruik):
                print(f"   [!] Data is nog leeg/onverwerkt voor {datum_str}.")
                nieuwe_gemiste_dagen.append(datum_str)
                samenvatting = {"datum": datum_str, "opgewekt": 0, "verbruikt": 0, "export": 0, "geldige_uren": 0}
                if is_normaal: normale_samenvattingen.append(samenvatting)
                else: inhaal_samenvattingen.append(samenvatting)
                continue

            # Uren berekenen
            dag_opslag = {'tot_prod': totals.get("production", 0) / 1000.0, 'tot_verb': totals.get("consumption", 0) / 1000.0, 'tot_exp': totals.get("export", 0) / 1000.0, 'uren': []}

            for uur in range(24):
                start_idx = uur * 4
                eind_idx = start_idx + 4
                
                prod_kw = [x if x is not None else 0 for x in productie[start_idx:eind_idx]] if len(productie) >= eind_idx else []
                verb_kw = [x if x is not None else 0 for x in verbruik[start_idx:eind_idx]] if len(verbruik) >= eind_idx else []
                exp_kw  = [x if x is not None else 0 for x in export[start_idx:eind_idx]] if export and len(export) >= eind_idx else []
                
                if prod_kw or verb_kw or exp_kw:
                    dag_geldige_uren += 1
                    uur_prod = sum(prod_kw) / 1000.0
                    uur_verb = sum(verb_kw) / 1000.0
                    uur_exp = sum(exp_kw) / 1000.0
                    dag_opslag['uren'].append((uur, uur_prod, uur_verb, uur_exp))

            samenvatting = {
                "datum": datum_str, "opgewekt": dag_opslag['tot_prod'], "verbruikt": dag_opslag['tot_verb'], "export": dag_opslag['tot_exp'], "geldige_uren": dag_geldige_uren
            }

            if is_normaal:
                normale_data_per_dag[datum_str] = dag_opslag
                normale_samenvattingen.append(samenvatting)
            else:
                inhaal_data_per_dag[datum_str] = dag_opslag
                inhaal_samenvattingen.append(samenvatting)

        # Geheugen opslaan
        with open(GEHEUGEN_BESTAND, "w") as f:
            json.dump(nieuwe_gemiste_dagen, f)
        
        # --- Genereer Bestanden ---
        normaal_bestand = None
        inhaal_bestand = None

        if normale_data_per_dag:
            start_dt = datetime.strptime(normale_dagen[0], "%Y-%m-%d")
            week_nummer = start_dt.isocalendar()[1]
            var_naam = f"enphase_w{week_nummer:02d}_{start_dt.year}"
            bestandsnaam = f"Enphase_kWh_{start_dt.year}_week{week_nummer:02d}.txt"
            normaal_bestand = genereer_js_bestand(normale_data_per_dag, var_naam, bestandsnaam)

        if inhaal_data_per_dag:
            var_naam = "enphase_inhaaldata"
            bestandsnaam = "Enphase_Inhaaldata.txt"
            inhaal_bestand = genereer_js_bestand(inhaal_data_per_dag, var_naam, bestandsnaam)
        
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
        else:
            print("\n⚠️ E-mail is NIET verzonden. Bestanden lokaal bewaard.")

        browser.close()

if __name__ == "__main__":
    scrape_enphase()