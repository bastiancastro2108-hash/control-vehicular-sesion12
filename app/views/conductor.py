"""Módulo CONDUCTOR: check-in operativo y reporte de novedades del vehículo."""
import streamlit as st

from core import repositorio as repo
from core.reglas import MARCA_FRENOS, contar_fallas, estado_esperado
from core.storage import subir_evidencia_reporte
from core.utils import EMOJI_ESTADO, a_hora_local


def render(usuario: dict) -> None:
    st.subheader("🧰 Check-in operativo del vehículo")

    rut = usuario.get("rut_conductor")
    if usuario["rol"] == "admin":  # el administrador puede simular a un conductor
        conductores = repo.listar_conductores()
        opciones = {f"{r.nombre_completo} · {r.rut}": r.rut for r in conductores.itertuples()}
        rut = opciones[st.selectbox("Simular conductor", list(opciones))]

    vehiculos = repo.vehiculos_autorizados(rut)
    if not vehiculos:
        st.warning("No tiene vehículos con autorización vigente.")
        return

    etiquetas = {f"{EMOJI_ESTADO.get(v['estado_operativo'], '⚪')} {v['patente']} · {v['marca_modelo']}": v
                 for v in vehiculos}
    vehiculo = etiquetas[st.selectbox("Vehículo", list(etiquetas))]
    km_actual = int(vehiculo["kilometraje_actual"] or 0)
    c1, c2 = st.columns(2)
    c1.metric("Kilometraje registrado", f"{km_actual:,} km".replace(",", "."))
    c2.metric("Estado actual", vehiculo["estado_operativo"])

    with st.form("form_reporte", clear_on_submit=True):
        km = st.number_input("Kilometraje de salida (odómetro)", min_value=km_actual, value=km_actual, step=1)
        combustible = st.slider("Nivel de combustible (%)", 0, 100, 75, step=5)
        presion_ok = st.radio("Presión de neumáticos", ["OK", "Baja presión"], horizontal=True) == "OK"
        luces_ok = st.radio("Luces", ["Operativas", "Con falla"], horizontal=True) == "Operativas"
        frenos_ok = st.radio("Sistema de frenos", ["OK", "Con falla"], horizontal=True) == "OK"
        observaciones = st.text_area("Novedades mecánicas / observaciones", max_chars=500)
        foto = st.camera_input("Foto del odómetro / evidencia")
        archivo = st.file_uploader("…o subir imagen", type=["jpg", "jpeg", "png"])
        enviar = st.form_submit_button("ENVIAR REPORTE", type="primary", width="stretch")

    if enviar:
        evidencia = foto or archivo
        if evidencia is None:
            st.error("Debe adjuntar la fotografía de evidencia.")
        else:
            _guardar_reporte(vehiculo, rut, int(km), combustible, presion_ok, luces_ok, frenos_ok,
                             observaciones, evidencia.getvalue())

    st.divider()
    st.markdown("**Mis últimos reportes**")
    historial = repo.listar_reportes(rut=rut)
    if historial.empty:
        st.caption("Aún no hay reportes.")
    else:
        historial["fecha"] = a_hora_local(historial["fecha_reporte"]).dt.strftime("%d-%m-%Y %H:%M")
        st.dataframe(
            historial[["fecha", "patente", "kilometraje_salida", "nivel_combustible",
                       "presion_neumaticos", "luces_operativas", "observaciones"]].head(10),
            hide_index=True, width="stretch",
            column_config={
                "kilometraje_salida": "Km",
                "nivel_combustible": st.column_config.ProgressColumn(
                    "Combustible", min_value=0, max_value=100, format="%d%%"),
                "presion_neumaticos": "Neumáticos OK", "luces_operativas": "Luces OK",
                "observaciones": "Observaciones",
            },
        )


def _guardar_reporte(vehiculo, rut, km, combustible, presion_ok, luces_ok, frenos_ok,
                     observaciones, foto_bytes) -> None:
    patente = vehiculo["patente"]
    if not frenos_ok:  # la tabla no tiene columna de frenos: se marca en observaciones
        observaciones = f"{MARCA_FRENOS} {observaciones}".strip()
    try:
        with st.spinner("Comprimiendo y subiendo evidencia…"):
            ruta = subir_evidencia_reporte(foto_bytes, patente)
        repo.insertar_reporte({
            "patente": patente,
            "rut_conductor": rut,
            "kilometraje_salida": km,
            "nivel_combustible": combustible,
            "presion_neumaticos": presion_ok,
            "luces_operativas": luces_ok,
            "observaciones": observaciones or None,
            "foto_evidencia_url": ruta,
        })

        # LÓGICA AUTOMATIZADA: el reporte actualiza la tabla maestra de vehículos
        fallas = contar_fallas(presion_ok, luces_ok, frenos_ok)
        nuevo_estado = estado_esperado(vehiculo["estado_operativo"], fallas)
        repo.actualizar_vehiculo(patente, {
            "kilometraje_actual": max(km, int(vehiculo["kilometraje_actual"] or 0)),
            "estado_operativo": nuevo_estado,
        })
        repo.limpiar_cache()

        st.success("Reporte registrado correctamente.")
        if nuevo_estado != vehiculo["estado_operativo"]:
            st.warning(f"Se informaron {fallas} falla(s). El vehículo pasó automáticamente a "
                       f"**{EMOJI_ESTADO.get(nuevo_estado, '')} {nuevo_estado}**.")
        if combustible < 20:
            st.info("⛽ Nivel de combustible bajo: coordine recarga antes de la misión.")
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudo registrar el reporte: {e}")
