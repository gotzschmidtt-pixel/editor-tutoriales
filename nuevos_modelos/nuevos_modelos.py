"""NUEVOS MODELOS: con un video corto tuyo (cajas, pantallas o la lista de equipos), la voz dice que el método sirve
para los modelos más recientes y ese video se ve mientras lo dice.

1. Lee qué modelos se ven en el video: el texto de pantalla (en tu PC) y, si tu IA ve imágenes, lo que ella reconoce.
   Si escribiste los modelos en la app, se usan esos.
2. Arma la frase con tu estilo (la IA, o una frase fija si no hay IA) y la graba con tu voz de ElevenLabs.
3. Mete el video en la pausa entre dos frases, del largo justo de la voz (acelera o congela el video si hace falta),
   y suma su subtítulo. Momento «auto»: después de la frase donde la voz habla de modelos o de para qué equipos
   sirve; si no lo dice, después de la introducción.

Uso: python nuevos_modelos.py --video 8_testimonios.mp4 --modelos nuevos_modelos/modelos.json --srt 3_voz.srt
       --salida 9_modelos.mp4 --ajustes ../../app/ajustes.json
modelos.json: {"MODELOS": [{"archivo": "x.mp4", "momento": "auto", "modelos": "Honor 600, Honor 8 Lite", "frase": ""}]}
"""
import argparse, base64, glob, hashlib, json, os, re, subprocess, sys, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('testimonios', 'voz', 'ia'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import testimonios as te  # noqa: E402

DISPARA = r'modelo|compatible|sirve (para|en|con)|funciona (para|en|con)|equipos|serie|versi[oó]n|android'
MARCAS = r'(honor|huawei|samsung|galaxy|xiaomi|redmi|poco|motorola|moto|oppo|vivo|realme|tecno|infinix|nokia|zte|iphone|pixel|oneplus)'


def cuadros(clip, dur, out, n=12):
    """Un cuadro cada tanto de todo el clip (máx. n) en out/."""
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, 'c_*.jpg')):
        os.remove(f)
    lista = []
    for k in range(n):
        t = dur * (k + 0.5) / n
        f = os.path.join(out, f'c_{k:02d}.jpg')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', clip, '-frames:v', '1', '-q:v', '3', f], check=True)
        lista.append((t, f))
    return lista


def modelos_por_texto(textos):
    """Sin IA: los nombres de marca seguidos de su modelo en el texto leído (Honor 600, Galaxy A15, Redmi Note 13)."""
    vistos = []
    for x in textos:
        for m in re.finditer(MARCAS + r'[\s\-]*((?:[a-z]*\d+[a-z0-9]*|note|magic|lite|pro|plus|max|ultra|x\d+\w*)(?:[\s\-]+(?:lite|pro|plus|max|ultra|note|5g|\d+[a-z]*)){0,2})', x, re.I):
            nombre = ' '.join(w.capitalize() if not re.search(r'\d', w) else w.upper() for w in f'{m.group(1)} {m.group(2)}'.split())
            if nombre.lower() not in (v.lower() for v in vistos):
                vistos.append(nombre)
    return vistos[:8]


def leer_modelos(clip, dur, carpeta, ajustes):
    """Los modelos que se ven en el clip: la IA si ve imágenes (con el texto leído de ayuda), si no el texto de pantalla."""
    import ia
    caps = cuadros(clip, dur, os.path.join(carpeta, 'cuadros'))
    ocr = ia.lector_ocr()
    textos = [' '.join(x[0] for x in ia.leer_textos(ocr, f)) for _, f in caps] if ocr else []
    if ajustes.get('modelo') and ajustes.get('url') and ajustes.get('imagenes', True):
        pedido = ("Son cuadros de un video corto que muestra celulares, sus cajas o una lista de equipos. Texto leído en cada cuadro: "
                  + ' || '.join(t[:200] for t in textos) + "\n\nDi qué modelos de celular se ven (marca y modelo exactos, como "
                  "aparecen; no inventes ninguno). Responde SOLO con un objeto JSON {\"modelos\": [\"Honor 600\", \"Honor 8 Lite\"]}.")
        try:
            r = ia.extraer_json(ia.llamar(ajustes, pedido, [(f'cuadro {k + 1}', f) for k, (_, f) in enumerate(caps)]))
            lista = [str(x).strip() for x in (r.get('modelos', []) if isinstance(r, dict) else r) if str(x).strip()]
            if lista:
                return lista[:8], 'la IA'
        except (SystemExit, ValueError) as e:
            print(f'· la IA no pudo leer los modelos ({str(e)[:160]}); uso el texto de pantalla', flush=True)
    return modelos_por_texto(textos), 'el texto de pantalla'


def lista_es(xs, articulo=''):
    xs = [articulo + x for x in xs]
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' y ' + xs[-1]


def escribir_frase(modelos, ajustes, idea):
    """Una o dos frases con el estilo del canal: el método sirve para los modelos más recientes."""
    fija = (f'Y ojo, que este método también sirve para los modelos más recientes, como {lista_es(modelos, 'el ')}. '
            'Así que no importa si tu equipo es nuevito: aquí también entra.') if modelos else \
           'Y ojo, que este método también sirve para los modelos más recientes, así que no importa si tu equipo es nuevito.'
    if not (ajustes.get('modelo') and ajustes.get('url')):
        return fija
    import ia
    pedido = (ia.ESTILO + "\n\nEscribe la voz en off (1 o 2 frases, máximo 40 palabras) que va mientras se ve un video corto con "
              "los modelos más recientes. Tiene que decir que este método sirve para los modelos más recientes"
              + (f" y nombrar estos, tal cual: {lista_es(modelos)}" if modelos else '') + ". No inventes otros modelos ni datos."
              + (f"\nLo que cuenta el autor del video: {idea[:1500]}" if idea else '') +
              "\nResponde SOLO con un objeto JSON {\"frase\": \"...\"}.")
    try:
        frase = str(ia.extraer_json(ia.llamar({**ajustes, 'imagenes': False}, pedido, [])).get('frase') or '').strip()
        if frase and all(m.lower() in frase.lower() for m in modelos):
            return frase
        print('· la frase de la IA no nombraba todos los modelos; uso la frase fija', flush=True)
    except (SystemExit, ValueError, AttributeError) as e:
        print(f'· la IA no escribió la frase ({str(e)[:160]}); uso la frase fija', flush=True)
    return fija


def voz(frase, carpeta, voz_id='94zOad0g7T7K4oa7zhDq', modelo='eleven_v4'):
    """La frase con tu voz de ElevenLabs (la misma de los bloques). Se guarda y no se vuelve a pagar si no cambió."""
    import voz as vz
    clave = hashlib.sha1(f'{frase}|{voz_id}|{modelo}'.encode()).hexdigest()[:12]
    mp3, al = os.path.join(carpeta, f'voz_{clave}.mp3'), os.path.join(carpeta, f'voz_{clave}.align.json')
    if os.path.exists(mp3) and os.path.exists(al):
        return mp3, json.load(open(al))
    body = json.dumps({'text': frase, 'model_id': modelo, 'language_code': 'es', 'voice_settings': {'stability': 0.5}}).encode()
    req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{voz_id}/with-timestamps?output_format=mp3_44100_128',
                                 data=body, headers={'Content-Type': 'application/json', **vz.CLAVE})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        raise SystemExit(f'ERROR: ElevenLabs respondió {e.code}: {e.read()[:300]}')
    for f in glob.glob(os.path.join(carpeta, 'voz_*')):
        os.remove(f)
    open(mp3, 'wb').write(base64.b64decode(r['audio_base64']))
    json.dump(r.get('alignment'), open(al, 'w'))
    return mp3, r.get('alignment')


def subtitulos(al, inicio):
    """Frases de ~45 caracteres con sus tiempos, como los subtítulos de la voz."""
    ch, s0, e0 = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    out, i, L = [], 0, len(ch)
    while i < L:
        j, corte = i, None
        while j < L and (j - i < 45 or corte is None):
            if ch[j] == ' ':
                corte = j
            if ch[j] in '.?!;' and j - i > 15:
                corte = j + 1; break
            j += 1
        if j >= L:
            corte = L
        txt = ''.join(ch[i:corte]).strip()
        if txt:
            out.append((inicio + s0[i], inicio + e0[corte - 1], txt))
        i = corte
        while i < L and ch[i] == ' ':
            i += 1
    return out


def momento(m, subs, dur):
    m = str(m or 'auto').strip().lower()
    if m == 'auto':
        for a, b, x in subs:  # la primera vez que la voz habla de modelos o de para qué equipos sirve
            if re.search(DISPARA, x, re.I) and a > 5:
                return b
        m = 'inicio'
    if m == 'inicio':  # después de la introducción
        return te.en_pausa(min(40, dur * 0.12), subs, dur)
    return te.momento(m, subs, dur, [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--modelos', required=True)
    ap.add_argument('--srt', default='3_voz.srt')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    a = ap.parse_args()
    try:
        ajustes = json.load(open(a.ajustes, encoding='utf-8'))
    except (OSError, ValueError):
        ajustes = {}
    idea = open('idea.txt', encoding='utf-8').read() if os.path.exists('idea.txt') else ''
    base = te.probar(a.video)
    carpeta = os.path.dirname(os.path.abspath(a.modelos))
    trabajo = os.path.abspath('trabajo_modelos')  # cuadros, voz y lo que se leyó (la carpeta del panel solo guarda tus videos)
    os.makedirs(trabajo, exist_ok=True)
    lista = [x for x in json.load(open(a.modelos, encoding='utf-8')).get('MODELOS', [])
             if os.path.isfile(os.path.join(carpeta, os.path.basename(x.get('archivo') or '')))]
    if not lista:
        raise SystemExit('ERROR: no hay video de nuevos modelos. Súbelo en el panel «Nuevos modelos».')
    x = lista[0]  # un video corto por tutorial
    clip = os.path.join(carpeta, os.path.basename(x['archivo']))
    info = te.probar(clip)
    modelos = [m.strip() for m in re.split(r'[,;\n]+', x.get('modelos') or '') if m.strip()]
    if modelos:
        print(f'Modelos que escribiste: {lista_es(modelos)}', flush=True)
    else:
        modelos, quien = leer_modelos(clip, info['dur'], trabajo, ajustes)
        print(f'Modelos que vio {quien}: {lista_es(modelos) if modelos else "ninguno con nombre claro"}', flush=True)
    frase = (x.get('frase') or '').strip() or escribir_frase(modelos, ajustes, idea)
    print(f'La voz dice: «{frase}»', flush=True)
    json.dump({'modelos': modelos, 'frase': frase}, open(os.path.join(trabajo, 'leido.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    mp3, al = voz(frase, trabajo)
    hablado = float(al['character_end_times_seconds'][-1]) if al else te.probar(mp3)['dur']
    largo = hablado + 0.9  # aire antes y después de la voz
    subs = te.leer_srt(a.srt)
    en = momento(x.get('momento'), subs, base['dur'])
    print(f'Entra en {int(en // 60)}:{int(en % 60):02d} y dura {largo:.1f} s', flush=True)

    W, H, F = base['w'] + base['w'] % 2, base['h'] + base['h'] % 2, base['fps']
    ajuste = (f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,'
              f'fps={F:.3f},format=yuv420p,setsar=1')
    vel = min(4.0, max(1.0, info['dur'] / largo))  # un clip largo se acelera (hasta ×4); uno corto se congela al final
    clip_v = (f"[1:v]setpts=(PTS-STARTPTS)/{vel:.3f},{ajuste},tpad=stop_mode=clone:stop_duration={largo:.2f},"
              f"trim=0:{largo:.2f},setpts=PTS-STARTPTS,fade=t=in:d=0.25,fade=t=out:st={largo - 0.25:.2f}:d=0.25[vm]")
    voz_a = (f"[2:a]aresample=48000,aformat=channel_layouts=stereo,adelay=400:all=1,apad,atrim=0:{largo:.3f},"
             f"loudnorm=I=-16:TP=-1.5,aresample=48000[am]")
    fil = [f"[0:v]trim=0:{en},setpts=PTS-STARTPTS,{ajuste}[v0];[0:a]atrim=0:{en},asetpts=PTS-STARTPTS,aresample=48000,"
           f"aformat=channel_layouts=stereo[a0]", clip_v, voz_a,
           f"[0:v]trim={en},setpts=PTS-STARTPTS,{ajuste}[v2];[0:a]atrim={en},asetpts=PTS-STARTPTS,aresample=48000,"
           f"aformat=channel_layouts=stereo[a2]", '[v0][a0][vm][am][v2][a2]concat=n=3:v=1:a=1[v][a]']
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-stats', '-y', '-i', a.video, '-i', clip, '-i', mp3,
                    '-filter_complex', ';'.join(fil), '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', a.salida], check=True)
    if subs or al:
        srt = os.path.splitext(a.salida)[0] + '.srt'
        nuevos = [(s, e, t) for s, e, t in subs if s < en - 0.01] + (subtitulos(al, en + 0.4) if al else []) + \
                 [(s + largo, e + largo, t) for s, e, t in subs if s >= en - 0.01]
        te.mover_srt(nuevos, [], srt)
    print(f'Listo {a.salida}: el video de nuevos modelos ({largo:.0f} s) con tu voz diciendo que sirve para los más recientes.')


if __name__ == '__main__':
    main()
