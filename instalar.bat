@echo off
chcp 65001 >nul
echo === Editor de tutoriales: instalación en Windows ===
echo.
cd /d "%~dp0"
set "D=%~dp0descargas_app"
rem lo guardado con guardar_para_otra_pc.bat se usa primero; lo que falte se baja con winget
echo 1/5 Programas base (Python, Node.js y ffmpeg)...
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
echo 2/5 Librerías de Python...
python -m pip install --find-links "%D%\paquetes" -r requirements.txt
rem y queda una copia en descargas_app para la próxima PC
python -m pip download --disable-pip-version-check -q -r requirements.txt -d "%D%\paquetes"
echo Detector de telefono, laptop, manos y caras (35 MB, gratis, una sola vez)...
python deteccion\deteccion.py --bajar
echo.
echo 3/5 Etiquetas (Playwright + Chromium)...
call npm install
set "PLAYWRIGHT_BROWSERS_PATH=%D%\playwright"
call npx playwright install chromium
echo.
echo 4/5 Remotion (tráiler, señales)...
pushd remotion
call npm install
popd
echo.
echo 5/5 Clave de ElevenLabs (voz, música, transcripción en línea)
set /p KEY=Pega tu API key de ElevenLabs (o Enter para saltar): 
if not "%KEY%"=="" setx ELEVENLABS_API_KEY "%KEY%" >nul && echo Clave guardada. Abre una ventana nueva para usarla.
echo.
echo Creando Estudio.exe (la app con su propia ventana)...
call "%~dp0crear_exe.bat"
exit /b
