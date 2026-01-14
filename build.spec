# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 스펙 파일 - DLL OCR 버전 (2.0V)
# 
# 빌드 전 주의사항:
# - dlls/ 폴더에 DLL이 있어야 합니다 (build.bat이 자동으로 추출함)
# - 또는 python dll_extractor.py 를 먼저 실행하세요

import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['ocr.py', 'gui.py', 'dll_extractor.py'],
    pathex=[base_dir],
    binaries=[
        ('dlls/oneocr.dll', 'dlls'),
        ('dlls/onnxruntime.dll', 'dlls'),
    ],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('best.pt', '.'),
        ('dlls/oneocr.onemodel', 'dlls'),
    ],
    hiddenimports=[
        'flask',
        'waitress',
        'pandas',
        'openpyxl',
        'cv2',
        'numpy',
        'ultralytics',
        'ctypes',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='주차단속시스템',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 모드 기본 (콘솔 창 숨김)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
