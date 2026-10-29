"""«🎙 Limpiar voz»: quita el ventilador, el zumbido y el eco de la habitación de tu voz original o del audio del celular.

Sirve para los tramos donde se escucha el audio grabado (testimonios, tu grabación para transcribir mejor). Tres motores:
  - pc (gratis, sin internet, por defecto): DeepFilterNet, un programa de 27 MB que se baja una sola vez a
    descargas_app/programas (sin PyTorch); si no se puede bajar, el filtro de ruido de ffmpeg (RNNoise o afftdn).
  - ffmpeg: solo los filtros de ffmpeg (lo más rápido, limpia menos).
  - eleven: el aislador de voz de ElevenLabs (en línea, ~1000 créditos por minuto de audio).
El video no se recodifica: solo cambia el audio. El archivo original queda como NOMBRE_sin_limpiar.mp4.

Uso: python limpiar_voz.py --entrada original.mp4 [--motor pc|ffmpeg|eleven] [--salida limpio.mp4]
"""
import argparse, os, shutil, stat, subprocess, sys, tempfile, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRAMAS = os.path.join(RAIZ, 'descargas_app', 'programas')
MODELOS = os.path.join(RAIZ, 'descargas_app', 'modelos')
DF_VERSION = '0.5.6'
DF_URL = {'win32': f'https://github.com/Rikorose/DeepFilterNet/releases/download/v{DF_VERSION}/deep-filter-{DF_VERSION}-x86_64-pc-windows-msvc.exe',
          'linux': f'https://github.com/Rikorose/DeepFilterNet/releases/download/v{DF_VERSION}/deep-filter-{DF_VERSION}-x86_64-unknown-linux-musl'}
RNN_URL = 'https://raw.githubusercontent.com/GregorR/rnnoise-models/master/somnolent-hogwash-2018-09-01/sh.rnnn'
SIN_VENTANA = {'creationflags': 0x08000000} if sys.platform == 'win32' else {}


def bajar(url, destino, que):
    if os.path.exists(destino):
        return destino
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    print(f'· bajo una sola vez {que} a descargas_app (gratis)…', flush=True)
    with urllib.request.urlopen(url, timeout=300) as r, open(destino + '.parcial', 'wb') as f:
        shutil.copyfileobj(r, f)
    os.replace(destino + '.parcial', destino)
    if sys.platform != 'win32':
        os.chmod(destino, os.stat(destino).st_mode | stat.S_IEXEC)
    return destino


def deep_filter():
    url = DF_URL.get('win32' if sys.platform == 'win32' else 'linux' if sys.platform.startswith('linux') else '')
    if not url:
        return None
    try:
        return bajar(url, os.path.join(PROGRAMAS, 'deep-filter' + ('.exe' if sys.platform == 'win32' else '')), 'DeepFilterNet (27 MB)')
    except (OSError, urllib.error.URLError) as e:
        print(f'· no pude bajar DeepFilterNet ({e}); uso el filtro de ffmpeg', flush=True)
        return None


def filtro_ffmpeg():
    """El mejor filtro de ruido de ffmpeg disponible: RNNoise (con su modelo de 300 KB) o afftdn."""
    try:
        m = bajar(RNN_URL, os.path.join(MODELOS, 'rnnoise_sh.rnnn'), 'el modelo de RNNoise (300 KB)')
        ruta = m.replace('\\', '/').replace(':', '\\:')
        return f"highpass=f=70,arnndn=m='{ruta}':mix=0.85,afftdn=nf=-30,loudnorm=I=-16:TP=-1.5"
    except (OSError, urllib.error.URLError):
        return 'highpass=f=70,afftdn=nf=-25:nr=14,loudnorm=I=-16:TP=-1.5'


def tiene_audio(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', f],
                       capture_output=True, text=True, **SIN_VENTANA)
    return bool(r.stdout.strip())


def ff(args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + args, check=True, **SIN_VENTANA)


def limpiar_audio(entrada, wav_salida, motor='pc'):
    """Deja en wav_salida (48 kHz) el audio limpio de `entrada`. Devuelve qué motor se usó."""
    tmp = tempfile.mkdtemp(prefix='limpiar_')
    try:
        if motor == 'eleven':
            sys.path.insert(0, os.path.join(RAIZ, 'sonidos'))
            import sonidos
            crudo = os.path.join(tmp, 'crudo.mp3')
            ff(['-i', entrada, '-vn', '-ac', '1', '-ar', '44100', '-b:a', '128k', crudo])
            limite = '----estudio'
            cuerpo = (f'--{limite}\r\nContent-Disposition: form-data; name="audio"; filename="audio.mp3"\r\n'
                      'Content-Type: audio/mpeg\r\n\r\n').encode() + open(crudo, 'rb').read() + f'\r\n--{limite}--\r\n'.encode()
            req = urllib.request.Request('https://api.elevenlabs.io/v1/audio-isolation', data=cuerpo,
                                         headers={'Content-Type': f'multipart/form-data; boundary={limite}', **sonidos._clave()})
            try:
                limpio = urllib.request.urlopen(req, timeout=600).read()
            except urllib.error.HTTPError as e:
                raise SystemExit(f'ElevenLabs no pudo aislar la voz: error {e.code} {e.read()[:200]}')
            f = os.path.join(tmp, 'limpio.mp3')
            open(f, 'wb').write(limpio)
            ff(['-i', f, '-af', 'loudnorm=I=-16:TP=-1.5', '-ar', '48000', '-ac', '2', wav_salida])
            return 'aislador de voz de ElevenLabs'
        df = deep_filter() if motor == 'pc' else None
        if df:
            crudo = os.path.join(tmp, 'crudo.wav')
            ff(['-i', entrada, '-vn', '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', crudo])
            sale = os.path.join(tmp, 'limpio')
            os.makedirs(sale)
            r = subprocess.run([df, '--output-dir', sale, '--atten-lim-db', '30', crudo], capture_output=True, text=True, **SIN_VENTANA)
            hecho = os.path.join(sale, 'crudo.wav')  # deep-filter lo escribe con el mismo nombre en --output-dir
            if r.returncode == 0 and os.path.exists(hecho):
                ff(['-i', hecho, '-af', 'highpass=f=60,loudnorm=I=-16:TP=-1.5', '-ar', '48000', '-ac', '2', wav_salida])
                return 'DeepFilterNet (en tu PC)'
            print(f'· DeepFilterNet no pudo ({(r.stderr or r.stdout)[-200:]}); uso el filtro de ffmpeg', flush=True)
        ff(['-i', entrada, '-vn', '-af', filtro_ffmpeg(), '-ar', '48000', '-ac', '2', wav_salida])
        return 'filtro de ruido de ffmpeg'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def limpiar_video(entrada, salida=None, motor='pc', respaldo=True):
    """Cambia solo el audio del video por su versión limpia. Sin --salida reemplaza el archivo y deja el de antes
    como NOMBRE_sin_limpiar.ext (una sola vez: si ya está, se limpia desde ese, no desde uno ya limpio)."""
    base, ext = os.path.splitext(entrada)
    previo = base + '_sin_limpiar' + ext
    fuente = previo if salida is None and os.path.exists(previo) else entrada
    if not tiene_audio(fuente):
        print(f'· {os.path.basename(entrada)} no tiene audio: nada que limpiar', flush=True)
        return None
    tmp = tempfile.mkdtemp(prefix='limpiar_v_')
    try:
        wav = os.path.join(tmp, 'limpio.wav')
        que = limpiar_audio(fuente, wav, motor)
        destino = salida or (base + '.limpio' + ext)
        ff(['-i', fuente, '-i', wav, '-map', '0:v?', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest',
            '-movflags', '+faststart', destino])
        if salida is None:
            if respaldo and not os.path.exists(previo):
                os.replace(entrada, previo)
            os.replace(destino, entrada)
            destino = entrada
        print(f'· {os.path.basename(entrada)}: voz limpia con {que}', flush=True)
        return destino
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def deshacer(entrada):
    base, ext = os.path.splitext(entrada)
    previo = base + '_sin_limpiar' + ext
    if os.path.exists(previo):
        os.replace(previo, entrada)
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entrada', nargs='+', required=True, help='uno o más videos (o una carpeta: todos sus .mp4)')
    ap.add_argument('--salida')
    ap.add_argument('--motor', choices=['pc', 'ffmpeg', 'eleven'], default='pc')
    ap.add_argument('--deshacer', action='store_true', help='vuelve a poner el audio de antes (NOMBRE_sin_limpiar)')
    a = ap.parse_args()
    archivos = []
    for e in a.entrada:
        if os.path.isdir(e):
            archivos += sorted(os.path.join(e, f) for f in os.listdir(e)
                               if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm')) and '_sin_limpiar' not in f and '.limpio.' not in f)
        elif os.path.exists(e):
            archivos.append(e)
    if not archivos:
        raise SystemExit('ERROR: no encontré videos para limpiar.')
    for f in archivos:
        if a.deshacer:
            print(f"· {os.path.basename(f)}: {'audio de antes puesto' if deshacer(f) else 'no tenía uno de antes'}", flush=True)
        else:
            limpiar_video(f, a.salida if len(archivos) == 1 else None, a.motor)


if __name__ == '__main__':
    main()
