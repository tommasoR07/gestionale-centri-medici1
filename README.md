# Gestionale Centri Medici — Documentazione Tecnica

> Applicazione web per la prenotazione di visite mediche in centri ospedalieri, sviluppata in Python con il framework Flask.

---

## Indice

1. [Panoramica del progetto](#1-panoramica-del-progetto)
2. [Stack tecnologico](#2-stack-tecnologico)
3. [Struttura del progetto](#3-struttura-del-progetto)
4. [Modello dati (Database)](#4-modello-dati-database)
5. [Funzionalità utente](#5-funzionalità-utente)
6. [Funzionalità admin (ospedale)](#6-funzionalità-admin-ospedale)
7. [Route e logica applicativa](#7-route-e-logica-applicativa)
8. [Gestione della concorrenza](#8-gestione-della-concorrenza)
9. [Sezione Donazioni Sangue](#9-sezione-donazioni-sangue)
10. [Avvio in locale](#10-avvio-in-locale)
11. [Deploy in produzione](#11-deploy-in-produzione)
12. [Variabili d'ambiente](#12-variabili-dambiente)
13. [Note di sicurezza](#13-note-di-sicurezza)

---

## 1. Panoramica del progetto

Il progetto è un **gestionale web** pensato per centri medici e ospedali. Permette:

- agli **utenti** di registrarsi, cercare slot disponibili per una visita medica e prenotarli;
- agli **amministratori** (uno per ospedale) di gestire gli slot del proprio ospedale: modificare prezzi, cambiare stati, eliminare prenotazioni.

Il progetto è interamente basato su Python/Flask e utilizza SQLite come database in sviluppo, con supporto per il deploy su piattaforme cloud (Render, Railway, VPS Linux).

---

## 2. Stack tecnologico

| Componente | Tecnologia |
|---|---|
| Linguaggio | Python 3.10+ |
| Framework web | Flask |
| ORM / Database | SQLAlchemy + SQLite |
| Autenticazione | Flask-Login |
| Form e validazione | WTForms |
| Template engine | Jinja2 (HTML) |
| Stile frontend | CSS personalizzato |
| Server produzione | Gunicorn |
| Deploy | Render / Railway / VPS |

**Composizione del codice:**
- Python: ~48%
- HTML (Jinja2 templates): ~50%
- CSS: ~1.5%

---

## 3. Struttura del progetto

```
gestionale-centri-medici1/
│
├── app.py              # Applicazione Flask: factory, routes, logica
├── models.py           # Modelli SQLAlchemy (tabelle del database)
├── forms.py            # Form WTForms (registrazione, login, ricerca)
├── create_db.py        # Script di inizializzazione DB, seed dati e creazione admin
│
├── templates/          # Template HTML (Jinja2)
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── bookings.html
│   ├── my_bookings.html
│   ├── admin_dashboard.html
│   ├── blood_donations.html
│   └── error.html
│
├── static/
│   └── css/            # Fogli di stile CSS
│
├── data/
│   └── donazioni_centri_italia.csv   # Dati statistici donazioni sangue
│
├── instance/
│   └── prenotazioni.db               # Database SQLite (generato da create_db.py)
│
├── requirements.txt    # Dipendenze Python
├── Procfile            # Comando di avvio per Render/Heroku
├── render.yaml         # Configurazione deploy Render
├── runtime.txt         # Versione Python specificata
└── .gitignore
```

---

## 4. Modello dati (Database)

Il database è definito in `models.py` tramite SQLAlchemy. Contiene quattro tabelle principali.

### Tabella `users`

Rappresenta sia gli utenti normali che gli amministratori degli ospedali.

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Integer (PK) | Identificatore univoco |
| `email` | String(255) | Email per utenti normali; username tipo `adminNomeOspedale` per admin |
| `password_hash` | String(255) | Password cifrata con Werkzeug |
| `role` | String(20) | `"user"` oppure `"admin"` |
| `admin_hospital_id` | Integer (FK) | Collega l'admin al suo ospedale (NULL per utenti normali) |

### Tabella `hospitals`

Rappresenta i centri medici/ospedali presenti nel sistema.

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Integer (PK) | Identificatore univoco |
| `name` | String(255) | Nome dell'ospedale (univoco) |
| `area` | String(255) | Area geografica o reparto |
| `description` | Text | Descrizione dell'ospedale |

### Tabella `specialties`

Rappresenta le specialità mediche offerte (es. Cardiologia, Ortopedia, …).

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Integer (PK) | Identificatore univoco |
| `area` | String(255) | Area medica di riferimento (es. "Area Medica") |
| `name` | String(255) | Nome della specialità |

> Vincolo: la coppia `(area, name)` è univoca.

### Tabella `slots`

Rappresenta i singoli appuntamenti/fasce orarie prenotabili.

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Integer (PK) | Identificatore univoco |
| `hospital_id` | Integer (FK) | Ospedale di riferimento |
| `specialty_id` | Integer (FK) | Specialità medica |
| `day` | Date | Giorno dello slot |
| `at` | Time | Orario dello slot |
| `status` | String(20) | Stato: `available`, `booked`, `blocked` |
| `booked_by` | Integer (FK) | ID utente che ha prenotato (NULL se libero) |
| `price_cents` | Integer | Prezzo in centesimi (default: 5000 = €50,00) |

**Proprietà calcolata:**
```python
@property
def price_eur(self) -> str:
    return f"{self.price_cents / 100:.2f}"
```
Converte i centesimi in formato euro leggibile (es. `"50.00"`).

**Indici e vincoli:**
- Chiave univoca su `(hospital_id, specialty_id, day, at)` → impossibile creare slot duplicati.
- Indice composito `ix_slot_lookup` per ricerche veloci.

---

## 5. Funzionalità utente

Gli utenti normali accedono tramite email e password e possono:

### Registrazione
- Inserimento di email e password.
- Controllo duplicati: se l'email è già registrata viene mostrato un avviso.
- La password viene salvata in forma cifrata (hash Werkzeug).

### Login / Logout
- Login con email e password.
- Dopo il login, l'utente viene reindirizzato alla pagina prenotazioni (o alla dashboard admin se è un admin).
- Logout disponibile in qualsiasi momento.

### Ricerca slot
Dalla pagina `/prenotazioni` l'utente può:
1. Selezionare un **ospedale** (con area geografica).
2. Selezionare una **specialità medica** (con area).
3. Scegliere una **data**.

Il sistema mostra tutti gli slot disponibili (`status = "available"`) per quella combinazione, ordinati per orario, con il **prezzo** di ogni visita visibile prima di confermare.

### Prenotazione
- Un click su "Prenota" invia una richiesta al server.
- La prenotazione viene eseguita con un **UPDATE atomico** (vedi sezione concorrenza).
- Se la prenotazione va a buon fine, l'utente viene reindirizzato a "Le mie prenotazioni".

### Le mie prenotazioni
Alla pagina `/le-mie-prenotazioni`, l'utente vede tutte le sue prenotazioni attive, ordinate per data decrescente.

### Cancellazione
L'utente può cancellare una propria prenotazione: lo slot torna automaticamente allo stato `available` e si libera per altri utenti.

---

## 6. Funzionalità admin (ospedale)

Ogni ospedale ha un account amministratore dedicato.

**Credenziali di default:**
- Username: `adminNomeOspedale` (es. `adminOspedaleCivile`)
- Password: `123456` (da cambiare prima del deploy reale)

> Gli account admin vengono creati automaticamente da `create_db.py` al momento dell'inizializzazione del database.

### Dashboard admin (`/admin`)
L'admin vede tutti gli slot del **proprio ospedale** per un giorno selezionabile. Per ogni slot può:

- **Eliminare** lo slot (visita rimossa definitivamente).
- **Cambiare stato** tra: `available`, `booked`, `blocked`.
  - Se portato a `available` o `blocked`, il campo `booked_by` viene azzerato.
- **Modificare il prezzo** (in euro, con conversione automatica in centesimi; range: €0 – €9.999).

L'admin non può accedere alla pagina prenotazioni utente (reindirizzato alla dashboard).

---

## 7. Route e logica applicativa

Tutte le route sono definite in `app.py` tramite la factory function `create_app()`.

| Route | Metodo | Accesso | Descrizione |
|---|---|---|---|
| `/` | GET | Tutti | Homepage |
| `/register` | GET, POST | Non autenticati | Registrazione nuovo utente |
| `/login` | GET, POST | Non autenticati | Login |
| `/logout` | GET | Autenticati | Logout |
| `/prenotazioni` | GET, POST | Utenti | Ricerca e visualizzazione slot |
| `/prenota/<slot_id>` | POST | Utenti | Conferma prenotazione slot |
| `/le-mie-prenotazioni` | GET | Utenti | Lista prenotazioni personali |
| `/cancella/<slot_id>` | POST | Utenti | Cancellazione prenotazione |
| `/donazioni-sangue` | GET | Autenticati | Statistiche donazioni sangue |
| `/admin` | GET | Admin | Dashboard ospedale |
| `/admin/slot/<id>/delete` | POST | Admin | Elimina slot |
| `/admin/slot/<id>/status` | POST | Admin | Modifica stato slot |
| `/admin/slot/<id>/price` | POST | Admin | Modifica prezzo slot |

**Separazione dei ruoli:**
- `is_admin()` verifica se l'utente autenticato ha `role == "admin"`.
- `admin_only()` termina la richiesta con errore 403 se l'utente non è admin.
- Gli utenti admin vengono reindirizzati fuori dalla sezione utente e viceversa.

---

## 8. Gestione della concorrenza

Un problema classico nelle applicazioni di prenotazione è la **race condition**: due utenti che tentano di prenotare lo stesso slot nello stesso istante.

Il sistema risolve questo con un **UPDATE atomico a livello di database**:

```python
result = db.session.execute(
    text("""
        UPDATE slots
        SET status='booked', booked_by=:uid
        WHERE id=:sid AND status='available'
    """),
    {"uid": current_user.id, "sid": slot_id},
)
if result.rowcount != 1:
    db.session.rollback()
    flash("Slot non più disponibile (prenotato da un altro utente).", "warning")
```

**Come funziona:**
- La clausola `WHERE status='available'` garantisce che solo uno dei due utenti concorrenti riesca ad aggiornare la riga (SQLite serializza le scritture).
- Se `rowcount` è 0, significa che un altro utente ha già prenotato: la transazione viene annullata e l'utente riceve un avviso.

---

## 9. Sezione Donazioni Sangue

La route `/donazioni-sangue` offre una **dashboard statistica** (in sola lettura) basata su un file CSV locale (`data/donazioni_centri_italia.csv`).

**Dati elaborati:**
- Totale donazioni per regione.
- Totale donazioni per mese.
- Top 10 centri per numero di donazioni.
- Filtro per regione tramite query string (`?regione=Lombardia`).

Le statistiche vengono calcolate a ogni richiesta leggendo e aggregando il CSV con `csv.DictReader` e `collections.defaultdict`.

---

## 10. Avvio in locale

**Requisiti:** Python 3.10 o superiore.

```bash
# 1. Crea e attiva l'ambiente virtuale
python -m venv .venv

# macOS / Linux:
source .venv/bin/activate

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 2. Installa le dipendenze
pip install -r requirements.txt

# 3. Inizializza il database (crea tabelle, seed dati, account admin)
python create_db.py

# 4. Avvia il server di sviluppo
python app.py
```

L'applicazione sarà raggiungibile su:
- **Stesso PC:** `http://127.0.0.1:5000`
- **Rete locale:** `http://<IP_DEL_PC>:5000`

> Il database SQLite viene salvato in `instance/prenotazioni.db`. La cartella `instance/` viene creata automaticamente da Flask.

### Slot generati automaticamente

Al momento dell'inizializzazione (`create_db.py`), vengono creati slot orari dalle **09:00 alle 17:00 (ogni ora)** per i **prossimi 7 giorni**, per ogni combinazione Ospedale/Specialità. La finestra di generazione è configurabile modificando `create_db.py`.

---

## 11. Deploy in produzione

Il progetto è predisposto per il deploy su **Render**, **Railway** o qualsiasi **VPS Linux**.

**File di deploy inclusi:**

| File | Scopo |
|---|---|
| `Procfile` | Comando di avvio per Render/Heroku |
| `render.yaml` | Configurazione automatica per Render |
| `runtime.txt` | Specifica la versione Python |
| `requirements.txt` | Include `gunicorn` per la produzione |
| `.gitignore` | Esclude `.venv`, database locale, file sensibili |

**Comando di avvio in produzione:**

```bash
gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
```

---

## 12. Variabili d'ambiente

| Variabile | Obbligatoria | Descrizione |
|---|---|---|
| `SECRET_KEY` | Consigliata | Chiave segreta Flask per sessioni e CSRF. In sviluppo usa `"dev-secret-change-me"`. |
| `PREFERRED_URL_SCHEME` | Consigliata | Impostare a `"https"` in produzione. |
| `PORT` | Solo produzione | Porta su cui avviare Gunicorn (fornita dalla piattaforma). |
| `FLASK_DEBUG` | Opzionale | Impostare a `"1"` per abilitare il debug mode in locale. |

Esempio configurazione produzione:
```
SECRET_KEY=una_chiave_lunga_e_casuale_generata
PREFERRED_URL_SCHEME=https
```

---

## 13. Note di sicurezza

- Le password sono salvate come hash sicuri tramite `werkzeug.security` (PBKDF2/SHA256).
- Le password admin di default (`123456`) **devono essere cambiate** prima di un deploy pubblico.
- Il pattern di aggiornamento atomico protegge da race condition sulle prenotazioni.
- In produzione è essenziale impostare una `SECRET_KEY` forte e casuale.
- Il file `instance/prenotazioni.db` e la cartella `.venv` sono esclusi dal repository tramite `.gitignore`.
- In sviluppo il server Flask non deve essere esposto pubblicamente (usare Gunicorn in produzione).

---

*Documentazione generata da codice sorgente — repository: [tommasoR07/gestionale-centri-medici1](https://github.com/tommasoR07/gestionale-centri-medici1)*