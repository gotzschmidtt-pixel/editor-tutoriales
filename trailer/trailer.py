"""Tráiler de inicio ANTES · DURANTE · DESPUÉS (la firma de fabian) hecho con Remotion.

Para cada clip del plan busca, dentro de su ventana del video original, el momento más
nítido y quieto (módulo nitidez) y corta ahí. Luego Remotion pone los sellos animados, los
destellos, el zoom y la placa final; se le agrega una frase con la voz de Mauricio y música.

Uso:
  python3 trailer.py --video original.mp4 --plan plan.json --salida trailer.mp4 \
      [--unir video_final.mp4 --final con_trailer.mp4] [--srt subs.srt]

plan.json: ver ejemplos/pico2_trailer.json. "voz" es opcional (cuesta ~1 crédito por carácter).
Con --unir pega el tráiler delante del video y, con --srt, corre los subtítulos.
"""
import argparse, json, os, re, shutil, subprocess, sys, urllib.request

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

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REMOTION = os.path.join(RAIZ, 'remotion')
PUB = os.path.join(REMOTION, 'public', 'trailer')
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador
from nitidez import analizar, mejor  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
FONDOS = os.path.join(RAIZ, 'mis_conocimientos', 'fondos')


DIAPOS = os.path.join(RAIZ, 'mis_conocimientos', 'diapositivas', 'referencias')
NOMBRE_IDIOMA = {'es': 'español', 'en': 'inglés', 'pt': 'portugués'}


def diapositiva_gpt(d, plan, antes, despues):
    """La placa final hecha entera por gpt-image-2.5-flare con el estilo que eligió fabian (30/10/2026, la de HONOR 8 LITE
    que hizo en ChatGPT): título 3D blanco y dorado, subtítulo en una píldora azul, los dos teléfonos reales (ANTES y
    DESPUÉS), el candado de Google roto y una flecha. Se guarda por texto e idioma en el proyecto: solo se vuelve a pagar
    si cambias el título, el subtítulo o el idioma del video. None si no se puede (sin clave o sin referencia)."""
    import base64, hashlib, urllib.request, uuid
    try:
        refs = [os.path.join(DIAPOS, x) for x in sorted(os.listdir(DIAPOS)) if x.lower().endswith(('.png', '.jpg'))][:2]
        clave = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('ias_guion', {}).get('gpt', {}).get('clave', '')
    except (OSError, ValueError):
        return None
    if not refs or not clave:
        return None
    try:
        idioma = json.load(open(os.path.join(d, 'idioma_video.json'), encoding='utf-8')).get('idioma') or 'es'
    except (OSError, ValueError, AttributeError):
        idioma = 'es'
    titulo, sub = plan.get('titulo') or '', plan.get('subtitulo') or ''
    huella = hashlib.sha1(json.dumps([titulo, sub, idioma, 1], ensure_ascii=False).encode()).hexdigest()[:10]
    final = os.path.join(d, f'diapositiva_{idioma}_{huella}.png')
    if os.path.exists(final):
        return final
    otro = '' if idioma == 'es' else f' (tradúcelos al {NOMBRE_IDIOMA.get(idioma, idioma)}, corto y natural)'
    prompt = ('Diapositiva final 16:9 del tráiler de un video tutorial de YouTube del canal de fabian. La PRIMERA imagen es la '
              'diapositiva que él eligió: copia EXACTAMENTE su estilo (no su texto, y sin el cursor, el botón «Editar» ni el ícono '
              'de compartir que se ven en la captura). Estilo: a la izquierda el título enorme en 3D, primera línea en blanco y el '
              'resto en dorado y amarillo brillante con borde y sombra; debajo el subtítulo en una píldora azul con borde de neón, '
              'con la palabra clave en amarillo; a la derecha los dos teléfonos REALES de este video (las otras imágenes: el '
              'bloqueado con «Verifica tu cuenta» y el libre con la pantalla de inicio), una flecha azul curva del bloqueado al '
              'libre, y entre ellos el candado de Google 3D rompiéndose con pedazos; fondo azul oscuro con luces de neón y piso que '
              f'refleja. Texto perfectamente escrito{otro}: título «{titulo}», subtítulo «{sub}». Ningún otro texto. Todo el diseño '
              'completo dentro de la imagen 16:9, sin cortar nada en los bordes.')
    imgs = refs[:1] + [x for x in (antes, despues) if x and os.path.exists(x)]
    b = uuid.uuid4().hex
    cuerpo = b''
    for campo, v in {'model': 'gpt-image-2.5-flare', 'prompt': prompt, 'size': '1536x864', 'quality': 'high', 'output_format': 'png'}.items():
        cuerpo += f'--{b}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{v}\r\n'.encode()
    for i, r in enumerate(imgs):
        tipo = 'image/jpeg' if r.lower().endswith('.jpg') else 'image/png'
        cuerpo += (f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="ref{i}{os.path.splitext(r)[1]}"\r\n'
                   f'Content-Type: {tipo}\r\n\r\n').encode() + open(r, 'rb').read() + b'\r\n'
    cuerpo += f'--{b}--\r\n'.encode()
    req = urllib.request.Request('https://api.openai.com/v1/images/edits', data=cuerpo,
                                 headers={'Authorization': 'Bearer ' + clave, 'Content-Type': f'multipart/form-data; boundary={b}'})
    print(f'· la IA de imágenes hace la placa final en {NOMBRE_IDIOMA.get(idioma, idioma)} (solo la primera vez con este título)…', flush=True)
    try:
        r = json.load(urllib.request.urlopen(req, timeout=400))
    except Exception as e:  # sin la diapositiva de GPT, la placa sale como antes: el tráiler no se frena
        print(f'· no pude hacer la placa con la IA ({str(e)[:150]}); va la de siempre', flush=True)
        return None
    crudo = final + '.crudo.png'
    open(crudo, 'wb').write(base64.b64decode(r['data'][0]['b64_json']))
    ff(['-i', crudo, '-vf', 'crop=iw:iw*9/16,scale=1920:1080', final])
    os.remove(crudo)
    return final


def fondo_de_marca(d):
    """El fondo de la placa final para la marca del proyecto (mis_conocimientos/fondos/fondos.json); None si no hay."""
    try:
        import conocimiento
        marca = (conocimiento.marca_de_proyecto(d) or '').lower()
        lista = json.load(open(os.path.join(FONDOS, 'fondos.json'), encoding='utf-8')).get('fondos', [])
    except Exception:
        return None
    f = next((os.path.join(FONDOS, x['archivo']) for x in lista if marca and str(x.get('marca', '')).lower() == marca), None)
    return f if f and os.path.isfile(f) else None
sys.path.insert(0, os.path.join(RAIZ, 'sonidos'))
import sonidos  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
import pronunciacion  # noqa: E402  FRP, DFU… dichos como en el resto del video

VOZ_ID = os.environ.get('VOZ_ID') or '94zOad0g7T7K4oa7zhDq'  # Mauricio, o la del idioma de la versión
IDIOMA = os.environ.get('VOZ_IDIOMA', '')
CIERRE = 2.4


def ff(args):
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + args, check=True)


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True, check=True).stdout)


def voz(texto, destino):
    body = json.dumps({'text': texto, 'model_id': 'eleven_v4', 'voice_settings': {'stability': 0.5},
                       **({'language_code': IDIOMA} if IDIOMA else {}), **pronunciacion.para_pedido(texto, CLAVE)}).encode()
    req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{VOZ_ID}?output_format=mp3_44100_128',
                                 data=body, headers={'Content-Type': 'application/json', **CLAVE})
    open(destino, 'wb').write(urllib.request.urlopen(req, timeout=120).read())


def correr_srt(srt, seg, destino):
    def mover(m):
        h, mi, s, ms = map(int, m.groups())
        t = h * 3600 + mi * 60 + s + ms / 1000 + seg
        return f"{int(round(t * 1000)) // 3600000:02d}:{int(round(t * 1000)) // 60000 % 60:02d}:{int(round(t * 1000)) // 1000 % 60:02d},{int(round(t * 1000)) % 1000:03d}"
    crudo = open(srt, 'rb').read()
    try:
        texto = crudo.decode('utf-8')
    except UnicodeDecodeError:  # subtítulos hechos antes en Windows con su codificación vieja
        texto = crudo.decode('cp1252', errors='replace')
    open(destino, 'w', encoding='utf-8').write(re.sub(r'(\d\d):(\d\d):(\d\d),(\d\d\d)', mover, texto))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--unir')
    ap.add_argument('--final')
    ap.add_argument('--srt')
    ap.add_argument('--donde', choices=['inicio', 'final'], default='inicio', help='el tráiler abre el video o lo cierra')
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding='utf-8'))
    shutil.rmtree(PUB, ignore_errors=True); os.makedirs(PUB)
    nt = analizar(a.video, os.path.join(PUB, 'original.nitidez.npz'))

    clips = []
    for k, c in enumerate(plan['clips'], 1):
        t0, t1 = c['ventana']
        centro = mejor(*nt, t0, t1)
        ini = min(max(t0, centro - c['dur'] / 2), max(t0, t1 - c['dur']))
        ff(['-ss', str(ini), '-t', str(c['dur'] + 0.2), '-i', a.video, '-an', '-vf',
            'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,framerate=fps=25,format=yuv420p',
            '-c:v', 'libx264', '-crf', '16', '-preset', 'veryfast', os.path.join(PUB, f'c{k}.mp4')])
        clips.append({'src': f'trailer/c{k}.mp4', 'dur': c['dur'], 'fase': c['fase']})
        print(f"{c['fase']:8s} {ini:6.1f}s")
    total = sum(c['dur'] for c in clips) + CIERRE

    # audio: música con entrada fuerte y salida suave; la voz encima, con la música agachada
    mus = plan.get('musica')
    fija = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mis_musica', 'musica_fija.mp3')
    if mus and not os.path.exists(mus['pista']) and os.path.exists(fija):
        mus = {**mus, 'pista': fija}  # sin música propia del proyecto, la misma de tus videos (mis_musica\musica_fija.mp3)
    if mus and not os.path.exists(mus['pista']):
        print('AVISO: no encontré la música del tráiler, va sin música'); mus = None
    filtros, ins = [], []
    if mus:
        ins += ['-ss', str(mus.get('desde', 0)), '-i', mus['pista']]
        filtros.append(f"[0:a]atrim=0:{total},afade=t=in:d=0.3,afade=t=out:st={total - 1.2}:d=1.2,volume=0.55[m]")
    if plan.get('voz'):
        # la voz se guarda junto a la salida y se reutiliza mientras el texto no cambie
        vf = os.path.splitext(a.salida)[0] + '.voz.mp3'
        previo = open(vf + '.txt', encoding='utf-8').read() if os.path.exists(vf) and os.path.exists(vf + '.txt') else None
        firma = plan['voz'] + (f'|{VOZ_ID}|{IDIOMA}' if IDIOMA else '')  # en otro idioma, también si cambió la voz
        if previo != firma:
            voz(plan['voz'], vf); open(vf + '.txt', 'w', encoding='utf-8').write(firma)
        iv = ins.count('-i'); ins += ['-i', vf]
        filtros.append(f"[{iv}:a]adelay=300:all=1,apad[v]")
        if mus:
            filtros.append('[v]asplit=2[v1][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=5:release=300[md];'
                           '[v1][md]amix=inputs=2:normalize=0:duration=longest[x]')
        else:
            filtros.append('[v]anull[x]')
    elif mus:
        filtros.append('[m]anull[x]')
    # 'audio' siempre va: si faltara, Remotion usa el de ejemplo (trailer/audio.mp3) y sin voz ni música fallaba con un 404
    props = {'clips': clips, 'titulo': plan['titulo'], 'subtitulo': plan.get('subtitulo'), 'audio': ''}
    d_proy = os.path.dirname(os.path.abspath(a.plan))
    # la placa final: la de GPT con el estilo que eligió fabian; si no se puede, el fondo de la marca con el título encima
    ref_a, ref_d = os.path.join(PUB, 'ref_antes.png'), os.path.join(PUB, 'ref_despues.png')
    ff(['-sseof', '-0.1', '-i', os.path.join(PUB, 'c1.mp4'), '-frames:v', '1', ref_a])
    ff(['-sseof', '-0.1', '-i', os.path.join(PUB, f'c{len(clips)}.mp4'), '-frames:v', '1', ref_d])
    diapo = diapositiva_gpt(d_proy, plan, ref_a, ref_d) if plan.get('diapositiva_gpt') is True else None
    if diapo:
        shutil.copyfile(diapo, os.path.join(PUB, 'diapositiva.png'))
        props['diapositiva'] = 'trailer/diapositiva.png'
        print(f'· placa final de GPT: {os.path.basename(diapo)}', flush=True)
    # los sellos ANTES / DURANTE / DESPUÉS dibujados por GPT 2.5 (los de la miniatura, guardados para todos los videos)
    sellos = {}
    for fase, color in (('ANTES', 'rojo'), ('DURANTE', 'naranja'), ('DESPUÉS', 'verde')):
        n = {'ANTES': 'antes', 'DURANTE': 'durante', 'DESPUÉS': 'despues'}[fase]
        f = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'etiquetas', f'{n}_{color}.png')
        if os.path.exists(f):
            shutil.copyfile(f, os.path.join(PUB, f'sello_{n}.png'))
            sellos[fase] = f'trailer/sello_{n}.png'
    if sellos:
        props['sellos'] = sellos
    try:  # dónde van los sellos (lo eliges en «🎬 Tráiler»)
        props['selloLugar'] = json.load(open(os.path.join(d_proy, 'edicion.json'), encoding='utf-8')).get('sello_lugar') or 'arriba-izquierda'
    except (OSError, ValueError):
        props['selloLugar'] = 'arriba-izquierda'
    fondo = None if diapo else fondo_de_marca(d_proy)
    if fondo:  # «fondo Honor», «fondo Motorola»…: el de la marca, detrás del título (pedido de fabian, 30/10/2026)
        shutil.copyfile(fondo, os.path.join(PUB, 'fondo' + os.path.splitext(fondo)[1]))
        props['fondo'] = 'trailer/fondo' + os.path.splitext(fondo)[1]
        print(f'· placa final con el fondo de la marca: {os.path.basename(fondo)}', flush=True)
    if filtros:
        filtros.append(f"[x]atrim=0:{total},loudnorm=I=-15:TP=-1.5,aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo[a]")
        ff(ins + ['-filter_complex', ';'.join(filtros), '-map', '[a]', '-ar', '48000', os.path.join(PUB, 'audio.wav')])
        props['audio'] = 'trailer/audio.wav'
    sfx = sonidos.del_trailer(clips, os.path.dirname(os.path.abspath(a.salida)))  # golpe en los sellos (si activaste los sonidos)
    if sfx:
        sonidos.superponer(os.path.join(PUB, 'audio.wav'), sfx, total)
        props['audio'] = 'trailer/audio.wav'

    tmp_node = codificar.temporal('trailer_node')
    env = codificar.env_temporal(os.environ, tmp_node)
    chrome = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
    if os.path.exists(chrome):
        env.setdefault('REMOTION_CHROME', chrome)
    # los datos van en un archivo: en Windows npx es un .cmd y el texto JSON en la línea de comandos se rompía con & % ^ | < >
    f_props = os.path.join(tmp_node, 'props.json')
    json.dump(props, open(f_props, 'w', encoding='utf-8'), ensure_ascii=False)
    # con pista de audio aunque no haya voz ni música: sin ella no se puede pegar al video (que sí tiene audio)
    subprocess.run([shutil.which('npx') or 'npx', 'remotion', 'render', 'src/index.ts', 'Trailer', os.path.abspath(a.salida),
                    '--props', f_props, '--crf', '18', '--enforce-audio-track'], cwd=REMOTION, env=env, check=True)
    shutil.rmtree(tmp_node, ignore_errors=True)

    if a.unir and a.final:
        n = duracion(a.salida)
        primero, segundo = (a.salida, a.unir) if a.donde == 'inicio' else (a.unir, a.salida)
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=avg_frame_rate',
                            '-of', 'csv=p=0', a.unir], capture_output=True, text=True).stdout.strip() or '25'
        fps = r if re.fullmatch(r'\d+(/\d+)?', r) and r not in ('0', '0/0') else '25'  # los del video (30 si grabaste a 60)
        ff(['-i', primero, '-i', segundo, '-filter_complex',
            f'[0:v]framerate=fps={fps},format=yuv420p,setsar=1[v0];[1:v]fps={fps},format=yuv420p,setsar=1[v1];'
            '[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]',
            '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k', a.final])
        if a.srt:  # al inicio, los subtítulos se corren lo que dura el tráiler; al final quedan igual
            correr_srt(a.srt, n if a.donde == 'inicio' else 0, os.path.splitext(a.final)[0] + '.srt')
        print(f"tráiler {n:.1f}s pegado {'delante' if a.donde == 'inicio' else 'al final'}: {a.final}")


if __name__ == '__main__':
    main()
