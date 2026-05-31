# SoluPark Desktop - Aplicación de Escritorio

## Descripción

SoluPark Desktop es la versión de escritorio del sistema de gestión de parqueaderos.
Funciona **100% offline** usando SQLite como base de datos local, y sincroniza
automáticamente con el servidor en la nube cuando hay conexión a internet.

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│              SoluPark Desktop (.exe)                  │
│                                                       │
│  ┌────────────┐   ┌──────────┐   ┌──────────────┐  │
│  │  Django     │──▶│  SQLite  │   │  Sync Engine │  │
│  │  Server     │   │  Local   │   │  (background)│  │
│  │  (127.0.0.1)│   └──────────┘   └──────┬───────┘  │
│  └─────┬──────┘                           │          │
│        │                                  ▼          │
│  ┌─────▼──────┐              ┌────────────────────┐ │
│  │  pywebview  │              │  PostgreSQL (nube) │ │
│  │  (ventana)  │              │  (cuando hay red)  │ │
│  └────────────┘              └────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Requisitos para desarrollo

- Python 3.12+
- pip (gestor de paquetes)

## Instalación para desarrollo

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements_desktop.txt

# 3. Ejecutar la app
python run_desktop.py
```

## Compilar el .exe

```bash
# Opción 1: Usar el script de build
build_desktop.bat

# Opción 2: Manual
pip install -r requirements_desktop.txt
python manage.py collectstatic --noinput --settings=parking_system.settings_desktop
pyinstaller solupark.spec --noconfirm
```

El ejecutable se genera en: `dist/SoluPark/SoluPark.exe`

## Distribución

Para distribuir la aplicación:

1. Comprime la carpeta `dist/SoluPark/` en un ZIP
2. El usuario solo necesita descomprimir y ejecutar `SoluPark.exe`
3. No requiere instalación de Python ni dependencias

## Datos de acceso inicial

Al ejecutar por primera vez:
- **Email:** admin@local.com
- **Contraseña:** admin123

## Almacenamiento de datos

Los datos se almacenan en: `%USERPROFILE%\.solupark\`

- `solupark_local.db` - Base de datos SQLite
- `cache/` - Caché de la aplicación
- `media/` - Archivos multimedia
- `logs/` - Logs de la aplicación

## Sincronización con la nube

Para habilitar la sincronización, edita el archivo `.env` junto al ejecutable:

```env
SOLUPARK_SYNC_URL=https://tu-servidor.com
SOLUPARK_SYNC_TOKEN=tu-token-de-autenticacion
SOLUPARK_SYNC_INTERVAL=60
```

### Cómo funciona la sincronización

1. Cada operación (entrada/salida de vehículos, pagos, etc.) se guarda localmente
2. Se agrega a una cola de sincronización
3. Cuando hay internet, el motor de sync envía los cambios al servidor
4. También recibe cambios del servidor (otros dispositivos)
5. Los conflictos se resuelven por timestamp (último en modificar gana)

### Indicador de estado

En la esquina inferior derecha de la app aparece un indicador:
- 🟢 **En línea** - Conectado y sincronizando
- 🟡 **Modo offline** - Sin conexión, trabajando localmente
- Badge azul con número - Operaciones pendientes de sincronizar

## Protección del código

El ejecutable compilado con PyInstaller empaqueta el código como bytecode Python (.pyc),
que no es legible directamente. Para protección adicional:

```bash
# Instalar pyarmor (ofuscación avanzada)
pip install pyarmor

# Ofuscar antes de compilar
pyarmor gen --pack onefile run_desktop.py
```

## Estructura del módulo desktop

```
desktop/
├── __init__.py          # Inicialización
├── app.py               # Punto de entrada (servidor + ventana)
├── apps.py              # Configuración Django app
├── setup.py             # Datos iniciales
├── sync_engine.py       # Motor de sincronización
├── sync_middleware.py   # Captura cambios para sincronizar
├── sync_models.py       # Modelos de cola de sync
├── context_processors.py # Variables de template
├── views.py             # API de sincronización
├── urls.py              # URLs del módulo
├── assets/
│   └── icon.ico         # Icono del ejecutable
├── templates/
│   └── desktop/
│       └── sync_indicator.html  # UI del indicador
└── migrations/
    └── 0001_initial.py  # Migración de modelos sync
```
