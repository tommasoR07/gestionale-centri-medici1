from __future__ import annotations

import csv
import os
from collections import defaultdict
from datetime import date, datetime

from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy import text

from models import db, User, Hospital, Specialty, Slot
from forms import RegisterForm, LoginForm, SearchSlotsForm


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["PREFERRED_URL_SCHEME"] = os.environ.get("PREFERRED_URL_SCHEME", "https")

    # DB sempre in instance/ per evitare path diversi (Windows)
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "prenotazioni.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"  # type: ignore[attr-defined]
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    def is_admin() -> bool:
        return bool(current_user.is_authenticated and getattr(current_user, "role", "user") == "admin")

    def admin_only():
        if not is_admin():
            abort(403)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("bookings"))

        form = RegisterForm()
        if form.validate_on_submit():
            email = (form.email.data or "").lower().strip()
            existing = User.query.filter_by(email=email).first()
            if existing:
                flash("Email già registrata. Prova a fare login.", "warning")
                return redirect(url_for("login"))

            u = User()
            u.email = email
            u.set_password(str(form.password.data or ""))
            db.session.add(u)
            db.session.commit()

            flash("Registrazione completata! Ora puoi fare login.", "success")
            return redirect(url_for("login"))

        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            if getattr(current_user, "role", "user") == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("bookings"))

        form = LoginForm()
        if form.validate_on_submit():
            ident = (form.email.data or "").strip()
            ident_norm = ident.lower()

            u = User.query.filter_by(email=ident_norm).first() or User.query.filter_by(email=ident).first()

            pwd = str(form.password.data or "")
            if (not u) or (not u.check_password(pwd)):
                flash("Credenziali non valide.", "danger")
                return render_template("login.html", form=form)

            login_user(u)
            flash("Login effettuato.", "success")

            if getattr(u, "role", "user") == "admin":
                return redirect(url_for("admin_dashboard"))

            next_url = request.args.get("next")
            return redirect(next_url or url_for("bookings"))

        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logout effettuato.", "info")
        return redirect(url_for("index"))

    def _fill_choices(form: SearchSlotsForm) -> None:
        hospitals = Hospital.query.order_by(Hospital.area.asc(), Hospital.name.asc()).all()
        specialties = Specialty.query.order_by(Specialty.area.asc(), Specialty.name.asc()).all()

        form.hospital_id.choices = [(h.id, f"{h.name} — {h.area}") for h in hospitals]
        form.specialty_id.choices = [(s.id, f"{s.area}: {s.name}") for s in specialties]

    @app.route("/prenotazioni", methods=["GET", "POST"])
    @login_required
    def bookings():
        if is_admin():
            return redirect(url_for("admin_dashboard"))

        form = SearchSlotsForm()
        _fill_choices(form)

        slots = []
        selected = None

        if request.method == "GET":
            form.day.data = date.today()

        if form.validate_on_submit():
            selected = {
                "hospital_id": form.hospital_id.data,
                "specialty_id": form.specialty_id.data,
                "day": form.day.data,
            }
            slots = (
                Slot.query.filter_by(
                    hospital_id=form.hospital_id.data,
                    specialty_id=form.specialty_id.data,
                    day=form.day.data,
                    status="available",
                )
                .order_by(Slot.at.asc())
                .all()
            )

        return render_template("bookings.html", form=form, slots=slots, selected=selected)

    @app.route("/prenota/<int:slot_id>", methods=["POST"])
    @login_required
    def book_slot(slot_id: int):
        if is_admin():
            abort(403)

        try:
            result = db.session.execute(
                text("""
                    UPDATE slots
                    SET status='booked', booked_by=:uid
                    WHERE id=:sid AND status='available'
                """),
                {"uid": current_user.id, "sid": slot_id},
            )

            if (getattr(result, "rowcount", 0) or 0) != 1:
                db.session.rollback()
                flash("Slot non più disponibile (probabilmente prenotato da un altro utente).", "warning")
                return redirect(url_for("bookings"))

            db.session.commit()
            flash("Prenotazione confermata!", "success")
            return redirect(url_for("my_bookings"))

        except Exception as e:
            db.session.rollback()
            flash(f"Errore durante la prenotazione: {e}", "danger")
            return redirect(url_for("bookings"))

    @app.route("/le-mie-prenotazioni")
    @login_required
    def my_bookings():
        if is_admin():
            return redirect(url_for("admin_dashboard"))

        booked = (
            Slot.query.filter_by(booked_by=current_user.id, status="booked")
            .order_by(Slot.day.desc(), Slot.at.desc())
            .all()
        )
        return render_template("my_bookings.html", booked=booked)

    @app.route("/cancella/<int:slot_id>", methods=["POST"])
    @login_required
    def cancel(slot_id: int):
        if is_admin():
            abort(403)

        try:
            slot = Slot.query.filter_by(
                id=slot_id,
                booked_by=current_user.id,
                status="booked",
            ).first()

            if not slot:
                flash("Prenotazione non trovata.", "warning")
                return redirect(url_for("my_bookings"))

            slot.status = "available"
            slot.booked_by = None
            db.session.commit()

            flash("Prenotazione cancellata. Lo slot è di nuovo disponibile.", "info")
            return redirect(url_for("my_bookings"))

        except Exception as e:
            db.session.rollback()
            flash(f"Errore durante la cancellazione: {e}", "danger")
            return redirect(url_for("my_bookings"))


    def _blood_donation_stats(selected_region: str = ""):
        """Legge il CSV locale e restituisce dati aggregati in sola lettura per i grafici."""
        csv_path = os.path.join(app.root_path, "data", "donazioni_centri_italia.csv")
        regions = set()
        totals_by_region = defaultdict(int)
        totals_by_month = defaultdict(int)
        totals_by_center = defaultdict(int)
        total_donations = 0
        total_rows = 0

        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    region = (row.get("regione") or "").strip()
                    center = (row.get("nome_centro") or "").strip()
                    month = (row.get("mese") or "").strip()
                    try:
                        donations = int(row.get("donazioni") or 0)
                    except (TypeError, ValueError):
                        donations = 0

                    if not region or not month:
                        continue

                    regions.add(region)
                    totals_by_region[region] += donations

                    if selected_region and region != selected_region:
                        continue

                    totals_by_month[month] += donations
                    if center:
                        totals_by_center[center] += donations
                    total_donations += donations
                    total_rows += 1
        except FileNotFoundError:
            flash("File dati donazioni non trovato.", "danger")

        top_centers = sorted(totals_by_center.items(), key=lambda item: item[1], reverse=True)[:10]

        return {
            "regions": sorted(regions),
            "selected_region": selected_region,
            "total_donations": total_donations,
            "total_rows": total_rows,
            "months_labels": sorted(totals_by_month.keys()),
            "months_values": [totals_by_month[m] for m in sorted(totals_by_month.keys())],
            "region_labels": sorted(totals_by_region.keys()),
            "region_values": [totals_by_region[r] for r in sorted(totals_by_region.keys())],
            "center_labels": [name for name, _ in top_centers],
            "center_values": [value for _, value in top_centers],
        }

    @app.route("/donazioni-sangue")
    @login_required
    def blood_donations():
        selected_region = (request.args.get("regione") or "").strip()
        stats = _blood_donation_stats(selected_region)
        if selected_region and selected_region not in stats["regions"]:
            selected_region = ""
            stats = _blood_donation_stats("")
            flash("Regione non valida: filtro rimosso.", "warning")
        return render_template("blood_donations.html", stats=stats)

    # -------------------------
    # AREA ADMIN (per ospedale)
    # -------------------------

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        admin_only()

        hosp = current_user.admin_hospital
        if not hosp:
            flash("Admin non associato ad alcun ospedale.", "danger")
            return redirect(url_for("logout"))

        day_str = request.args.get("day")
        try:
            sel_day = datetime.strptime(day_str, "%Y-%m-%d").date() if day_str else date.today()
        except Exception:
            sel_day = date.today()

        slots = (
            Slot.query.filter_by(hospital_id=hosp.id, day=sel_day)
            .order_by(Slot.at.asc())
            .all()
        )

        return render_template("admin_dashboard.html", hospital=hosp, sel_day=sel_day, slots=slots)

    @app.route("/admin/slot/<int:slot_id>/delete", methods=["POST"])
    @login_required
    def admin_delete_slot(slot_id: int):
        admin_only()

        hosp = current_user.admin_hospital
        slot = Slot.query.filter_by(id=slot_id, hospital_id=hosp.id).first()
        if not slot:
            flash("Slot non trovato.", "warning")
            return redirect(url_for("admin_dashboard"))

        day_str = slot.day.strftime("%Y-%m-%d")
        try:
            db.session.delete(slot)
            db.session.commit()
            flash("Visita/slot eliminato.", "info")
        except Exception as e:
            db.session.rollback()
            flash(f"Errore eliminazione: {e}", "danger")

        return redirect(url_for("admin_dashboard", day=day_str))

    @app.route("/admin/slot/<int:slot_id>/status", methods=["POST"])
    @login_required
    def admin_set_status(slot_id: int):
        admin_only()

        hosp = current_user.admin_hospital
        slot = Slot.query.filter_by(id=slot_id, hospital_id=hosp.id).first()
        if not slot:
            flash("Slot non trovato.", "warning")
            return redirect(url_for("admin_dashboard"))

        new_status = (request.form.get("status") or "").strip().lower()
        if new_status not in {"available", "booked", "blocked"}:
            flash("Stato non valido.", "warning")
            return redirect(url_for("admin_dashboard", day=slot.day.strftime("%Y-%m-%d")))

        try:
            slot.status = new_status
            if new_status in {"available", "blocked"}:
                slot.booked_by = None
            db.session.commit()
            flash("Stato aggiornato.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Errore aggiornamento stato: {e}", "danger")

        return redirect(url_for("admin_dashboard", day=slot.day.strftime("%Y-%m-%d")))

    @app.route("/admin/slot/<int:slot_id>/price", methods=["POST"])
    @login_required
    def admin_set_price(slot_id: int):
        admin_only()

        hosp = current_user.admin_hospital
        slot = Slot.query.filter_by(id=slot_id, hospital_id=hosp.id).first()
        if not slot:
            flash("Slot non trovato.", "warning")
            return redirect(url_for("admin_dashboard"))

        price_str = (request.form.get("price") or "").replace(",", ".").strip()
        try:
            eur = float(price_str)
            if eur < 0 or eur > 9999:
                raise ValueError()
            slot.price_cents = int(round(eur * 100))
            db.session.commit()
            flash("Prezzo aggiornato.", "success")
        except Exception:
            db.session.rollback()
            flash("Prezzo non valido. Usa un numero (es. 55.00).", "warning")

        return redirect(url_for("admin_dashboard", day=slot.day.strftime("%Y-%m-%d")))

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, message="Accesso negato."), 403

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
