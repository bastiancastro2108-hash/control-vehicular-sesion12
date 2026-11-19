"""Módulo GUARDIA (terreno / móvil): validación y registro de accesos en garita."""
import html

import streamlit as st

from core import repositorio as repo
from core.ocr import OCR_DISPONIBLE, leer_patente
from core.reglas import evaluar_acceso
from core.storage import registrar_acceso_garita
from core.utils import EMOJI_ESTADO, normalizar_patente

COLORES = {"Autorizado": "#2e7d32", "Alerta": "#f9a825", "Denegado": "#c62828"}
ICONOS = {"Autorizado": "✅ AUTORIZADO", "Alerta": "⚠️ ALERTA DE ESTADO", "Denegado": "⛔ DENEGADO"}

# Botones grandes y de alto contraste para pantallas táctiles
CSS_MOVIL = """
<style>
div.stButton > button, div.stFormSubmitButton > button {
    min-height: 3.4rem; font-size: 1.15rem; font-weight: 700;
}
input { font-size: 1.15rem !important; }
</style>
"""


def _tarjeta_resultado(resultado: str, motivos: list[str], vehiculo: dict | None) -> None:
    color = COLORES[resultado]
    detalle = "<br>".join(html.escape(m) for m in motivos)
    st.markdown(
        f"""<div style="background:{color};color:white;padding:1.2rem;border-radius:12px;
        text-align:center;margin:0.5rem 0">
        <div style="font-size:1.9rem;font-weight:800">{ICONOS[resultado]}</div>
        <div style="font-size:1.05rem;margin-top:.4rem">{detalle}</div></div>""",
        unsafe_allow_html=True,
    )
    if vehiculo:
        estado = vehiculo["estado_operativo"]
        st.markdown(
            f"**{html.escape(vehiculo['patente'])}** · {html.escape(vehiculo['marca_modelo'])} "
            f"({html.escape(vehiculo['tipo_vehiculo'])}) · {EMOJI_ESTADO.get(estado, '')} {estado}"
        )
        habilitados = [a["conductores"] for a in vehiculo.get("autorizaciones", [])
                       if a.get("vigente") and a.get("conductores")]
        if habilitados:
            with st.expander(f"Conductores autorizados para esta unidad ({len(habilitados)})"):
                for c in habilitados:
                    st.write(f"• {c['grado_o_cargo']} {c['nombre_completo']} — {c['rut']} ({c['estado']})")


def render(usuario: dict) -> None:
    st.markdown(CSS_MOVIL, unsafe_allow_html=True)
    st.subheader("🛂 Control de acceso — Garita")

    conductores = repo.listar_conductores()
    if conductores.empty:
        st.warning("No se pudieron leer los conductores. Revise la llave en secrets.toml.")
        return
    opciones = {f"{r.nombre_completo} · {r.rut}": r.rut for r in conductores.itertuples()}

    with st.form("form_acceso", clear_on_submit=True):
        patente_txt = st.text_input("Patente", placeholder="ABCD-12" +
                                    (" (o déjela vacía para leerla de la foto)" if OCR_DISPONIBLE else ""))
        movimiento = st.radio("Movimiento", ["Entrada", "Salida"], horizontal=True)
        conductor_sel = st.selectbox("Conductor", list(opciones), index=None,
                                     placeholder="Escriba nombre o RUT…")
        foto = st.camera_input("Foto de la patente (evidencia)")
        archivo = st.file_uploader("…o subir imagen", type=["jpg", "jpeg", "png"])
        enviar = st.form_submit_button("VALIDAR Y REGISTRAR", type="primary", width="stretch")

    if not enviar:
        return

    evidencia = foto or archivo
    foto_bytes = evidencia.getvalue() if evidencia else None
    patente = normalizar_patente(patente_txt)
    if not patente and foto_bytes and OCR_DISPONIBLE:
        with st.spinner("Leyendo patente desde la foto…"):
            patente = leer_patente(foto_bytes) or ""
        st.info(f"Patente detectada por OCR: **{patente or 'no reconocida'}**")
    if not patente or not conductor_sel:
        st.error("Debe indicar la patente y el conductor.")
        return

    rut = opciones[conductor_sel]
    with st.spinner("Consultando ficha vehicular…"):
        vehiculo = repo.ficha_vehiculo(patente)
        evaluacion = evaluar_acceso(vehiculo, rut, movimiento)

    _tarjeta_resultado(evaluacion["resultado"], evaluacion["motivos"], vehiculo)

    # Todo intento (incluso los denegados) queda en la bitácora de garita, con su foto
    if foto_bytes is None:
        st.warning("Movimiento NO registrado en bitácora: falta la fotografía de evidencia.")
        return
    try:
        registrar_acceso_garita(foto_bytes, patente, rut, movimiento, evaluacion["resultado"])
        st.cache_data.clear()
        st.success(f"{movimiento} registrada en la bitácora con evidencia fotográfica.")
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudo registrar el movimiento: {e}")
