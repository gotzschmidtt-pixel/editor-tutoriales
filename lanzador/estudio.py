"""Estudio.exe: abre el Estudio de tutoriales como un programa, sin ventana negra ni pestañas.

Arranca app/app.py en segundo plano (si no estaba ya abierta) y la muestra en su propia ventana
con Edge o Chrome en modo aplicación. Al cerrar la ventana, la app se apaga sola a los pocos minutos
(si no hay un paso trabajando).

Se convierte en .exe en tu PC con crear_exe.bat (PyInstaller). Usa el Python, ffmpeg y Node que ya
instaló instalar.bat; el .exe no los trae dentro.
"""
import os, shutil, socket, subprocess, sys, time, webbrowser

PUERTO = 8765
URL = f'http://localhost:{PUERTO}'
# el .exe vive en la carpeta principal del editor; el .py, en lanzador/
AQUI = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NO_VENTANA = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def aviso(msg):
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, 'Estudio de tutoriales', 0x10)
    else:
        print(msg)


def abierta():
    try:
        socket.create_connection(('127.0.0.1', PUERTO), timeout=0.5).close()
        return True
    except OSError:
        return False


def arrancar():
    app = os.path.join(AQUI, 'app', 'app.py')
    if not os.path.exists(app):
        aviso(f'No encuentro app\\app.py.\n\nPon Estudio.exe en la carpeta principal del editor (donde está iniciar.bat).\n\nEstoy en: {AQUI}')
        sys.exit(1)
    py = shutil.which('pythonw') or shutil.which('python') or shutil.which('python3')
    if not py:
        aviso('No encuentro Python. Corre instalar.bat y reinicia la PC.')
        sys.exit(1)
    salida = open(os.path.join(AQUI, 'app', 'registro_app.txt'), 'a', encoding='utf-8')
    env = dict(os.environ, SIN_NAVEGADOR='1', AUTO_SALIR='1', PYTHONIOENCODING='utf-8')
    subprocess.Popen([py, app], cwd=AQUI, env=env, stdout=salida, stderr=subprocess.STDOUT, creationflags=NO_VENTANA)
    for _ in range(60):
        if abierta():
            return
        time.sleep(0.5)
    aviso('La app no arrancó. Abre iniciar.bat para ver el error en la ventana negra, '
          'o revisa app\\registro_app.txt.')
    sys.exit(1)


def navegador():
    pf = [os.environ.get(k, '') for k in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA')]
    rutas = [os.path.join(b, 'Microsoft', 'Edge', 'Application', 'msedge.exe') for b in pf] + \
            [os.path.join(b, 'Google', 'Chrome', 'Application', 'chrome.exe') for b in pf]
    return next((r for r in rutas if r and os.path.exists(r)), None) or shutil.which('msedge') or shutil.which('chrome')


def ventana():
    nav = navegador()
    if not nav:
        return webbrowser.open(URL)
    # perfil propio fuera de la carpeta del editor (que puede estar sincronizada)
    perfil = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'EstudioTutoriales', 'ventana')
    subprocess.Popen([nav, f'--app={URL}', f'--user-data-dir={perfil}', '--window-size=1440,920', '--no-first-run'])


if __name__ == '__main__':
    if not abierta():
        arrancar()
    ventana()
