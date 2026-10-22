@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "D=%~dp0descargas_app"
echo === Guardar todo lo que descarga la app, para instalarla en otra PC ===
echo Todo queda en %D%
echo.
echo 1/5 Librerias de Python (lector de texto, Whisper, Claude, yt-dlp, numpy, opencv)...
python -m pip download --disable-pip-version-check -r requirements.txt -d "%D%\paquetes"
echo.
echo 2/5 ffmpeg...
if not exist "%D%\programas\ffmpeg" mkdir "%D%\programas\ffmpeg"
for /f "delims=" %%F in ('where ffmpeg 2^>nul') do if not exist "%D%\programas\ffmpeg\ffmpeg.exe" copy /y "%%F" "%D%\programas\ffmpeg\ffmpeg.exe" >nul
for /f "delims=" %%F in ('where ffprobe 2^>nul') do if not exist "%D%\programas\ffmpeg\ffprobe.exe" copy /y "%%F" "%D%\programas\ffmpeg\ffprobe.exe" >nul
if exist "%D%\programas\ffmpeg\ffmpeg.exe" (echo ffmpeg guardado.) else (echo No encontre ffmpeg en esta PC.)
echo.
echo 3/5 Instaladores de Python y Node.js...
winget download -e --id Python.Python.3.12 -d "%D%\programas" --accept-package-agreements --accept-source-agreements
winget download -e --id OpenJS.NodeJS.LTS -d "%D%\programas" --accept-package-agreements --accept-source-agreements
if errorlevel 1 echo (Si dice que "download" no existe, actualiza "App Installer" en Microsoft Store. En la otra PC se bajan solos con internet.)
echo.
echo 4/5 Navegador de las etiquetas animadas...
if exist "%LOCALAPPDATA%\ms-playwright" robocopy "%LOCALAPPDATA%\ms-playwright" "%D%\playwright" /E /NFL /NDL /NJH /NJS /NP >nul
if exist "%D%\playwright" (echo Navegador guardado.) else (echo No encontre el navegador; instalar.bat lo baja en la otra PC.)
echo.
echo 5/5 Modelos de IA en tu PC (Ollama)
if not exist "%USERPROFILE%\.ollama\models" (echo No tienes modelos de Ollama. & goto fin)
choice /m "Copiar tambien los modelos de Ollama? Pesan varios GB"
if errorlevel 2 goto fin
robocopy "%USERPROFILE%\.ollama\models" "%D%\ollama_modelos" /E /NFL /NDL /NJH /NJS
:fin
echo.
echo Listo. Para la otra PC: copia la carpeta editor-tutoriales ENTERA (con descargas_app y tus proyectos)
echo y alla corre instalar.bat: usa lo guardado y solo baja lo que falte.
pause
