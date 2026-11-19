"""Punto de entrada de la aplicación.

Ejecutar desde la RAÍZ del proyecto (donde está la carpeta .streamlit):
    streamlit run app/main.py
"""
import streamlit as st

from core.auth import cerrar_sesion, pantalla_login, usuario_actual

usuario = usuario_actual()

# El Puesto de Mando usa pantalla ancha (PC); Guardia y Conductor, diseño centrado (móvil)
st.set_page_config(
    page_title="Control Vehicular",
    page_icon="🚙",
    layout="wide" if usuario and usuario["rol"] == "admin" else "centered",
)

if usuario is None:
    pantalla_login()
    st.stop()

# ---------------------------------------------------------------------------
# Enrutamiento condicional según el rol autenticado
# ---------------------------------------------------------------------------
from views import admin, conductor, guardia  # noqa: E402

VISTAS_POR_ROL = {
    "admin": {"🎖️ Puesto de Mando": admin, "🛂 Garita (Guardia)": guardia, "🧰 Conductor": conductor},
    "guardia": {"🛂 Garita (Guardia)": guardia},
    "conductor": {"🧰 Conductor": conductor},
}
NOMBRE_ROL = {"admin": "Administrador", "guardia": "Guardia", "conductor": "Conductor"}

vistas = VISTAS_POR_ROL.get(usuario["rol"], {})

with st.sidebar:
    st.markdown(f"**👤 {usuario['nombre']}**  \nPerfil: {NOMBRE_ROL.get(usuario['rol'], usuario['rol'])}")
    seleccion = st.radio("Módulo", list(vistas)) if len(vistas) > 1 else next(iter(vistas), None)
    st.divider()
    if st.button("Cerrar sesión", width="stretch"):
        cerrar_sesion()

if seleccion is None:
    st.error("Perfil sin módulos asignados.")
else:
    vistas[seleccion].render(usuario)
