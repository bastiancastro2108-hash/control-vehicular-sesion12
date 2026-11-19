"""Inicio de sesión y manejo de la sesión con st.session_state.

Las claves NO están en el código: se leen de .streamlit/secrets.toml, sección [usuarios].
- admin / guardia: usuario fijo + su clave.
- conductor: entra con su RUT (debe existir en la tabla conductores y estar Activo)
  + la clave de conductores.
"""
import hmac
import time

import streamlit as st

from core import repositorio as repo
from core.utils import formatear_rut, parece_rut

MAX_INTENTOS = 5
BLOQUEO_SEG = 60
NOMBRES = {"admin": "Puesto de Mando", "guardia": "Guardia de Garita"}


def usuario_actual() -> dict | None:
    return st.session_state.get("usuario")


def _clave_correcta(clave: str, rol: str) -> bool:
    try:
        esperada = st.secrets["usuarios"][rol]
    except Exception:
        return False
    return hmac.compare_digest(clave.encode(), str(esperada).encode())


def iniciar_sesion(usuario: str, clave: str) -> tuple[dict | None, str]:
    usuario = usuario.strip()
    if usuario.lower() in NOMBRES:
        rol = usuario.lower()
        if _clave_correcta(clave, rol):
            return {"usuario": rol, "rol": rol, "rut_conductor": None, "nombre": NOMBRES[rol]}, ""
        return None, "Usuario o clave incorrectos."

    if parece_rut(usuario):
        conductor = repo.conductor_por_rut(formatear_rut(usuario))
        if conductor and _clave_correcta(clave, "conductor"):
            if conductor["estado"] != "Activo":
                return None, f"Conductor en estado «{conductor['estado']}»: acceso no habilitado."
            return {"usuario": conductor["rut"], "rol": "conductor", "rut_conductor": conductor["rut"],
                    "nombre": f"{conductor['grado_o_cargo']} {conductor['nombre_completo']}"}, ""
    return None, "Usuario o clave incorrectos."


def cerrar_sesion() -> None:
    st.session_state.clear()
    st.cache_data.clear()
    st.rerun()


def pantalla_login() -> None:
    st.markdown(
        "<h1 style='text-align:center'>🚙 Control Vehicular</h1>"
        "<p style='text-align:center;opacity:.7'>Control de acceso y estado operativo de flota</p>",
        unsafe_allow_html=True,
    )
    if time.time() < st.session_state.get("bloqueado_hasta", 0):
        st.error(f"Demasiados intentos fallidos. Espere {int(st.session_state.bloqueado_hasta - time.time())} s.")
        return

    with st.form("login"):
        usuario = st.text_input("Usuario o RUT", placeholder="admin · guardia · 18.234.567-K")
        clave = st.text_input("Clave", type="password")
        entrar = st.form_submit_button("Ingresar", type="primary", width="stretch")

    if entrar:
        perfil, mensaje = iniciar_sesion(usuario, clave) if usuario and clave else (None, "Complete ambos campos.")
        if perfil:
            st.session_state.usuario = perfil
            st.session_state.intentos = 0
            st.rerun()
        st.session_state.intentos = st.session_state.get("intentos", 0) + 1
        if st.session_state.intentos >= MAX_INTENTOS:
            st.session_state.bloqueado_hasta = time.time() + BLOQUEO_SEG
            st.session_state.intentos = 0
        st.error(mensaje)
