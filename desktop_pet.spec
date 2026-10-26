# Build from a clean checkout; never bundle .env or data/.
from pathlib import Path
root = Path(SPECPATH)
datas=[(str(root/'形象'),'形象'),(str(root/'assets'),'assets'),(str(root/'.env.example'),'.')]
a=Analysis([str(root/'main.py')],pathex=[str(root)],binaries=[],datas=datas,
    hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['torch','tensorflow','PyQt5','PyQt6','PySide2','tkinter'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='DesktopPet',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='DesktopPet')
