from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # Per utenti normali: email reale.
    # Per admin ospedale: username tipo "adminNomeOspedale" (non necessariamente email).
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # "user" | "admin"
    role = db.Column(db.String(20), nullable=False, default="user", index=True)

    # Se role == "admin", questo lega l'admin al suo ospedale
    admin_hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=True, index=True)

    admin_hospital = db.relationship("Hospital", lazy="joined", foreign_keys=[admin_hospital_id])

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Hospital(db.Model):
    __tablename__ = "hospitals"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    area = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)


class Specialty(db.Model):
    __tablename__ = "specialties"

    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(255), nullable=False)  # es: Area Medica
    name = db.Column(db.String(255), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("area", "name", name="uq_specialty_area_name"),
    )


class Slot(db.Model):
    __tablename__ = "slots"

    id = db.Column(db.Integer, primary_key=True)

    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False, index=True)
    specialty_id = db.Column(db.Integer, db.ForeignKey("specialties.id"), nullable=False, index=True)

    day = db.Column(db.Date, nullable=False, index=True)
    at = db.Column(db.Time, nullable=False, index=True)

    # available | booked | blocked
    status = db.Column(db.String(20), nullable=False, default="available", index=True)

    # Se booked da utente, contiene l'id utente. Se booked manualmente dall'admin, può essere NULL.
    booked_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # Prezzo della visita (in centesimi)
    price_cents = db.Column(db.Integer, nullable=False, default=5000)

    hospital = db.relationship("Hospital", lazy="joined")
    specialty = db.relationship("Specialty", lazy="joined")
    user = db.relationship("User", lazy="joined", foreign_keys=[booked_by])

    __table_args__ = (
        db.UniqueConstraint("hospital_id", "specialty_id", "day", "at", name="uq_slot_unique"),
        db.Index("ix_slot_lookup", "hospital_id", "specialty_id", "day", "at"),
    )

    @property
    def price_eur(self) -> str:
        return f"{self.price_cents / 100:.2f}"
