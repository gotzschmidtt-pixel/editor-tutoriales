"""«📱 3 Shorts resumen» (pedido de fabian, 02/11/2026: «no has hecho un resumen del video del proceso completo para cada
uno… ¿puede la app hacer esto?»). En vez de un trozo del guion por Short, la app hace 3 Shorts de ~55-60 s que cuentan el
proceso COMPLETO, cada uno con un gancho distinto:
  1. «antes y después» (el problema y cómo terminó), 2. «en 1 minuto» (pasos numerados), 3. «¿ya probaste todo?».

Pasos (nada gasta hasta que fabian aprueba):
  1. proponer(): la IA de texto de «⚙ Ajustes IA» (centavos) lee el guion del video largo y el mapa del video y escribe los 3
     guiones, frase por frase, con la toma del grabado que muestra cada frase y los títulos/descripciones ES/EN/PT.
     Reglas de fabian: versiones de Android y MagicOS en una frase «con cualquier parche», nunca «SIN PC», máx. 3 emociones,
     cierre al tutorial completo, ~750-820 letras. Queda en shorts_resumen.json (editable en la app).
  2. costo(): letras de voz = créditos de ElevenLabs, a la vista antes de gastar.
  3. voz(): solo con confirmar=True (el SI de fabian): voz Mauricio en voz_short/S<n>F<k>.mp3.
  4. armar(): gratis. Cada frase con sus tomas en planos de ≤ 4,5 s (la ventana del programa con zoom guiado si hay
     short_encuadres.json), subtítulos estilo C +50 %, música fija, sin difuminados ni portada. Deja SHORT_RESUMEN_<n>.mp4 y
     shorts_resumen_textos.txt (WhatsApp primero, hashtags y comentario fijado).
"""
import json, math, os, re, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
ARCHIVO = 'shorts_resumen.json'
GANCHOS = [('antes_despues', 'Antes y después: empieza diciendo que el teléfono estaba bloqueado y «mira cómo terminó»'),
           ('un_minuto', 'En 1 minuto: el proceso como pasos numerados («Paso uno… paso cuatro»)'),
           ('ya_probaste', '¿Ya probaste todo?: le habla al que ya intentó TalkBack, Bluetooth y códigos sin resultado')]
EMOCION = re.compile(r'\[[a-z ]+\]\s*')
TROZO, AIRE, RETRASO = 4.5, 0.3, 0.1
FIN = {'es': 'Tutorial completo en mi canal (link en el comentario fijado).', 'en': 'Full tutorial on my channel (link in the pinned comment).',
       'pt': 'Tutorial completo no meu canal (link no comentário fixado).'}
FIJADO = {'es': '📌 Tutorial completo paso a paso: (pega aquí el enlace del video largo cuando lo subas)',
          'en': '📌 Full step-by-step tutorial: (paste the long video link here once it is up)',
          'pt': '📌 Tutorial completo passo a passo: (cole aqui o link do vídeo longo quando ele estiver no ar)'}


def _llamar_ia(texto):
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    return ia.llamar(json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')), texto, [])


def _json(txt):
    m = re.search(r'\{.*\}', txt or '', re.S)
    return json.loads(m.group(0)) if m else {}


def letras(texto):
    return len(EMOCION.sub('', texto or '').strip())


def _modelo(d):
    try:
        return (json.load(open(os.path.join(d, 'youtube', 'metadatos.json'), encoding='utf-8')).get('modelo') or '').strip()
    except (OSError, ValueError):
        return ''


def prompt(d):
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    bloques = [{'id': b['id'], 'src': (b.get('montaje') or {}).get('src_inicio'), 'texto': b.get('texto', '')} for b in g['bloques']]
    try:
        mapa = [{'t': round(float(c.get('t') or 0)), 'pantalla': str(c.get('texto') or c.get('pantalla') or '')[:80]}
                for c in json.load(open(os.path.join(d, 'mapa_video.json'), encoding='utf-8')).get('cuadros', [])]
    except (OSError, ValueError):
        mapa = []
    modelo = _modelo(d) or os.path.basename(os.path.abspath(d))
    ganchos = '\n'.join(f'{i + 1}. {n}: {t}' for i, (n, t) in enumerate(GANCHOS))
    return f"""Escribe 3 guiones de YouTube Shorts (voz en off, español latino, tuteando) para el video «{modelo}».
Cada Short cuenta el proceso COMPLETO de principio a fin en 55-60 s (entre 750 y 820 letras de voz), con un gancho distinto:
{ganchos}
Reglas obligatorias de fabian:
- Una frase corta con las versiones: «Android quince, dieciséis, diecisiete o superior, y MagicOS nueve, diez u once, con cualquier parche» (adáptala a la marca si no es Honor).
- NUNCA digas «sin PC». Números escritos como se dicen. Nombra el modelo como «{modelo}».
- Máximo 3 etiquetas de emoción por guion entre corchetes en inglés ([curious], [excited], [serious]), nunca dos seguidas.
- La última frase manda al tutorial completo del canal.
- No inventes datos: usa solo lo que dice el guion del video largo.
Para cada frase da las tomas del grabado original (segundos [desde, hasta], 3-5 s cada una) que muestran EXACTAMENTE lo que dice,
usando los segundos del guion (src) y del mapa de pantallas.
Además, para cada Short: título (máx. 70 letras, sin emojis, sin < > ni comillas) y una descripción de 1-2 frases, en es, en y pt.
GUION DEL VIDEO LARGO: {json.dumps(bloques, ensure_ascii=False)}
MAPA DE PANTALLAS (segundo, lo que se lee): {json.dumps(mapa[:150], ensure_ascii=False)}
Responde SOLO con JSON: {{"shorts": [{{"gancho": "antes_despues", "frases": [{{"texto": "…", "tomas": [[18, 22]]}}],
"titulos": {{"es": "…", "en": "…", "pt": "…"}}, "descripciones": {{"es": "…", "en": "…", "pt": "…"}}}}, …]}}"""


def validar(r):
    """Lo que no cumple las reglas de fabian (lista de avisos); nunca deja pasar «sin PC»."""
    avisos = []
    for n, s in enumerate(r.get('shorts') or [], 1):
        txt = ' '.join(f.get('texto', '') for f in s.get('frases') or [])
        if re.search(r'\bsin\s+pc\b', txt, re.I):
            avisos.append(f'Short {n}: dice «sin PC» (prohibido para este canal)')
        if len(EMOCION.findall(txt)) > 3:
            avisos.append(f'Short {n}: más de 3 emociones')
        if 'parche' not in txt.lower():
            avisos.append(f'Short {n}: falta la frase de versiones «con cualquier parche»')
        if not 650 <= letras(txt) <= 900:
            avisos.append(f'Short {n}: {letras(txt)} letras (lo ideal, 750-820 para 55-60 s)')
        if any(not f.get('tomas') for f in s.get('frases') or []):
            avisos.append(f'Short {n}: hay frases sin toma')
    return avisos


def proponer(d, llamar=None):
    r = _json((llamar or _llamar_ia)(prompt(d)))
    if not r.get('shorts'):
        raise ValueError('La IA no devolvió los 3 guiones; prueba de nuevo.')
    r['avisos'] = validar(r)
    r['costo'] = costo(r)
    json.dump(r, open(os.path.join(d, ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return r


def leer(d):
    try:
        return json.load(open(os.path.join(d, ARCHIVO), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def guardar(d, r):
    r['avisos'], r['costo'] = validar(r), costo(r)
    json.dump(r, open(os.path.join(d, ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return r


def costo(r):
    """{'letras': n, 'creditos': n}: ElevenLabs cobra ~1 crédito por letra (las etiquetas de emoción no se leen)."""
    n = sum(letras(f.get('texto', '')) for s in r.get('shorts') or [] for f in s.get('frases') or [])
    return {'letras': n, 'creditos': n}


def voz(d, confirmar=False):
    """La voz Mauricio de las frases (GASTA ElevenLabs). Solo con confirmar=True, después del SI de fabian."""
    if not confirmar:
        raise PermissionError('La voz gasta créditos de ElevenLabs: hace falta la confirmación de fabian.')
    r = leer(d)
    bloques = [{'id': f'S{n}F{k}', 'texto': f['texto'], 'tipo': 'libre', 'humor': False,
                'montaje': {'modo': 'lento', 'src_inicio': float(f['tomas'][0][0]), 'src_fin': float(f['tomas'][0][0]) + 30,
                            'velocidad': 1.0, 'congelar_s': None}}
               for n, s in enumerate(r['shorts'], 1) for k, f in enumerate(s['frases'], 1)]
    g = os.path.join(d, '.shorts_resumen_guion.json')
    json.dump({'bloques': bloques}, open(g, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(RAIZ, 'voz', 'voz.py'), '--guion', g, '--salida', os.path.join(d, 'voz_short')],
                   check=True, cwd=d)


def _encuadre(encuadres, s0):
    """La referencia de encuadre guiado (short_encuadres.json) cuyo rango del grabado contiene s0, si hay."""
    for conf in encuadres.values():
        rango = conf.get('rango')
        if conf.get('referencia') and rango and rango[0] <= s0 <= rango[1]:
            return conf
    return None


def armar(d, cuales=(1, 2, 3)):
    """Gratis (la voz ya está hecha). Deja SHORT_RESUMEN_<n>.mp4 y shorts_resumen_textos.txt."""
    import cv2
    import short
    import codificar
    r = leer(d)
    orig = os.path.join(d, 'original.mp4')
    try:
        encuadres = json.load(open(os.path.join(d, 'short_encuadres.json'), encoding='utf-8'))
    except (OSError, ValueError):
        encuadres = {}
    hechos = []
    for n in cuales:
        s = r['shorts'][n - 1]
        cap = cv2.VideoCapture(orig)
        marcas, memoria = short.marcas_autor(d), short.deteccion.Memoria(orig)
        tmp = tempfile.mkdtemp()
        partes, tomas = [], []
        for k, f in enumerate(s['frases'], 1):
            bid = f'S{n}F{k}'
            mp3 = os.path.join(d, 'voz_short', f'{bid}.mp3')
            largo = round(short.duracion(mp3) + AIRE, 2)
            piezas, cada = [], largo / len(f['tomas'])
            for a, _b in f['tomas']:
                m = max(1, math.ceil(cada / TROZO))
                piezas += [(float(a) + j * cada / m, cada / m) for j in range(m)]
            lista = []
            for j, (s0, dur) in enumerate(piezas):
                conf = _encuadre(encuadres, s0)
                guiado = short.seguir_ref(cap, s0, dur, conf, d) if conf else None
                claves, zoom, _ = guiado or short.seguir(cap, s0, dur, marcas, memoria)
                ch = round(short.H / zoom / 2) * 2
                cw = round(ch * 9 / 16 / 2) * 2
                cl = [(t, x - cw / 2, y - ch / 2) for t, x, y in claves]
                vf = (f"crop={cw}:{ch}:x='{short.expr(cl, 1, 0, short.W - cw)}':y='{short.expr(cl, 2, 0, short.H - ch)}',"
                      f'scale={short.SW}:{short.SH},setsar=1,fps=30,format=yuv420p')
                p = os.path.join(tmp, f'v{k:02d}_{j:02d}.mp4')
                codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{dur:.3f}', '-i', orig, '-vf', vf,
                               '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', p], check=True)
                lista.append(p)
            lf = os.path.join(tmp, f'l{k:02d}.txt')
            open(lf, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n".replace('\\', '/') for p in lista))
            p = os.path.join(tmp, f'p{k:02d}.mp4')
            codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lf, '-i', mp3,
                           '-filter_complex', f'[1:a]adelay={int(RETRASO * 1000)}:all=1,apad,atrim=0:{largo:.3f},'
                           'aresample=44100,aformat=channel_layouts=stereo[a]', '-map', '0:v', '-map', '[a]', '-t', f'{largo:.3f}',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-c:a', 'aac', '-b:a', '160k', p], check=True)
            partes.append(p)
            tomas.append({'id': bid, 'carpeta': 'voz_short', 'largo': largo, 'texto': f['texto']})
        cap.release()
        memoria.guardar()
        lista = os.path.join(tmp, 'lista.txt')
        open(lista, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n".replace('\\', '/') for p in partes))
        junto = os.path.join(tmp, 'junto.mp4')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', junto],
                       check=True)
        ass = f'short_resumen_{n}_subs.ass'
        open(os.path.join(d, ass), 'w', encoding='utf-8').write(short.subtitulos(d, tomas, RETRASO))
        entradas, audio = ['-i', junto], '[0:a]anull[a]'
        if os.path.exists(short.MUSICA):
            entradas += ['-stream_loop', '-1', '-i', short.MUSICA]
            audio = '[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]'
        salida = f'SHORT_RESUMEN_{n}.mp4'
        codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                      ['-filter_complex', f'[0:v]ass={ass}[v];{audio}', '-map', '[v]', '-map', '[a]', '-c:v', 'libx264',
                       '-preset', 'medium', '-crf', '19', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', salida],
                      check=True, cwd=d)
        short.poner_logos(d, tomas, os.path.join(d, salida), RETRASO)  # logos de lo que nombra la voz
        hechos.append({'archivo': salida, 'duracion': round(short.duracion(os.path.join(d, salida)), 1),
                       'revision': _revisar(d, salida, ass)})
    textos(d, r)
    return hechos


def _revisar(d, salida, ass):
    """«✅ Revisor automático» sobre el Short recién armado; sin ❌ graves no queda como listo."""
    sys.path.insert(0, os.path.join(RAIZ, 'revision'))
    try:
        import revisor_auto
        inf = revisor_auto.revisar(os.path.join(d, salida), os.path.join(d, ass), True)
        return {'ok': inf['ok'], 'informe': os.path.splitext(salida)[0] + '.revision.md'}
    except Exception as e:
        return {'ok': False, 'informe': None, 'error': str(e)}


def textos(d, r=None):
    """Títulos y descripciones ES/EN/PT de los Shorts: WhatsApp primero, cierre al tutorial, hashtags y comentario fijado."""
    import youtube
    r = r or leer(d)
    modelo = re.sub(r'\W', '', _modelo(d).replace('Honor', '')) or 'Honor'
    hs = {'es': f'#Honor #FRP #CuentaGoogle #{modelo}', 'en': f'#Honor #FRPBypass #GoogleAccount #{modelo}',
          'pt': f'#Honor #FRP #ContaGoogle #{modelo}'}
    out = []
    for n, s in enumerate(r.get('shorts') or [], 1):
        out.append(f'===== SHORT_RESUMEN_{n}.mp4 ({s.get("gancho", "")}) =====')
        for k in ('es', 'en', 'pt'):
            t = youtube.limpiar_yt((s.get('titulos') or {}).get(k, ''))
            t = youtube.signos_es(t) if k == 'es' else t
            desc = youtube.limpiar_yt(youtube.con_contacto(f"{(s.get('descripciones') or {}).get(k, '')}\n\n{FIN[k]}\n\n{hs[k]}", k))
            out += [f'--- {k.upper()} ---', 'TÍTULO: ' + t, 'DESCRIPCIÓN:', desc, 'COMENTARIO FIJADO:', FIJADO[k], '']
    open(os.path.join(d, 'shorts_resumen_textos.txt'), 'w', encoding='utf-8').write('\n'.join(out))
    return '\n'.join(out)


# ------------------------------------------------------------------ la pestaña de la app («📱 3 Shorts resumen»)
ESTADO = {}  # carpeta → {'estado': 'voz'|'armando'|'listo'|'error', 'msg': …}


def _fondo(d, que, fn):
    import threading

    def correr():
        ESTADO[d] = {'estado': que, 'msg': ''}
        try:
            r = fn()
            ESTADO[d] = {'estado': 'listo', 'msg': json.dumps(r, ensure_ascii=False) if r else ''}
        except Exception as e:  # se muestra en la pestaña
            ESTADO[d] = {'estado': 'error', 'msg': str(e)[-500:]}
    threading.Thread(target=correr, daemon=True).start()


def get(h, ruta, q, d):
    if ruta == '/api/shorts_resumen/estado':
        r = leer(d)
        return h.responder({'guion': r, 'costo': costo(r) if r else None, 'trabajo': ESTADO.get(d, {}),
                            'hechos': sorted(f for f in os.listdir(d) if f.startswith('SHORT_RESUMEN_') and f.endswith('.mp4'))})
    return h.error('No existe.')


def post(h, ruta, q, largo, d):
    datos = json.loads(h.rfile.read(largo) or b'{}') if largo else {}
    try:
        if ruta == '/api/shorts_resumen/proponer':  # la IA de texto (centavos): los 3 guiones
            return h.responder(proponer(d))
        if ruta == '/api/shorts_resumen/guardar':  # lo que fabian corrigió a mano
            return h.responder(guardar(d, datos.get('guion') or {}))
        if ruta == '/api/shorts_resumen/voz':  # GASTA ElevenLabs: solo con «confirmo»
            if not datos.get('confirmo'):
                return h.error(f"La voz gasta ~{costo(leer(d))['creditos']} créditos de ElevenLabs: confirma primero.")
            _fondo(d, 'voz', lambda: voz(d, confirmar=True))
            return h.responder({'ok': True})
        if ruta == '/api/shorts_resumen/armar':  # gratis
            _fondo(d, 'armando', lambda: armar(d))
            return h.responder({'ok': True})
    except Exception as e:
        return h.error(str(e))
    return h.error('No existe.')
