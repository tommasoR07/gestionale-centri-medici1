from __future__ import annotations

import os
import re
import unicodedata
from datetime import date, timedelta, time

from app import create_app
from models import db, Hospital, Specialty, Slot, User

HOSPITALS = [
    ("AOU Città della Salute e della Scienza (Torino)", "Torino e Area Metropolitana",
     "Comprende l'ospedale Molinette (principale hub), il Regina Margherita (infantile), il San Lazzaro e il SGAS."),
    ("Ospedale Mauriziano (Torino)", "Torino e Area Metropolitana",
     "Eccellenza riconosciuta a livello nazionale."),
    ("AOU San Luigi Gonzaga (Orbassano)", "Torino e Area Metropolitana",
     "Polo universitario rilevante."),
    ("Ospedale Humanitas Cellini (Torino)", "Torino e Area Metropolitana",
     "Struttura privata di alto livello."),
    ("Clinica Fornaca (Torino)", "Torino e Area Metropolitana",
     "Struttura privata di prestigio."),
    ("Azienda Ospedaliera Santi Antonio, Biagio e Cesare Arrigo", "Alessandria",
     "Hub fondamentale per la regione, noto per l'infantile."),
    ("Azienda Ospedaliera Santa Croce e Carle", "Cuneo",
     "Struttura di rilievo regionale."),
    ("AOU Maggiore della Carità", "Novara",
     "Principale punto di riferimento per il quadrante nord-est."),
    ("Ospedale degli Infermi (ASL Biella)", "Biella",
     "Inserito nella classifica dei migliori ospedali italiani."),
    ("ASL Verbano Cusio Ossola", "Verbania/Domodossola",
     "Gestisce i presidi del territorio."),
]

SPECIALTIES = {
    "Area Medica": [
        "Medicina Interna", "Cardiologia (UTIC)", "Neurologia", "Pneumologia", "Gastroenterologia",
        "Nefrologia", "Oncologia", "Ematologia", "Endocrinologia", "Geriatria",
        "Malattie Infettive", "Pediatria"
    ],
    "Area Chirurgica": [
        "Chirurgia Generale", "Ortopedia e Traumatologia", "Ostetricia e Ginecologia",
        "Oculistica", "Otorinolaringoiatria", "Urologia", "Chirurgia Vascolare",
        "Chirurgia Plastica", "Neurochirurgia"
    ],
    "Servizi Diagnostici e di Supporto": [
        "Radiologia/Diagnostica per Immagini", "Laboratorio Analisi", "Anatomia Patologica",
        "Farmacia Ospedaliera", "Medicina Trasfusionale"
    ],
    "Riabilitazione e Lungodegenza": [
        "Recupero e Rieducazione Funzionale", "Cure Palliative"
    ],
}

DEFAULT_PRICES_EUR = {
    "Area Medica": 55.00,
    "Area Chirurgica": 95.00,
    "Servizi Diagnostici e di Supporto": 45.00,
    "Riabilitazione e Lungodegenza": 60.00,
}


def _to_ascii(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def admin_username(hospital_name: str) -> str:
    base = _to_ascii(hospital_name)
    base = re.sub(r"[^A-Za-z0-9]+", " ", base).strip()
    parts = [p for p in base.split() if p]
    camel = "".join(p[:1].upper() + p[1:] for p in parts)
    return f"admin{camel}"


def reset_db_if_exists(app) -> None:
    db_uri: str = app.config["SQLALCHEMY_DATABASE_URI"]
    if db_uri.startswith("sqlite:///"):
        path = db_uri.replace("sqlite:///", "")
        if os.path.exists(path):
            os.remove(path)


def seed() -> None:
    # Hospitals
    if Hospital.query.count() == 0:
        for name, area, desc in HOSPITALS:
            h = Hospital()
            h.name = name
            h.area = area
            h.description = desc
            db.session.add(h)
        db.session.commit()

    # Specialties
    if Specialty.query.count() == 0:
        for area, items in SPECIALTIES.items():
            for sname in items:
                s = Specialty()
                s.area = area
                s.name = sname
                db.session.add(s)
        db.session.commit()

    hospitals = Hospital.query.all()
    specs = Specialty.query.all()

    # Admin users (uno per ospedale)
    for h in hospitals:
        uname = admin_username(h.name)
        existing = User.query.filter_by(email=uname).first()
        if not existing:
            u = User()
            u.email = uname
            u.role = "admin"
            u.admin_hospital_id = h.id
            u.set_password("123456")
            db.session.add(u)
    db.session.commit()

    # Slots: prossimi 7 giorni, 09:00-17:00 (ogni ora)
    start = date.today()
    days = 7
    hours = list(range(9, 18))  # 9..17

    for d in range(days):
        day_val = start + timedelta(days=d)
        for h in hospitals:
            for s in specs:
                eur = DEFAULT_PRICES_EUR.get(s.area, 50.00)
                price_cents = int(round(eur * 100))
                for hr in hours:
                    slot = Slot()
                    slot.hospital_id = h.id
                    slot.specialty_id = s.id
                    slot.day = day_val
                    slot.at = time(hour=hr, minute=0)
                    slot.status = "available"
                    slot.price_cents = price_cents
                    db.session.add(slot)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def main() -> None:
    app = create_app()
    with app.app_context():
        reset_db_if_exists(app)
        db.create_all()
        seed()
        print("DB inizializzato e seed completato.")
        print("Account admin creati (password: 123456). Esempi:")
        hs = Hospital.query.limit(3).all()
        for h in hs:
            print(" -", admin_username(h.name))


if __name__ == "__main__":
    main()