"""Todo lo que la app descarga queda en descargas_app/ (dentro de la carpeta de la app), para no bajarlo dos veces y
para llevarlo a otra PC: copias la carpeta de la app entera y en la PC nueva instalar.bat usa lo guardado.

  descargas_app/paquetes/    librerías de Python (.whl): lector de texto, Whisper, Claude, yt-dlp, numpy, opencv…
  descargas_app/modelos/     modelos de Whisper (transcribir sin internet)
  descargas_app/playwright/  el navegador de las etiquetas animadas
  descargas_app/programas/   ffmpeg (y los instaladores de Python y Node si corriste guardar_para_otra_pc.bat)
"""
import os, subprocess, sys, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, 'descargas_app')
PAQUETES = os.path.join(CARPETA, 'paquetes')
MODELOS = os.path.join(CARPETA, 'modelos')
PLAYWRIGHT = os.path.join(CARPETA, 'playwright')
FFMPEG = os.path.join(CARPETA, 'programas', 'ffmpeg')
SIN_VENTANA = {'creationflags': 0x08000000} if sys.platform == 'win32' else {}


def preparar_entorno(env=None):
    """Que los programas usen lo guardado en descargas_app: su ffmpeg y su navegador, si están."""
    env = os.environ if env is None else env
    if os.path.isfile(os.path.join(FFMPEG, 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')):
        env['PATH'] = FFMPEG + os.pathsep + env.get('PATH', '')
    if os.path.isdir(PLAYWRIGHT) and os.listdir(PLAYWRIGHT):  # el navegador guardado (lo copia guardar_para_otra_pc.bat)
        env.setdefault('PLAYWRIGHT_BROWSERS_PATH', PLAYWRIGHT)
    return env


def instalar(paquetes, mostrar=print, python=None, limite=3600):
    """Instala `paquetes` usando primero lo guardado en descargas_app/paquetes. Lo que falta se baja ahí ANTES de
    instalar: cada archivo que termina de bajar queda guardado, así una descarga cortada sigue donde iba la próxima vez
    en vez de empezar de cero. Devuelve True si quedó instalado."""
    py = python or sys.executable
    os.makedirs(PAQUETES, exist_ok=True)
    base = [py, '-m', 'pip', '--disable-pip-version-check']
    desde_carpeta = base + ['install', '--no-index', '--find-links', PAQUETES] + list(paquetes)
    if subprocess.run(desde_carpeta, capture_output=True, **SIN_VENTANA).returncode == 0:
        mostrar(f'· instalado desde descargas_app (sin bajar nada): {", ".join(paquetes)}')
        return True
    mostrar(f'· bajando {", ".join(paquetes)} a descargas_app\\paquetes (queda guardado para la próxima vez y para otra PC)…')
    pr = subprocess.Popen(base + ['download', '--progress-bar', 'off', '-d', PAQUETES] + list(paquetes),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', **SIN_VENTANA)
    inicio, errores = time.time(), []
    for linea in pr.stdout:
        linea = linea.strip()
        if linea.startswith(('Collecting', 'Downloading', 'Saved', 'File was already')):
            mostrar(f'· [{int(time.time() - inicio)} s] ' + linea.replace(PAQUETES, 'descargas_app\\paquetes')[:160])
        elif linea.startswith('ERROR') or 'No matching distribution' in linea:
            errores.append(linea); mostrar('· ' + linea[:300])
        if time.time() - inicio > limite:
            pr.kill(); mostrar('· la descarga tardó demasiado; lo que ya bajó quedó guardado y sigue la próxima vez'); return False
    pr.wait()
    r = subprocess.run(desde_carpeta, capture_output=True, text=True, encoding='utf-8', errors='replace', **SIN_VENTANA)
    if r.returncode != 0:
        final = [x for x in (r.stdout + r.stderr).splitlines() if x.startswith('ERROR')][-2:]
        mostrar('· no se pudo instalar: ' + ' / '.join(final or errores or ['revisa tu internet'])[:400]
                + f' (tu Python es {sys.version.split()[0]})')
        return False
    mostrar(f'· instalado: {", ".join(paquetes)}')
    return True
