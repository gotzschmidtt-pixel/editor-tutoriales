@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Creando Estudio.exe ===
echo.
rem Si la app esta abierta con Estudio.exe, Windows no deja reemplazarlo
taskkill /f /im Estudio.exe >nul 2>nul
set "OBRA=%LOCALAPPDATA%\EstudioTutoriales\crear_exe"
if exist "%OBRA%" rmdir /s /q "%OBRA%"
python -m pip install --upgrade pyinstaller
for /l %%i in (1,1,2) do (
  if not exist "%~dp0Estudio.exe" python -m PyInstaller --noconfirm --clean --onefile --noconsole --name Estudio --icon "%~dp0lanzador\estudio.ico" --distpath "%~dp0." --workpath "%OBRA%\obra" --specpath "%OBRA%" "%~dp0lanzador\estudio.py"
)
set "DESTINO=%~dp0Estudio.exe"
set "ARGS="
if not exist "%~dp0Estudio.exe" goto sin_exe
goto acceso

:sin_exe
rem Casi siempre es el antivirus (Windows Defender) que bloquea la copia del .exe nuevo.
rem Igual te dejo el icono en el escritorio: abre la misma app con Python, sin ventana negra.
echo.
echo No se pudo crear Estudio.exe (el antivirus suele bloquearlo). Pongo el acceso directo igual, sin .exe.
for /f "delims=" %%p in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%p"
if not defined PYW (echo No encuentro pythonw. Corre instalar.bat. & pause & exit /b 1)
set "DESTINO=%PYW%"
set "ARGS="%~dp0lanzador\estudio.py""

:acceso
echo.
echo Poniendo "Estudio de tutoriales" en el escritorio...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Estudio de tutoriales.lnk'); $s.TargetPath=$env:DESTINO; $s.Arguments=$env:ARGS; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0lanzador\estudio.ico,0'; $s.Save()"
echo.
echo Listo. Abre "Estudio de tutoriales" desde tu escritorio.
if exist "%~dp0Estudio.exe" echo Si Windows muestra "Windows protegio su PC", pulsa "Mas informacion" y luego "Ejecutar de todas formas".
pause
