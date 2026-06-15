# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all certifi data files (cacert.pem — required for HTTPS/TLS)
certifi_datas = collect_data_files('certifi')

# Collect all openai submodules (the SDK uses extensive lazy imports)
openai_imports = collect_submodules('openai')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=certifi_datas,
    hiddenimports=[
        # Matplotlib Qt backend chain
        'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_agg',
        'matplotlib.backends.qt_compat',
        'matplotlib.backends.qt_editor.figureoptions',
        'matplotlib.figure',
        'matplotlib.font_manager',
        'matplotlib.ticker',
        # PyQt6
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        # Pydantic (used by openai)
        'pydantic',
        'pydantic_core',
        # ── openai SDK and its transitive dependencies ──
        *openai_imports,
        # HTTP transport layer
        'httpx',
        'httpcore',
        'h11',
        # Async support
        'anyio',
        'sniffio',
        # TLS certificates
        'certifi',
        # Misc openai deps
        'distro',
        'jiter',
        'tqdm',
        'idna',
        # Additional stdlib-ish modules sometimes missed
        'email.mime.multipart',
        'email.mime.text',
        # Project config module (imported by ai_client)
        'config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyinstaller_hooks/runtime_hook_certifi.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MacSystemMonitorAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MacSystemMonitorAI',
)
app = BUNDLE(
    coll,
    name='MacSystemMonitorAI.app',
    icon='icon.icns',
    bundle_identifier='com.macsystemmonitor.ai',
    version='1.0.0',
    info_plist={
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'LSUIElement': False,
        'NSHumanReadableCopyright': 'Copyright © 2025. All rights reserved.',
    },
)
