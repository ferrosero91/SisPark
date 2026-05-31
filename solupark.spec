# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file para SoluPark Desktop.
Genera: dist/SoluPark/SoluPark.exe
"""
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None
BASE_DIR = os.path.dirname(os.path.abspath(SPEC))

# === HIDDEN IMPORTS ===
hidden_imports = []
hidden_imports += collect_submodules('django')
hidden_imports += collect_submodules('crispy_forms')
hidden_imports += collect_submodules('crispy_tailwind')
hidden_imports += collect_submodules('whitenoise')
hidden_imports += collect_submodules('barcode')
hidden_imports += collect_submodules('openpyxl')
hidden_imports += collect_submodules('reportlab')
hidden_imports += collect_submodules('PIL')
hidden_imports += collect_submodules('decouple')
hidden_imports += collect_submodules('webview')
hidden_imports += [
    'parking_system',
    'parking_system.settings_desktop',
    'parking_system.urls',
    'parking_system.wsgi',
    'parking.apps',
    'parking.models',
    'parking.models_config',
    'parking.views',
    'parking.forms',
    'parking.context_processors',
    'tenants.apps',
    'tenants.models',
    'tenants.middleware',
    'tenants.managers',
    'tenants.context',
    'tenants.context_processors',
    'users.apps',
    'users.models',
    'users.views',
    'users.backends',
    'users.middleware',
    'permissions.apps',
    'permissions.models',
    'permissions.services',
    'permissions.decorators',
    'permissions.mixins',
    'permissions.templatetags',
    'permissions.templatetags.permission_tags',
    'audit.apps',
    'audit.models',
    'audit.services',
    'monthly_contracts.apps',
    'monthly_contracts.models',
    'monthly_contracts.services',
    'monthly_contracts.views',
    'monthly_contracts.forms',
    'third_parties.apps',
    'third_parties.models',
    'third_parties.views',
    'third_parties.forms',
    'reports.apps',
    'reports.views',
    'config.apps',
    'config.models',
    'config.views',
    'config.forms',
    'superadmin.apps',
    'superadmin.views',
    'desktop.apps',
    'desktop.sync_models',
    'desktop.sync_engine',
    'desktop.sync_middleware',
    'desktop.context_processors',
    'desktop.views',
    'desktop.setup',
    # Django internals que a veces se pierden
    'django.contrib.admin.apps',
    'django.contrib.auth.apps',
    'django.contrib.contenttypes.apps',
    'django.contrib.sessions.apps',
    'django.contrib.messages.apps',
    'django.contrib.staticfiles.apps',
    'django.contrib.humanize.apps',
    'django.contrib.humanize.templatetags',
    'django.contrib.humanize.templatetags.humanize',
]

# === DATA FILES (templates, static, etc.) ===
datas = []

# Templates de cada app
template_apps = [
    'parking', 'users', 'monthly_contracts', 'third_parties',
    'config', 'superadmin', 'tenants', 'permissions', 'desktop'
]
for app in template_apps:
    tpl_dir = os.path.join(BASE_DIR, app, 'templates')
    if os.path.exists(tpl_dir):
        datas.append((tpl_dir, os.path.join(app, 'templates')))

# Static files (ya recopilados)
staticfiles_dir = os.path.join(BASE_DIR, 'staticfiles')
if os.path.exists(staticfiles_dir):
    datas.append((staticfiles_dir, 'staticfiles'))

static_dir = os.path.join(BASE_DIR, 'static')
if os.path.exists(static_dir):
    datas.append((static_dir, 'static'))

# Archivo .env para desktop
env_desktop = os.path.join(BASE_DIR, '.env.desktop')
if os.path.exists(env_desktop):
    datas.append((env_desktop, '.'))

# Icono
icon_file = os.path.join(BASE_DIR, 'desktop', 'assets', 'icon.ico')

# Datos de reportlab (fuentes)
datas += collect_data_files('reportlab')

# === ANALYSIS ===
a = Analysis(
    ['run_desktop.py'],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'notebook',
        'pytest',
        'test',
        'tests',
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SoluPark',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if os.path.exists(icon_file) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SoluPark',
)
