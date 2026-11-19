"""Conexión única a Supabase.

Las credenciales se leen SIEMPRE desde .streamlit/secrets.toml (st.secrets),
nunca se escriben en el código. Ese archivo está en .gitignore.
"""
import streamlit as st
from supabase import Client, create_client


@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    """Crea el cliente una sola vez y lo reutiliza entre recargas de la app."""
    try:
        cfg = st.secrets["supabase"]
        url, key = cfg["url"], cfg["key"]
    except Exception:
        st.error(
            "🔐 No se encontraron las credenciales de Supabase.\n\n"
            "Revise el archivo **.streamlit/secrets.toml** con la sección "
            "`[supabase]`, `url` y `key`."
        )
        st.stop()
    return create_client(url, key)
