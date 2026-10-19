@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Creando Estudio.exe ===
echo.
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --onefile --noconsole --name Estudio --icon "%~dp0lanzador\estudio.ico" --distpath "%~dp0." --workpath "%TEMP%\estudio_exe" --specpath "%TEMP%\estudio_exe" "%~dp0lanzador\estudio.py"
if not exist "%~dp0Estudio.exe" (echo. & echo No se pudo crear Estudio.exe. Mira el mensaje de arriba. & pause & exit /b 1)
echo.
echo Poniendo "Estudio de tutoriales" en el escritorio...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Estudio de tutoriales.lnk'); $s.TargetPath='%~dp0Estudio.exe'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0Estudio.exe,0'; $s.Save()"
echo.
echo Listo. Abre "Estudio de tutoriales" desde tu escritorio.
echo Si Windows muestra "Windows protegio su PC", pulsa "Mas informacion" y luego "Ejecutar de todas formas".
pause
