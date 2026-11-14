"""«🩹 Qué se corrige del original»: busca en tu grabación los errores que antes se corregían a mano y te los muestra para
que los apruebes ANTES de escribir el guion. Pedido de fabian (13/11/2026), sacado del tutorial Honor 400 Lite, para
TODAS las marcas.

Lo que busca (gratis, en tu PC: la transcripción y el texto que se lee en pantalla del mapa del video):
  1. intento_fallido    un paso que sale mal y se repite («me disculpan, es vol menos», «otra vez», «no entró»)
                        → se corta el intento malo y queda solo el bueno.
  2. web_prohibida      la voz nombra o la pantalla muestra una web que no va (frpunlock.co / .com)
                        → la voz nueva dice tus páginas y encima de la barra va la placa «GSMPRIME.CO • XIAOMIUNLOCK.COM».
  3. modelo_equivocado  dices otro modelo de la marca que no es el del proyecto («a este Honor Magic 8 Lite» en el 400 Lite)
                        → la voz nueva dice el modelo del proyecto.
  4. promesa_tiempo     «en unos minutos», «instantáneo» por la KEY o el servidor, contra la regla de la marca
                        (Honor: horas; Xiaomi cuenta Mi: máximo 24 h) → la voz nueva dice el tiempo real.
  5. espera_larga       reinicio, formateo o configuración largos → se aceleran.
  6. testimonio_largo   los testimonios de WhatsApp en medio del video (2 minutos) → se cortan de ahí y quedan ~25 s en el
                        cierre, con 1-2 frases de tu voz.
  7. comentarios        mostrar o hablar de los comentarios de YouTube a mitad del video → se cortan.
Con --ia, tu IA de «⚙ Ajustes IA» revisa la lista y agrega lo que tu PC no vio (gasta un poco de la IA de texto).

Las reglas (webs prohibidas, tus páginas, tiempo por marca, largo del testimonio…) salen de
mis_conocimientos/correcciones/reglas.json (privado, GUIONES-IA); si no está, de REGLAS de aquí abajo.

Deja correcciones.json (cada corrección con «usar», para marcarla o no en la app) y QUE_SE_CORRIGE.md (el informe para
leer). NADA se aplica hasta que lo apruebas: «✅ Aplicar lo marcado» (--aplicar) pasa los cortes y acelerados a
acortar.json, el testimonio a testimonios/, la placa encima de la web prohibida a original.mp4 (el de antes queda como
original_sin_corregir.mp4) y deja las frases a cambiar para la IA del guion (ia.py las lee y además corrige sola el texto
del guion: correcciones_guion()).

Uso:
  python corregir_original.py --proyecto .             # busca y deja el informe
  python corregir_original.py --proyecto . --ia        # además con tu IA
  python corregir_original.py --proyecto . --aplicar   # aplica lo marcado
"""
import argparse, copy, json, os, re, subprocess, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CONOCIMIENTOS = os.path.join(RAIZ, 'mis_conocimientos')
ARCHIVO = 'correcciones.json'
INFORME = 'QUE_SE_CORRIGE.md'
RESPALDO = 'original_sin_corregir.mp4'

REGLAS = {
    # webs que nunca van, ni en la voz ni en pantalla (se buscan sin espacios ni puntos: «frp unlock punto com», «frpunlog»)
    'webs_prohibidas': ['frpunlock', 'frpunlog', 'frpunloc'],
    'webs_buenas': {'pantalla': 'GSMPRIME.CO • XIAOMIUNLOCK.COM',
                    'voz': 'G S M Prime punto co y Xiaomi Unlock punto com'},
    # lo que tarda el servidor según la marca: la voz nueva usa «frase»
    'tiempo_por_marca': {
        'HONOR': {'frase': 'puede tardar unas horas, según la demanda del servidor'},
        'XIAOMI': {'frase': 'el servidor oficial lo hace en máximo 24 horas'},
        '*': {'frase': 'el tiempo depende de la demanda del servidor'},
    },
    'testimonio_max_s': 25,
    'testimonio_minimo_s': 40,     # un tramo de testimonios más corto no se toca
    'testimonio_texto': ('En nuestro canal de WhatsApp hay cientos de testimonios de clientes reales, con el antes y el '
                         'después. El enlace para unirte está en la descripción.'),
    'espera_minima_s': 20,         # una espera más corta la deja «Acortar»
    'espera_queda_s': 12,          # cuánto dura más o menos una espera acelerada
    'comentarios_minimo_s': 15,
    # regla fija (fabian, 13/11/2026): entre el minuto 1 y 2 de cada tutorial la voz nombra tus páginas y sale la placa
    'paginas_entre_s': [60, 120],
    'paginas_frase': 'Y recuerda nuestras páginas oficiales: G S M Prime punto co y Xiaomi Unlock punto com.',
}

TIPOS = {
    'intento_fallido': 'Intento que falla',
    'web_prohibida': 'Web que no va',
    'modelo_equivocado': 'Modelo equivocado',
    'promesa_tiempo': 'Promesa de tiempo',
    'espera_larga': 'Espera larga',
    'testimonio_largo': 'Testimonios largos',
    'comentarios': 'Comentarios de YouTube',
    'paginas_min_1_2': 'Páginas entre el minuto 1 y 2',
}
DICE_PAGINAS = r'g\s*s\s*m\s*prime|gsmprime|xiaomi\s*unlock|xiaomiunlock'

# --- detectores (todo en minúsculas y sin acentos) ---
ERROR_FUERTE = (r'me disculp|disculpen|disculpa(me)?\b|perdon|me equivoque|nos equivocamos|me confundi|'
                r'no (funciono|entro|sirvio|salio|resulto|paso nada|lo (detecto|reconocio|leyo))|no (me )?(quiere|quiso) (entrar|prender)|'
                r'otra vez|de nuevo|volvemos a (intentar|empezar|hacer|apagar)|intentemos|vamos a repetir|repetimos|'
                r'cosas que pasan|no es (vol|volumen|el boton|la tecla)')
ACCION = (r'\b(presion\w*|aprieto|aprietan|apretamos|mant\w*n\w*|conect\w*|apag\w*|prend\w*|encend\w*|pulsa\w*|'
          r'vol(umen)? (mas|menos)|enchuf\w*|entr(ar|amos) (en|al|a) (modo|fastboot|recovery|dfu))\b')
TIEMPO = (r'en (unos |pocos |un par de |cuestion de |solo |solamente )?(minutos|segundos)\b|en (un|1|dos|2|tres|3|cinco|5|diez|10) minutos?\b|'
          r'al instante|instantane\w*|inmediat\w*|en segundos|rapidito|esperar unos minutos|esperamos unos minutos')
SOBRE_SERVIDOR = r'\b(key|ki|clave|codigo|code|servidor|server|pedido|orden|respuesta|desbloqueo|desvincul\w*|liberacion)\b'
ESPERA = (r'reinici\w*|reboot|formate\w*|restablec\w*|cargando|carga el|mientras carga|esperemos|esperamos|esperar|'
          r'logo|actualizando|instalando|please wait|optimizando')
CONFIG = (r'\bidioma|\bregion\b|acept\w* todo|aceptamos|terminos|wi-?fi|red wifi|mas tarde|continuar|siguiente|finalizar|'
          r'configur\w*|no gracias|servicios de google|omitir')
TESTIMONIO = (r'testimon\w*|timonios|conversacion(es)? real|nos han compartido|clientes?\b|confianza|canal (en|de) whatsapp|'
              r'nuestro canal|el despues|el antes|facebook')
COMENTARIO = r'coment\w*|escribirnos|escribanos|nos escriben|inquietudes|alguna duda|cualquier duda|les vamos a (estar )?respond\w*|suscrib\w*'
OCR_COMENTARIO = r'comentarios|respuestas?\b|hace \d+ (dias?|horas?|semanas?|meses?)|@\w{3,}|responder|me gusta'
OCR_TESTIMONIO = r'whatsapp|seguidores|canal|testimon'
LISTA_MODELOS = (r'todos los (modelos|equipos)|desde el|hasta el|como (el|los)|tambien|modelos? (como|desde)|sirve para|'
                 r'funciona (para|con|en)|otro(s)? (modelo|equipo)|y (el|la)|ademas|en nuestro canal|otro video|video del')
DEICTICO = r'\b(este|esta|a este|aqui tenemos|tenemos (un|una)|nuestro|el dispositivo|mi)\s*$'

SERIES = {'HONOR': ['magic', 'x', 'play'], 'XIAOMI': ['redmi', 'poco', 'note', 'mi'], 'SAMSUNG': ['galaxy'],
          'MOTOROLA': ['moto', 'edge'], 'APPLE': ['iphone', 'ipad'], 'HUAWEI': ['mate', 'nova', 'p', 'y']}
MARCA_PALABRA = {'honor': 'HONOR', 'xiaomi': 'XIAOMI', 'redmi': 'XIAOMI', 'poco': 'XIAOMI', 'samsung': 'SAMSUNG',
                 'galaxy': 'SAMSUNG', 'motorola': 'MOTOROLA', 'moto': 'MOTOROLA', 'iphone': 'APPLE', 'huawei': 'HUAWEI'}
SUFIJOS = {'lite', 'pro', 'plus', 'max', 'ultra', 'mini', 'prime', 'se', 'fe', 'neo', 'power', 'play', 'stylus', 'edge', 'x',
           's', 'c', 'a', 'g', 'e', 'note', 'magic', 'turbo', 'gt', 'v', 'flip', 'fold'}
ARREGLA = {'light': 'lite', 'lait': 'lite', 'plas': 'plus', 'mas': 'plus'}


def normal(t):
    t = unicodedata.normalize('NFD', str(t or '').lower())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


def compacto(t):
    return re.sub(r'[^0-9a-zñ]', '', normal(t))


def mmss(s):
    s = max(0, float(s))
    return f'{int(s // 60)}:{int(s % 60):02d}'


def leer_json(f, defecto):
    try:
        return json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        return defecto


def reglas():
    """REGLAS de aquí, con lo que diga mis_conocimientos/correcciones/reglas.json encima (tu archivo privado manda)."""
    r = copy.deepcopy(REGLAS)
    propio = leer_json(os.path.join(CONOCIMIENTOS, 'correcciones', 'reglas.json'), {})
    for k, v in (propio.items() if isinstance(propio, dict) else []):
        if k.startswith('_'):
            continue
        if isinstance(v, dict) and isinstance(r.get(k), dict):
            r[k].update({kk: (dict(r[k].get(kk) or {}, **vv) if isinstance(vv, dict) else vv) for kk, vv in v.items()})
        else:
            r[k] = v
    return r


# ---------- lo que se dice ----------
def palabras(d):
    """[{texto, inicio, fin}] de transcripcion.json; si no, de transcripcion.srt o .txt («[  0.0-  6.5] texto»),
    repartiendo el tiempo de cada línea entre sus palabras."""
    pal = [w for w in leer_json(os.path.join(d, 'transcripcion.json'), []) if isinstance(w, dict) and 'inicio' in w]
    if pal:
        return sorted(({'texto': str(w.get('texto', '')), 'inicio': float(w['inicio']),
                        'fin': float(w.get('fin', w['inicio'] + 0.3))} for w in pal), key=lambda w: w['inicio'])
    lineas = []
    srt = os.path.join(d, 'transcripcion.srt')
    if os.path.exists(srt):
        for bloque in re.split(r'\n\s*\n', open(srt, encoding='utf-8', errors='replace').read().strip()):
            m = re.search(r'(\d+):(\d\d):(\d\d)[,.](\d+)\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d+)', bloque)
            if m:
                g = [int(x) for x in m.groups()]
                a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                lineas.append((a, b, ' '.join(bloque[m.end():].split('\n')[1:])))
    txt = os.path.join(d, 'transcripcion.txt')
    if not lineas and os.path.exists(txt):
        for ln in open(txt, encoding='utf-8', errors='replace'):
            m = re.match(r'\s*\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)', ln)
            if m:
                lineas.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    out = []
    for a, b, t in lineas:
        ws = t.split()
        for k, w in enumerate(ws):
            paso = (b - a) / max(len(ws), 1)
            out.append({'texto': w, 'inicio': round(a + k * paso, 2), 'fin': round(a + (k + 1) * paso, 2)})
    return out


class Dicho:
    """La transcripción como un texto (minúsculas, sin acentos) que sabe en qué segundo está cada letra."""

    def __init__(self, pal):
        self.pal, partes, self.pos = pal, [], []
        n = 0
        for i, w in enumerate(pal):
            t = normal(w['texto'])
            partes.append(t)
            self.pos.append(n)
            n += len(t) + 1
        self.texto = ' '.join(partes)

    def palabra(self, c):
        import bisect
        return max(0, bisect.bisect_right(self.pos, c) - 1)

    def buscar(self, rx, desde=0.0, hasta=1e9):
        """[(inicio_s, fin_s, texto, índice de palabra)] de cada coincidencia."""
        out = []
        for m in re.finditer(rx, self.texto):
            i, j = self.palabra(m.start()), self.palabra(max(m.end() - 1, m.start()))
            a, b = self.pal[i]['inicio'], self.pal[j]['fin']
            if desde <= a <= hasta:
                out.append((a, b, m.group(0), i))
        return out

    def frase(self, a, b, margen=0.0):
        return ' '.join(w['texto'] for w in self.pal if a - margen <= w['inicio'] <= b + margen)

    def antes(self, i, n=8):
        return ' '.join(normal(w['texto']) for w in self.pal[max(0, i - n):i])

    def inicio_frase(self, t):
        """El comienzo de la frase donde cae t (después de una pausa de 0,6 s o más)."""
        k = next((i for i, w in enumerate(self.pal) if w['inicio'] >= t), len(self.pal) - 1)
        while k > 0 and self.pal[k]['inicio'] - self.pal[k - 1]['fin'] < 0.6 and t - self.pal[k - 1]['inicio'] < 6:
            k -= 1
        return self.pal[k]['inicio'] if self.pal else t

    def fin_frase(self, t):
        k = next((i for i, w in enumerate(self.pal) if w['fin'] >= t), len(self.pal) - 1)
        while k + 1 < len(self.pal) and self.pal[k + 1]['inicio'] - self.pal[k]['fin'] < 0.6 and self.pal[k]['fin'] - t < 6:
            k += 1
        return self.pal[k]['fin'] if self.pal else t


# ---------- lo que se ve ----------
def mapa(d):
    """[{t, texto, pantalla, accion}] de mapa_video.json; si no hay, lo arma tu PC (solo el texto de pantalla, gratis)."""
    cuadros = (leer_json(os.path.join(d, 'mapa_video.json'), {}) or {}).get('cuadros')
    if cuadros or not os.path.exists(os.path.join(d, 'original.mp4')):
        return cuadros or []
    try:
        sys.path.insert(0, os.path.join(RAIZ, 'ia'))
        import ia
        return ia.mapa_video(d, None)
    except Exception as e:  # sin el lector de pantalla igual sirve la transcripción
        print(f'· no pude leer el texto de la pantalla ({e}); busco solo en lo que dices', flush=True)
        return []


def visto(c):
    return normal(' '.join(str(c.get(x) or '') for x in ('pantalla', 'accion', 'texto')))


def tramos_en_mapa(cuadros, rx, dur, compacto_=False):
    """[(inicio, fin, texto)] de los cambios de pantalla seguidos donde se lee rx."""
    out = []
    for k, c in enumerate(cuadros):
        t = compacto(c.get('texto')) if compacto_ else visto(c)
        m = re.search(rx, t)
        if not m:
            continue
        fin = cuadros[k + 1]['t'] if k + 1 < len(cuadros) else min(dur, c['t'] + 10)
        if out and c['t'] - out[-1][1] < 1:
            out[-1] = (out[-1][0], fin, out[-1][2])
        else:
            out.append((float(c['t']), float(fin), m.group(0)))
    return out


def juntar(hits, hueco):
    """Agrupa [(a, b, txt, i)] que quedan a menos de `hueco` segundos: [[hits...]]."""
    grupos = []
    for h in sorted(hits):
        if grupos and h[0] - grupos[-1][-1][1] <= hueco:
            grupos[-1].append(h)
        else:
            grupos.append([h])
    return grupos


def duracion(d, pal):
    f = os.path.join(d, 'original.mp4')
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                           capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except (OSError, subprocess.CalledProcessError, ValueError):
        return pal[-1]['fin'] + 2 if pal else 0.0


# ---------- el proyecto ----------
def marca_y_modelo(d):
    """('HONOR', 'honor 400 lite') del nombre del proyecto o de idea.txt («modelo: Honor 400 Lite»)."""
    idea = ''
    try:
        idea = open(os.path.join(d, 'idea.txt'), encoding='utf-8', errors='replace').read()[:3000]
    except OSError:
        pass
    m = re.search(r'modelo\s*[:=]\s*(.+)', idea, re.I)
    for texto in ([m.group(1)] if m else []) + [os.path.basename(os.path.abspath(d)).replace('_', ' ').replace('-', ' '), idea]:
        mod = modelos_en(normal(texto))
        if mod:
            return mod[0][0], mod[0][1]
    try:
        sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
        import conocimiento
        return (conocimiento.marca_de_proyecto(d) or '').upper(), ''
    except Exception:
        return '', ''


def modelos_en(t):
    """[(MARCA, 'honor 400 lite', inicio, fin)] de cada modelo nombrado (marca o serie + algo con un número)."""
    out = []
    ws = [(m.group(0), m.start(), m.end()) for m in re.finditer(r'[0-9a-zñ]+', t)]
    for k, (w, a, _) in enumerate(ws):
        marca = MARCA_PALABRA.get(w)
        serie = next((mk for mk, ss in SERIES.items() if w in ss and len(w) > 1), None)
        if not marca and not serie:
            continue
        toks, j = [w], k + 1
        while j < len(ws) and len(toks) < 5:
            x = ARREGLA.get(ws[j][0], ws[j][0])
            if re.fullmatch(r'\d{1,4}[a-z]{0,2}', x) or x in SUFIJOS or (serie is None and x in sum(SERIES.values(), [])):
                toks.append(x)
                j += 1
            else:
                break
        if any(re.search(r'\d', x) for x in toks) and len(toks) >= 2:
            out.append((marca or serie, ' '.join(ARREGLA.get(x, x) for x in toks), a, ws[j - 1][2]))
    return out


def mismo_modelo(a, b):
    sin = lambda x: [y for y in x.split() if y not in MARCA_PALABRA]  # «honor 400 lite» = «400 lite»
    return sin(a) == sin(b)


def sacar_ids(lista):
    for k, c in enumerate(sorted(lista, key=lambda c: c['inicio']), 1):
        c['id'] = f'C{k:02d}'
    return sorted(lista, key=lambda c: c['inicio'])


# ---------- los 7 detectores ----------
def intentos_fallidos(dicho, dur):
    out = []
    for g in juntar(dicho.buscar(ERROR_FUERTE), 40):
        err_a, err_b = g[0][0], g[-1][1]
        if err_a < 10 or err_b > dur - 20:
            continue
        previas = dicho.buscar(ACCION, err_a - 45, err_a)
        sin_apagar = [x for x in previas if not re.match(r'apag|prend|encend', x[2])]
        previas = sin_apagar or previas  # apagar el teléfono hace falta también para el intento bueno: se deja
        if not previas:
            continue
        a = dicho.inicio_frase(previas[0][0])
        # el intento bueno: la próxima acción después de la disculpa
        nueva = next((x for x in dicho.buscar(ACCION, err_b + 1, err_b + 60)), None)
        b = (nueva[0] - 0.4) if nueva else dicho.fin_frase(err_b)
        if b - a < 8:
            continue
        nombre = next((x[2] for x in previas if x[2].startswith('vol')), previas[0][2])  # «vol más» dice más que «presionar»
        accion = re.sub(r'\s+', ' ', nombre)
        out.append({'tipo': 'intento_fallido', 'inicio': round(a, 1), 'fin': round(b, 1),
                    'dice': dicho.frase(err_a, err_b, 2)[:160],
                    'resumen': f'el intento con «{accion}» que falla',
                    'correccion': 'Se corta y queda solo el intento bueno.',
                    'acciones': [{'hacer': 'cortar'}], 'seguridad': 'media' if len(g) == 1 else 'alta'})
    return out


def webs_prohibidas(dicho, cuadros, dur, rg):
    rx = '|'.join(re.escape(compacto(w)) for w in rg['webs_prohibidas'] if compacto(w))
    if not rx:
        return []
    out, buenas = [], rg['webs_buenas']
    # en la voz: se busca sin espacios ni puntos («frp unlock punto com»), en ventanas de 5 palabras
    vistos = []
    for i in range(len(dicho.pal)):
        ventana = dicho.pal[i:i + 5]
        cc = compacto(' '.join(w['texto'] for w in ventana))
        m = re.search(rx, cc)
        if m and not re.search(rx, compacto(' '.join(w['texto'] for w in ventana[1:]))) or (m and len(ventana) == 1):
            a, b = ventana[0]['inicio'], ventana[-1]['fin']
            if not vistos or a - vistos[-1][1] > 3:
                vistos.append((a, b))
    for a, b in vistos:
        out.append({'tipo': 'web_prohibida', 'donde': 'voz', 'inicio': round(a, 1), 'fin': round(b, 1),
                    'dice': dicho.frase(a - 1, b + 1)[:160], 'resumen': 'la voz original nombra una web que no va',
                    'correccion': f'La voz nueva dice {buenas["voz"]}.',
                    'acciones': [{'hacer': 'voz', 'cambiar': 'web', 'por': buenas['voz']}], 'seguridad': 'alta'})
    for a, b, txt in tramos_en_mapa(cuadros, rx, dur, compacto_=True):
        out.append({'tipo': 'web_prohibida', 'donde': 'pantalla', 'inicio': round(a, 1), 'fin': round(b, 1),
                    'se_ve': txt, 'resumen': f'el video muestra «{txt}» en pantalla',
                    'correccion': f'Encima va la placa «{buenas["pantalla"]}».',
                    'acciones': [{'hacer': 'placa', 'texto': buenas['pantalla'], 'buscar': rg['webs_prohibidas']}],
                    'seguridad': 'alta'})
    return out


def modelos_equivocados(dicho, marca, modelo):
    if not modelo:
        return []
    out, usados = [], []
    for mk, nombre, ca, cb in modelos_en(dicho.texto):
        if any(ca < y and cb > x for x, y in usados):  # «Honor Magic 8 Lite» y «Magic 8 Lite» son el mismo
            continue
        usados.append((ca, cb))
        if mk != marca and not (marca and MARCA_PALABRA.get(nombre.split()[0]) == marca) and not (marca and mk in SERIES.get(marca, [])):
            if mk != marca:
                continue
        if mismo_modelo(nombre, modelo):
            continue
        i = dicho.palabra(ca)
        antes = dicho.antes(i, 10)
        if re.search(LISTA_MODELOS, antes):  # «sirve para todos los modelos desde el Honor 600 Lite»: está bien
            continue
        seguro = bool(re.search(DEICTICO, dicho.antes(i, 3)))
        a, b = dicho.pal[i]['inicio'], dicho.pal[dicho.palabra(cb - 1)]['fin']
        out.append({'tipo': 'modelo_equivocado', 'inicio': round(a, 1), 'fin': round(b, 1),
                    'dice': dicho.frase(a - 2, b + 1)[:160], 'dijo': nombre, 'modelo': modelo,
                    'resumen': f'el original dice «{nombre.title()}» por error',
                    'correccion': f'La voz nueva dice {modelo.title()}.',
                    'acciones': [{'hacer': 'voz', 'cambiar': nombre, 'por': modelo.title()}],
                    'seguridad': 'alta' if seguro else 'media'})
    return out


def promesas_tiempo(dicho, marca, rg):
    regla = rg['tiempo_por_marca'].get(marca) or rg['tiempo_por_marca'].get('*') or {}
    out = []
    for a, b, txt, i in dicho.buscar(TIEMPO):
        cerca = ' '.join(normal(w['texto']) for w in dicho.pal[max(0, i - 14):i + 14])
        if not re.search(SOBRE_SERVIDOR, cerca):  # «esperamos unos segundos a que prenda»: está bien
            continue
        if out and a - out[-1]['fin'] < 5:
            continue
        out.append({'tipo': 'promesa_tiempo', 'inicio': round(a, 1), 'fin': round(b, 1), 'dice': dicho.frase(a - 3, b + 3)[:160],
                    'resumen': f'«{txt}» por la KEY o el servidor',
                    'correccion': f'La voz nueva dice que {regla.get("frase", "depende de la demanda del servidor")}.',
                    'acciones': [{'hacer': 'voz', 'cambiar': txt, 'por': regla.get('frase', '')}], 'seguridad': 'alta'})
    return out


def esperas_largas(dicho, cuadros, dur, rg):
    out = []
    for nombre, rx in (('reinicio y formateo', ESPERA), ('configuración', CONFIG)):
        # «se va a reiniciar» es explicar lo que viene (y el clic se tiene que ver); la espera es cuando pasa
        hits = [(a, b, t, i) for a, b, t, i in dicho.buscar(rx) if not re.search(r'\b(va|van|vamos) a\s*$|\bse va\s*$', dicho.antes(i, 3) + ' ')]
        hits += [(a, b, t, -1) for a, b, t in tramos_en_mapa(cuadros, rx, dur)]
        for g in juntar(hits, 25):
            a, b = g[0][0], max(h[1] for h in g) + (6 if nombre == 'configuración' else 10)
            if len(g) < 2 or b - a < rg['espera_minima_s']:
                continue
            b = min(b, dur - 3)
            largo = b - a
            v = round(min(8.0, max(2.0, largo / rg['espera_queda_s'])), 1)
            out.append({'tipo': 'espera_larga', 'inicio': round(a, 1), 'fin': round(b, 1), 'que': nombre,
                        'dice': dicho.frase(a, a + 8)[:120], 'resumen': f'espera larga ({nombre})',
                        'correccion': f'Se acelera ×{v:g} (de {int(largo)} s a unos {int(largo / v)} s).',
                        'acciones': [{'hacer': 'acelerar', 'velocidad': v}], 'seguridad': 'media'})
    return out


def testimonios_largos(dicho, cuadros, dur, rg):
    out = []
    hits = dicho.buscar(TESTIMONIO) + [(a, b, t, -1) for a, b, t in tramos_en_mapa(cuadros, OCR_TESTIMONIO, dur)]
    for g in juntar(hits, 30):
        if len(g) < 4:
            continue
        a, b = dicho.inicio_frase(g[0][0]), dicho.fin_frase(max(h[1] for h in g))
        if b - a < rg['testimonio_minimo_s'] or b > dur - 15:  # ya en el cierre: se deja
            continue
        queda = rg['testimonio_max_s']
        out.append({'tipo': 'testimonio_largo', 'inicio': round(a, 1), 'fin': round(b, 1), 'dice': dicho.frase(a, a + 10)[:140],
                    'resumen': 'testimonios de WhatsApp a mitad del video',
                    'correccion': f'Se dejan unos {queda} s en el cierre, con 1-2 frases.',
                    'acciones': [{'hacer': 'cortar'},
                                 {'hacer': 'testimonio_cierre', 'desde': round(a, 1), 'hasta': round(min(b, a + queda), 1),
                                  'texto': rg['testimonio_texto']}],
                    'seguridad': 'alta'})
    return out


def comentarios(dicho, cuadros, dur, rg):
    out = []
    hits = dicho.buscar(COMENTARIO) + [(a, b, t, -1) for a, b, t in tramos_en_mapa(cuadros, OCR_COMENTARIO, dur)]
    for g in juntar(hits, 25):
        a, b = dicho.inicio_frase(g[0][0]), dicho.fin_frase(max(h[1] for h in g))
        en_pantalla = any(h[3] == -1 for h in g)
        if b - a < rg['comentarios_minimo_s'] or b > dur - 45 or a < 20:  # en el cierre pedir comentarios está bien
            continue
        if len(g) < 3 and not en_pantalla:
            continue
        out.append({'tipo': 'comentarios', 'inicio': round(a, 1), 'fin': round(b, 1), 'dice': dicho.frase(a, a + 10)[:140],
                    'resumen': 'comentarios de YouTube a mitad del video', 'correccion': 'Se cortan.',
                    'acciones': [{'hacer': 'cortar'}], 'seguridad': 'alta' if en_pantalla else 'media'})
    return out


def paginas_ausentes(dicho, dur, rg):
    """Regla fija (fabian, 13/11/2026): entre el minuto 1 y 2 se nombran tus páginas. Si el original no lo hace, la voz
    nueva lo dice (correcciones_guion y paginas_min_1_2 lo aseguran en el guion; la placa la pone etiquetas.py)."""
    a, b = rg['paginas_entre_s']
    if dur < b or dicho.buscar(DICE_PAGINAS, a, b):
        return []
    return [{'tipo': 'paginas_min_1_2', 'inicio': float(a), 'fin': float(b), 'dice': dicho.frase(a, a + 8)[:120],
             'resumen': 'entre el minuto 1 y 2 no se nombran tus páginas',
             'correccion': 'La voz nueva las dice y sale la placa «' + rg['webs_buenas']['pantalla'] + '».',
             'acciones': [{'hacer': 'voz', 'cambiar': '', 'por': rg['paginas_frase']}], 'seguridad': 'alta'}]


def paginas_min_1_2(bloques, largo, d=None):
    """En el guion: si ningún bloque que suena entre el minuto 1 y 2 nombra tus páginas, se agrega la frase al bloque que
    suena ahí (el que no es un paso crítico ni el gancho, si hay). largo(b) = segundos que dura el bloque. Corre siempre."""
    if d and not marca_y_modelo(d)[0]:  # una noticia (sin marca de teléfono) va sin páginas
        return []
    rg = reglas()
    a, b = rg['paginas_entre_s']
    t, dentro = 0.0, []
    for x in bloques:
        d = largo(x)
        if t < b and t + d > a:
            dentro.append((x, t))
        t += d
    if not dentro or t < b:
        return []
    if any(re.search(DICE_PAGINAS, normal(x.get('texto'))) for x, _ in dentro):
        return []
    buenos = [(x, s) for x, s in dentro if s + largo(x) >= a + 10 and s <= b - 15] or dentro
    elegido = next((x for x, _ in buenos if not x.get('gancho') and x.get('tipo') != 'critico'), buenos[0][0])
    elegido['texto'] = (str(elegido.get('texto') or '').rstrip() + ' ' + rg['paginas_frase']).strip()
    return [f"{elegido.get('id', '?')}: agregué tus páginas (regla: entre el minuto 1 y 2 se nombran GSMPRIME.CO y XIAOMIUNLOCK.COM)"]


def etiqueta_paginas(bloques, items):
    """La placa de tus páginas entre el minuto 1 y 2 (etiquetas.py, con el tiempo real de cada bloque). Si ya hay una
    etiqueta «web» en ese minuto no agrega nada. Devuelve la etiqueta a sumar o None."""
    rg = reglas()
    a, b = rg['paginas_entre_s']
    if any(i.get('tipo') == 'web' and a - 5 <= float(i.get('t', -1)) <= b for i in items):
        return None
    for x in bloques:
        ini = x.get('inicio_min')
        if ini is None or ini > b:
            continue
        m = re.search(DICE_PAGINAS, normal(x.get('texto')))
        if m and ini + 2 >= a - 30:
            return {'bloque': x['id'], 'frase': m.group(0), 'tipo': 'web', 'titulo': 'Nuestras páginas',
                    'texto': rg['webs_buenas']['pantalla'], 'dur': 5.0, 'origen': 'paginas_min_1_2'}
    return None


def sin_pisarse(lista):
    """Dos cortes que se pisan quedan en uno; un acelerado que pisa un corte se queda con lo que sobra a los lados."""
    cortes = sorted((c for c in lista if any(x['hacer'] == 'cortar' for x in c['acciones'])), key=lambda c: c['inicio'])
    otros = [c for c in lista if c not in cortes]
    unidos = []
    for c in cortes:
        if unidos and c['inicio'] < unidos[-1]['fin'] and unidos[-1]['tipo'] == c['tipo']:
            unidos[-1]['fin'] = max(unidos[-1]['fin'], c['fin'])
        else:
            unidos.append(c)
    out = list(unidos)
    for c in otros:
        if any(k['inicio'] <= c['inicio'] and c['fin'] <= k['fin'] for k in unidos) and \
                all(x['hacer'] in ('voz', 'acelerar') for x in c['acciones']):
            continue  # cae dentro de un tramo que se corta: ya no se oye ni se ve
        if not any(x['hacer'] == 'acelerar' for x in c['acciones']):
            out.append(c)
            continue
        trozos = [(c['inicio'], c['fin'])]
        for k in unidos:
            trozos = [x for a, b in trozos for x in ((a, min(b, k['inicio'])), (max(a, k['fin']), b)) if x[1] - x[0] > 0]
        for a, b in trozos:
            if b - a >= 8:
                out.append(dict(copy.deepcopy(c), inicio=round(a, 1), fin=round(b, 1)))
    return out


def con_ia(d, lista, dicho, marca, modelo, dur):
    """Tu IA revisa la lista y agrega lo que tu PC no vio (mismos 7 tipos). Si no hay IA, la lista queda igual."""
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    aj = leer_json(os.path.join(RAIZ, 'app', 'ajustes.json'), {})
    if not (aj.get('url') or aj.get('tipo') == 'claude'):
        print('· no hay IA configurada en «⚙ Ajustes IA»: queda lo que encontró tu PC', flush=True)
        return lista
    trans = ia.transcripcion(d) or '\n'.join(f'[{mmss(w["inicio"])}] {w["texto"]}' for w in dicho.pal[::1])[:40000]
    ya = '\n'.join(f'- {mmss(c["inicio"])}–{mmss(c["fin"])} {c["tipo"]}: {c["resumen"]}' for c in lista) or '(nada)'
    pedido = f"""Eres editor de los videos tutoriales del autor (marca {marca or '?'}, modelo del video: {modelo or '?'}).
Busca en la transcripción los errores de la grabación ORIGINAL que hay que corregir, de estos tipos:
intento_fallido (un paso sale mal y se repite: marca solo el intento malo), modelo_equivocado (nombra otro modelo como si fuera
este), promesa_tiempo («en unos minutos» por la key o el servidor), espera_larga (reinicio, formateo, configuración),
testimonio_largo (testimonios a mitad del video), comentarios (habla de los comentarios de YouTube a mitad del video).
Tu PC ya encontró estos (corrígelos si el tramo está mal y agrega los que falten):
{ya}

Transcripción:
{trans}

Responde SOLO con JSON {{"correcciones": [{{"tipo": "...", "inicio": "m:ss", "fin": "m:ss", "resumen": "qué pasa, corto"}}]}}."""
    r = ia.extraer_json(ia.llamar(aj, pedido, []))

    def seg(x):
        x = str(x).strip()
        if ':' in x:
            m, s = x.rsplit(':', 1)
            return int(m) * 60 + float(s)
        return float(x)
    plantilla = {'intento_fallido': ([{'hacer': 'cortar'}], 'Se corta y queda solo el intento bueno.'),
                 'espera_larga': ([{'hacer': 'acelerar', 'velocidad': 4.0}], 'Se acelera.'),
                 'comentarios': ([{'hacer': 'cortar'}], 'Se cortan.')}
    for x in (r.get('correcciones', []) if isinstance(r, dict) else []):
        try:
            a, b, tipo = seg(x['inicio']), seg(x['fin']), x['tipo']
        except (KeyError, ValueError, TypeError):
            continue
        if tipo not in plantilla or not (0 <= a < b <= dur) or b - a < 5:
            continue
        mismo = next((c for c in lista if c['tipo'] == tipo and c['inicio'] < b and c['fin'] > a), None)
        if mismo:  # la IA ajusta el tramo que encontró tu PC
            mismo['inicio'], mismo['fin'], mismo['ia'] = round(a, 1), round(b, 1), True
            continue
        acc, corr = plantilla[tipo]
        lista.append({'tipo': tipo, 'inicio': round(a, 1), 'fin': round(b, 1), 'dice': dicho.frase(a, a + 8)[:140],
                      'resumen': str(x.get('resumen') or TIPOS[tipo])[:120], 'correccion': corr,
                      'acciones': copy.deepcopy(acc), 'seguridad': 'media', 'ia': True})
    return lista


def buscar(d, usar_ia=False):
    rg = reglas()
    pal = palabras(d)
    dicho = Dicho(pal)
    dur = duracion(d, pal)
    cuadros = mapa(d)
    marca, modelo = marca_y_modelo(d)
    print(f'Busco qué corregir del original ({mmss(dur)}; marca {marca or "?"}, modelo {modelo.title() or "?"})…', flush=True)
    if not pal:
        print('AVISO: no hay transcripción; solo miro el texto de la pantalla. Transcribe primero para encontrar más.', flush=True)
    lista = (intentos_fallidos(dicho, dur) + webs_prohibidas(dicho, cuadros, dur, rg) + modelos_equivocados(dicho, marca, modelo)
             + promesas_tiempo(dicho, marca, rg) + testimonios_largos(dicho, cuadros, dur, rg) + comentarios(dicho, cuadros, dur, rg))
    lista += esperas_largas(dicho, cuadros, dur, rg)
    lista += paginas_ausentes(dicho, dur, rg) if marca else []
    if usar_ia:
        try:
            lista = con_ia(d, lista, dicho, marca, modelo, dur)
        except (SystemExit, Exception) as e:
            print(f'· la IA no pudo ({e}); queda lo que encontró tu PC', flush=True)
    lista = sin_pisarse(lista)
    try:  # tus «⭐ cortes importantes» nunca se cortan ni se aceleran
        sys.path.insert(0, os.path.join(RAIZ, 'importantes'))
        import importantes
        imp = importantes.leer(d)
    except Exception:
        imp = []
    for c in lista:
        choca = [x for x in imp if x['inicio'] < c['fin'] and x['fin'] > c['inicio']]
        c['usar'] = not (choca and any(a['hacer'] in ('cortar', 'acelerar') for a in c['acciones']))
        if choca and not c['usar']:
            c['nota'] = 'toca un ⭐ corte importante: queda sin marcar'
    viejo = {(c['tipo'], round(c['inicio'])): c.get('usar') for c in (leer_json(os.path.join(d, ARCHIVO), {}) or {}).get('correcciones', [])}
    for c in lista:  # lo que ya desmarcaste sigue desmarcado
        if viejo.get((c['tipo'], round(c['inicio']))) is False:
            c['usar'] = False
    datos = {'marca': marca, 'modelo': modelo, 'original_s': round(dur, 1), 'aplicado': False,
             'correcciones': sacar_ids(lista)}
    json.dump(datos, open(os.path.join(d, ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(d, INFORME), 'w', encoding='utf-8').write(informe(datos))
    return datos


def informe(datos):
    """«Qué se corrige del original», como lo escribe fabian: una línea por corrección."""
    ls = ['## Qué se corrige del original', '']
    lista = datos['correcciones']
    if not lista:
        return '\n'.join(ls + ['No encontré nada que corregir: el original va bien.', ''])
    for c in lista:
        largo = c['fin'] - c['inicio']
        dura = f' (casi {round(largo / 60, 1):g} minutos)' if largo >= 75 else ''
        marca = '' if c.get('usar', True) else '[sin marcar] '
        duda = ' (revísalo: no estoy seguro)' if c.get('seguridad') == 'media' else ''
        if c['tipo'] == 'paginas_min_1_2':
            ls.append(f"- {marca}Entre el minuto 1 y 2 no se nombran tus páginas: {c['correccion'][0].lower() + c['correccion'][1:]}")
        elif c['tipo'] in ('modelo_equivocado', 'promesa_tiempo'):
            ls.append(f"- {marca}En {mmss(c['inicio'])} {c['resumen']}: {c['correccion'][0].lower() + c['correccion'][1:]}{duda}")
        else:
            ls.append(f"- {marca}{mmss(c['inicio'])} a {mmss(c['fin'])}: {c['resumen']}{dura}. {c['correccion']}{duda}")
    ls += ['', f"Total: {len(lista)} correcciones. Se aplican con «✅ Aplicar lo marcado» (las sin marcar no)."]
    return '\n'.join(ls) + '\n'


# ---------- aplicar ----------
def a_acortar(d, lista, dur):
    """Los cortes y acelerados aprobados van a acortar.json (tipo «correccion»); lo que ya había se respeta donde no choca."""
    f = os.path.join(d, 'acortar.json')
    plan = leer_json(f, None) or {'original_s': round(dur, 1), 'objetivo_s': 0, 'tramos': []}
    nuevos = []
    for c in lista:
        for x in c['acciones']:
            if x['hacer'] in ('cortar', 'acelerar'):
                t = {'id': c['id'], 'inicio': c['inicio'], 'fin': c['fin'], 'tipo': 'correccion', 'usar': True,
                     'motivo': f"corrección: {c['resumen']}", 'accion': x['hacer']}
                if x['hacer'] == 'acelerar':
                    t['velocidad'] = x.get('velocidad', 4.0)
                nuevos.append(t)
    resto = []
    for t in plan.get('tramos', []):
        if t.get('tipo') == 'correccion':
            continue
        trozos = [(t['inicio'], t['fin'])]
        for n in nuevos:
            trozos = [y for a, b in trozos for y in ((a, min(b, n['inicio'])), (max(a, n['fin']), b)) if y[1] - y[0] > 0]
        resto += [dict(t, inicio=round(a, 2), fin=round(b, 2)) for a, b in trozos if b - a >= 2]
    plan['tramos'] = sorted(resto + nuevos, key=lambda t: t['inicio'])
    plan['original_s'] = plan.get('original_s') or round(dur, 1)
    json.dump(plan, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return len(nuevos)


def a_testimonios(d, lista):
    """El trozo de testimonios que se queda (~25 s) va a testimonios/ como un testimonio más: entra en el cierre, después
    de la frase que habla de clientes y confianza, con tu voz diciendo 1-2 frases."""
    carpeta = os.path.join(d, 'testimonios')
    f = os.path.join(carpeta, 'testimonios.json')
    datos = leer_json(f, {}) or {}
    tes = [t for t in datos.get('TESTIMONIOS', []) if t.get('origen') != 'correccion']
    orig = os.path.join(d, RESPALDO if os.path.exists(os.path.join(d, RESPALDO)) else 'original.mp4')
    hechos = 0
    for c in lista:
        for x in c['acciones']:
            if x['hacer'] != 'testimonio_cierre':
                continue
            os.makedirs(carpeta, exist_ok=True)
            nombre = f"del_original_{c['id']}.mp4"
            if os.path.exists(orig):
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f"{x['desde']:.2f}", '-i', orig,
                                '-t', f"{x['hasta'] - x['desde']:.2f}", '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                                '-c:a', 'aac', '-movflags', '+faststart', os.path.join(carpeta, nombre)], check=True)
            tes.append({'archivo': nombre, 'momento': 'auto', 'texto': x.get('texto', ''), 'origen': 'correccion',
                        'nota': f"del original {mmss(x['desde'])}–{mmss(x['hasta'])}"})
            hechos += 1
    if hechos or any(t.get('origen') == 'correccion' for t in datos.get('TESTIMONIOS', [])):
        datos['TESTIMONIOS'] = tes
        os.makedirs(carpeta, exist_ok=True)
        json.dump(datos, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return hechos


def placa_png(texto, ancho, salida):
    """La placa de tus páginas: negra con neón celeste y letras blancas (tu estilo favorito). Si en mis_conocimientos/logos
    está placa_webs.png (hecha con GPT), se usa esa."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    propia = os.path.join(CONOCIMIENTOS, 'logos', 'placa_webs.png')
    if os.path.exists(propia):
        im = Image.open(propia).convert('RGBA')
        im = im.resize((int(ancho), max(1, int(im.height * ancho / im.width))))
        im.save(salida)
        return im.size
    alto = max(28, int(ancho * 0.11))
    fuente = None
    for n in ('arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            fuente = ImageFont.truetype(n, int(alto * 0.52))
            break
        except OSError:
            continue
    fuente = fuente or ImageFont.load_default()
    im = Image.new('RGBA', (int(ancho) + 16, alto + 16), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    g.rounded_rectangle((8, 8, im.width - 8, im.height - 8), radius=alto // 4, outline=(0, 220, 255, 255), width=max(3, alto // 12))
    im = im.filter(ImageFilter.GaussianBlur(3))
    g = ImageDraw.Draw(im)
    g.rounded_rectangle((8, 8, im.width - 8, im.height - 8), radius=alto // 4, fill=(8, 10, 16, 245), outline=(0, 220, 255, 255),
                        width=max(2, alto // 18))
    tw = g.textlength(texto, font=fuente)
    if tw > im.width - 24:  # que entre: se achica la letra
        fuente = fuente.font_variant(size=max(10, int(fuente.size * (im.width - 24) / tw))) if hasattr(fuente, 'font_variant') else fuente
        tw = g.textlength(texto, font=fuente)
    izq, sep, der = texto.partition('•')
    x, y = (im.width - tw) / 2, im.height / 2
    g.text((x, y), izq + sep, font=fuente, fill=(255, 255, 255, 255), anchor='lm')
    g.text((x + g.textlength(izq + sep, font=fuente), y), der, font=fuente, fill=(255, 214, 0, 255), anchor='lm')
    im.save(salida)
    return im.size


def cajas_web(d, video, a, b, buscar_, paso=0.5):
    """[(t, x0, y0, x1, y1)] donde se lee la web prohibida, cada medio segundo del tramo (OCR de tu PC)."""
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    ocr = ia.lector_ocr()
    if not ocr:
        return []
    tmp = os.path.join(d, 'ia_capturas', 'correccion_tmp.jpg')
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    claves = [compacto(x) for x in buscar_ if compacto(x)]
    out, t = [], a
    while t <= b:
        try:
            ia.sacar_cuadro(video, t, tmp, calidad=2)
            for txt, x0, y0, x1, y1 in ia.leer_textos(ocr, tmp):
                if any(k in compacto(txt) for k in claves):
                    out.append((round(t, 2), x0, y0, x1, y1))
                    break
        except Exception:
            pass
        t += paso
    if os.path.exists(tmp):
        os.remove(tmp)
    return out


def tramos_placa(cajas, paso=0.5, guarda=2.0):
    """Junta las cajas en tramos donde la barra casi no se mueve: [(desde, hasta, x0, y0, x1, y1)]. Donde un cuadro no se
    leyó, la placa sigue en su lugar hasta `guarda` segundos (que no parpadee)."""
    out = []
    for t, x0, y0, x1, y1 in cajas:
        if out:
            a, b, X0, Y0, X1, Y1 = out[-1]
            mueve = max(abs(x0 - X0), abs(y0 - Y0), abs(x1 - X1), abs(y1 - Y1)) / max(X1 - X0, 1)
            if t - b <= guarda and mueve < 0.15:
                out[-1] = (a, t + paso, min(x0, X0), min(y0, Y0), max(x1, X1), max(y1, Y1))
                continue
            if t - b <= guarda:
                out[-1] = (a, t, X0, Y0, X1, Y1)
        out.append((max(0.0, t - paso / 2), t + paso, x0, y0, x1, y1))
    return out


def poner_placas(d, lista):
    """La placa de tus páginas encima de la web prohibida, siguiéndola, quemada en original.mp4 (el de antes queda como
    original_sin_corregir.mp4 y se usa como fuente si vuelves a aplicar)."""
    pedidos = [(c, x) for c in lista for x in c['acciones'] if x['hacer'] == 'placa']
    if not pedidos:
        return 0
    orig, resp = os.path.join(d, 'original.mp4'), os.path.join(d, RESPALDO)
    if not os.path.exists(orig):
        print('· no está original.mp4: la placa queda para después', flush=True)
        return 0
    fuente = resp if os.path.exists(resp) else orig
    tramos = []
    for c, x in pedidos:
        cajas = cajas_web(d, fuente, c['inicio'], c['fin'], x.get('buscar') or REGLAS['webs_prohibidas'])
        tramos += [(t, x['texto']) for t in tramos_placa(cajas)]
        print(f"· {mmss(c['inicio'])}–{mmss(c['fin'])}: la web se lee en {len(cajas)} cuadros", flush=True)
    if not tramos:
        print('AVISO: no encontré la web en la imagen con el lector de pantalla; la placa no se puso. Márcala a mano.', flush=True)
        return 0
    tmpdir = os.path.join(d, 'ia_capturas')
    os.makedirs(tmpdir, exist_ok=True)
    entradas, fil, prev = [], [], '0:v'
    for k, ((a, b, x0, y0, x1, y1), texto) in enumerate(tramos):
        png = os.path.join(tmpdir, f'placa_{k:02d}.png')
        w, h = placa_png(texto, max(120, (x1 - x0) * 1.25), png)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        entradas += ['-i', png]
        fil.append(f"[{prev}][{k + 1}:v]overlay=x={cx - w / 2:.0f}:y={cy - h / 2:.0f}:enable='between(t,{a:.2f},{b:.2f})'[p{k}]")
        prev = f'p{k}'
    if fuente == orig:
        os.replace(orig, resp)
        fuente = resp
    print(f'Pongo la placa de tus páginas en {len(tramos)} tramos y rearmo original.mp4…', flush=True)
    sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
    try:
        import codificar
        correr = codificar.run
    except Exception:
        correr = subprocess.run
    script = os.path.join(tmpdir, 'placa_filtro.txt')
    open(script, 'w', encoding='utf-8').write(';\n'.join(fil))
    try:
        correr(['ffmpeg', '-nostdin', '-v', 'error', '-stats', '-y', '-i', fuente] + entradas +
               ['-filter_complex_script', script, '-map', f'[{prev}]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'veryfast',
                '-crf', '18', '-c:a', 'copy', '-movflags', '+faststart', orig + '.parcial.mp4'], check=True)
        os.replace(orig + '.parcial.mp4', orig)
    finally:
        for f in [script] + [entradas[i + 1] for i in range(0, len(entradas), 2)]:
            if os.path.exists(f):
                os.remove(f)
    return len(tramos)


def aplicar(d):
    datos = leer_json(os.path.join(d, ARCHIVO), None)
    if not datos:
        raise SystemExit('ERROR: todavía no hay correcciones: pulsa «🔎 Buscar qué corregir» primero.')
    lista = [c for c in datos['correcciones'] if c.get('usar')]
    dur = datos.get('original_s') or 0
    n_cortes = a_acortar(d, lista, dur)
    n_tes = a_testimonios(d, lista)
    n_placas = poner_placas(d, lista)
    n_voz = sum(1 for c in lista for x in c['acciones'] if x['hacer'] == 'voz')
    datos['aplicado'] = True
    json.dump(datos, open(os.path.join(d, ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo: {n_cortes} cortes o acelerados en «Acortar», {n_tes} testimonio(s) al cierre, {n_placas} placa(s) en '
          f'pantalla y {n_voz} frase(s) que la voz nueva dice bien.')
    if n_cortes:
        print('Para ver la grabación ya corregida: «✂️ Acortar» → «🎬 Rehacer con lo marcado». El guion con IA ya salta esos tramos.')


# ---------- para la IA del guion (ia.py) ----------
def aprobadas(d):
    datos = leer_json(os.path.join(d, ARCHIVO), None) or {}
    return [c for c in datos.get('correcciones', []) if c.get('usar')] if datos.get('aplicado') else []


def texto_para_ia(d):
    """Lo que la IA del guion tiene que decir distinto del original (lo aprobado en «🩹 Qué se corrige»)."""
    lista = aprobadas(d)
    if not lista:
        return ''
    rg = reglas()
    ls = []
    for c in lista:
        ls.append(f"- {mmss(c['inicio'])}–{mmss(c['fin'])}: {c['resumen']}. {c['correccion']}")
    return ("CORRECCIONES DEL ORIGINAL (las aprobó el autor; la voz nueva NO repite estos errores):\n" + '\n'.join(ls) +
            f"\nNunca nombres {', '.join(rg['webs_prohibidas'][:1])} ni otra web que no sea {rg['webs_buenas']['voz']}. Los tramos "
            "cortados no se usan; los testimonios van solo en el cierre, en 1-2 frases.")


def correcciones_guion(d, bloques):
    """Arregla sola la voz nueva (texto del guion) aunque la IA se equivoque: web prohibida → tus páginas, otro modelo de
    la marca dicho como si fuera este → el del proyecto, «en unos minutos» por la KEY → el tiempo de la regla de la marca.
    Corre siempre (son reglas fijas). Devuelve los avisos."""
    rg = reglas()
    marca, modelo = marca_y_modelo(d)
    avisos = []
    web = '|'.join(r'\s*'.join(re.escape(ch) for ch in compacto(w)) for w in rg['webs_prohibidas'] if compacto(w))
    rx_web = re.compile(r'(www\s*\.?\s*)?(' + web + r')\s*(\.|punto)?\s*(com|co)?(/\S*)?', re.I) if web else None
    regla_t = (rg['tiempo_por_marca'].get(marca) or rg['tiempo_por_marca'].get('*') or {}).get('frase', '')
    for b in bloques:
        t0 = t = b.get('texto') or ''
        if rx_web and rx_web.search(normal(t)):
            t = sustituir(t, rx_web, rg['webs_buenas']['voz'])
        if modelo:
            for mk, nombre, ca, cb in sorted(modelos_en(normal(t)), key=lambda x: -x[2]):
                if mk == marca and not mismo_modelo(nombre, modelo) and re.search(DEICTICO, normal(t)[:ca]) \
                        and not re.search(LISTA_MODELOS, normal(t)[max(0, ca - 60):ca]):
                    t = t[:ca] + modelo.title() + t[cb:]
        if regla_t and re.search(SOBRE_SERVIDOR, normal(t)):
            t = quitar_promesa(t, regla_t)
        if t != t0:
            b['texto'] = t
            avisos.append(f"{b.get('id', '?')}: corregí la voz según «🩹 Qué se corrige del original» («{t0[:60]}…»)")
    return avisos


def quitar_promesa(texto, frase):
    """«La Key llega en unos minutos desde el servidor.» → «La Key llega desde el servidor; puede tardar unas horas, según
    la demanda del servidor.» (quita la promesa y pone la regla de la marca al final de esa frase)."""
    while True:
        n = normal(texto)
        m = re.search(TIEMPO, n) if len(n) == len(texto) else None
        if not m:
            return texto
        a, b = m.start(), m.end()
        while a > 0 and texto[a - 1] == ' ':
            a -= 1
        texto = texto[:a] + texto[b:]
        fin = re.search(r'[.!?…]', texto[a:])
        k = a + fin.start() if fin else len(texto)
        cola = texto[k:] if fin else '.'
        texto = texto[:k].rstrip(' ,;') + '; ' + frase + cola


def sustituir(texto, rx, por, minuscula=False):
    """Reemplaza en el texto con acentos lo que rx encuentra en su versión sin acentos (misma longitud letra a letra)."""
    n = normal(texto)
    if len(n) != len(texto):  # letras raras que cambian el largo: se trabaja sobre la versión sin acentos
        return rx.sub(por, n)
    out, prev = [], 0
    for m in rx.finditer(n):
        out += [texto[prev:m.start()], por]
        prev = m.end()
    return ''.join(out + [texto[prev:]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--ia', action='store_true', help='que tu IA revise la lista y agregue lo que falte')
    ap.add_argument('--aplicar', action='store_true', help='aplicar lo marcado en correcciones.json')
    ap.add_argument('--suave', action='store_true', help='si algo falla, avisa y sigue (antes del guion)')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    if a.aplicar:
        aplicar(d)
        return
    try:
        datos = buscar(d, a.ia)
    except Exception as e:
        if not a.suave:
            raise
        print(f'AVISO: no pude buscar qué corregir del original ({e}); el guion sigue igual.')
        return
    print(informe(datos))
    if a.suave and datos['correcciones']:
        print('OJO: revisa «🩹 Qué se corrige» y aplica lo que va; hasta entonces el guion no salta esos tramos.')
    print(f'Informe: {os.path.join(d, INFORME)}. Revisa, desmarca lo que no va y pulsa «✅ Aplicar lo marcado».')


if __name__ == '__main__':
    main()
