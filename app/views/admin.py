"""Módulo PUESTO DE MANDO (PC): panel BI, feed de accesos, auditoría y gestión."""
import html
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core import repositorio as repo
from core.reglas import tiene_falla_frenos
from core.storage import listar_accesos, urls_firmadas
from core.utils import COLOR_ESTADO, EMOJI_ESTADO, EMOJI_RESULTADO, a_hora_local

ESTADOS = list(COLOR_ESTADO)
ESCALA_ESTADO = alt.Scale(domain=ESTADOS, range=list(COLOR_ESTADO.values()))
ESCALA_RESULTADO = alt.Scale(domain=["Autorizado", "Alerta", "Denegado"],
                             range=["#2e7d32", "#f9a825", "#c62828"])


# ============================================================================
def render(usuario: dict) -> None:
    st.subheader("🎖️ Puesto de Mando — Panel de inteligencia operativa")

    with st.sidebar:
        st.markdown("### Filtros")
        rango = st.date_input("Período", (date.today() - timedelta(days=30), date.today()),
                              format="DD/MM/YYYY")
        if st.button("🔄 Actualizar datos", width="stretch"):
            repo.limpiar_cache()
            st.rerun()
    desde, hasta = (rango if isinstance(rango, tuple) and len(rango) == 2 else (rango[0], rango[0]))

    vehiculos = repo.listar_vehiculos()
    if vehiculos.empty:
        st.warning("No hay vehículos visibles. Revise la URL y la llave **secreta** en secrets.toml.")
        return
    conductores = repo.listar_conductores()
    accesos = listar_accesos(desde, hasta)
    reportes = repo.listar_reportes(desde, hasta)

    tab_estado, tab_analitica, tab_feed, tab_auditoria, tab_gestion = st.tabs(
        ["📊 Estado de flota", "📈 Analítica", "🕒 Feed de accesos", "🔎 Auditoría", "⚙️ Gestión"])

    with tab_estado:
        _kpis(vehiculos, accesos)
        _matriz_estado(vehiculos)
        _alertas(vehiculos, reportes)
    with tab_analitica:
        _analitica(vehiculos, conductores, accesos)
    with tab_feed:
        _feed(accesos, conductores)
    with tab_auditoria:
        _auditoria(vehiculos, conductores, accesos)
    with tab_gestion:
        _gestion(vehiculos)


# ============================================================================
@st.fragment(run_every=30)  # se refresca solo cada 30 s (monitoreo en tiempo real)
def _kpis(vehiculos: pd.DataFrame, accesos: pd.DataFrame) -> None:
    vehiculos = repo.listar_vehiculos()
    total = len(vehiculos)
    conteo = vehiculos["estado_operativo"].value_counts()
    operativos = int(conteo.get("Operativo", 0))
    mantencion = int(conteo.get("Requiere Mantención", 0))
    criticos = int(conteo.get("Crítico", 0))

    # último movimiento válido de cada patente: si fue "Entrada", el vehículo está al interior
    validos = accesos[accesos["resultado"] != "Denegado"].drop_duplicates("patente")
    al_interior = int((validos["tipo_movimiento"] == "Entrada").sum())
    denegados = int((accesos["resultado"] == "Denegado").sum()) if not accesos.empty else 0

    c = st.columns(5)
    c[0].metric("Disponibilidad de flota", f"{operativos / total:.0%}", f"{operativos} de {total} operativos",
                delta_color="off")
    c[1].metric("🟡 Requieren mantención", mantencion)
    c[2].metric("🔴 Críticos (inmovilizados)", criticos)
    c[3].metric("Vehículos al interior", al_interior)
    c[4].metric("Accesos en el período", len(accesos), f"{denegados} denegados", delta_color="inverse")
    st.progress(operativos / total, text=f"Apresto operativo de la flota: {operativos / total:.0%}")


def _matriz_estado(vehiculos: pd.DataFrame) -> None:
    st.markdown("#### Matriz de estado por vehículo")
    tarjetas = []
    for v in vehiculos.itertuples():
        color = COLOR_ESTADO.get(v.estado_operativo, "#607d8b")
        km = f"{int(v.kilometraje_actual or 0):,}".replace(",", ".")
        tarjetas.append(
            f"""<div style="background:{color};color:white;border-radius:10px;padding:.7rem;">
            <div style="font-weight:800;font-size:1.1rem">{html.escape(v.patente)}</div>
            <div style="font-size:.85rem">{html.escape(v.marca_modelo)}</div>
            <div style="font-size:.8rem;opacity:.9">{html.escape(v.tipo_vehiculo)} · {km} km</div>
            <div style="font-size:.8rem;font-weight:700;margin-top:.3rem">{html.escape(v.estado_operativo)}</div>
            </div>"""
        )
    st.markdown(
        "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:.6rem'>"
        + "".join(tarjetas) + "</div>",
        unsafe_allow_html=True,
    )
    st.caption("🟢 Operativo · 🟡 Requiere Mantención · 🔴 Crítico")


def _alertas(vehiculos: pd.DataFrame, reportes: pd.DataFrame) -> None:
    st.markdown("#### 🚨 Alertas")
    fuera = vehiculos[vehiculos["estado_operativo"] != "Operativo"]
    if fuera.empty:
        st.success("Toda la flota se encuentra operativa.")
    for v in fuera.itertuples():
        st.warning(f"{EMOJI_ESTADO.get(v.estado_operativo, '⚪')} **{v.patente}** ({v.marca_modelo}) — {v.estado_operativo}")
    if not reportes.empty:
        bajos = reportes.drop_duplicates("patente")
        bajos = bajos[bajos["nivel_combustible"] < 20]
        for r in bajos.itertuples():
            st.info(f"⛽ **{r.patente}**: último reporte con {r.nivel_combustible}% de combustible.")


# ============================================================================
def _analitica(vehiculos: pd.DataFrame, conductores: pd.DataFrame, accesos: pd.DataFrame) -> None:
    st.markdown("#### Kilometraje acumulado por vehículo")
    st.altair_chart(
        alt.Chart(vehiculos).mark_bar().encode(
            x=alt.X("kilometraje_actual:Q", title="Kilómetros"),
            y=alt.Y("patente:N", sort="-x", title=None),
            color=alt.Color("estado_operativo:N", scale=ESCALA_ESTADO, title="Estado"),
            tooltip=["patente", "marca_modelo", "tipo_vehiculo", "anio",
                     alt.Tooltip("kilometraje_actual:Q", format=",")],
        ).properties(height=380).interactive(),
        width="stretch",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Kilometraje por tipo de vehículo")
        por_tipo = vehiculos.groupby("tipo_vehiculo", as_index=False)["kilometraje_actual"].sum()
        st.altair_chart(
            alt.Chart(por_tipo).mark_arc(innerRadius=60).encode(
                theta="kilometraje_actual:Q", color=alt.Color("tipo_vehiculo:N", title="Tipo"),
                tooltip=["tipo_vehiculo", alt.Tooltip("kilometraje_actual:Q", format=",")]),
            width="stretch",
        )
    with col2:
        st.markdown("#### Distribución del kilometraje")
        st.altair_chart(
            alt.Chart(vehiculos).mark_bar().encode(
                x=alt.X("kilometraje_actual:Q", bin=alt.Bin(maxbins=8), title="Rango de km"),
                y=alt.Y("count():Q", title="N° de vehículos"), tooltip=["count():Q"]),
            width="stretch",
        )

    st.divider()
    if accesos.empty:
        st.info("Sin accesos registrados en el período. Registre movimientos desde el módulo Guardia.")
        return

    acc = accesos.merge(conductores[["rut", "unidad_destino"]], how="left",
                        left_on="rut_conductor", right_on="rut")
    acc["unidad_destino"] = acc["unidad_destino"].fillna("Sin unidad")
    acc["hora"] = acc["fecha"].dt.hour

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("#### Frecuencia de accesos por vehículo")
        st.altair_chart(
            alt.Chart(acc).mark_bar().encode(
                x=alt.X("count():Q", title="Accesos"),
                y=alt.Y("patente:N", sort="-x", title=None),
                color=alt.Color("resultado:N", scale=ESCALA_RESULTADO, title="Resultado"),
                tooltip=["patente", "resultado", "count():Q"]),
            width="stretch",
        )
    with col4:
        st.markdown("#### Accesos por unidad / sector")
        st.altair_chart(
            alt.Chart(acc).mark_bar().encode(
                x=alt.X("count():Q", title="Accesos"),
                y=alt.Y("unidad_destino:N", sort="-x", title=None),
                color=alt.Color("tipo_movimiento:N", title="Movimiento"),
                tooltip=["unidad_destino", "tipo_movimiento", "count():Q"]),
            width="stretch",
        )

    st.markdown("#### Flujo horario de accesos")
    st.altair_chart(
        alt.Chart(acc).mark_bar().encode(
            x=alt.X("hora:O", title="Hora del día"), y=alt.Y("count():Q", title="Accesos"),
            color=alt.Color("tipo_movimiento:N", title="Movimiento"),
            tooltip=["hora", "tipo_movimiento", "count():Q"]),
        width="stretch",
    )


# ============================================================================
def _feed(accesos: pd.DataFrame, conductores: pd.DataFrame) -> None:
    st.markdown("#### Feed cronológico de accesos (con evidencia fotográfica)")
    if accesos.empty:
        st.info("Sin accesos en el período seleccionado.")
        return
    df = accesos.head(100).merge(conductores[["rut", "nombre_completo"]], how="left",
                                 left_on="rut_conductor", right_on="rut")
    urls = urls_firmadas(tuple(df["foto"]))
    df["evidencia"] = df["foto"].map(urls)
    df["fecha_local"] = df["fecha"].dt.strftime("%d-%m-%Y %H:%M:%S")
    df["resultado"] = df["resultado"].map(lambda r: f"{EMOJI_RESULTADO.get(r, '')} {r}")
    st.dataframe(
        df[["evidencia", "fecha_local", "patente", "tipo_movimiento", "resultado", "nombre_completo"]],
        hide_index=True, width="stretch", row_height=70,
        column_config={
            "evidencia": st.column_config.ImageColumn("Foto", width="small"),
            "fecha_local": "Fecha", "patente": "Patente", "tipo_movimiento": "Movimiento",
            "resultado": "Resultado", "nombre_completo": "Conductor",
        },
    )


# ============================================================================
def _auditoria(vehiculos: pd.DataFrame, conductores: pd.DataFrame, accesos: pd.DataFrame) -> None:
    st.markdown("#### Visor de bitácora por patente")
    patente = st.selectbox("Patente a auditar", vehiculos["patente"].tolist())
    v = vehiculos.set_index("patente").loc[patente]
    km = f"{int(v.kilometraje_actual or 0):,}".replace(",", ".")
    st.markdown(f"**{patente}** · {v.marca_modelo} · {v.tipo_vehiculo} · {v.anio} · "
                f"{EMOJI_ESTADO.get(v.estado_operativo, '')} {v.estado_operativo} · {km} km")

    reportes = repo.listar_reportes(patente=patente)
    nombres = dict(zip(conductores["rut"], conductores["nombre_completo"]))
    st.markdown("##### Reportes de estado de los conductores")
    if reportes.empty:
        st.info("Esta unidad no tiene reportes de estado.")
    else:
        urls = urls_firmadas(tuple(reportes["foto_evidencia_url"].dropna().unique()))
        for r in reportes.head(20).itertuples():
            fecha = a_hora_local(pd.Series([r.fecha_reporte])).iloc[0].strftime("%d-%m-%Y %H:%M")
            fallas = [n for n, ok in (("neumáticos", r.presion_neumaticos), ("luces", r.luces_operativas),
                                      ("frenos", not tiene_falla_frenos(r.observaciones))) if not ok]
            icono = "🔴" if len(fallas) >= 2 else "🟡" if fallas else "🟢"
            with st.expander(f"{icono} {fecha} — {nombres.get(r.rut_conductor, r.rut_conductor)}"):
                c1, c2 = st.columns([1, 2])
                url = urls.get(r.foto_evidencia_url)
                if url:
                    c1.image(url, width="stretch")
                else:
                    c1.caption("Sin fotografía")
                c2.write(f"**Kilometraje:** {r.kilometraje_salida:,} km".replace(",", "."))
                c2.write(f"**Combustible:** {r.nivel_combustible}%")
                c2.write(f"**Fallas:** {', '.join(fallas) if fallas else 'ninguna'}")
                c2.write(f"**Observaciones:** {r.observaciones or '—'}")

    st.markdown("##### Historial de accesos de la unidad (período seleccionado)")
    acc = accesos[accesos["patente"] == patente].copy()
    if acc.empty:
        st.caption("Sin accesos registrados en el período.")
    else:
        acc["fecha"] = acc["fecha"].dt.strftime("%d-%m-%Y %H:%M")
        acc["conductor"] = acc["rut_conductor"].map(nombres)
        st.dataframe(acc[["fecha", "tipo_movimiento", "resultado", "conductor"]],
                     hide_index=True, width="stretch")


# ============================================================================
def _gestion(vehiculos: pd.DataFrame) -> None:
    st.markdown("#### Liberar / cambiar estado de un vehículo (post-mantención)")
    with st.form("form_estado"):
        c1, c2 = st.columns(2)
        patente = c1.selectbox("Vehículo", vehiculos["patente"].tolist())
        estado = c2.selectbox("Nuevo estado", ESTADOS)
        if st.form_submit_button("Guardar estado"):
            repo.actualizar_vehiculo(patente, {"estado_operativo": estado})
            repo.limpiar_cache()
            st.success(f"{patente} → {estado}")
            st.rerun()
