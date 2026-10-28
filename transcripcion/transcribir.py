"""Transcribe la voz de un video a texto con tiempos por palabra (para guion y subtítulos).

Motores:
  scribe   ElevenLabs Scribe, en línea, el mejor con español latino y ruido de taller.
  whisper  faster-whisper en tu PC, gratis y sin internet (pip install faster-whisper).
  alinear  ElevenLabs Forced Alignment: no transcribe; toma el .txt que corregiste a mano y le pone el tiempo exacto
           de cada palabra (útil después de Whisper). Deja la versión anterior en *.antes_alinear.

Uso:
  python3 transcribir.py --video "Mi video.mp4" --salida mi_video [--motor scribe|whisper] [--modelo large-v3-turbo]
Escribe mi_video.txt (texto), mi_video.srt (subtítulos) y mi_video.json (palabras con inicio y fin).
"""
import argparse, json, os, re, shutil, subprocess, tempfile, urllib.error, urllib.request, uuid

# En tu PC: define la variable ELEVENLABS_API_KEY. En el entorno de Claude la clave la pone el proxy.
def _clave():
    """La clave de ElevenLabs: la variable ELEVENLABS_API_KEY o la guardada con el botón 🔑 de la app."""
    k = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if k:
        return k, 'variable ELEVENLABS_API_KEY'
    aj = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'ajustes.json')
    try:
        k = json.load(open(aj, encoding='utf-8')).get('elevenlabs', '').strip()
    except (OSError, ValueError):
        k = ''
    return k, aj


_K, FUENTE_CLAVE = _clave()
CLAVE = {'xi-api-key': _K} if _K else {}


def audio(video):
    print('Sacando el audio del video (en videos grandes tarda un poco)…', flush=True)
    f = os.path.join(tempfile.mkdtemp(prefix='stt_'), 'audio.mp3')
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', video, '-vn', '-ac', '1', '-ar', '16000', '-b:a', '64k', f])
    if r.returncode != 0 or not os.path.exists(f):
        raise SystemExit('ERROR: no pude sacar el audio. ¿El video tiene sonido? ¿Está instalado ffmpeg?')
    print(f'Audio listo ({os.path.getsize(f) / 1e6:.1f} MB).', flush=True)
    return f


# palabras clave para Scribe v2 (cuesta ~20% más; probado en IOS27_FRP: arregla «modo FU», «Weishe», «RAM Disk»)
PALABRAS_CLAVE = ['modo DFU', 'DFU', 'modo Recovery', 'Exit Recovery', '3uTools', 'iTunes', 'ECID', 'Ramdisk', 'Boot Ramdisk',
                  'Bypass Hello Screen', 'Hello Screen', 'iCloud', 'FRP', 'FRP Files', 'UnlockTool', 'IMEI', 'SSH', 'payload',
                  'Waveshare RP2350', 'Raspberry Pi Pico', 'AliExpress', 'xiaomiunlock.com', 'App Store', 'Face ID',
                  'iPhone', 'Xiaomi', 'Honor', 'PWN', 'Motorola', 'Samsung', 'fastboot', 'modo fastboot', 'ADB',
                  'cuenta Google', 'parche de seguridad', 'Easy-Unlocker']


def palabras_clave():
    # límites de ElevenLabs: hasta 1000, cada una < 50 letras, máximo 5 palabras y sin < > { } [ ] \
    vistas, salida = set(), []
    for k in PALABRAS_CLAVE:
        k = ' '.join(re.sub(r'[<>{}\[\]\\]', ' ', str(k)).split())
        if k and len(k) < 50 and len(k.split()) <= 5 and k.lower() not in vistas:
            vistas.add(k.lower())
            salida.append(k)
    return salida[:1000]


def scribe(f, idioma):
    lim = uuid.uuid4().hex
    campo = lambda n, v: f'--{lim}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode()
    partes = [campo('model_id', 'scribe_v2'), campo('language_code', idioma),
              *[campo('keyterms', k) for k in palabras_clave()],
              f'--{lim}\r\nContent-Disposition: form-data; name="file"; filename="audio.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode(),
              open(f, 'rb').read(), f'\r\n--{lim}--\r\n'.encode()]
    req = urllib.request.Request('https://api.elevenlabs.io/v1/speech-to-text', data=b''.join(partes),
                                 headers={'Content-Type': f'multipart/form-data; boundary={lim}', **CLAVE})
    print('Clave de ElevenLabs: guardada' if _K else 'Clave de ElevenLabs: ninguna', flush=True)
    print('Enviando el audio a ElevenLabs Scribe…', flush=True)
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read()[:300].decode(errors='replace')
        if e.code in (401, 403):
            raise SystemExit('ERROR: ElevenLabs rechazó la clave o falta. Pulsa «🔑 Clave ElevenLabs» arriba en la app y pega tu clave (o define '
                             'ELEVENLABS_API_KEY) y que tenga permiso de Speech to Text. Detalle: ' + cuerpo)
        raise SystemExit(f'ERROR: ElevenLabs respondió {e.code}: {cuerpo}')
    except urllib.error.URLError as e:
        raise SystemExit(f'ERROR: no hay conexión con ElevenLabs ({e.reason}). Revisa tu internet o usa Whisper.')
    return [{'texto': w['text'], 'inicio': w['start'], 'fin': w['end']} for w in r['words'] if w.get('type') == 'word']


def alinear(f, texto):
    """ElevenLabs Forced Alignment: tu texto ya corregido + el audio → el segundo exacto de cada palabra (no vuelve a transcribir)."""
    lim = uuid.uuid4().hex
    partes = [f'--{lim}\r\nContent-Disposition: form-data; name="text"\r\n\r\n'.encode(), texto.encode('utf-8'), b'\r\n',
              f'--{lim}\r\nContent-Disposition: form-data; name="file"; filename="audio.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode(),
              open(f, 'rb').read(), f'\r\n--{lim}--\r\n'.encode()]
    req = urllib.request.Request('https://api.elevenlabs.io/v1/forced-alignment', data=b''.join(partes),
                                 headers={'Content-Type': f'multipart/form-data; boundary={lim}', **CLAVE})
    print('Clave de ElevenLabs: guardada' if _K else 'Clave de ElevenLabs: ninguna', flush=True)
    print('Enviando el audio y tu texto corregido a ElevenLabs Forced Alignment…', flush=True)
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read()[:300].decode(errors='replace')
        if e.code in (401, 403):
            raise SystemExit('ERROR: ElevenLabs rechazó la clave o le falta el permiso «Forced Alignment» (elevenlabs.io → '
                             'Developers → API Keys → editar la clave). Detalle: ' + cuerpo)
        raise SystemExit(f'ERROR: ElevenLabs respondió {e.code}: {cuerpo}')
    except urllib.error.URLError as e:
        raise SystemExit(f'ERROR: no hay conexión con ElevenLabs ({e.reason}). Revisa tu internet.')
    if r.get('loss') is not None:
        print(f'Calidad de la alineación (loss, menos es mejor): {r["loss"]:.3f}', flush=True)
    return [{'texto': w['text'].strip(), 'inicio': w['start'], 'fin': w['end']} for w in r.get('words', []) if w.get('text', '').strip()]


def whisper(f, idioma, modelo):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit('ERROR: Whisper no está instalado. Abre una terminal en la carpeta de la app y escribe:\n'
                         '    python -m pip install faster-whisper\nLuego vuelve a darle a Transcribir.')
    print(f'Cargando Whisper «{modelo}» (la primera vez descarga el modelo, hasta ~1,6 GB)…', flush=True)
    # el modelo queda en descargas_app/modelos (para no bajarlo otra vez y llevarlo a otra PC)
    guardar = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'descargas_app', 'modelos', 'whisper')
    os.makedirs(guardar, exist_ok=True)
    # palabras técnicas de tus tutoriales: sin esto Whisper escribe «modo de feo» por DFU y «3d tools» por 3uTools
    glosario = ('Tutorial de reparación de celulares: modo DFU, modo Recovery, Exit Recovery, 3uTools, iTunes, ECID, Ramdisk, '
                'bypass, Hello Screen, iCloud, FRP, payload, SSH, iPhone, Xiaomi, Honor, Raspberry Pi Pico, UnlockTool.')
    segs, _ = WhisperModel(modelo, compute_type='int8', download_root=guardar).transcribe(f, language=idioma, word_timestamps=True,
                                                                                         initial_prompt=glosario)
    return [{'texto': w.word.strip(), 'inicio': w.start, 'fin': w.end} for s in segs for w in s.words]


def ts(x):
    return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round(x % 1 * 1000)) % 1000:03d}"


def frases(palabras, maximo=42):
    """Agrupa palabras en líneas de subtítulo: corta en puntuación, en pausas o al llegar a ~42 caracteres."""
    out, act = [], []
    for k, w in enumerate(palabras):
        act.append(w)
        txt = ' '.join(x['texto'] for x in act)
        pausa = k + 1 < len(palabras) and palabras[k + 1]['inicio'] - w['fin'] > 0.6
        if len(txt) >= maximo or txt[-1] in '.?!' or pausa or k + 1 == len(palabras):
            out.append((act[0]['inicio'], act[-1]['fin'], txt)); act = []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--motor', choices=['scribe', 'whisper', 'alinear'], default='scribe',
                    help='alinear: usa el texto de <salida>.txt (que corregiste a mano) y le pone los tiempos exactos con Forced Alignment')
    ap.add_argument('--modelo', default='large-v3-turbo', help='solo whisper: tiny, base, small, medium, large-v3, large-v3-turbo (por defecto; la primera vez baja ~1,6 GB)')
    ap.add_argument('--idioma', default='es')
    a = ap.parse_args()
    if a.motor == 'alinear':
        try:
            texto = open(a.salida + '.txt', encoding='utf-8').read().strip()
        except OSError:
            texto = ''
        if not texto:
            raise SystemExit(f'ERROR: para alinear hace falta {a.salida}.txt con el texto corregido. Transcribe primero.')
        for ext in ('.json', '.srt', '.txt'):  # la versión anterior queda de respaldo
            if os.path.exists(a.salida + ext):
                shutil.copyfile(a.salida + ext, a.salida + ext + '.antes_alinear')
    f = audio(a.video)
    if a.motor == 'alinear':
        pal = alinear(f, texto)
    else:
        pal = scribe(f, a.idioma) if a.motor == 'scribe' else whisper(f, a.idioma, a.modelo)
    json.dump(pal, open(a.salida + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    fr = frases(pal)
    open(a.salida + '.txt', 'w', encoding='utf-8').write('\n'.join(t for _, _, t in fr) + '\n')
    open(a.salida + '.srt', 'w', encoding='utf-8').write('\n'.join(f'{k}\n{ts(i)} --> {ts(e)}\n{t}\n' for k, (i, e, t) in enumerate(fr, 1)))
    if not pal:
        print('OJO: no se escuchó ninguna voz en el video (solo ruido o música). La transcripción quedó vacía.')
    print(f'{len(pal)} palabras, {len(fr)} líneas -> {a.salida}.txt / .srt / .json')


if __name__ == '__main__':
    main()
