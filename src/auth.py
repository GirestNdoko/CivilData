"""Accès protégé par mot de passe (à activer en hébergement).

Le mot de passe se définit dans la variable d'environnement APP_PASSWORD
ou dans les « Secrets » de Streamlit. S'il n'est pas défini (usage local),
l'application s'ouvre sans mot de passe.
"""

import hmac
import os


def get_secret(name):
    """Lit un secret : variable d'environnement d'abord, puis Streamlit."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def password_matches(typed, expected):
    """Comparaison à temps constant."""
    return hmac.compare_digest(typed.encode("utf-8"), expected.encode("utf-8"))


def require_password():
    """Bloque l'application tant que le bon mot de passe n'est pas saisi."""
    import streamlit as st

    expected = get_secret("APP_PASSWORD")
    if not expected:
        return  # usage local : pas de mot de passe

    if st.session_state.get("authenticated"):
        return

    st.title("🏗️ CivilData")
    typed = st.text_input("Mot de passe", type="password")
    if typed:
        if password_matches(typed, expected):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    st.stop()
