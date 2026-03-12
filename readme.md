⚡ Greenchoice Dag-Scraper
Een Python-toolset om eenvoudig je energieverbruik (stroom en gas) van Greenchoice op te halen. De data kan worden geëxporteerd naar een CSV-bestand en direct via e-mail worden verzonden.

Bevat zowel een geautomatiseerd script als een gebruiksvriendelijke grafische interface (GUI).

🚀 Features
Haalt uurlijkse verbruiksdata op (Stroom in, Stroom uit, Gas).

Manual Scraper: Een Tkinter GUI om eenvoudig specifieke datums te kiezen, data in te zien, op te slaan als CSV en te mailen.

Auto Scraper: Een script ontworpen om via een taakplanner (bijv. cronjob of Windows Task Scheduler) automatisch de data van gisteren op te halen en te mailen. Houdt ook gemiste dagen bij via gemiste_dagen.json.

Configuratie via .env zodat wachtwoorden veilig lokaal blijven.

📁 Bestanden
manual-scraper.py - De applicatie met grafische interface.

scraper.py - Het script voor geautomatiseerd scrapen op de achtergrond.

start_scraper.bat - Handig batch-bestand om het automatische script op Windows te starten.

.env.example - Voorbeeld van het configuratiebestand.

index.html - Optionele webweergave / dashboard.

🛠️ Installatie
1. Clone de repository:

git clone [https://github.com/JOUW_USERNAME/greenchoice-scraper.git](https://github.com/JOUW_USERNAME/greenchoice-scraper.git)
cd greenchoice-scraper
2. Installeer de benodigde Python libraries:

pip install playwright tkcalendar python-dotenv
3. Installeer de Playwright browsers:

playwright install chromium
4. Stel de configuratie in:
Kopieer .env.example naar een nieuw bestand genaamd .env en vul je gegevens in:

# Greenchoice Inlog
GC_EMAIL="jouw@email.nl"
GC_WACHTWOORD="JouwWachtwoord"
GC_CUSTOMER_ID="12345678"
GC_AGREEMENT_ID="87654321"

# E-mail Instellingen (optioneel)
GMAIL_AFZENDER="jouw-bot@gmail.com"
GMAIL_WACHTWOORD="jouw-app-wachtwoord"
MAIL_ONTVANGER="ontvanger@email.nl"
(Let op: Gebruik voor Gmail een App-wachtwoord als je 2FA (Tweestapsverificatie) hebt ingeschakeld).

💻 Gebruik
Handmatige GUI gebruiken
Start de interface om zelf een dag te selecteren, de data te bekijken, lokaal op te slaan of te mailen:

python manual-scraper.py
Automatische scraper gebruiken
Laat het script zonder interface draaien om de data van de vorige dag op te halen:

python scraper.py
Tip: Koppel start_scraper.bat aan de Windows Taakplanner (Task Scheduler) om dit elke ochtend automatisch op de achtergrond te laten draaien.

⚠️ Disclaimer
Dit project is niet geaffilieerd met Greenchoice. Webscraping kan tegen de algemene voorwaarden van de website ingaan. Gebruik is op eigen risico.