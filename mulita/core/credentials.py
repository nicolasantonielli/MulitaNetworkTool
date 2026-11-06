"""Contrasenas sugeridas para las cuentas temporales de los servidores."""
import secrets

# Sin l, o, I, O, 0 ni 1, que se confunden al leerlos.
PASSWORD_ALPHABET = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
PASSWORD_LENGTH = 8


def suggest_password() -> str:
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))
