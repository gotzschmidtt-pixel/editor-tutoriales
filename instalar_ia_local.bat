@echo off
chcp 65001 >nul
echo === IA open source en tu PC (Ollama) ===
echo Funciona sin internet una vez instalada. Necesita espacio en disco.
echo.
where ollama >nul 2>nul || winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
where ollama >nul 2>nul || (echo. & echo Ollama se instaló. Cierra esta ventana y vuelve a abrir instalar_ia_local.bat. & pause & exit /b 1)
echo.
echo Elige el modelo:
echo   1 = Gemma 3 12B  (mejor guion, unos 8 GB, para PC con 16 GB de RAM o tarjeta de video)
echo   2 = Gemma 3 4B   (más liviano, unos 3 GB, para PC sencilla)
echo   3 = Qwen 2.5 VL 7B (alternativa, unos 6 GB)
set /p M=Escribe 1, 2 o 3 y Enter: 
if "%M%"=="2" (set MOD=gemma3:4b) else if "%M%"=="3" (set MOD=qwen2.5vl:7b) else (set MOD=gemma3:12b)
echo.
echo Descargando %MOD% (tarda según tu internet)...
ollama pull %MOD%
if errorlevel 1 (echo No se pudo descargar. Revisa tu internet. & pause & exit /b 1)
echo.
echo Listo. En la app abre "Ajustes IA" y elige el Ollama que corresponde a %MOD%. No necesita clave.
pause
