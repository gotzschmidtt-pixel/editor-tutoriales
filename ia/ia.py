"""La parte creativa con la IA que tú elijas: GPT, DeepSeek, Gemini u Ollama (local).

Arma el encargo (prompt) con tu transcripción, capturas nítidas del video y el formato exacto
del JSON que espera la app, y luego revisa y corrige lo que la IA devuelve (tiempos, frases que no
existen en el guion, ventanas fuera del video).

Dos modos:
  prompt  escribe ia_prompt_<tarea>.txt y las capturas en ia_capturas/, para copiar y pegar en el chat que quieras.
  api     lo manda a una API compatible con OpenAI (OpenAI, DeepSeek, Gemini, Ollama) y guarda el JSON.
  revisar valida y corrige un JSON pegado a mano (el mismo arreglo que se hace en modo api).

Uso:
  python ia.py --proyecto mis_proyectos/x --tarea guion|etiquetas|trailer --modo prompt|api|revisar
               [--ajustes app/ajustes.json] [--idea "de qué trata el video y qué datos son seguros"]
"""
import argparse, base64, json, os, re, subprocess, sys, unicodedata, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
from nitidez import analizar, mejor, repartidos  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'trailer'))
import pistas  # noqa: E402

ARCHIVO = {'guion': 'guion.json', 'etiquetas': 'etiquetas.json', 'trailer': 'trailer.json'}
PALABRAS_POR_S = 2.6

ESTILO = """Estilo de la narración (fabian, tutoriales de reparación de celulares):
- Entretenido y sencillo de entender, en español latino, tuteando.
- Humor picante ligero (doble sentido suave) SOLO fuera de los pasos críticos. En los pasos críticos (pines, archivos, valores) nada de chistes: claro y exacto.
- Al inicio, una invitación con humor a comentar las dudas.
- Nombres de botones, menús y archivos escritos tal cual aparecen en pantalla.
- NO inventes datos: precios, pines, temperaturas, webs o nombres de archivo solo si están en la transcripción, en las capturas o en la idea del autor. Si falta un dato, escribe la frase sin él."""


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True, check=True).stdout)


def normal(c):
    return ''.join(x for x in unicodedata.normalize('NFD', c.lower()) if unicodedata.category(x) != 'Mn')


def capturas(d, n=14):
    """Saca n capturas del video original a ia_capturas/, repartidas por todo el video (de cada tramo, su cuadro
    más nítido) y en los momentos de más movimiento (acciones, cortes). Devuelve [(segundo, ruta)]."""
    orig = os.path.join(d, 'original.mp4')
    t, ni, mo = analizar(orig, os.path.join(d, 'original.nitidez.npz'))
    tiempos = repartidos(t, ni, mo, top=n)
    out = os.path.join(d, 'ia_capturas')
    os.makedirs(out, exist_ok=True)
    quedan = {f'captura_{s:06.1f}s.jpg' for s in tiempos}
    for viejo in os.listdir(out):  # las de una tanda anterior con otra cantidad
        if viejo.startswith('captura_') and viejo not in quedan:
            os.remove(os.path.join(out, viejo))
    lista = []
    for s in tiempos:
        f = os.path.join(out, f'captura_{s:06.1f}s.jpg')
        if not os.path.exists(f):
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(s), '-i', orig, '-frames:v', '1',
                            '-vf', 'scale=768:-2', '-q:v', '4', f], check=True)
        lista.append((s, f))
    return lista


def capturas_pistas(d, an):
    """Las imágenes de las pistas del tráiler y un cuadro nítido en cada segundo candidato, a ia_capturas/.
    Devuelve [(descripción, ruta)] para sumar a las capturas."""
    out = os.path.join(d, 'ia_capturas')
    os.makedirs(out, exist_ok=True)
    for viejo in os.listdir(out):
        if viejo.startswith('pista_'):
            os.remove(os.path.join(out, viejo))
    orig = os.path.join(d, 'original.mp4')
    nt = analizar(orig, os.path.join(d, 'original.nitidez.npz'))
    lista = []
    for fase in pistas.FASES:
        for p in an[fase]:
            nombre = f'{pistas.NOMBRE[fase]} {p["n"]}'
            if p['imagen']:
                f = os.path.join(out, f'pista_{fase}_{p["n"]}.jpg')
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', p['imagen'], '-frames:v', '1',
                                '-vf', 'scale=768:-2', '-q:v', '4', f], check=True)
                lista.append((f'imagen que mandó el autor como pista {nombre}', f))
            for x, _ in p['candidatos'][:3]:
                s = mejor(*nt, max(0, x - 2), x + 2)
                f = os.path.join(out, f'pista_{fase}_{p["n"]}_{s:06.1f}s.jpg')
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(s), '-i', orig, '-frames:v', '1',
                                '-vf', 'scale=768:-2', '-q:v', '4', f], check=True)
                lista.append((f'segundo {s:.1f} del video original (cerca de la pista {nombre})', f))
    return lista


def mmss(s):
    return f'{int(s // 60)}:{int(s % 60):02d}'


def transcripcion(d, largo_max=45000):
    """La transcripción COMPLETA en líneas «[m:ss] texto». Nunca se corta: si es muy larga, se agrupa en
    tramos más largos (menos marcas de tiempo, el mismo texto)."""
    f = os.path.join(d, 'transcripcion.srt')
    if not os.path.exists(f):
        return ''
    lineas = []
    for bloque in re.split(r'\n\s*\n', open(f, encoding='utf-8', errors='replace').read().strip()):
        m = re.search(r'(\d\d):(\d\d):(\d\d)[,.]\d+\s*-->', bloque)
        if m:
            h, mi, s = map(int, m.groups())
            texto = ' '.join(bloque[m.end():].split('\n')[1:]).strip()
            if texto:
                lineas.append((h * 3600 + mi * 60 + s, texto))
    for tramo in (0, 15, 30, 60, 120):
        if tramo:
            juntas = []
            for s, txt in lineas:
                if juntas and s - juntas[-1][0] < tramo:
                    juntas[-1] = (juntas[-1][0], juntas[-1][1] + ' ' + txt)
                else:
                    juntas.append((s, txt))
        else:
            juntas = lineas
        out = '\n'.join(f'[{mmss(s)}] {txt}' for s, txt in juntas)
        if len(out) <= largo_max:
            break
    else:
        print(f'AVISO: la transcripción es muy larga ({len(out)} caracteres); va completa, pero un modelo con poco '
              'contexto podría no leerla entera. Usa un modelo con más contexto o divide el video.', flush=True)
    return out


def ejemplo_guion():
    g = json.load(open(os.path.join(RAIZ, 'proyectos', 'pico2', 'guion_pico_largo.json'), encoding='utf-8'))
    claves = ('id', 'ancla', 'texto', 'montaje')
    return json.dumps({'bloques': [{k: b[k] for k in claves} for b in g['bloques'] if b['id'] in ('L01', 'L04', 'L10', 'L15')]},
                      ensure_ascii=False, indent=1)


def estilo_activo(ajustes):
    """(nombre, perfil.md, perfil.json) del estilo elegido en el panel Alimentación, o None."""
    nombre = (ajustes or {}).get('estilo')
    e = os.path.join(RAIZ, 'mis_estilos', nombre or '')
    if not nombre or not os.path.exists(os.path.join(e, 'perfil.md')):
        return None
    try:
        medidas = json.load(open(os.path.join(e, 'perfil.json'), encoding='utf-8'))
    except (OSError, ValueError):
        medidas = {}
    return nombre, open(os.path.join(e, 'perfil.md'), encoding='utf-8').read(), medidas


def encargo(d, tarea, idea, caps, an=None, estilo=None):
    dur = duracion(os.path.join(d, 'original.mp4'))
    trans = transcripcion(d)
    lista_caps = '\n'.join(f'- Captura {k}: ' + (s if isinstance(s, str) else f'segundo {s:.1f} del video original')
                          for k, (s, _) in enumerate(caps, 1))
    partes = [f"Eres guionista de videos tutoriales de YouTube. Vas a trabajar sobre un video de {dur:.0f} segundos."]
    if idea:
        partes.append(f"Lo que cuenta el autor del video (datos confirmados):\n{idea}")
    partes.append(f"Capturas adjuntas (en orden):\n{lista_caps}")
    if trans:
        partes.append(f"Transcripción COMPLETA de lo que dice el autor en su grabación, de principio a fin ([minuto:segundo] texto):\n{trans}")

    if estilo and tarea in ('guion', 'trailer'):
        partes.append(f"Estilo aprendido de los videos de referencia del autor («{estilo[0]}»). Imítalo en tono, ritmo, "
                      f"aperturas, llamados y cierre, sin copiar datos de otros videos:\n{estilo[1][:9000]}")
    if tarea == 'guion':
        objetivo = idea and re.search(r'(\d+)\s*(?:a\s*\d+\s*)?min', idea)
        partes += [ESTILO, f"""Escribe el guion por bloques. Cada bloque tiene:
- "id": L01, L02, ...
- "ancla": qué se ve en pantalla en ese bloque (corto).
- "texto": lo que dice la voz en off. Unas {PALABRAS_POR_S} palabras por segundo de bloque.
- "montaje": de qué tramo del video ORIGINAL sale la imagen y cómo se estira:
    {{"modo": "lento", "src_inicio": s, "src_fin": s, "velocidad": 0.4 a 1.0}}  (velocidad < 1 = cámara lenta)
    {{"modo": "congelar", "src_inicio": s, "congelar_s": s}}  (pausa en un cuadro; úsalo cuando se explica algo que se ve quieto)
    {{"modo": "lento+congelar", "src_inicio": s, "src_fin": s, "velocidad": v, "congelar_s": s}}
    {{"modo": "imagen", "congelar_s": s}}  (muestra la imagen del proyecto, por ejemplo un mapa)
  Los tramos van en orden, dentro de 0 a {dur:.0f} s, y cubren las partes importantes del video.
{'- Duración total buscada: unos ' + objetivo.group(1) + ' minutos.' if objetivo else '- Duración total: la que necesite el video para entenderse bien, sin relleno.'}
Responde SOLO con un objeto JSON {{"bloques": [...]}}, sin texto alrededor. Ejemplo del formato (de otro video):
{ejemplo_guion()}"""]
    elif tarea == 'etiquetas':
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
        textos = '\n'.join(f"{b['id']}: {b['texto']}" for b in g['bloques'])
        partes += [f"""Este es el guion ya escrito:
{textos}

Elige los datos valiosos que merecen una etiqueta en pantalla: webs, nombres de archivo, precios, pines, valores, botones y consejos.
Para cada uno: "bloque" (id), "frase" (2 a 4 palabras COPIADAS TAL CUAL del texto de ese bloque; la etiqueta aparece cuando la voz las dice),
"tipo" (web | archivo | dato | precio | pin | consejo), "titulo" (1 a 3 palabras), "texto" (el dato, corto), "dur" (3 a 6 segundos)
y, solo para "pin", "color" (hex del color del cable).
Responde SOLO con un objeto JSON {{"etiquetas": [...]}}. Ejemplo de un elemento:
{{"bloque": "L15", "frase": "gsmprime", "tipo": "web", "titulo": "Descarga aquí", "texto": "gsmprime.co", "dur": 4.5}}"""]
    elif tarea == 'trailer':
        partes += [f"""Arma el tráiler de inicio de unos 10 segundos con la firma del autor: ANTES, DURANTE y DESPUÉS.
Muestra lo mejor de lo mejor para que el espectador se quede: ANTES = cómo empieza (pieza suelta, problema), DURANTE = las
tomas más vistosas del proceso, DESPUÉS = el resultado funcionando.
Formato: {{"titulo": "máximo 5 palabras", "subtitulo": "frase corta con gancho", "voz": "una frase de la voz en off, máximo 15 palabras",
"clips": [{{"fase": "ANTES" | "DURANTE" | "DESPUÉS", "ventana": [desde_s, hasta_s], "dur": 1.2 a 2.6}}]}}
Las ventanas son segundos del video original (0 a {dur:.0f}); usa las capturas para saber qué hay en cada momento.
Entre 1 y 2 clips ANTES, 2 a 4 DURANTE, 1 a 2 DESPUÉS. Responde SOLO con el objeto JSON."""]
        tr = estilo and (estilo[2].get('trailer') or None)
        if tr:
            partes.append(f"En los videos de referencia el tráiler inicial dura unos {tr['dura_s']} s, con unas {tr['tomas']:.0f} tomas "
                          f"de {tr['toma_media_s']} s cada una. Ajusta la cantidad de clips y su «dur» a ese ritmo.")
        if an and pistas.hay(an):
            partes.append(pistas.texto_prompt(an))
    return '\n\n'.join(partes)


def verificar_orden(d, bloques):
    """Revisión independiente de la IA: que los tramos sigan el orden del video y que lo que narra cada bloque
    se diga cerca de su tramo en tu grabación. Solo avisa (no cambia nada) y deja el detalle en revision_guion.txt."""
    avisos, previo = [], None
    for b in bloques:
        mo = b['montaje']
        if mo.get('src_inicio') is None:
            continue
        ini, fin = mo['src_inicio'], mo.get('src_fin') or mo['src_inicio']
        if previo and ini < previo[1] - 3:
            avisos.append(f"{b['id']}: vuelve atrás en el video (empieza en {mmss(ini)} y el bloque {previo[0]} terminaba en "
                          f"{mmss(previo[1])}). Si no es a propósito, la acción queda fuera de orden")
        previo = (b['id'], max(fin, previo[1] if previo else 0))
    palabras = pistas.palabras_video(d)
    if palabras:
        norm = [(w['inicio'], pistas.normal(w['texto'])[:5]) for w in palabras]
        for b in bloques:
            mo = b['montaje']
            if mo.get('src_inicio') is None or mo['modo'] == 'imagen':
                continue
            raices = {w[:5] for w in pistas.palabras_clave(b['texto'])}
            if len(raices) < 3:
                continue
            ini, fin = mo['src_inicio'], mo.get('src_fin') or mo['src_inicio'] + (mo.get('congelar_s') or 3)
            cerca = {r for t, r in norm if ini - 8 <= t <= fin + 8 and r in raices}
            otro = [(x, v) for x, v in pistas.dicho(palabras, b['texto'], top=1) if not ini - 15 <= x <= fin + 15]
            if len(cerca) <= 1 and otro and otro[0][1] >= 0.5:
                avisos.append(f"{b['id']}: lo que narra no se dice cerca de su tramo ({mmss(ini)}–{mmss(fin)}); "
                              f"se parece más a lo que dices en {mmss(otro[0][0])}. Revisa si la imagen va con la voz")
    open(os.path.join(d, 'revision_guion.txt'), 'w', encoding='utf-8').write(
        '\n'.join(avisos) + '\n' if avisos else 'Sin problemas de orden: los tramos siguen el video y cada bloque va con lo que dices.\n')
    return avisos


def extraer_json(txt):
    txt = txt.strip()
    m = re.search(r'```(?:json)?\s*(.*?)```', txt, re.S)
    if m:
        txt = m.group(1)
    i = min([p for p in (txt.find('{'), txt.find('[')) if p >= 0], default=0)
    return json.loads(txt[i:])


def revisar(d, tarea, datos):
    """Corrige lo que la IA suele hacer mal. Devuelve (datos_corregidos, avisos)."""
    avisos = []
    dur = duracion(os.path.join(d, 'original.mp4'))
    if tarea == 'guion':
        bloques = datos['bloques'] if isinstance(datos, dict) else datos
        t = 0.0
        for k, b in enumerate(bloques, 1):
            b.setdefault('id', f'L{k:02d}'); b.setdefault('tipo', 'libre'); b.setdefault('ancla', '')
            mo = b['montaje']
            for c in ('src_inicio', 'src_fin'):
                if mo.get(c) is not None:
                    mo[c] = round(min(max(float(mo[c]), 0), dur - 0.1), 2)
            if mo['modo'].startswith('lento'):
                mo['velocidad'] = min(max(float(mo.get('velocidad') or 1), 0.25), 1.0)
                if mo['src_fin'] <= mo['src_inicio']:
                    mo['src_fin'] = min(dur - 0.1, mo['src_inicio'] + 3); avisos.append(f"{b['id']}: tramo vacío, lo alargué a 3 s")
            mo.setdefault('congelar_s', None)
            largo = ((mo['src_fin'] - mo['src_inicio']) / mo['velocidad'] if mo['modo'].startswith('lento') else 0) + (mo.get('congelar_s') or 0)
            voz = round(len(b['texto'].split()) / PALABRAS_POR_S + 1.0, 1)
            if voz > largo:  # la voz no cabe: se agrega una pausa congelada al final (no tapa nada)
                extra = round(voz - largo + 0.5, 1)
                if mo['modo'] == 'lento':
                    mo['modo'] = 'lento+congelar'; mo['congelar_s'] = extra
                else:
                    mo['congelar_s'] = round((mo.get('congelar_s') or 0) + extra, 1)
                largo += extra
                avisos.append(f"{b['id']}: la voz no cabía, agregué {extra} s de pausa")
            b['inicio_min'] = round(t, 1); b['fin_max'] = round(t + largo, 1); b['voz_estimada_s'] = voz
            t += largo
        avisos += verificar_orden(d, bloques)
        return {'video': 'original.mp4', 'duracion_s': round(t, 1), 'bloques': bloques}, avisos
    if tarea == 'etiquetas':
        lista = datos['etiquetas'] if isinstance(datos, dict) else datos
        textos = {b['id']: normal(b['texto']) for b in json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']}
        buenas = []
        for e in lista:
            if normal(e.get('frase', '')) in textos.get(e.get('bloque'), ''):
                buenas.append(e)
            else:
                avisos.append(f"quité «{e.get('texto')}»: la frase «{e.get('frase')}» no está en {e.get('bloque')}")
        return buenas, avisos
    if tarea == 'trailer':
        for c in datos['clips']:
            a, b = (min(max(float(x), 0), dur - 0.5) for x in c['ventana'])
            if b - a < c['dur']:
                b = min(dur - 0.1, a + c['dur'] + 0.5)
            c['ventana'] = [round(a, 1), round(b, 1)]
            c['fase'] = {'DESPUES': 'DESPUÉS'}.get(c['fase'].upper(), c['fase'].upper())
        datos.setdefault('musica', {'pista': 'musica.mp3', 'desde': 40})
        an = pistas.analizar(d, dur)
        if pistas.hay(an):
            avisos += pistas.revisar_clips(an, datos['clips'])
        return datos, avisos
    return datos, avisos


def llamar_claude(ajustes, texto, caps):
    """Claude con la librería oficial de Anthropic (no habla el formato de OpenAI)."""
    try:
        import anthropic
    except ImportError:
        raise SystemExit('ERROR: falta la librería de Claude. Corre instalar.bat, o abre una terminal en la carpeta '
                         'de la app y escribe:\n  python -m pip install anthropic')
    contenido = []
    if ajustes.get('imagenes', True):
        for _, f in caps:
            contenido.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                                          'data': base64.b64encode(open(f, 'rb').read()).decode()}})
        contenido.append({'type': 'text', 'text': texto})
    else:
        contenido.append({'type': 'text', 'text': texto + '\n\n(No puedes ver las capturas: guíate por la transcripción y los segundos.)'})
    cliente = anthropic.Anthropic(api_key=ajustes.get('clave') or None, timeout=900)
    try:
        # en streaming para que una respuesta larga no corte la conexión
        with cliente.beta.messages.stream(
            model=ajustes.get('modelo') or 'claude-opus-5-5',
            max_tokens=64000,
            system='Respondes únicamente con JSON válido.',
            output_config={'effort': 'medium'},
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',  # si un filtro de seguridad rechaza por error, otro modelo responde
            messages=[{'role': 'user', 'content': contenido}],
        ) as flujo:
            r = flujo.get_final_message()
    except anthropic.AuthenticationError:
        raise SystemExit('ERROR: Claude rechazó la clave. Revisa la clave en «⚙ Ajustes IA» (empieza con sk-ant-).')
    except anthropic.PermissionDeniedError as e:
        raise SystemExit(f'ERROR: tu clave de Claude no tiene permiso para este modelo: {e.message}')
    except anthropic.NotFoundError:
        raise SystemExit(f'ERROR: Claude no conoce el modelo «{ajustes.get("modelo")}». Prueba con claude-opus-5-5.')
    except anthropic.RateLimitError:
        raise SystemExit('ERROR: Claude dice que hiciste muchas peticiones o no tienes saldo. Espera un poco o revisa tu cuenta en console.anthropic.com.')
    except anthropic.APIStatusError as e:
        raise SystemExit(f'ERROR: Claude respondió con error {e.status_code}: {e.message}')
    except anthropic.APIConnectionError:
        raise SystemExit('ERROR: no hay conexión con Claude. Revisa tu internet.')
    if r.stop_reason == 'refusal':
        raise SystemExit('ERROR: Claude no quiso responder esta petición. Prueba cambiando la idea o usa otra IA.')
    return ''.join(b.text for b in r.content if b.type == 'text')


def contexto_ollama(texto, imagenes):
    """Ventana de contexto que pide el encargo (texto ~3 caracteres por token, ~300 tokens por imagen, y la
    respuesta), para que Ollama no corte el pedido en silencio. Entre 32k y 128k."""
    tokens = len(texto) // 3 + imagenes * 300 + 8000
    return min(131072, max(32768, -(-tokens // 8192) * 8192))


def llamar_ollama(ajustes, texto, caps):
    """Ollama por su API propia: la compatible con OpenAI no deja subir el contexto y cortaría el pedido."""
    msg = {'role': 'user', 'content': texto}
    if ajustes.get('imagenes', True):
        msg['images'] = [base64.b64encode(open(f, 'rb').read()).decode() for _, f in caps]
    else:
        msg['content'] += '\n\n(No puedes ver las capturas: guíate por la transcripción y los segundos.)'
    cuerpo = {'model': ajustes['modelo'], 'stream': False, 'format': 'json',
              'messages': [{'role': 'system', 'content': 'Respondes únicamente con JSON válido.'}, msg],
              'options': {'num_ctx': contexto_ollama(texto, len(msg.get('images', []))), 'temperature': 0.8}}
    base = re.sub(r'/v1/?$', '', ajustes['url'].rstrip('/'))
    req = urllib.request.Request(base + '/api/chat', data=json.dumps(cuerpo).encode(), headers={'Content-Type': 'application/json'})
    print(f'Pensando con {ajustes["modelo"]} en tu PC (puede tardar varios minutos)…', flush=True)
    try:
        r = json.load(urllib.request.urlopen(req, timeout=3600))
    except urllib.error.HTTPError as e:
        cuerpo = e.read()[:400].decode(errors='replace')
        if e.code == 404:
            raise SystemExit(f'ERROR: Ollama no tiene el modelo «{ajustes["modelo"]}». Corre instalar_ia_local.bat. Detalle: {cuerpo}')
        raise SystemExit(f'ERROR: Ollama respondió con error {e.code}: {cuerpo}')
    except urllib.error.URLError:
        raise SystemExit('ERROR: Ollama no está abierto. Ábrelo desde el menú Inicio (o corre instalar_ia_local.bat) y vuelve a intentar.')
    return r['message']['content']


def llamar(ajustes, texto, caps):
    if ajustes.get('tipo') == 'claude' or ajustes.get('proveedor', '').startswith('Claude'):
        return llamar_claude(ajustes, texto, caps)
    if ':11434' in ajustes.get('url', ''):
        return llamar_ollama(ajustes, texto, caps)
    contenido = [{'type': 'text', 'text': texto}]
    if ajustes.get('imagenes', True):
        for _, f in caps:
            contenido.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(open(f, 'rb').read()).decode()}})
        msg = {'role': 'user', 'content': contenido}
    else:
        msg = {'role': 'user', 'content': texto + '\n\n(No puedes ver las capturas: guíate por la transcripción y los segundos.)'}
    cuerpo = {'model': ajustes['modelo'], 'messages': [
        {'role': 'system', 'content': 'Respondes únicamente con JSON válido.'}, msg], 'temperature': 0.8}
    if ajustes.get('json', True):
        cuerpo['response_format'] = {'type': 'json_object'}
    url = ajustes['url'].rstrip('/') + '/chat/completions'
    cab = {'Content-Type': 'application/json'}
    if ajustes.get('clave'):
        cab['Authorization'] = 'Bearer ' + ajustes['clave']
    print('Mandando ' + (f'{len(caps)} capturas y ' if ajustes.get('imagenes', True) else 'solo texto (sin capturas) y ') + 'el encargo…', flush=True)
    for intento in range(3):
        req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers=cab)
        try:
            r = json.load(urllib.request.urlopen(req, timeout=600))
            break
        except urllib.error.HTTPError as e:
            detalle = e.read()[:500].decode(errors='replace')
            # algunos modelos (GPT-5, varios Qwen-VL) no aceptan temperatura o el modo JSON: se reintenta sin eso
            if e.code == 400 and 'temperature' in detalle and 'temperature' in cuerpo:
                del cuerpo['temperature']; continue
            if e.code == 400 and 'response_format' in detalle and 'response_format' in cuerpo:
                del cuerpo['response_format']; continue
            if e.code in (401, 403):
                raise SystemExit(f'ERROR: la IA rechazó la clave ({e.code}). Revísala en «⚙ Ajustes IA». Detalle: {detalle}')
            if e.code == 404:
                raise SystemExit(f'ERROR: la IA no conoce el modelo «{ajustes["modelo"]}» o la dirección está mal. Detalle: {detalle}')
            raise SystemExit(f'ERROR: la IA respondió con error {e.code}: {detalle}')
        except urllib.error.URLError as e:
            raise SystemExit(f'ERROR: no hay conexión con la IA en {ajustes["url"]} ({e.reason}). Revisa la dirección y tu internet.')
    return r['choices'][0]['message']['content']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--tarea', required=True, choices=list(ARCHIVO))
    ap.add_argument('--modo', default='prompt', choices=['prompt', 'api', 'revisar'])
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--idea', default='')
    ap.add_argument('--entrada', help='modo revisar: archivo con la respuesta pegada (por defecto, el JSON actual)')
    a = ap.parse_args()
    d = a.proyecto
    idea = a.idea or (open(os.path.join(d, 'idea.txt'), encoding='utf-8').read() if os.path.exists(os.path.join(d, 'idea.txt')) else '')
    destino = os.path.join(d, ARCHIVO[a.tarea])

    if a.modo == 'revisar':
        datos = extraer_json(open(a.entrada or destino, encoding='utf-8').read())
    else:
        try:
            n = int(json.load(open(a.ajustes, encoding='utf-8')).get('capturas', 14))
        except (OSError, ValueError, TypeError):
            n = 14
        caps = capturas(d, max(4, min(n, 60)))
        an = None
        if a.tarea == 'trailer':
            an = pistas.analizar(d, duracion(os.path.join(d, 'original.mp4')))
            if pistas.hay(an):
                extra = capturas_pistas(d, an)
                print(f'Usando tus pistas del tráiler ({len(extra)} imágenes más):\n' + pistas.texto_prompt(an), flush=True)
                caps += extra
        try:
            aj = json.load(open(a.ajustes, encoding='utf-8'))
        except (OSError, ValueError):
            aj = {}
        estilo = estilo_activo(aj)
        if estilo and a.tarea in ('guion', 'trailer'):
            print(f'Usando tu estilo «{estilo[0]}» (panel Alimentación).', flush=True)
        texto = encargo(d, a.tarea, idea, caps, an, estilo)
        if a.modo == 'prompt':
            f = os.path.join(d, f'ia_prompt_{a.tarea}.txt')
            open(f, 'w', encoding='utf-8').write(texto)
            print(f'Prompt en {f}. Adjunta las {len(caps)} capturas de ia_capturas/ si tu IA ve imágenes.')
            return
        ajustes = json.load(open(a.ajustes, encoding='utf-8'))
        print(f"Pidiendo {a.tarea} a {ajustes['modelo']} ({ajustes['url']})…", flush=True)
        respuesta = llamar(ajustes, texto, caps)
        open(os.path.join(d, f'ia_respuesta_{a.tarea}.txt'), 'w', encoding='utf-8').write(respuesta)
        try:
            datos = extraer_json(respuesta)
        except ValueError:
            corto = ' '.join(respuesta.split())[:220] or '(respuesta vacía)'
            raise SystemExit(f'ERROR: la IA ({ajustes["modelo"]}) no devolvió el {a.tarea} en el formato pedido; '
                             f'puede que lo haya rechazado. Contestó: «{corto}». Prueba con otro modelo en «⚙ Ajustes IA» '
                             f'(GPT o Qwen suelen aceptar estos temas) y vuelve a pulsar.')
        if a.tarea == 'guion' and not (datos.get('bloques') if isinstance(datos, dict) else datos):
            raise SystemExit(f'ERROR: la IA ({ajustes["modelo"]}) contestó sin bloques de guion: '
                             f'«{" ".join(respuesta.split())[:220]}». Prueba con otro modelo en «⚙ Ajustes IA».')
    datos, avisos = revisar(d, a.tarea, datos)
    if os.path.exists(destino):
        os.replace(destino, destino + '.anterior')
    json.dump(datos, open(destino, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for x in avisos:
        print('·', x)
    print(f'Guardado {ARCHIVO[a.tarea]} (la versión anterior quedó como {ARCHIVO[a.tarea]}.anterior)')


if __name__ == '__main__':
    main()
