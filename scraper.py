import json
import csv
import smtplib
import os
from dotenv import load_dotenv

# Laad de geheime variabelen in
load_dotenv()
from datetime import datetime, timedelta
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

vandaag = datetime.now()

globale_start = (vandaag - timedelta(days=7)).strftime("%Y-%m-%d")
globale_eind = (vandaag - timedelta(days=1)).strftime("%Y-%m-%d")

GEHEUGEN_BESTAND = "gemiste_dagen.json"

def stuur_email(bijlagen_lijst, aantal_geldige_rijen, dag_samenvattingen):
    print("E-mail klaarmaken voor verzending via Gmail...")
    
    afzender_email = os.getenv("GMAIL_AFZENDER")
    afzender_wachtwoord = os.getenv("GMAIL_WACHTWOORD")
    ontvanger_email = os.getenv("MAIL_ONTVANGER")
    
    msg = EmailMessage()
    
    verwachte_uren = len(dag_samenvattingen) * 24
    laatste_dag = dag_samenvattingen[-1]

    if aantal_geldige_rijen == verwachte_uren:
        msg['Subject'] = f'⚡ Greenchoice Verbruik ({globale_start} tot {globale_eind})'
        waarschuwing_tekst = ""
        
    elif aantal_geldige_rijen == (verwachte_uren - 24) and laatste_dag['geldige_uren'] == 0:
        msg['Subject'] = f'⏳ Vertraagde data ({aantal_geldige_rijen}/{verwachte_uren}) - Greenchoice'
        waarschuwing_tekst = f"\nℹ️ INFO: De data van gisteren ({laatste_dag['datum']}) is nog niet verwerkt door de netbeheerder. Geen paniek, de bot probeert deze dag volgende week automatisch opnieuw op te halen!\n"
        
    else:
        msg['Subject'] = f'⚠️ LET OP: Afwijkende data ({aantal_geldige_rijen}/{verwachte_uren}) - Greenchoice'
        waarschuwing_tekst = f"\n🚨 WAARSCHUWING: Er ontbreken data-punten!\nNormaal verwachten we {verwachte_uren} uren voor deze check, maar we hebben er nu {aantal_geldige_rijen}. De dagen met 0 uren worden opgeslagen en volgende week opnieuw geprobeerd.\n"

    msg['From'] = afzender_email
    msg['To'] = ontvanger_email
    
    overzicht_tekst = "📅 Dagelijkse Totalen:\n"
    overzicht_tekst += "-" * 75 + "\n"
    for dag in dag_samenvattingen:
        if dag['geldige_uren'] == 24:
            overzicht_tekst += f"• {dag['datum']} -> ✅ 24/24 uren | ⚡ {dag['stroom']:.2f} kWh | 🔄 {abs(dag['terug']):.2f} kWh | 🔥 {dag['gas']:.2f} m³\n"
        elif dag['geldige_uren'] == 0:
            overzicht_tekst += f"• {dag['datum']} -> ⏳  0/24 uren | (Wordt volgende run opnieuw geprobeerd!)\n"
        else:
            overzicht_tekst += f"• {dag['datum']} -> ⚠️ {dag['geldige_uren']:>2}/24 uren | ⚡ {dag['stroom']:.2f} kWh | 🔄 {abs(dag['terug']):.2f} kWh | 🔥 {dag['gas']:.2f} m³\n"
    overzicht_tekst += "-" * 75 + "\n"

    bericht = f"""Hoi!

Hier is je automatische energie-update.
{waarschuwing_tekst}
{overzicht_tekst}
Je vindt de {len(bijlagen_lijst)} losse CSV-bestanden voor Excel in de bijlagen.

Groeten van je eigen Python Bot 🤖
"""
    msg.set_content(bericht)

    for bestand in bijlagen_lijst:
        with open(bestand, 'rb') as f:
            bestand_data = f.read()
        msg.add_attachment(bestand_data, maintype='text', subtype='csv', filename=bestand)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(afzender_email, afzender_wachtwoord)
            smtp.send_message(msg)
        print("✅ E-mail met slimme uren-controle succesvol verzonden!")
        return True # --- NIEUW: We geven door dat het gelukt is! ---
    except Exception as e:
        print(f"❌ Fout bij verzenden van e-mail: {e}")
        return False # --- NIEUW: We geven door dat het is mislukt ---

def scrape_greenchoice():
    with sync_playwright() as p:
        gemiste_dagen_lijst = []
        if os.path.exists(GEHEUGEN_BESTAND):
            with open(GEHEUGEN_BESTAND, "r") as f:
                gemiste_dagen_lijst = json.load(f)
                print(f"Geheugen geladen! Ik moet deze oude dagen nog inhalen: {gemiste_dagen_lijst}")

        dagen_om_te_scrapen = []
        for dagen_terug in range(7, 0, -1):
            dagen_om_te_scrapen.append((vandaag - timedelta(days=dagen_terug)).strftime("%Y-%m-%d"))

        dagen_om_te_scrapen = list(set(dagen_om_te_scrapen + gemiste_dagen_lijst))
        dagen_om_te_scrapen.sort() 

        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()

        print("Inloggen bij Greenchoice...")
        page.goto("https://mijn.greenchoice.nl/inloggen")
        page.get_by_test_id("cookiebar__disagree").click()
        # Inloggen
        page.get_by_role("textbox", name="E-mailadres").fill(os.getenv("GC_EMAIL")) 
        page.locator('input[name="password"]').fill(os.getenv("GC_WACHTWOORD"))
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Inloggen").click() 

        page.wait_for_timeout(5000)
        print(f"Ingelogd! We gaan in totaal {len(dagen_om_te_scrapen)} dagen ophalen...")

        aantal_geldige_rijen = 0
        gegenereerde_bestanden = [] 
        dag_samenvattingen = [] 
        nieuwe_gemiste_dagen = [] 
        
        for dag_start in dagen_om_te_scrapen:
            start_obj = datetime.strptime(dag_start, "%Y-%m-%d")
            dag_eind = (start_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            
            print(f"-> Data ophalen voor {dag_start}...")
            
            klant_id = os.getenv("GC_CUSTOMER_ID")
            contract_id = os.getenv("GC_AGREEMENT_ID")
            api_url = f"https://mijn.greenchoice.nl/api/v2/customers/{klant_id}/agreements/{contract_id}/consumptions?interval=Hour&start={dag_start}&end={dag_eind}"
            api_response = page.request.get(api_url)
            
            if api_response.status == 200:
                ruwe_data = api_response.json() 
                
                dag_data = [] 
                dag_totaal_stroom = 0
                dag_totaal_terug = 0
                dag_totaal_gas = 0
                dag_geldige_uren = 0 
                
                for uur in ruwe_data.get("consumptionCosts", []):
                    if uur.get("hasConsumption") == True:
                        aantal_geldige_rijen += 1
                        dag_geldige_uren += 1 

                    elec = uur.get("electricity") or {}
                    gas = uur.get("gas") or {}

                    stroom_in = elec.get("totalDeliveryConsumption") or 0
                    stroom_uit = elec.get("totalFeedInConsumption") or 0
                    gas_verbruik = gas.get("totalDeliveryConsumption") or 0

                    dag_totaal_stroom += stroom_in
                    dag_totaal_terug += stroom_uit
                    dag_totaal_gas += gas_verbruik

                    dag_data.append({
                        "Timestamp": uur.get("consumedOn"),
                        "Verbruik stroom": stroom_in,
                        "Teruglevering stroom": stroom_uit,
                        "Gas verbruik": gas_verbruik
                    })
                
                dag_samenvattingen.append({
                    "datum": dag_start,
                    "stroom": dag_totaal_stroom,
                    "terug": dag_totaal_terug,
                    "gas": dag_totaal_gas,
                    "geldige_uren": dag_geldige_uren
                })
                
                if dag_geldige_uren == 0:
                    print(f"   [!] Geen data gevonden voor {dag_start}. Ik onthoud deze voor de volgende keer!")
                    nieuwe_gemiste_dagen.append(dag_start)
                else:
                    dag_bestandsnaam = f"verbruik_{dag_start}.csv"
                    with open(dag_bestandsnaam, "w", newline="", encoding="utf-8") as csvfile:
                        kolomnamen = ["Timestamp", "Verbruik stroom", "Teruglevering stroom", "Gas verbruik"]
                        writer = csv.DictWriter(csvfile, fieldnames=kolomnamen)
                        writer.writeheader()
                        writer.writerows(dag_data)
                    gegenereerde_bestanden.append(dag_bestandsnaam)
                
            else:
                print(f"⚠️ Fout bij ophalen van {dag_start}: API gaf code {api_response.status}")
                nieuwe_gemiste_dagen.append(dag_start)
                
            page.wait_for_timeout(1000)
            
        print(f"\nKlaar! Totaal {aantal_geldige_rijen} uren gevonden.")
        
        with open(GEHEUGEN_BESTAND, "w") as f:
            json.dump(nieuwe_gemiste_dagen, f)
        
        # We vangen het 'True' of 'False' antwoord van de e-mail functie op
        email_is_gelukt = stuur_email(gegenereerde_bestanden, aantal_geldige_rijen, dag_samenvattingen)
        
        # --- NIEUW: BESTANDEN OPRUIMEN ---
        if email_is_gelukt:
            print("\n🧹 E-mail is verzonden. We ruimen de tijdelijke CSV-bestanden op...")
            for bestand in gegenereerde_bestanden:
                try:
                    os.remove(bestand)
                    print(f"   🗑️ Verwijderd: {bestand}")
                except Exception as e:
                    print(f"   ⚠️ Kon {bestand} niet verwijderen: {e}")
            print("✨ Opruimen voltooid! De map is weer netjes.")
        else:
            print("\n⚠️ E-mail is NIET verzonden. Ik bewaar de CSV-bestanden zodat je ze lokaal hebt!")

        browser.close()

if __name__ == "__main__":
    scrape_greenchoice()