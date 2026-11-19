"""Consultas a las 4 tablas del proyecto: conductores, vehiculos, autorizaciones y reportes_estado."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from core.db import get_client
from core.utils import ZONA_HORARIA

TTL = 30  # segundos de caché para el dashboard (casi tiempo real)


def limpiar_cache() -> None:
    st.cache_data.clear()


# ----------------------------- catálogos ------------------------------------
@st.cache_data(ttl=TTL, show_spinner=False)
def listar_vehiculos() -> pd.DataFrame:
    return pd.DataFrame(get_client().table("vehiculos").select("*").order("patente").execute().data)


@st.cache_data(ttl=TTL, show_spinner=False)
def listar_conductores() -> pd.DataFrame:
    return pd.DataFrame(get_client().table("conductores").select("*").order("nombre_completo").execute().data)


def conductor_por_rut(rut: str) -> dict | None:
    res = get_client().table("conductores").select("*").eq("rut", rut).limit(1).execute()
    return res.data[0] if res.data else None


# --------------------------- guardia ----------------------------------------
def ficha_vehiculo(patente: str) -> dict | None:
    """UNA sola llamada a la API: vehículo + autorizaciones + datos del conductor.

    Supabase (PostgREST) une las tablas usando las llaves foráneas
    autorizaciones.patente -> vehiculos.patente y
    autorizaciones.rut_conductor -> conductores.rut  (equivale a dos JOIN).
    """
    res = (get_client().table("vehiculos")
           .select("patente, tipo_vehiculo, marca_modelo, anio, kilometraje_actual, estado_operativo,"
                   " autorizaciones(rut_conductor, vigente,"
                   " conductores(rut, nombre_completo, grado_o_cargo, unidad_destino, estado))")
           .eq("patente", patente).limit(1).execute())
    return res.data[0] if res.data else None


# --------------------------- conductor --------------------------------------
def vehiculos_autorizados(rut: str) -> list[dict]:
    res = (get_client().table("autorizaciones")
           .select("patente, vehiculos(patente, tipo_vehiculo, marca_modelo, kilometraje_actual, estado_operativo)")
           .eq("rut_conductor", rut).eq("vigente", True).execute())
    return [r["vehiculos"] for r in res.data if r.get("vehiculos")]


def insertar_reporte(reporte: dict) -> None:
    get_client().table("reportes_estado").insert(reporte).execute()


def actualizar_vehiculo(patente: str, cambios: dict) -> None:
    get_client().table("vehiculos").update(cambios).eq("patente", patente).execute()


# --------------------------- reportes ---------------------------------------
@st.cache_data(ttl=TTL, show_spinner=False)
def listar_reportes(desde: date | None = None, hasta: date | None = None,
                    patente: str | None = None, rut: str | None = None) -> pd.DataFrame:
    q = get_client().table("reportes_estado").select("*")
    if desde and hasta:
        tz = ZoneInfo(ZONA_HORARIA)
        q = (q.gte("fecha_reporte", datetime.combine(desde, time.min, tzinfo=tz).isoformat())
              .lt("fecha_reporte", datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=tz).isoformat()))
    if patente:
        q = q.eq("patente", patente)
    if rut:
        q = q.eq("rut_conductor", rut)
    return pd.DataFrame(q.order("fecha_reporte", desc=True).limit(1000).execute().data)
