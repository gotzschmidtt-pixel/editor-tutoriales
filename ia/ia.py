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
import numpy as np  # noqa: E402

ARCHIVO = {'guion': 'guion.json', 'etiquetas': 'etiquetas.json', 'trailer': 'trailer.json', 'senales': 'senales.json'}
VEL_MAX = 6.0  # lo más que se acelera un tramo (esperas, cargas) para que no queden minutos sin voz
RELLENO = 1.5  # segundos de imagen sin voz que se aceptan por bloque
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
        meta = max(1, round(meta_guion(d, dur, idea)[0] / 60))
        partes += [ESTILO, f"""Escribe el guion por bloques. Cada bloque tiene:
- "id": L01, L02, ...
- "ancla": qué se ve en pantalla en ese bloque (corto).
- "texto": lo que dice la voz en off. Unas {PALABRAS_POR_S} palabras por segundo de bloque.
- "montaje": de qué tramo del video ORIGINAL sale la imagen y a qué velocidad:
    {{"modo": "lento", "src_inicio": s, "src_fin": s, "velocidad": 0.6 a {VEL_MAX:.0f}}}  (1 = normal; MÁS de 1 = acelerado, para esperas, cargas,
      instalaciones y partes repetidas; menos de 1 solo para un detalle rápido que hay que ver bien)
    {{"modo": "congelar", "src_inicio": s, "congelar_s": s}}  (pausa en un cuadro; úsalo cuando se explica algo que se ve quieto)
    {{"modo": "lento+congelar", "src_inicio": s, "src_fin": s, "velocidad": v, "congelar_s": s}}
    {{"modo": "imagen", "congelar_s": s}}  (muestra la imagen del proyecto, por ejemplo un mapa)
  Los tramos van en orden, dentro de 0 a {dur:.0f} s. Salta lo que no aporta (esperas largas, errores, repeticiones).
- REGLA DE DURACIÓN: cada bloque dura lo que tarda la voz en decir su texto. Si el tramo del original es más largo que eso,
  acelera (velocidad = segundos del tramo / segundos de la voz) o toma solo la parte importante. Nada de minutos sin voz.
- Duración total buscada: unos {meta} minutos{'' if objetivo else f', parecido al original ({dur / 60:.0f} min); puede pasarse un poco si la idea del autor trae guion extra para agregar'}. Como el video dura
  lo que dura la voz, el guion completo debe tener unas {round(meta * 60 * PALABRAS_POR_S)} palabras en total: si escribes menos,
  el video queda mucho más corto. Explica cada paso con calma en vez de resumir.
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


def leer_idea(d):
    f = os.path.join(d, 'idea.txt')
    return open(f, encoding='utf-8').read() if os.path.exists(f) else ''


def meta_guion(d, dur, idea=None):
    """Cuánto debe durar el video (s) y el rango aceptable. Por defecto, parecido a la grabación;
    si la idea dice «que dure unos N minutos», eso manda. Puede pasarse un poco (guion extra del autor)."""
    idea = leer_idea(d) if idea is None else idea
    m = idea and re.search(r'(\d+)\s*(?:a\s*\d+\s*)?min', idea)
    meta = int(m.group(1)) * 60 if m else dur * 0.95
    return meta, meta * 0.8, meta * 1.2


def largo_bloque(mo):
    return ((mo['src_fin'] - mo['src_inicio']) / mo['velocidad'] if mo['modo'].startswith('lento') else 0) + (mo.get('congelar_s') or 0)


def ajustar_largo(bloques, voces, minimo, maximo, avisos):
    """Arreglo sin IA: si el total queda corto, los tramos acelerados van más despacio (hasta velocidad normal y
    unos segundos de imagen sin voz por bloque); si queda largo, se aceleran los tramos y se quitan pausas sin voz."""
    t = sum(largo_bloque(b['montaje']) for b in bloques)
    if t < minimo:
        margen = []
        for b, voz in zip(bloques, voces):
            mo = b['montaje']
            if not mo['modo'].startswith('lento') or mo['velocidad'] <= 1:
                margen.append(0); continue
            tramo = mo['src_fin'] - mo['src_inicio']
            margen.append(max(0, min(tramo, voz + RELLENO + 6) - tramo / mo['velocidad']))
        falta = minimo - t
        total = sum(margen)
        if total > 0:
            k = min(1, falta / total)
            for b, g, voz in zip(bloques, margen, voces):
                if g > 0:
                    mo = b['montaje']; tramo = mo['src_fin'] - mo['src_inicio']
                    mo['velocidad'] = round(max(1, tramo / (tramo / mo['velocidad'] + g * k)), 2)
                    mo['relleno_s'] = round(max(0, largo_bloque(mo) - voz - RELLENO) + 0.5, 1)  # que la voz no lo vuelva a acortar
            avisos.append(f"el guion quedaba corto ({mmss(t)}): dejé ir más despacio los tramos acelerados para sumar "
                          f"{mmss(min(falta, total))} de imagen")
    elif t > maximo:
        sobra = t - maximo
        for b, voz in zip(bloques, voces):
            if sobra <= 0:
                break
            mo = b['montaje']
            antes = largo_bloque(mo)
            if mo['modo'].startswith('lento'):
                tramo = mo['src_fin'] - mo['src_inicio']
                mo['velocidad'] = round(min(VEL_MAX, max(mo['velocidad'], tramo / max(antes - sobra, voz + 0.3, 0.5))), 2)
            if mo.get('congelar_s'):
                resto = largo_bloque(mo) - (voz + 0.3)
                if resto > 0:
                    mo['congelar_s'] = round(max(0, mo['congelar_s'] - min(resto, sobra)), 1)
                    if mo['congelar_s'] < 0.5 and mo['modo'] == 'lento+congelar':
                        mo['modo'], mo['congelar_s'] = 'lento', None
            sobra -= antes - largo_bloque(mo)
        avisos.append(f"el guion quedaba largo ({mmss(t)}): aceleré tramos y quité pausas sin voz")
    t = 0.0
    for b in bloques:
        largo = largo_bloque(b['montaje'])
        b['inicio_min'] = round(t, 1); b['fin_max'] = round(t + largo, 1)
        t += largo
    return t


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
                mo['velocidad'] = min(max(float(mo.get('velocidad') or 1), 0.5), VEL_MAX)
                if mo['src_fin'] <= mo['src_inicio']:
                    mo['src_fin'] = min(dur - 0.1, mo['src_inicio'] + 3); avisos.append(f"{b['id']}: tramo vacío, lo alargué a 3 s")
            mo.setdefault('congelar_s', None)
            voz = round(len(b['texto'].split()) / PALABRAS_POR_S + 1.0, 1)
            # el video no puede durar mucho más que la voz: se acelera el tramo y se quitan pausas que sobran
            if mo['modo'].startswith('lento'):
                tramo = mo['src_fin'] - mo['src_inicio']
                if tramo / mo['velocidad'] > voz + RELLENO:
                    v = round(min(VEL_MAX, tramo / (voz + 0.5)), 2)
                    if v > mo['velocidad']:
                        avisos.append(f"{b['id']}: aceleré el tramo a ×{v:g} para que no quede imagen sin voz "
                                      f"({tramo / mo['velocidad']:.0f} s → {tramo / v:.0f} s)")
                        mo['velocidad'] = v
                sobra = tramo / mo['velocidad'] + (mo['congelar_s'] or 0) - (voz + RELLENO)
                if mo['congelar_s'] and sobra > 0:
                    mo['congelar_s'] = round(max(0, mo['congelar_s'] - sobra), 1)
                    if mo['congelar_s'] < 0.5:
                        mo['modo'], mo['congelar_s'] = 'lento', None
                    avisos.append(f"{b['id']}: quité {sobra:.1f} s de pausa que quedaba sin voz")
            elif mo.get('congelar_s') and mo['congelar_s'] > voz + RELLENO:
                avisos.append(f"{b['id']}: acorté la pausa de {mo['congelar_s']:g} s a {voz + 0.5:g} s (lo que dura la voz)")
                mo['congelar_s'] = round(voz + 0.5, 1)
            largo = ((mo['src_fin'] - mo['src_inicio']) / mo['velocidad'] if mo['modo'].startswith('lento') else 0) + (mo.get('congelar_s') or 0)
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
        meta, minimo, maximo = meta_guion(d, dur)
        t = ajustar_largo(bloques, [b['voz_estimada_s'] for b in bloques], minimo, maximo, avisos)
        if t > maximo:
            avisos.append(f"el video queda en {mmss(t)}, más largo de lo buscado ({mmss(meta)}): hay más texto de voz que video")
        elif t < minimo:
            avisos.append(f"quedó corto: unos {mmss(t)} de {mmss(meta)} buscados. Falta texto de voz en el guion")
        else:
            avisos.append(f"duración estimada {mmss(t)} (tu grabación dura {mmss(dur)})")
        return {'video': 'original.mp4', 'duracion_s': round(t, 1), 'largo_revisado': True, 'bloques': bloques}, avisos
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
    if re.search(r'\.\.\.|…', ajustes.get('clave') or ''):
        raise SystemExit('ERROR: la clave de Claude está recortada (tiene «...»): es la versión corta de la lista de claves. '
                         'En console.anthropic.com → API Keys crea una clave nueva y copia la COMPLETA (unos 100 caracteres).')
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


def tamano(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                        '-of', 'csv=p=0', f], capture_output=True, text=True, check=True).stdout
    w, h = r.strip().split(',')[:2]
    return int(w), int(h)

GENERICAS = set('boton botones opcion opciones icono menu el la los las de del en un una al y o a pestana casilla campo texto dato valor tecla '
                'pantalla seccion ventana interruptor enlace link barra que se con para'.split())


def lector_ocr():
    """Lector de texto de la pantalla (RapidOCR). Se instala solo la primera vez; si no se puede, devuelve None."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        print('Instalando el lector de texto de pantalla (solo la primera vez)…', flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '-q', 'rapidocr_onnxruntime'],
                       capture_output=True, timeout=900)
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception:
            print('· no pude instalar el lector de texto; ubico las señales solo con la IA', flush=True)
            return None
    try:
        return RapidOCR()
    except Exception as e:
        print(f'· el lector de texto no arrancó ({e}); ubico las señales solo con la IA', flush=True)
        return None


def leer_textos(ocr, imagen):
    """[(texto normalizado, x0, y0, x1, y1)] en píxeles de la imagen."""
    try:
        res, _ = ocr(imagen)
    except Exception:
        return []
    out = []
    for caja, txt, conf in res or []:
        if float(conf) < 0.5 or not txt.strip():
            continue
        xs, ys = [p[0] for p in caja], [p[1] for p in caja]
        out.append((txt, min(xs), min(ys), max(xs), max(ys)))
    return out


def compacto(c):
    return re.sub(r'[^0-9a-zñ]', '', normal(c))


def claves(m):
    """Lo que debería leerse en pantalla: el rótulo y lo nombrado en «que», sin «botón», «opción»… delante.
    Devuelve [(palabras sin genéricas)], en minúsculas y sin acentos."""
    vistos, out = set(), []
    for c in [m.get('texto') or '', m.get('que') or '']:
        pal = [w for w in re.findall(r'[0-9a-zñ]+', normal(c)) if w not in GENERICAS]
        if pal and ''.join(pal) not in vistos and len(''.join(pal)) >= 2:
            vistos.add(''.join(pal)); out.append(pal)
    return out


def buscar_en_pantalla(textos, m, guia=None):
    """La caja de texto en pantalla que mejor coincide con lo que hay que señalar. Devuelve (x0, y0, x1, y1, puntaje) o None.
    El lector a veces pega las palabras («Numerodeserie»), por eso se compara sin espacios.
    guia: (x, y) que dio la IA, para desempatar cuando el mismo texto aparece varias veces."""
    from difflib import SequenceMatcher
    mejor_ = None
    for pal in claves(m):
        k = ''.join(pal)
        for txt, x0, y0, x1, y1 in textos:
            t = compacto(txt)
            if not t:
                continue
            n = len(t)
            if k == t:
                p, i, j = 1.0, 0, n
            elif len(k) >= 3 and k in t:  # es parte de una línea más larga: recorto a la parte que coincide
                i = t.index(k); p, j = 0.92, i + len(k)
            else:
                # todas las palabras en orden dentro de la línea («número serie» en «Número de serie: HN…»)
                i = j = pos = 0; ok = len(pal) > 1
                for nw, w in enumerate(pal):
                    q = t.find(w, pos) if len(w) >= 2 else -1
                    if q < 0:
                        ok = False; break
                    if nw == 0:
                        i = q
                    pos = j = q + len(w)
                if ok:
                    p = 0.86
                else:
                    p, i, j = SequenceMatcher(None, k, t).ratio(), 0, n
            if p < 0.78:
                continue
            a, b = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * j / n
            if guia:
                cx, cy = (a + b) / 2, (y0 + y1) / 2
                p -= min(0.15, ((cx - guia[0]) ** 2 + (cy - guia[1]) ** 2) ** 0.5 / 4000)
            if not mejor_ or p > mejor_[4]:
                mejor_ = (a, y0, b, y1, p)
    return mejor_


def dibujar_marca(f, s, W, salida):
    """Copia del cuadro con la marca en rojo, para que la IA revise si quedó bien puesta."""
    import cv2
    im = cv2.imread(f)
    if im is None:
        return False
    k = im.shape[1] / W
    x, y = int(s['x'] * k), int(s['y'] * k)
    if s['tipo'] == 'caja':
        w, h = int(s['w'] * k / 2), int(s['h'] * k / 2)
        cv2.rectangle(im, (x - w, y - h), (x + w, y + h), (0, 0, 255), 4)
    else:
        cv2.circle(im, (x, y), max(int(s.get('r', 60) * k), 12), (0, 0, 255), 4)
        cv2.drawMarker(im, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 18, 3)
    return cv2.imwrite(salida, im)


MARCAS_DIR = 'marcas_senales'
CADENA = ['1_montaje.mp4', '2_insertos.mp4', '3_voz.mp4', '4_musica.mp4', '5_etiquetas.mp4', '6_senales.mp4', '7_tarjetas.mp4']
FORMAS = {'circulo', 'flecha', 'caja'}


def marcas_autor(d):
    """Lo que el autor pidió en «Flechas y círculos»: capturas (con nota) y pedidos de texto o de voz."""
    try:
        datos = json.load(open(os.path.join(d, MARCAS_DIR, 'marcas.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return [], []
    capturas_, pedidos = [], []
    for p in datos.get('MARCAS', []):
        if not isinstance(p, dict):
            continue
        tipo, nota = p.get('tipo'), (p.get('nota') or '').strip()
        if tipo == 'captura' and p.get('archivo'):
            capturas_.append(p)
        elif tipo == 'audio' and p.get('archivo'):
            txt = pistas.transcribir_audio(d, os.path.basename(p['archivo']), MARCAS_DIR)
            if txt or nota:
                pedidos.append(' '.join(x for x in (txt, nota) if x))
        elif nota:
            pedidos.append(nota + (f" (en el {p['segundo']})" if p.get('segundo') else ''))
    return capturas_, pedidos


def momento(d, c, video):
    """Segundo del video donde va la captura del autor: el que anotó (si es del video ya montado) o el cuadro más parecido."""
    seg = pistas.segundos(c.get('segundo'))
    if seg is not None and c.get('video') in CADENA:
        return seg, 1.0
    f = os.path.join(d, MARCAS_DIR, os.path.basename(c['archivo']))
    crudo = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', video, '-vf', f'fps=2,scale={pistas.MINI_W}:{pistas.MINI_H},format=gray',
                            '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    n = len(crudo) // (pistas.MINI_W * pistas.MINI_H)
    if not n:
        return None, 0
    s = pistas._gris(crudo, n) @ pistas._gris(pistas._mini(f, ['-frames:v', '1']), 1)[0]
    if seg is not None:  # anotó un segundo pero del original: se busca el parecido más cercano a ese punto
        s = s - 0.0005 * abs(np.arange(n) / 2 - seg)
    i = int(s.argmax())
    return round(i / 2 + 0.25, 2), float(s[i])


def ubicar(m, p, f, ocr, W, H):
    """Arma la señal con la posición que dio la IA (en %), y la clava encima del texto si el lector lo encuentra en el cuadro.
    Devuelve (señal, si quedó leída en pantalla) o (None, False)."""
    try:
        x, y = float(p['x']), float(p['y'])
    except (KeyError, TypeError, ValueError):
        x = y = None
    tam_w, tam_h = (float(p.get('w') or 8) * W / 100, float(p.get('h') or 8) * H / 100)
    exacta = False
    if ocr:  # si lo que hay que señalar es un texto en pantalla, va justo encima de ese texto
        esc = W / 1024
        guia = (x * 1024 / 100, y * 1024 * H / W / 100) if x is not None else None
        hit = buscar_en_pantalla(leer_textos(ocr, f), m, guia)
        if hit:
            a, b, c, e, _ = hit
            x, y = (a + c) / 2 * esc * 100 / W, (b + e) / 2 * esc * 100 / H
            tam_w, tam_h = (c - a) * esc + 24, (e - b) * esc + 16
            exacta = True
    if x is None or not (2 <= x <= 98 and 2 <= y <= 98):
        return None, False
    tipo = m.get('tipo') if m.get('tipo') in FORMAS else 'circulo'
    if exacta and tipo == 'circulo' and not m.get('forma_fija') and tam_w > 4.5 * tam_h:  # texto largo: mejor una caja
        tipo = 'caja'
    s = {'bloque': m.get('bloque'), 'frase': m.get('frase'), 'tipo': tipo, 'x': round(x * W / 100), 'y': round(y * H / 100), 'dur': 3}
    if tipo == 'caja':
        s['w'], s['h'] = round(min(max(tam_w * 1.15, 120), W * 0.6)), round(min(max(tam_h * 1.3, 60), H * 0.4))
        s['foco'] = True
    else:
        s['r'] = round(min(max(max(tam_w, tam_h) * (0.62 if exacta else 0.7), H * 0.045), H * 0.16))
        s['foco'] = tipo == 'circulo'
    if tipo == 'flecha':
        apuntar(s, tam_w, tam_h, W, H)
    if (m.get('texto') or '').strip():
        s['texto'] = m['texto'].strip()[:28]
    return s, exacta


def senales_auto(d, ajustes, video):
    """Flechas y círculos sin escribir nada: 1) la IA elige en el guion qué señalar y con qué frase (más lo que pidió el autor),
    2) se saca el cuadro del video justo cuando la voz dice esa frase, 3) la IA ubica la cosa en cada cuadro,
    4) las capturas del autor se buscan en el video y la IA ubica ahí lo que marcó."""
    sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
    from etiquetas import buscar
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    propias, pedidos = marcas_autor(d)
    textos = '\n'.join(f"{b['id']} (en pantalla: {b.get('ancla', '')}): {b['texto']}" for b in g['bloques'])
    extra = ('\n\nEl autor pidió además (esto va primero, aunque pase del máximo):\n' + '\n'.join(f'- {x}' for x in pedidos)) if pedidos else ''
    pedido = f"""Este es el guion de un video tutorial (voz en off sobre lo que se ve en pantalla):
{textos}

Elige los momentos donde una flecha o un círculo ayuda a seguir el paso: el botón u opción que hay que tocar,
el dato importante en la pantalla del celular o la PC, la pieza o conector. Máximo uno por bloque y entre 4 y 12 en total.
Para cada uno: "bloque" (id), "frase" (2 a 4 palabras COPIADAS TAL CUAL del texto de ese bloque; la marca aparece cuando la
voz las dice), "que" (qué hay que señalar, tal como se vería en pantalla, ej. «botón Aceptar», «opción Restablecer»),
"tipo" (circulo para botones y opciones, flecha para algo pequeño, caja para un texto o dato largo) y "texto"
(rótulo opcional de 1 a 3 palabras, o vacío).{extra}
Responde SOLO con un objeto JSON {{"marcas": [...]}}."""
    print(f'Eligiendo qué señalar con {ajustes["modelo"]}…' + (f' (más {len(pedidos)} pedido{"s" if len(pedidos) > 1 else ""} tuyo{"s" if len(pedidos) > 1 else ""})' if pedidos else ''), flush=True)
    r1 = llamar(ajustes, pedido, [])
    open(os.path.join(d, 'ia_respuesta_senales_1.txt'), 'w', encoding='utf-8').write(r1)
    try:
        marcas = extraer_json(r1)
    except Exception:
        if not propias:
            raise
        marcas = []
    marcas = marcas.get('marcas', []) if isinstance(marcas, dict) else marcas
    inicio = {b['id']: b['inicio_min'] for b in g['bloques']}
    W, H = tamano(video)
    out = os.path.join(d, 'ia_capturas')
    os.makedirs(out, exist_ok=True)
    for viejo in os.listdir(out):
        if viejo.startswith('senal_'):  # también las copias _revision y _autor
            os.remove(os.path.join(out, viejo))
    validas, caps, tiempos = [], [], []
    for m in marcas if isinstance(marcas, list) else []:
        if not isinstance(m, dict):
            continue
        al_f = os.path.join(d, 'voz', f"{m.get('bloque')}.align.json")
        if m.get('bloque') not in inicio or not os.path.exists(al_f):
            continue
        t = buscar(json.load(open(al_f, encoding='utf-8')), m.get('frase', ''))
        if t is None:
            print(f"· salto «{m.get('frase')}»: no está tal cual en {m.get('bloque')}", flush=True)
            continue
        t = inicio[m['bloque']] + 0.3 + t
        f = os.path.join(out, f'senal_{len(validas) + 1:02d}.jpg')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', video, '-frames:v', '1',
                        '-vf', 'scale=1024:-2', '-q:v', '3', f], check=True)
        validas.append(m); tiempos.append(t)
        caps.append((f"imagen {len(validas)}: {m.get('que')}", f))
    if not validas and not propias:
        raise SystemExit('ERROR: la IA no eligió ninguna frase que esté tal cual en el guion; no hay flechas que poner.')
    pos = {}
    if validas:
        lista = '\n'.join(f'- Imagen {k}: {m.get("que")}' for k, m in enumerate(validas, 1))
        pedido2 = f"""Te mando {len(validas)} imágenes de un video, en orden. En cada una busca lo que se indica:
{lista}

Para cada imagen da dónde está su CENTRO, en porcentaje del ancho (x, 0 = borde izquierdo, 100 = derecho) y del alto
(y, 0 = arriba, 100 = abajo), y su tamaño aproximado en porcentaje (w, h). Si no se ve claramente, pon "x": null.
Responde SOLO con un objeto JSON {{"posiciones": [{{"imagen": 1, "x": 50, "y": 40, "w": 12, "h": 6}}, ...]}}."""
        print(f'Ubicando {len(validas)} señales en sus cuadros…', flush=True)
        r2 = llamar(ajustes, pedido2, caps)
        open(os.path.join(d, 'ia_respuesta_senales_2.txt'), 'w', encoding='utf-8').write(r2)
        pos = extraer_json(r2)
        pos = {int(p.get('imagen', 0)): p for p in (pos.get('posiciones', []) if isinstance(pos, dict) else pos)}
    ocr = lector_ocr()
    senales, dudosas = [], []
    for k, m in enumerate(validas, 1):
        s, exacta = ubicar(m, pos.get(k) or {}, caps[k - 1][1], ocr, W, H)
        if not s:
            print(f"· salto «{m.get('que')}»: la IA no lo vio en el cuadro", flush=True)
            continue
        s['_t'] = tiempos[k - 1]
        senales.append(s)
        if not exacta:
            dudosas.append((len(senales) - 1, k, m))
        print(f"{m['bloque']}  {s['tipo']:8s} «{m['frase']}» → {m.get('que')} ({s['x'] * 100 / W:.0f}%, {s['y'] * 100 / H:.0f}%)"
              + ('  ✓ leído en pantalla' if exacta else ''), flush=True)
    if propias:
        senales_autor(d, ajustes, propias, video, W, H, out, caps, ocr, inicio, senales, dudosas)
    if dudosas and ajustes.get('revisar_senales', True):
        senales = revisar_senales(d, ajustes, senales, dudosas, caps, W, H)
    # las del autor mandan: se quitan las automáticas que caen encima de una suya
    suyas = [s['_t'] for s in senales if s.get('autor')]
    senales = [s for s in senales if s.get('autor') or all(abs(s['_t'] - t) > 3.5 for t in suyas)]
    for s in senales:
        s.pop('_t', None)
    return senales


def senales_autor(d, ajustes, propias, video, W, H, out, caps, ocr, inicio, senales, dudosas):
    """Las capturas que mandó el autor: se busca en qué segundo del video están y la IA ubica en ese cuadro lo que marcó."""
    pares, imgs = [], []
    for c in propias:
        t, parecido = momento(d, c, video)
        nombre = os.path.basename(c['archivo'])
        if t is None or parecido < 0.35:
            print(f"· tu captura {nombre} no se parece a ningún momento del video: anota el segundo o captúrala del reproductor", flush=True)
            continue
        n = len(pares) + 1
        f = os.path.join(out, f'senal_autor_{n:02d}.jpg')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', video, '-frames:v', '1',
                        '-vf', 'scale=1024:-2', '-q:v', '3', f], check=True)
        suya = os.path.join(out, f'senal_autor_{n:02d}_captura.jpg')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', os.path.join(d, MARCAS_DIR, nombre), '-frames:v', '1',
                        '-vf', 'scale=1024:-2', '-q:v', '3', suya], check=True)
        nota = (c.get('nota') or '').strip()
        pares.append((c, t, f, nota))
        imgs += [(f'captura {n} del autor' + (f': {nota}' if nota else ''), suya), (f'cuadro {n} del video', f)]
        print(f'· tu captura {nombre} va en el {mmss(t)} del video', flush=True)
    if not pares:
        return
    lista = '\n'.join(f'- Par {n}: captura {n} del autor, luego cuadro {n} del video.'
                      + (f' El autor dice: «{nota}».' if nota else '')
                      + (f' Quiere un {"recuadro" if c["forma"] == "caja" else c["forma"]}.' if c.get('forma') in FORMAS else '')
                      for n, (c, t, f, nota) in enumerate(pares, 1))
    pedido = f"""El autor de un video tutorial me mandó capturas para mostrar dónde quiere una flecha, un círculo o un recuadro
(a veces lo dibujó encima de la captura, a veces solo muestra la pantalla y lo explica en la nota). Te mando {len(pares)} pares
de imágenes, en orden: primero su captura y después el mismo momento sacado del video final.
{lista}

Para cada par, mira qué quiere señalar el autor y búscalo en el CUADRO DEL VIDEO (la segunda imagen del par). Da:
"par", "que" (qué es, tal como se lee en pantalla, ej. «botón Aceptar»), "tipo" (circulo, flecha o caja), "texto" (rótulo de
1 a 3 palabras o vacío; si el autor escribió un rótulo, úsalo), y el CENTRO en porcentaje del cuadro del video
(x, 0 = izquierda, 100 = derecha; y, 0 = arriba, 100 = abajo) con su tamaño (w, h). Si no lo encuentras, "x": null.
Responde SOLO con un objeto JSON {{"marcas": [{{"par": 1, "que": "...", "tipo": "circulo", "texto": "", "x": 50, "y": 40, "w": 10, "h": 6}}]}}."""
    print('Ubicando ' + (f'las {len(pares)} capturas que mandaste…' if len(pares) > 1 else 'la captura que mandaste…'), flush=True)
    try:
        r = llamar(ajustes, pedido, imgs)
    except SystemExit as e:
        print(f'· no pude ubicar tus capturas ({e})', flush=True)
        return
    open(os.path.join(d, 'ia_respuesta_senales_autor.txt'), 'w', encoding='utf-8').write(r)
    try:
        res = extraer_json(r)
    except Exception:
        print('· la IA no respondió bien sobre tus capturas', flush=True)
        return
    res = {int(x.get('par', 0)): x for x in (res.get('marcas', []) if isinstance(res, dict) else res) if isinstance(x, dict)}
    for n, (c, t, f, nota) in enumerate(pares, 1):
        p = res.get(n) or {}
        bloque = max((b for b in inicio if inicio[b] <= t), key=lambda b: inicio[b], default=None)
        m = {'que': p.get('que') or nota, 'texto': p.get('texto') or '', 'bloque': bloque, 'frase': (nota or p.get('que') or 'tu captura')[:40],
             'tipo': c['forma'] if c.get('forma') in FORMAS else p.get('tipo'), 'forma_fija': c.get('forma') in FORMAS}
        s, exacta = ubicar(m, p, f, ocr, W, H)
        if not s:
            print(f'· en tu captura {n} la IA no encontró qué señalar; prueba con una nota más clara', flush=True)
            continue
        s.update(t=t, _t=t, autor=True)
        caps.append((f'cuadro {n} del video', f))
        senales.append(s)
        if not exacta:
            dudosas.append((len(senales) - 1, len(caps), m))
        print(f"tuya {mmss(t)}  {s['tipo']:8s} → {m['que']} ({s['x'] * 100 / W:.0f}%, {s['y'] * 100 / H:.0f}%)"
              + ('  ✓ leído en pantalla' if exacta else ''), flush=True)


def angulo_libre(x, y):
    """La flecha llega desde el lado con más espacio libre (en grados, 0 = desde la derecha)."""
    dx = -1 if x > 50 else 1
    dy = 1 if y < 35 else (-1 if y > 65 else -0.6)
    import math
    return round(math.degrees(math.atan2(dy, dx)))


def apuntar(s, tw, th, W, H):
    """Flecha de largo fijo que llega desde el lado libre y se detiene en el borde de lo señalado, sin taparlo."""
    import math
    s['angulo'] = angulo_libre(s["x"] * 100 / W, s['y'] * 100 / H)
    a = math.radians(s['angulo'])
    c, n = abs(math.cos(a)) or 1e-6, abs(math.sin(a)) or 1e-6
    s['hueco'] = round(min(tw / 2 / c, th / 2 / n) + 10)
    s['r'] = round(H * 0.085)
    s.pop('foco', None)


def revisar_senales(d, ajustes, senales, dudosas, caps, W, H):
    """Segunda mirada: dibujo cada marca dudosa en su cuadro y la IA dice si quedó bien, la corrige o la quita."""
    imgs, lista = [], []
    for n, (i, k, m) in enumerate(dudosas, 1):
        f = caps[k - 1][1].replace('.jpg', '_revision.jpg')
        if dibujar_marca(caps[k - 1][1], senales[i], W, f):
            imgs.append((f"imagen {n}: {m.get('que')}", f)); lista.append((n, i, m))
    if not imgs:
        return senales
    texto = '\n'.join(f'- Imagen {n}: debería marcar {m.get("que")}' for n, i, m in lista)
    pedido = f"""En cada imagen dibujé una marca ROJA (círculo con una cruz en el centro, o un rectángulo):
{texto}

Mira si la marca está encima de eso. Para cada imagen responde una de tres:
- {{"imagen": 1, "ok": true}} si está bien puesta,
- {{"imagen": 2, "x": 61, "y": 33, "w": 10, "h": 5}} con el centro y tamaño correctos en porcentaje de la imagen, si está corrida,
- {{"imagen": 3, "quitar": true}} si eso no se ve en la imagen.
Responde SOLO con un objeto JSON {{"revision": [...]}}."""
    print(f'Revisando {len(imgs)} señales dibujadas en sus cuadros…', flush=True)
    try:
        r = llamar(ajustes, pedido, imgs)
    except SystemExit as e:
        print(f'· no pude revisar las señales ({e}); las dejo como están', flush=True)
        return senales
    open(os.path.join(d, 'ia_respuesta_senales_3.txt'), 'w', encoding='utf-8').write(r)
    try:
        rv = extraer_json(r)
    except Exception:
        return senales
    rv = {int(x.get('imagen', 0)): x for x in (rv.get('revision', []) if isinstance(rv, dict) else rv) if isinstance(x, dict)}
    quitar = set()
    for n, i, m in lista:
        x = rv.get(n) or {}
        s = senales[i]
        if x.get('quitar'):
            quitar.add(i); print(f"· quito «{m.get('que')}»: en la revisión no se ve", flush=True)
            continue
        try:
            nx, ny = float(x['x']), float(x['y'])
        except (KeyError, TypeError, ValueError):
            continue
        if not (2 <= nx <= 98 and 2 <= ny <= 98):
            continue
        s['x'], s['y'] = round(nx * W / 100), round(ny * H / 100)
        tw, th = float(x.get('w') or 0) * W / 100, float(x.get('h') or 0) * H / 100
        if tw and th:
            if s['tipo'] == 'caja':
                s['w'], s['h'] = round(min(max(tw * 1.15, 120), W * 0.6)), round(min(max(th * 1.3, 60), H * 0.4))
            else:
                s['r'] = round(min(max(max(tw, th) * 0.7, H * 0.045), H * 0.16))
        if s['tipo'] == 'flecha':
            apuntar(s, tw or 60, th or 40, W, H)
        print(f"· corregí «{m.get('que')}» → ({nx:.0f}%, {ny:.0f}%)", flush=True)
    return [s for i, s in enumerate(senales) if i not in quitar]


def corregir_largo(d, ajustes, texto, caps, respuesta, datos, intentos=2):
    """Si el guion de la IA da un video muy corto o muy largo, se lo devuelvo con los números para que lo arregle.
    Me quedo con la versión más cercana a la duración buscada."""
    import copy
    dur = duracion(os.path.join(d, 'original.mp4'))
    meta, minimo, maximo = meta_guion(d, dur)

    def medir(x):
        bl = x['bloques'] if isinstance(x, dict) else x
        palabras = sum(len(str(b.get('texto', '')).split()) for b in bl)
        try:
            t = revisar(d, 'guion', copy.deepcopy(x))[0]['duracion_s']
        except Exception:
            t = None
        return palabras, t

    mejor_, (pal, t) = datos, medir(datos)
    mejor_t = t
    for n in range(intentos):
        if t is None or minimo <= t <= maximo:
            break
        quiero = round(meta * PALABRAS_POR_S * 0.9)
        corto = t < minimo
        print(f'El guion da {mmss(t)} y busco unos {mmss(meta)}: le pido a la IA que lo '
              + ('alargue' if corto else 'acorte') + f' (intento {n + 1})…', flush=True)
        pedido = (texto + "\n\nTu respuesta anterior fue:\n" + respuesta[:30000] +
                  f"\n\nPROBLEMA: con ese guion el video dura {mmss(t)} y tiene que durar unos {mmss(meta)} "
                  f"(entre {mmss(minimo)} y {mmss(maximo)}). El video dura lo que dura la voz: tu guion tiene {pal} palabras "
                  f"y necesita unas {quiero}. " +
                  ("Alárgalo: explica con más detalle cada paso, agrega bloques para las partes de la grabación que saltaste "
                   "y usa tramos más largos del original. " if corto else
                   "Acórtalo: resume los textos, une o quita bloques que no aporten y usa velocidad mayor en esperas. ") +
                  "Devuelve el guion COMPLETO corregido, mismo formato, SOLO el objeto JSON.")
        try:
            r = llamar(ajustes, pedido, caps)
            nuevo = extraer_json(r)
            if not (nuevo.get('bloques') if isinstance(nuevo, dict) else nuevo):
                break
        except (SystemExit, ValueError) as e:
            print(f'· no pude corregir el largo con la IA ({e}); sigo con lo que hay', flush=True)
            break
        respuesta, (pal, t) = r, medir(nuevo)
        open(os.path.join(d, f'ia_respuesta_guion_largo{n + 1}.txt'), 'w', encoding='utf-8').write(r)
        if t is not None and (mejor_t is None or abs(t - meta) < abs(mejor_t - meta)):
            mejor_, mejor_t = nuevo, t
    return mejor_


def paquete(d, tarea, prompt, caps):
    """para_claude.zip: todo lo que Claude necesita en el chat para escribir el guion y dejarlo en tu carpeta."""
    import zipfile
    destino = os.path.join(d, 'para_claude.zip')
    proyecto = os.path.basename(os.path.abspath(d))
    leeme = f"""Paquete para Claude · proyecto «{proyecto}» · tarea: {tarea}

Claude: escribe {ARCHIVO[tarea]} siguiendo ia_prompt_{tarea}.txt (las capturas están en ia_capturas/ y la
transcripción con tiempos en transcripcion.json). Déjalo en la carpeta del proyecto, en mis_proyectos/{proyecto}/{ARCHIVO[tarea]}
(si ya hay uno, el actual va aparte como {ARCHIVO[tarea]}.anterior). Después el autor pulsa «Hacer todo».
Ruta de esta carpeta en la PC del autor: {os.path.abspath(d)}
"""
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('LEEME.txt', leeme)
        z.write(prompt, os.path.basename(prompt))
        for nombre in ['transcripcion.json', 'transcripcion.txt', 'idea.txt', ARCHIVO[tarea], 'mejoras_guion.txt']:
            f = os.path.join(d, nombre)
            if os.path.exists(f):
                z.write(f, nombre)
        for _, f in caps:
            z.write(f, 'ia_capturas/' + os.path.basename(f))
    print(f'Listo para_claude.zip ({os.path.getsize(destino) / 1e6:.1f} MB, {len(caps)} capturas). '
          'Súbelo al chat con Claude y pídele el guion.', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--tarea', required=True, choices=list(ARCHIVO))
    ap.add_argument('--modo', default='prompt', choices=['prompt', 'api', 'revisar', 'paquete'])
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--idea', default='')
    ap.add_argument('--video', help='tarea senales: el video donde van las flechas (para sacar los cuadros)')
    ap.add_argument('--entrada', help='modo revisar: archivo con la respuesta pegada (por defecto, el JSON actual)')
    a = ap.parse_args()
    d = a.proyecto
    idea = a.idea or (open(os.path.join(d, 'idea.txt'), encoding='utf-8').read() if os.path.exists(os.path.join(d, 'idea.txt')) else '')
    destino = os.path.join(d, ARCHIVO[a.tarea])

    if a.tarea == 'senales':  # va por su cuenta: dos pedidos y cuadros del video ya montado
        if a.modo != 'api':
            raise SystemExit('ERROR: las flechas automáticas necesitan una IA con visión configurada (⚙ Ajustes IA).')
        datos = senales_auto(d, json.load(open(a.ajustes, encoding='utf-8')), a.video or os.path.join(d, '3_voz.mp4'))
        if os.path.exists(destino):
            os.replace(destino, destino + '.anterior')
        json.dump(datos, open(destino, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'Guardado senales.json con {len(datos)} señales')
        return
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
        if a.modo in ('prompt', 'paquete'):
            f = os.path.join(d, f'ia_prompt_{a.tarea}.txt')
            open(f, 'w', encoding='utf-8').write(texto)
            if a.modo == 'paquete':
                paquete(d, a.tarea, f, caps)
                return
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
        if a.tarea == 'guion':
            datos = corregir_largo(d, ajustes, texto, caps, respuesta, datos)
    datos, avisos = revisar(d, a.tarea, datos)
    if os.path.exists(destino):
        os.replace(destino, destino + '.anterior')
    json.dump(datos, open(destino, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for x in avisos:
        print('·', x)
    if a.tarea == 'guion':  # lo que la app corrigió, para mostrártelo antes de seguir
        open(os.path.join(d, 'mejoras_guion.txt'), 'w', encoding='utf-8').write(''.join(x + '\n' for x in avisos))
    print(f'Guardado {ARCHIVO[a.tarea]} (la versión anterior quedó como {ARCHIVO[a.tarea]}.anterior)')


if __name__ == '__main__':
    main()
