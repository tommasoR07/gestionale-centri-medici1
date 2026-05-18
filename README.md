# Gestionale Centri Medici1 — Web (Python/Flask)

Questo progetto contiene **solo la parte web** (da aprire con Visual Studio Code) con:

## Funzioni Utente
- Registrazione utente
- Login / Logout
- Pagina Prenotazioni con elenco ospedali e specialità
- Prenotazione di una visita a una certa **data e ora**
- **Prezzo** per ogni visita (visibile prima della prenotazione)
- Gestione concorrenza: se due utenti provano a prenotare lo **stesso slot** nello stesso momento, solo uno ci riesce (update atomico su DB).

## Funzioni Admin (Ospedale)
- Account dedicato per ogni ospedale del tipo **`adminNomeOspedale`**
- Password uguale per tutti: **`123456`**
- Area ospedale: visualizza slot del proprio ospedale
- Può:
  - **eliminare** uno slot/visita
  - segnare slot come **Occupato** o **Non disponibile**
  - **modificare il prezzo** dello slot

> Gli account admin vengono creati automaticamente da `create_db.py`.

---

## Requisiti
- Python 3.10+ consigliato

## Avvio rapido (Windows/macOS/Linux)

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Crea DB + seed (rigenera il DB per schema aggiornato)
python create_db.py

python app.py
```

Nota: il database SQLite viene creato in `instance/prenotazioni.db` (così non ci sono ambiguità di percorso).

Poi apri:
- http://127.0.0.1:5000

---

## Note sugli slot
Per semplicità, all'avvio del DB vengono generati slot orari **09:00–17:00 (ogni ora)** per i **prossimi 7 giorni** per ogni coppia Ospedale/Specialità.

Puoi cambiare la finestra di generazione in `create_db.py`.

## Struttura
- `app.py` (routes)
- `models.py` (DB)
- `forms.py` (WTForms)
- `templates/` (HTML)
- `static/` (CSS)
- `create_db.py` (inizializzazione DB + seed + admin)


---

## Avvio online / produzione

Il progetto è predisposto per essere pubblicato online su servizi come Render, Railway o un VPS Linux.

File aggiunti per il deploy:
- `Procfile` con comando di avvio produzione
- `render.yaml` per deploy su Render
- `runtime.txt` con versione Python
- `.gitignore` per non caricare `.venv`, database locale e file sensibili
- `gunicorn` in `requirements.txt`

### Variabili d'ambiente consigliate

Imposta almeno:

```bash
SECRET_KEY=una_chiave_lunga_e_casuale
PREFERRED_URL_SCHEME=https
```

### Comando produzione

```bash
gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
```

### Comando locale aggiornato

```bash
python app.py
```

In locale il sito parte su:

```text
http://127.0.0.1:5000
```

Per renderlo raggiungibile nella stessa rete locale:

```text
http://IP_DEL_PC:5000
```

Nota sicurezza: prima di pubblicarlo davvero conviene cambiare le password admin predefinite (`123456`).
