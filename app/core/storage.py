"""Supabase Storage: compresión de fotos, subida de evidencias y bitácora de garita.

La bitácora de accesos del guardia se guarda en el bucket (no en una tabla):
cada foto se nombra con los datos del evento, por ejemplo
    garita/20261118/143502__ABCD-12__18.234.567-K__Entrada__Autorizado__a1b2.jpg
Así el sistema funciona solo con las tablas y el bucket del proyecto del profesor.
"""
import io
import re
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from core.db import get_client
from core.utils import ZONA_HORARIA

BUCKET = "evidencias-vehiculares"
MAX_BYTES = 800 * 1024  # límite del bucket: 800 KB
CARPETA_GARITA = "garita"
PATRON_GARITA = re.compile(
    r"(?P<hora>\d{6})__(?P<patente>[A-Z0-9-]+)__(?P<rut>[0-9.]+-[0-9K]|SIN-RUT)__"
    r"(?P<movimiento>Entrada|Salida)__(?P<resultado>Autorizado|Alerta|Denegado)__\w+\.jpg"
)


# ----------------------------- fotos ----------------------------------------
def comprimir_imagen(data: bytes, max_bytes: int = MAX_BYTES) -> bytes:
    """Reduce la foto a JPEG <= 800 KB (ahorra datos móviles y cumple el límite del bucket)."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")  # respeta la orientación del celular
    img.thumbnail((1600, 1600))
    while True:
        for calidad in (85, 75, 65, 55, 45):
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=calidad, optimize=True)
            if buffer.tell() <= max_bytes:
                return buffer.getvalue()
        img = img.resize((int(img.width * 0.75), int(img.height * 0.75)))


def _subir(ruta: str, data: bytes) -> str:
    get_client().storage.from_(BUCKET).upload(
        ruta, comprimir_imagen(data), {"content-type": "image/jpeg", "upsert": "false"}
    )
    return ruta


def subir_evidencia_reporte(data: bytes, patente: str) -> str:
    """Foto del conductor (odómetro / novedad). Devuelve la ruta para reportes_estado."""
    ahora = datetime.now(ZoneInfo(ZONA_HORARIA))
    return _subir(f"reportes/{patente}/{ahora:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:4]}.jpg", data)


def registrar_acceso_garita(data: bytes, patente: str, rut: str | None,
                            movimiento: str, resultado: str) -> str:
    """Guarda la foto de garita con los datos del evento en el nombre del archivo."""
    ahora = datetime.now(ZoneInfo(ZONA_HORARIA))
    nombre = (f"{ahora:%H%M%S}__{re.sub(r'[^A-Z0-9-]', '', patente)}__{rut or 'SIN-RUT'}__"
              f"{movimiento}__{resultado}__{uuid.uuid4().hex[:4]}.jpg")
    return _subir(f"{CARPETA_GARITA}/{ahora:%Y%m%d}/{nombre}", data)


@st.cache_data(ttl=60, show_spinner=False)
def listar_accesos(desde: date, hasta: date) -> pd.DataFrame:
    """Lee la bitácora de garita desde el bucket (una carpeta por día)."""
    filas = []
    dia = max(desde, hasta - timedelta(days=62))  # máximo 2 meses por consulta
    while dia <= hasta:
        carpeta = f"{CARPETA_GARITA}/{dia:%Y%m%d}"
        for archivo in get_client().storage.from_(BUCKET).list(carpeta, {"limit": 1000}):
            m = PATRON_GARITA.fullmatch(archivo.get("name", ""))
            if m:
                fecha = datetime.strptime(f"{dia:%Y%m%d}{m['hora']}", "%Y%m%d%H%M%S")
                filas.append({
                    "fecha": fecha.replace(tzinfo=ZoneInfo(ZONA_HORARIA)),
                    "patente": m["patente"],
                    "rut_conductor": None if m["rut"] == "SIN-RUT" else m["rut"],
                    "tipo_movimiento": m["movimiento"],
                    "resultado": m["resultado"],
                    "foto": f"{carpeta}/{archivo['name']}",
                })
        dia += timedelta(days=1)
    columnas = ["fecha", "patente", "rut_conductor", "tipo_movimiento", "resultado", "foto"]
    df = pd.DataFrame(filas, columns=columnas)
    return df.sort_values("fecha", ascending=False, ignore_index=True)


@st.cache_data(ttl=1800, show_spinner=False)
def urls_firmadas(rutas: tuple[str, ...], segundos: int = 3600) -> dict[str, str]:
    """Genera enlaces temporales para mostrar las fotos (sirve con bucket público o privado)."""
    resultado = {r: r for r in rutas if r and r.startswith("http")}  # si ya es una URL completa
    rutas_bucket = [r for r in rutas if r and not r.startswith("http")]
    if rutas_bucket:
        firmadas = get_client().storage.from_(BUCKET).create_signed_urls(rutas_bucket, segundos)
        for item in firmadas:
            url = item.get("signedURL") or item.get("signedUrl")
            if url and not item.get("error"):
                resultado[item["path"]] = url
    return resultado
