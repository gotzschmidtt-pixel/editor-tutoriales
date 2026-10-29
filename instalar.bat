@echo off
chcp 65001 >nul
echo === Editor de tutoriales: instalación en Windows ===
echo.
cd /d "%~dp0"
set "D=%~dp0descargas_app"
rem lo guardado con guardar_para_otra_pc.bat se usa primero; lo que falte se baja con winget
echo 1/6 Programas base (Python, Node.js y ffmpeg)...
where python >nul 2>nul || for %%F in ("%D%\programas\*ython*.exe") do "%%F" /passive PrependPath=1
where python >nul 2>nul || winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
where node >nul 2>nul || for %%F in ("%D%\programas\*ode*.msi") do msiexec /i "%%F" /passive
where node >nul 2>nul || winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
if exist "%D%\programas\ffmpeg\ffmpeg.exe" set "PATH=%D%\programas\ffmpeg;%PATH%"
where ffmpeg >nul 2>nul || winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
echo.
echo Si alguno se acaba de instalar, cierra esta ventana y vuelve a abrir instalar.bat para que Windows los encuentre.
where python >nul 2>nul || (echo Falta Python en el PATH. Reabre la ventana. & pause & exit /b 1)
where node >nul 2>nul || (echo Falta Node.js en el PATH. Reabre la ventana. & pause & exit /b 1)
where ffmpeg >nul 2>nul || (echo Falta ffmpeg en el PATH. Reabre la ventana. & pause & exit /b 1)
echo.
echo 2/6 Librerías de Python...
python -m pip install --find-links "%D%\paquetes" -r requirements.txt
rem y queda una copia en descargas_app para la próxima PC
python -m pip download --disable-pip-version-check -q -r requirements.txt -d "%D%\paquetes"
echo.
echo 3/6 Modelos que la app usa en tu PC (gratis, una sola vez, unos 1,8 GB en total)...
python instalador\bajar_todo.py
echo.
echo 4/6 Etiquetas (Playwright + Chromium)...
call npm install
set "PLAYWRIGHT_BROWSERS_PATH=%D%\playwright"
call npx playwright install chromium
echo.
echo 5/6 Remotion (tráiler, señales) y su navegador...
pushd remotion
call npm install
call npx remotion browser ensure
popd
echo.
echo 6/6 Clave de ElevenLabs (voz, música, transcripción en línea)
set /p KEY=Pega tu API key de ElevenLabs (o Enter para saltar): 
if not "%KEY%"=="" setx ELEVENLABS_API_KEY "%KEY%" >nul && echo Clave guardada. Abre una ventana nueva para usarla.
echo.
echo Opcionales (puedes instalarlos despues con instalar_ia_local.bat o desde tailscale.com):
choice /m "Instalar la IA en tu PC (Ollama, funciona sin internet, pesa de 3 a 8 GB)"
if not errorlevel 2 call "%~dp0instalar_ia_local.bat"
choice /m "Instalar Tailscale (usar la app desde el celular con datos moviles, fuera del Wi-Fi de casa)"
if not errorlevel 2 winget install -e --id Tailscale.Tailscale --accept-package-agreements --accept-source-agreements
echo El APK para el celular esta en android\Estudio.apk (pasos en android\LEEME.md).
echo.
echo Creando Estudio.exe (la app con su propia ventana)...
call "%~dp0crear_exe.bat"
exit /b
