from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
    password2 = PasswordField("Conferma password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Crea account")


class LoginForm(FlaskForm):
    # Supporta sia email reale che username admin (es. adminNomeOspedale)
    email = StringField("Email o Username", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class SearchSlotsForm(FlaskForm):
    hospital_id = SelectField("Ospedale", coerce=int, validators=[DataRequired()])
    specialty_id = SelectField("Specialità", coerce=int, validators=[DataRequired()])
    day = DateField("Data", validators=[DataRequired()], format="%Y-%m-%d")
    submit = SubmitField("Cerca slot")
