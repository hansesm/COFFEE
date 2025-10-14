# app/fields.py
from django.db import models
from django.core import signing
from django.conf import settings

class EncryptedTextField(models.TextField):
    """
    Verschlüsseltes Textfeld mit Django-internem Fernet-Signing.
    """
    def get_prep_value(self, value):
        """Beim Speichern verschlüsseln."""
        if value is None or value == "":
            return value
        signer = signing.Signer(key=settings.SECRET_KEY)
        return signer.sign_object(value, serializer=signing.JSONSerializer)

    def from_db_value(self, value, expression, connection):
        """Beim Laden entschlüsseln."""
        if value is None or value == "":
            return value
        signer = signing.Signer(key=settings.SECRET_KEY)
        try:
            return signer.unsign_object(value, serializer=signing.JSONSerializer)
        except signing.BadSignature:
            # falls Daten korrupt oder Key gewechselt
            return None

    def to_python(self, value):
        """Für Form-Felder und Serialisierung"""
        return value
