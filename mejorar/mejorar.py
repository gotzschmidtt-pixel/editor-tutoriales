"""«✨ Mejorar imagen» con Real-ESRGAN: agranda y limpia los cuadros quietos (pausas, miniatura, capturas) con tu tarjeta.

Usa realesrgan-ncnn-vulkan, un programa de 45 MB que se baja una sola vez a descargas_app/programas/realesrgan (gratis, sin
PyTorch). Corre en la tarjeta gráfica (NVIDIA, AMD o Intel, con Vulkan). El cuadro se agranda ×4 con el modelo
realesrgan-x4plus (quita ruido de poca luz y el borroso de la cámara) y se vuelve a su tamaño: queda más nítido y limpio.

Se activa por proyecto en «🎛 Audio e imagen» (edicion.json: "mejorar_imagen": true). Lo usan:
  - el montaje, en las pausas con cuadro quieto («quieto» en el montaje del bloque);
  - la miniatura automática.
Si el programa no corre en tu PC (sin tarjeta con Vulkan), avisa una vez y sigue con el cuadro como estaba.

Uso suelto: python mejorar.py --entrada cuadro.png [--salida mejor.png] [--modelo realesrgan-x4plus]
            python mejorar.py --bajar     (solo baja el programa)
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, urllib.error, urllib.request, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, 'descargas_app', 'programas', 'realesrgan')
VERSION = '20220424'
URL = {'win32': f'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-{VERSION}-windows.zip',
       'linux': f'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-{VERSION}-ubuntu.zip',
       'darwin': f'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-{VERSION}-macos.zip'}
EXE = 'realesrgan-ncnn-vulkan' + ('.exe' if sys.platform == 'win32' else '')
SIN_VENTANA = {'creationflags': 0x08000000} if sys.platform == 'win32' else {}
_FALLO = []  # si ya falló en este proceso, no se vuelve a intentar en cada cuadro


def carpeta_tmp():
    """Los archivos de paso van en descargas_app/tmp y no en el Temp de Windows: en PC1 el antivirus no deja que
    DeepFilterNet ni Real-ESRGAN escriban en Temp («Acceso denegado», «encode image failed»)."""
    d = os.path.join(RAIZ, 'descargas_app', 'tmp')
    os.makedirs(d, exist_ok=True)
    return d


def programa(bajar=True):
    """La ruta del programa (lo baja la primera vez), o None si no se pudo."""
    for raiz, _, archivos in os.walk(CARPETA) if os.path.isdir(CARPETA) else []:
        if EXE in archivos:
            return os.path.join(raiz, EXE)
    plataforma = 'win32' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'
    if not bajar or plataforma not in URL:
        return None
    os.makedirs(CARPETA, exist_ok=True)
    zipf = os.path.join(CARPETA, 'realesrgan.zip')
    print('· bajo una sola vez Real-ESRGAN (45 MB, gratis) a descargas_app\\programas\\realesrgan…', flush=True)
    try:
        with urllib.request.urlopen(URL[plataforma], timeout=600) as r, open(zipf + '.parcial', 'wb') as f:
            shutil.copyfileobj(r, f)
        os.replace(zipf + '.parcial', zipf)
        with zipfile.ZipFile(zipf) as z:
            for n in z.namelist():  # solo dentro de su carpeta
                destino = os.path.realpath(os.path.join(CARPETA, n))
                if not destino.startswith(os.path.realpath(CARPETA) + os.sep):
                    raise ValueError(f'ruta rara en el zip: {n}')
            z.extractall(CARPETA)
        os.remove(zipf)
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, ValueError) as e:
        print(f'· no pude bajar Real-ESRGAN ({e}); sigo sin mejorar la imagen', flush=True)
        return None
    exe = programa(bajar=False)
    if exe and sys.platform != 'win32':
        os.chmod(exe, 0o755)
    return exe


def quieres(d):
    """¿Este proyecto pidió mejorar la imagen? (edicion.json: "mejorar_imagen": true)"""
    try:
        return bool(json.load(open(os.path.join(d, 'edicion.json'), encoding='utf-8')).get('mejorar_imagen'))
    except (OSError, ValueError, AttributeError):
        return False


def imagen(entrada, salida=None, modelo='realesrgan-x4plus', mismo_tamano=True):
    """Mejora una imagen. Devuelve la ruta de la mejorada (salida, o la misma entrada si se reemplaza), o None si no se pudo
    (la entrada queda como estaba)."""
    if _FALLO:
        return None
    exe = programa()
    if not exe:
        _FALLO.append(1)
        return None
    import cv2
    original = cv2.imread(entrada)
    if original is None:
        return None
    h, w = original.shape[:2]
    tmp = tempfile.mkdtemp(prefix='esrgan_', dir=carpeta_tmp())
    try:
        fuente = os.path.join(tmp, 'in.png')
        grande = os.path.join(tmp, 'out.png')
        cv2.imwrite(fuente, original)
        # en tiras chicas, para que entre en tarjetas de 2 GB: en la GTX 1050 de PC1 256 se queda sin memoria
        # («vkQueueSubmit failed -4») y 100 anda; si igual falla, prueba más chico
        for tira in ('256', '100', '32'):
            r = subprocess.run([exe, '-i', fuente, '-o', grande, '-n', modelo, '-t', tira, '-f', 'png'],
                               cwd=os.path.dirname(exe), capture_output=True, text=True, timeout=600, **SIN_VENTANA)
            prueba = cv2.imread(grande) if r.returncode == 0 and os.path.exists(grande) else None
            if prueba is not None and prueba.mean() > 2:  # sin memoria, a veces sale negra aunque «termine bien»
                break
            if os.path.exists(grande):
                os.remove(grande)
        im = cv2.imread(grande) if r.returncode == 0 and os.path.exists(grande) else None
        if im is None:
            _FALLO.append(1)
            print('· Real-ESRGAN no pudo correr en esta PC (¿tarjeta sin Vulkan?): sigo con la imagen como estaba. '
                  + (r.stderr or r.stdout or '').strip()[-200:], flush=True)
            return None
        if mismo_tamano:
            im = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
        destino = salida or entrada
        cv2.imwrite(destino, im)
        return destino
    except (OSError, subprocess.TimeoutExpired) as e:
        _FALLO.append(1)
        print(f'· Real-ESRGAN no pudo ({e}); sigo con la imagen como estaba', flush=True)
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def si_quieres(png, d):
    """Para el montaje: mejora el cuadro solo si el proyecto lo pidió. No falla nunca."""
    if quieres(d) and imagen(png):
        print(f'· cuadro mejorado con Real-ESRGAN: {os.path.basename(png)}', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entrada')
    ap.add_argument('--salida')
    ap.add_argument('--modelo', default='realesrgan-x4plus')
    ap.add_argument('--bajar', action='store_true')
    a = ap.parse_args()
    if a.bajar:
        print(programa() or 'no se pudo bajar')
        return
    if not a.entrada:
        raise SystemExit('falta --entrada')
    print(imagen(a.entrada, a.salida, a.modelo) or 'no se pudo mejorar')


if __name__ == '__main__':
    main()
