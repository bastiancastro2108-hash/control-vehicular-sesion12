"""Reglas de negocio puras (sin Streamlit ni Supabase): fáciles de probar."""


def evaluar_acceso(vehiculo: dict | None, rut: str, movimiento: str) -> dict:
    """Decide Autorizado / Alerta / Denegado cruzando vehículo + conductor + autorización.

    vehiculo: resultado de repositorio.ficha_vehiculo() (con autorizaciones embebidas).
    """
    if vehiculo is None:
        return {"resultado": "Denegado", "motivos": ["Patente no registrada en el catálogo de la flota."]}

    autorizaciones = vehiculo.get("autorizaciones") or []
    vigente = next((a for a in autorizaciones
                    if a.get("rut_conductor") == rut and a.get("vigente")), None)

    if vigente is None:
        return {"resultado": "Denegado",
                "motivos": ["El conductor NO tiene autorización vigente para este vehículo."]}

    conductor = vigente.get("conductores") or {}
    if conductor.get("estado") != "Activo":
        return {"resultado": "Denegado",
                "motivos": [f"Conductor en estado «{conductor.get('estado', 'desconocido')}»."]}

    estado = vehiculo.get("estado_operativo")
    if estado == "Crítico":
        if movimiento == "Salida":
            return {"resultado": "Denegado",
                    "motivos": ["Vehículo en estado CRÍTICO: inmovilizado, no puede salir."]}
        return {"resultado": "Alerta",
                "motivos": ["Ingreso permitido, pero el vehículo está CRÍTICO: derivar a mantención."]}
    if estado == "Requiere Mantención":
        return {"resultado": "Alerta",
                "motivos": ["Autorizado, pero el vehículo REQUIERE MANTENCIÓN."]}

    return {"resultado": "Autorizado", "motivos": ["Conductor y vehículo habilitados."]}


def contar_fallas(presion_ok: bool, luces_ok: bool, frenos_ok: bool) -> int:
    return sum(not ok for ok in (presion_ok, luces_ok, frenos_ok))


def estado_esperado(estado_actual: str, fallas: int) -> str:
    """Misma regla que el trigger SQL (se usa para mostrar el aviso al conductor)."""
    if fallas >= 2:
        return "Crítico"
    if fallas == 1 and estado_actual != "Crítico":
        return "Requiere Mantención"
    return estado_actual


# La tabla reportes_estado no tiene columna para frenos: la falla se deja
# marcada al inicio de las observaciones para poder auditarla después.
MARCA_FRENOS = "[FALLA FRENOS]"


def tiene_falla_frenos(observaciones: str | None) -> bool:
    return MARCA_FRENOS in (observaciones or "")
