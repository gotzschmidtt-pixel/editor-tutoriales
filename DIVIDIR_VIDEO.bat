@echo off
chcp 65001 >nul
rem Arrastra uno o varios videos ENCIMA de este archivo: los corta en partes de menos de 450 MB,
rem sin perder calidad, en una carpeta NOMBRE_PARTES al lado del video.
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
if not "%~1"=="" goto con_video
echo Arrastra el video ENCIMA de este archivo DIVIDIR_VIDEO.bat
echo o pega aqui la ruta del video y presiona Enter:
set /p VIDEO=Video: 
python dividir\dividir.py "%VIDEO:"=%"
goto fin
:con_video
python dividir\dividir.py %*
:fin
echo.
pause
