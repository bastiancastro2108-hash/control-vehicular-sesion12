# Sistema de Control de Acceso y Estado Operativo de Flota

Aplicación web/móvil desarrollada en Streamlit y Supabase (PostgreSQL + Storage) para la actividad de la Sesión 12.

## Perfiles de usuario
| Perfil | Dispositivo | Funciones |

Guardia de Garita: (Móvil) Valida patente + conductor + autorización + estado del vehículo y registra la entrada/salida con foto de evidencia (Autorizado / Alerta / Denegado). Lectura de patente por OCR (easyocr).
Conductor Operativo: (Móvil) Check-in del vehículo asignado: kilometraje, combustible, neumáticos, luces, frenos, observaciones y foto. Si reporta fallas, el estado del vehículo se actualiza automáticamente.
Puesto de Mando: (PC) Disponibilidad de flota, matriz de estado por colores, analítica de kilometraje y accesos, feed de accesos con fotos, auditoría por patente y liberación de vehículos tras mantención.

## Estructura
```
app/
├── main.py            # inicio: login y navegación según el rol
├── core/
│   ├── db.py          # conexión a Supabase (lee st.secrets)
│   ├── auth.py        # inicio de sesión con st.session_state
│   ├── repositorio.py # consultas a las tablas
│   ├── reglas.py      # reglas de acceso y de estado del vehículo
│   ├── storage.py     # compresión de fotos (<800 KB) y bitácora de garita
│   ├── ocr.py         # lectura de patentes (easyocr)
│   └── utils.py       # formatos de patente/RUT, colores, zona horaria
└── views/
    ├── guardia.py
    ├── conductor.py
    └── admin.py
```

## Base de datos
Se utilizan las tablas `conductores`, `vehiculos`, `autorizaciones` y `reportes_estado`, y el bucket `evidencias-vehiculares` (máx. 800 KB por imagen).
- La bitácora de garita se guarda en el bucket, en `garita/AAAAMMDD/`, con los datos del evento en el nombre de cada foto.
- Las fotos de los conductores se guardan en `reportes/<PATENTE>/` y su ruta queda en `reportes_estado.foto_evidencia_url`.
- Una falla de frenos se registra con la marca `[FALLA FRENOS]` en `observaciones`.

## Ejecución local
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py
```

## Secretos
Las credenciales no estan en el repositorio. Se configuran en `.streamlit/secrets.toml` (excluido por `.gitignore`) con esta estructura:
```toml
[supabase]
url = "..."
key = "..."

[usuarios]
admin = "..."
guardia = "..."
conductor = "..."
```
El conductor inicia sesión con su RUT (registrado y en estado *Activo*) y la clave de conductores.