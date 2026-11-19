"""Lectura OCR de patentes (OPCIONAL).

Requiere `pip install easyocr` (pesado: instala PyTorch). Si no está instalado,
la app funciona igual y el guardia escribe la patente a mano.
"""
import io
import re

import numpy as np
import streamlit as st
from PIL import Image

from core.utils import normalizar_patente

try:
    import easyocr  # noqa: F401
    OCR_DISPONIBLE = True
except ImportError:
    OCR_DISPONIBLE = False

PATRON = re.compile(r"[A-Z]{4}\d{2}|[A-Z]{2}\d{4}")


@st.cache_resource(show_spinner="Cargando modelo OCR…")
def _lector():
    import easyocr
    return easyocr.Reader(["es", "en"], gpu=False)


def leer_patente(data: bytes) -> str | None:
    if not OCR_DISPONIBLE:
        return None
    imagen = np.array(Image.open(io.BytesIO(data)).convert("RGB"))
    textos = _lector().readtext(imagen, detail=0)
    candidato = re.sub(r"[^A-Z0-9]", "", "".join(textos).upper())
    encontrado = PATRON.search(candidato)
    return normalizar_patente(encontrado.group()) if encontrado else None
