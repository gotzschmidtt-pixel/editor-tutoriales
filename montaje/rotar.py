"""Regla de fabian (31/10/2026), para TODOS los videos: el primer minuto (el inicio, hasta ~1:20) no puede ser una escena
larga repetida. Las pausas largas de esos bloques ROTAN trozos reales del grabado, de 3 a 5 s, elegidos por lo que dice
la voz en cada frase: antes (cuenta de Google, bloqueado) → herramienta (el programa, la PC) → cable / Fastboot →
proceso (borrar, reiniciar) → después (pantalla de inicio, Ajustes). Nunca el mismo trozo seguido, nunca una captura
fija (las capturas quedan solo para las miniaturas), y nada con precio ni datos personales (según el texto que leyó el
mapa del video en esa pantalla). Si no hay material suficiente para rotar, deja un aviso en avisos_inicio.json (la vista
previa lo muestra) en vez de repetir la escena en silencio.

Lo usa montaje.py: planear() dice, para cada bloque del inicio con una pausa larga, qué trozos van en esa pausa.

Primer minuto (pedido de fabian, 03/11/2026: ahí se va del 30 al 50 % de la gente):
- Los bloques del gancho ("gancho": true, los escribe la IA del guion) traen "tomas": [[desde, hasta], ...], una por frase.
  Su pausa se llena con esas tomas, cada una en el segundo en que la voz dice su frase. Una toma con precio o datos
  personales, o que repite el trozo de antes, se cambia por un trozo elegido aquí (y se avisa). Sin tomas, rota como siempre.
- Cada trozo candidato tiene puntos: las palabras de la frase que se leen en esa pantalla (las raras, como fastboot, erase u
  omitir, valen más), que esté nítido y quieto y que no cambie de pantalla en sus 3-5 s. Se elige el de más puntos (antes,
  el primero del grabado: para «entramos en modo fastboot» salían pantallas USB y nunca FASTBOOT).
"""
import functools, json, math, os, re, sys, unicodedata

LIMITE = 80.0         # segundos del video armado donde rige la regla (el inicio)
PAUSA_MIN = 6.0       # una pausa más corta se deja como estaba (la repetición de su escena no alcanza a cansar)
PAUSA_MIN_GANCHO = 3.0  # el gancho rota aunque su pausa sea corta: sus frases son cortas y cada una lleva su trozo
TROZO = (3.0, 5.0)    # largo de cada trozo
CORTE_GANCHO = 1.5    # con las tomas de la IA el corte cae en cada frase (ritmo de ~2 s del gancho), nunca un trozo más corto
SEPARACION = 8.0      # dos trozos del inicio no salen de momentos tan cercanos del grabado
GANCHO = (45.0, 60.0)  # el gancho dura ~45 s; si pasa de 60 s se avisa (la gente se va antes de que empiece el paso a paso)
# revisión (03/11/2026): con los puntos, «libre y sin la cuenta» elegía la pantalla bloqueada (dice «cuenta») y el después
# salía de un Ajustes nítido a mitad del proceso. El antes es el comienzo del grabado y el después su final: nunca uno por
# el otro, y entre los suyos solo compiten los que están a menos de EXTREMO s del de siempre
OPUESTO = {'antes': 'despues', 'despues': 'antes'}
EXTREMO = 120.0
AVISOS = 'avisos_inicio.json'
SENSIBLE = re.compile(r'\$\s*\d|@|\+\d{7,}|\b\d{9,}\b|imei|serial|s/n|precio|price|order|pedido|pago|payment|tarjeta|contrase', re.I)
# (palabras de la voz, palabras de la pantalla) de cada tema
TEMAS = {
    'antes': (r'cuenta de google|bloquead|atrapad|verific|no te deja|omitir|frp|pide la cuenta',
              r'verifica tu cuenta|accede a tu cuenta|google|omitir|bloque'),
    'herramienta': (r'programa|herramienta|computador|\bpc\b|laptop|milagro|software|descarga',
                    r'unlocker|reader|tool|programa|descargas'),
    'cable': (r'cable|usb|conect|fastboot|modo|apag|botones?|volumen',
              r'fastboot|rescue|connect|usb'),
    'proceso': (r'quitar|eliminar|borr|paso a paso|reinici|desbloque|proceso|método|metodo',
                r'erase|checking|okay|preparando|comprobando|buscando|reboot'),
    'despues': (r'libre|nuevo|termina|listo|despu|funciona|magicos|android|parche|versión|version',
                r'\b\d{1,2}:\d\d\b|acerca del|bienvenid|ajustes|magicos|camara|configur'),
}
ORDEN = list(TEMAS)


def tema_de(frase, previo=None):
    """El tema de una frase de la voz; sin pista clara, el que sigue al anterior en el orden antes → después."""
    for t, (voz, _) in TEMAS.items():
        if re.search(voz, frase, re.I):
            return t
    return ORDEN[(ORDEN.index(previo) + 1) % len(ORDEN)] if previo else 'antes'


def frases(carpeta_voz, bid, inicio):
    """[(segundo del video armado, frase)] de la voz del bloque (su .align.json), o [] si no está."""
    try:
        al = json.load(open(os.path.join(carpeta_voz, f'{bid}.align.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    txt, ts = ''.join(al['characters']), al['character_start_times_seconds']
    salida, pos = [], 0
    for f in re.split(r'(?<=[.?!…])\s+', txt):
        i = txt.find(f, pos)
        if i < 0 or not f.strip():
            continue
        pos = i + len(f)
        salida.append((inicio + 0.3 + ts[i], f))
    return salida


def pantallas(mapa):
    """[(segundo, texto)] de los cuadros del mapa (lo que se lee y, si la IA lo vio, qué pantalla es y qué se hace)."""
    out = []
    for c in mapa or []:
        try:
            out.append((float(c.get('t') or 0), ' '.join(str(c.get(k) or '') for k in ('texto', 'pantalla', 'accion'))))
        except (AttributeError, TypeError, ValueError):
            continue
    return sorted(out)


def leer_mapa(mapa_f):
    try:
        return pantallas(json.load(open(mapa_f, encoding='utf-8'))['cuadros'])
    except (OSError, ValueError, KeyError, TypeError):
        return []


def en_pantalla(cuadros, desde, hasta):
    """Los cuadros del mapa que se ven entre desde y hasta: el último de antes (sigue en pantalla hasta el cambio) y los de adentro."""
    antes = [c for c in cuadros if c[0] <= desde]
    return antes[-1:] + [c for c in cuadros if desde < c[0] <= hasta]


def sensible(cuadros, desde, hasta):
    """Qué se lee entre desde y hasta con precio o datos personales (correo, teléfono, IMEI, saldo…), o '' si nada.
    Dice qué es sin copiar el dato: el aviso queda en archivos del proyecto."""
    for _, texto in en_pantalla(cuadros, desde, hasta):
        m = SENSIBLE.search(texto)
        if m:
            x = m.group()
            return ('un precio' if x.startswith('$') else 'un correo' if x == '@' else
                    'un número largo (teléfono, IMEI o pedido)' if x[-1].isdigit() else f'«{x.lower()}»')
    return ''


def tomas_de(b):
    """[(desde, hasta) o None] de las tomas que eligió la IA para un bloque del gancho, una por frase y en su orden."""
    out, tomas = [], b.get('tomas')
    for x in tomas if isinstance(tomas, list) else []:  # «"tomas": 5» de la IA no tumba la revisión ni el montaje
        try:
            if isinstance(x, dict):
                x = x.get('ventana') or [x.get('desde'), x.get('hasta')]
            while isinstance(x[0], (list, tuple)):  # [[18, 22]] por frase, como en los Shorts
                x = x[0]
            a, z = float(x[0]), float(x[1])
            out.append((a, z) if z > a >= 0 else None)
        except (TypeError, ValueError, IndexError, KeyError):
            out.append(None)
    return out


_ALINEAR = []


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s).lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


@functools.lru_cache(maxsize=512)
def _palabras(frase):
    """(grupos de 1 a 3 palabras de la frase que podrían leerse en pantalla, normalizar): los de alinear.py, que ya quitan
    las palabras comunes. Si no se puede cargar, las palabras largas sueltas."""
    if not _ALINEAR:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'alinear'))
            import alinear
            _ALINEAR.append(alinear)
        except Exception:
            _ALINEAR.append(None)
    if _ALINEAR[0] is None:
        return tuple(w for w in _norm(frase).split() if len(w) >= 5), _norm
    return tuple(_ALINEAR[0].candidatos(frase)), _ALINEAR[0].norm


class Puntos:
    """Los puntos de cada trozo candidato para una frase: palabras de la frase que se leen en esa pantalla (las raras del
    video valen más), nitidez y quietud (los datos nt de nitidez/ que montaje.py ya cargó) y si cambia de pantalla."""

    def __init__(self, cuadros, nt=None):
        self.cuadros = cuadros
        self.textos, self.df, self.normal = None, {}, {}
        self.nt, self.ref = nt, None
        if nt is not None:
            try:
                import numpy as np
                self.ref = (float(np.percentile(nt[1], 75)) or 1.0, float(np.percentile(nt[2], 90)) or 1.0)
            except Exception:
                self.nt = None

    def palabras(self, frase, texto):
        grupos, norm = _palabras(frase)
        if self.textos is None:
            self.textos = [' ' + norm(t) + ' ' for _, t in self.cuadros]
        n, pts = max(1, len(self.textos)), 0.0
        if texto not in self.normal:
            p = ' ' + norm(texto) + ' '
            self.normal[texto] = (p, {w[:5] for w in p.split() if len(w) >= 5})
        pantalla, raices = self.normal[texto]
        for g in grupos:
            if f' {g} ' in pantalla:
                pts += len(g.split()) * math.log(1 + n / max(1, self.cuantas(f' {g} ')))
            elif ' ' not in g and len(g) >= 5 and g[:5] in raices:  # volumen ↔ volume, reinicia ↔ reiniciar: vale la mitad
                pts += 0.5 * math.log(1 + n / max(1, self.cuantas(f' {g[:5]}')))
        return pts

    def rara(self, frase, texto):
        """Si en esa pantalla se lee algo de la frase que sale en pocas pantallas del video (un tercio o menos). Solo así entra
        una pantalla de otro tema: la marca o el programa, que salen en casi todas, no la traen (revisión, 03/11/2026:
        «conectamos el cable a tu Honor» ponía la pantalla bloqueada porque dice HONOR, y no la de USB)."""
        if self.palabras(frase, texto) <= 0:
            return False
        grupos, _ = _palabras(frase)
        pantalla, raices = self.normal[texto]
        n = max(1, len(self.textos))
        return any(self.cuantas(f' {g} ') * 3 <= n if f' {g} ' in pantalla else
                   ' ' not in g and len(g) >= 5 and g[:5] in raices and self.cuantas(f' {g[:5]}') * 3 <= n for g in grupos)

    def cuantas(self, trozo):
        """En cuántas pantallas del video se lee: lo que sale en todas (la marca, el programa) casi no cuenta."""
        if trozo not in self.df:
            self.df[trozo] = sum(1 for t in self.textos if trozo in t)
        return self.df[trozo]

    def de(self, frase, s, largo):
        vis = en_pantalla(self.cuadros, s, s + largo + 1.5)  # el cuadro del mapa cae hasta 1,5 s después del cambio
        texto = vis[0][1] if vis else ''
        pts = self.palabras(frase, texto) if frase and texto else 0.0
        if any(t > s + 0.5 and ' '.join(x.split()) != ' '.join(texto.split()) for t, x in vis[1:]):
            pts -= 1.5  # otro cambio de pantalla en sus 3-5 s: el trozo no muestra una sola cosa
        if self.nt is not None:
            import numpy as np
            tt, ni, mo = self.nt
            sel = (tt >= s) & (tt <= s + largo)
            if sel.any():
                pts += 0.5 * min(1.0, float(np.median(ni[sel])) / self.ref[0])  # nítido
                pts += 0.5 * (1 - min(1.0, float(mo[sel].mean()) / self.ref[1]))  # quieto
        return pts


def candidatos(mapa_f, dur_original):
    """{tema: [segundo del grabado]} con las pantallas del mapa que muestran ese tema y no tienen datos sensibles."""
    try:
        cuadros = json.load(open(mapa_f, encoding='utf-8'))['cuadros']
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    por_tema = {t: [] for t in TEMAS}
    for c in cuadros:
        texto = ' '.join(str(c.get(k) or '') for k in ('texto', 'pantalla', 'accion'))
        t0 = float(c.get('t') or 0)
        if SENSIBLE.search(texto) or t0 + TROZO[1] > dur_original:
            continue
        for t, (_, pantalla) in TEMAS.items():
            if re.search(pantalla, texto, re.I):
                por_tema[t].append(t0)
    return por_tema


def trozos(largo):
    """Parte un tramo en trozos de 3 a 5 s (iguales), los que hagan falta."""
    n = max(1, round(largo / 4.0))
    while largo / n > TROZO[1]:
        n += 1
    while n > 1 and largo / n < TROZO[0]:
        n -= 1
    return [largo / n] * n


def _mmss(s):
    return f'{int(s // 60)}:{s % 60:04.1f}'


def planear(bloques, mapa_f, carpeta_voz, dur_original, fps, guardar_avisos=True, nt=None):
    """{id del bloque: [(segundo del grabado, cuadros)]} para las pausas largas del inicio. Escribe/borra avisos_inicio.json
    (con guardar_avisos=False, en una prueba de unos pocos bloques, no lo toca). nt: (tiempos, nitidez, movimiento) de
    nitidez/, para preferir los trozos nítidos y quietos."""
    plan, avisos, usados = {}, [], []
    por_tema = candidatos(mapa_f, dur_original)
    cuadros = leer_mapa(mapa_f)
    puntos = Puntos(cuadros, nt)
    previo, ultimo = None, None  # ultimo: (desde, hasta) del grabado que se ve justo antes (nunca el mismo trozo seguido)
    for b in bloques:
        m, ini = b.get('montaje') or {}, b.get('inicio_min')
        gancho = bool(b.get('gancho'))  # el gancho es el inicio aunque se pase del límite (si dura de más, se avisa abajo)
        if (ini is None or (ini >= LIMITE and not gancho) or not str(m.get('modo', '')).endswith('congelar') or m.get('quieto')
                or m.get('sin_rotar') or float(m.get('congelar_s') or 0) < (PAUSA_MIN_GANCHO if gancho else PAUSA_MIN)):
            if m.get('src_inicio') is not None and m.get('modo') != 'imagen':  # su escena es lo que se ve justo antes del siguiente
                ultimo = (m['src_inicio'], m.get('src_fin') or m['src_inicio'] + 3)
            continue
        pausa = float(m.get('congelar_s') or 0)
        tramo = (m['src_fin'] - m['src_inicio']) / (m.get('velocidad') or 1) if m['modo'] == 'lento+congelar' else 0
        p0, p1 = ini + tramo, ini + tramo + pausa  # la pausa, en segundos del video armado
        fr = frases(carpeta_voz, b['id'], ini)
        tomas = tomas_de(b) if gancho else []
        propio = (m['src_inicio'], m.get('src_fin') or m['src_inicio'])  # «congelar»: src_fin puede venir vacío
        if m['modo'] == 'lento+congelar':
            ultimo = propio
        # cortes de la pausa donde empieza cada frase: nunca un tramo de menos de 3 s (con las tomas de la IA, de 1,5 s)
        minimo = CORTE_GANCHO if any(tomas) else TROZO[0]
        cortes = [p0]
        for t, _ in fr:
            if t - cortes[-1] >= minimo and p1 - t >= minimo:
                cortes.append(t)
        cortes.append(p1)
        piezas, sigue, avisadas = [], None, set()  # sigue: (frase, segundo, largo) de la última toma de la IA puesta
        for a, z in zip(cortes, cortes[1:]):
            x = a
            for largo in trozos(z - a):
                k = max((i for i, (t, _) in enumerate(fr) if t <= x + 0.5), default=0)  # la frase que se dice ahí
                frase = fr[k][1] if fr else ''
                tema = tema_de(frase, previo)
                x += largo
                elegido = None
                if k < len(tomas) and tomas[k]:  # gancho: la toma que eligió la IA para esta frase
                    desde, hasta = tomas[k]
                    continua = bool(sigue and sigue[0] == k)  # la frase sigue: su toma sigue corriendo en el grabado
                    s = sigue[1] + sigue[2] if continua else desde
                    dato = sensible(cuadros, s, s + largo)
                    if s + largo > dur_original:
                        problema = 'se sale de la grabación'
                    elif dato:
                        problema = f'tiene precio o datos personales en pantalla ({dato})'
                    elif not continua and ultimo and min(s + largo, ultimo[1]) - max(s, ultimo[0]) > 0.5:
                        problema = f'repite el trozo que se ve justo antes ({_mmss(ultimo[0])}–{_mmss(ultimo[1])})'
                    else:
                        problema = None
                        elegido = (s, 'toma IA')
                    if problema and k not in avisadas:
                        avisadas.add(k)
                        avisos.append({'bloque': b['id'], 'aviso': f'{b["id"]}: la toma {k + 1} de la IA ({_mmss(desde)}–{_mmss(hasta)}) '
                                                                   f'{problema}: puse otro trozo del grabado. Elige otra toma en el guion.'})
                        print('AVISO inicio ·', avisos[-1]['aviso'], flush=True)
                if not elegido:
                    # las pantallas donde se lee algo poco común de la frase entran aunque no sean de ningún tema, pero nunca
                    # una del ANTES en una frase del DESPUÉS ni al revés
                    contra = set(por_tema.get(OPUESTO.get(tema), [])) - set(por_tema.get(tema, []))
                    con_palabras = [c for c, texto in cuadros if frase and c not in contra and puntos.rara(frase, texto)]
                    for t in [tema] + [y for y in ORDEN if y != tema]:  # sin material del tema: el más cercano que haya
                        orden_t = sorted(por_tema.get(t, []), reverse=(t == 'despues'))  # el después, de lo último del grabado
                        if t == tema:
                            orden_t += [c for c in sorted(con_palabras, reverse=(t == 'despues')) if c not in orden_t]
                        libres = [s for s in orden_t if all(abs(s - u) > SEPARACION for u in usados)
                                  and not (propio[0] - 2 <= s <= propio[1] + 2)
                                  and s + largo <= dur_original and not sensible(cuadros, s, s + largo)]
                        if libres:  # el de más puntos; si empatan, el primero (el orden de siempre)
                            if t in OPUESTO:  # el antes y el después: solo los cercanos al de siempre (comienzo o final del grabado)
                                libres = [s for s in libres if abs(s - libres[0]) <= EXTREMO]
                            elegido = (max(libres, key=lambda s: puntos.de(frase, s, largo)), t)
                            break
                if not elegido:
                    piezas = None
                    break
                sigue = (k, elegido[0], largo) if elegido[1] == 'toma IA' else None
                usados.append(elegido[0])
                previo = tema if elegido[1] == 'toma IA' else elegido[1]
                ultimo = (elegido[0], elegido[0] + largo)
                # los cuadros se cuentan sobre el tiempo del video armado (como montaje.py desde la mejora 1): cada toma
                # empieza en el cuadro de su frase. Antes cada trozo redondeaba por su cuenta y se corría ±1 cuadro (03/11/2026)
                piezas.append((elegido[0], int(round(x * fps)) - int(round((x - largo) * fps)), elegido[1]))
            if piezas is None:
                break
        if piezas:
            total = int(round(pausa * fps))
            piezas[-1] = (piezas[-1][0], piezas[-1][1] + total - sum(p[1] for p in piezas), piezas[-1][2])  # cuadro exacto
            plan[b['id']] = [(s, n) for s, n, _ in piezas]
            print(b['id'], '· inicio: la pausa rota', len(piezas), 'trozos del grabado:',
                  ', '.join(f'{t} {int(s // 60)}:{s % 60:04.1f}' for s, _, t in piezas), flush=True)
        else:
            avisos.append({'bloque': b['id'], 'pausa_s': round(pausa, 1),
                           'aviso': f'{b["id"]}: no hay suficientes pantallas distintas en el grabado para rotar los {pausa:.0f} s de pausa '
                                    'del inicio: la escena se repite. Acorta la pausa, sube material extra o pide a Claude que elija los trozos.'})
            print('AVISO inicio ·', avisos[-1]['aviso'], flush=True)
    ganchos = [b for b in bloques if b.get('gancho') and b.get('inicio_min') is not None]
    fin = max((float(b.get('fin_max') or b['inicio_min']) for b in ganchos), default=0)
    if fin > GANCHO[1]:  # en los primeros 30 s se va mucha gente: un gancho largo no la retiene
        avisos.append({'bloque': ganchos[-1]['id'], 'aviso': f'el gancho ({", ".join(b["id"] for b in ganchos)}) dura {fin:.0f} s: pasa de '
                                                            f'{GANCHO[0]:.0f}-{GANCHO[1]:.0f} s. Acórtalo a unos {GANCHO[0]:.0f} s '
                                                            '(frases más cortas o menos bloques).'})
        print('AVISO inicio ·', avisos[-1]['aviso'], flush=True)
    if not guardar_avisos:
        return plan
    if avisos:
        json.dump(avisos, open(AVISOS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    elif os.path.exists(AVISOS):
        os.remove(AVISOS)
    return plan
