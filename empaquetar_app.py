"""Arma el ZIP de actualización de la app con la versión en el nombre: editor-tutoriales_v1.5.1_2026-11-14.zip

Uso:
  python empaquetar_app.py                    -> lo deja en descargas_app/
  python empaquetar_app.py --salida CARPETA   -> lo deja en CARPETA
  python empaquetar_app.py --drive CARPETA    -> además lo copia a tu carpeta de Google Drive (la de «Drive para escritorio»)

Si en app/ajustes.json pones "carpeta_drive": "G:\\Mi unidad\\APP EDITOR ZIP", lo copia ahí siempre, sin --drive.
Mete solo el código de la app (lo que está en GitHub): nunca tus proyectos, claves, estilos ni conocimientos.
"""
import argparse, json, os, shutil, subprocess, sys, time, zipfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
NOMBRE = 'editor-tutoriales'
# lo tuyo nunca va en el zip (igual que NO_TOCAR de app/app.py)
FUERA = {'mis_proyectos', 'mis_estilos', 'mis_musica', 'mis_conocimientos', 'mis_sonidos', 'mis_proyectos_editables',
         'descargas_app', '.git', 'node_modules', 'trabajo', 'ffmpeg_nvidia', '__pycache__'}
FUERA_ARCHIVOS = {'app/ajustes.json', 'app/ajustes.json.copia', 'app/ajustes.json.tmp', 'app/registro_app.txt',
                  'app/registro_actualizacion.txt', 'Estudio.exe'}


def version():
    try:
        return open(os.path.join(RAIZ, 'VERSION'), encoding='utf-8').read().strip() or '0'
    except OSError:
        return '0'


def archivos_de_la_app():
    """Los archivos que sigue git (así sale igual que GitHub). Sin git: toda la carpeta menos lo tuyo."""
    try:
        r = subprocess.run(['git', 'ls-files', '-z'], cwd=RAIZ, capture_output=True, timeout=60)
        if r.returncode == 0 and r.stdout:
            return sorted(x for x in r.stdout.decode('utf-8').split('\0') if x)
    except (OSError, subprocess.SubprocessError):
        pass
    lista = []
    for raiz, dirs, archivos in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in FUERA]
        for a in archivos:
            rel = os.path.relpath(os.path.join(raiz, a), RAIZ).replace(os.sep, '/')
            if not a.endswith(('.pyc', '.mp4', '.mp3', '.wav', '.npz', '.keystore', '.zip')):
                lista.append(rel)
    return sorted(lista)


def carpeta_drive_de_ajustes():
    try:
        return json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('carpeta_drive') or ''
    except (OSError, ValueError):
        return ''


def empaquetar(salida, drive=''):
    v = version()
    os.makedirs(salida, exist_ok=True)
    destino = os.path.join(salida, f"{NOMBRE}_v{v}_{time.strftime('%Y-%m-%d')}.zip")
    n = 0
    with zipfile.ZipFile(destino + '.tmp', 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in archivos_de_la_app():
            if rel.split('/')[0] in FUERA or rel in FUERA_ARCHIVOS:
                continue
            ruta = os.path.join(RAIZ, *rel.split('/'))
            if os.path.isfile(ruta):
                z.write(ruta, f'{NOMBRE}/{rel}')
                n += 1
    os.replace(destino + '.tmp', destino)
    copia = ''
    if drive:
        os.makedirs(drive, exist_ok=True)
        copia = os.path.join(drive, os.path.basename(destino))
        shutil.copy2(destino, copia)
    return {'version': v, 'zip': destino, 'archivos': n, 'drive': copia}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--salida', default=os.path.join(RAIZ, 'descargas_app'))
    ap.add_argument('--drive', default='', help='carpeta de Google Drive para escritorio donde copiar el zip')
    a = ap.parse_args()
    r = empaquetar(a.salida, a.drive or carpeta_drive_de_ajustes())
    print(f"APP v{r['version']}: {r['zip']} ({r['archivos']} archivos)")
    if r['drive']:
        print(f"Copiado a Drive: {r['drive']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
