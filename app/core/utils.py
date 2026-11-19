"""Funciones auxiliares: normalización de patentes/RUT, fechas y colores."""
import re

import pandas as pd

ZONA_HORARIA = "America/Santiago"

COLOR_ESTADO = {
    "Operativo": "#2e7d32",            # verde
    "Requiere Mantención": "#f9a825",  # amarillo
    "Crítico": "#c62828",              # rojo
}
EMOJI_ESTADO = {"Operativo": "🟢", "Requiere Mantención": "🟡", "Crítico": "🔴"}
EMOJI_RESULTADO = {"Autorizado": "✅", "Alerta": "⚠️", "Denegado": "⛔"}


def normalizar_patente(texto: str | None) -> str:
    """'abcd 12', 'ABCD12', 'abcd-12' -> 'ABCD-12' (formato del catálogo)."""
    limpio = re.sub(r"[^A-Z0-9]", "", (texto or "").upper())
    if re.fullmatch(r"[A-Z]{4}\d{2}", limpio):      # patente nueva BBBB-12
        return f"{limpio[:4]}-{limpio[4:]}"
    if re.fullmatch(r"[A-Z]{2}\d{4}", limpio):      # patente antigua AB-1234
        return f"{limpio[:2]}-{limpio[2:]}"
    return limpio


def formatear_rut(texto: str | None) -> str:
    """'18234567k' / '18.234.567-K' -> '18.234.567-K'."""
    limpio = re.sub(r"[^0-9Kk]", "", texto or "").upper()
    if len(limpio) < 2:
        return limpio
    cuerpo, dv = limpio[:-1], limpio[-1]
    cuerpo_fmt = f"{int(cuerpo):,}".replace(",", ".") if cuerpo.isdigit() else cuerpo
    return f"{cuerpo_fmt}-{dv}"


def parece_rut(texto: str) -> bool:
    return bool(re.fullmatch(r"[\d.]{7,11}-?[\dkK]", (texto or "").strip()))


def a_hora_local(serie: pd.Series) -> pd.Series:
    """Convierte timestamps UTC de Supabase a hora de Chile."""
    return pd.to_datetime(serie, utc=True, format="ISO8601").dt.tz_convert(ZONA_HORARIA)
