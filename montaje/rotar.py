"""Regla de fabian (31/10/2026), para TODOS los videos: el primer minuto (el inicio, hasta ~1:20) no puede ser una escena
larga repetida. Las pausas largas de esos bloques ROTAN trozos reales del grabado, de 3 a 5 s, elegidos por lo que dice
la voz en cada frase: antes (cuenta de Google, bloqueado) → herramienta (el programa, la PC) → cable / Fastboot →
proceso (borrar, reiniciar) → después (pantalla de inicio, Ajustes). Nunca el mismo trozo seguido, nunca una captura
fija (las capturas quedan solo para las miniaturas), y nada con precio ni datos personales (según el texto que leyó el
mapa del video en esa pantalla). Si no hay material suficiente para rotar, deja un aviso en avisos_inicio.json (la vista
previa lo muestra) en vez de repetir la escena en silencio.

Lo usa montaje.py: planear() dice, para cada bloque del inicio con una pausa larga, qué trozos van en esa pausa.
"""
import json, os, re

LIMITE = 80.0         # segundos del video armado donde rige la regla (el inicio)
PAUSA_MIN = 6.0       # una pausa más corta se deja como estaba (la repetición de su escena no alcanza a cansar)
TROZO = (3.0, 5.0)    # largo de cada trozo
SEPARACION = 8.0      # dos trozos del inicio no salen de momentos tan cercanos del grabado
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


def planear(bloques, mapa_f, carpeta_voz, dur_original, fps):
    """{id del bloque: [(segundo del grabado, cuadros)]} para las pausas largas del inicio. Escribe/borra avisos_inicio.json."""
    plan, avisos, usados = {}, [], []
    por_tema = candidatos(mapa_f, dur_original)
    previo = None
    for b in bloques:
        m, ini = b.get('montaje') or {}, b.get('inicio_min')
        if ini is None or ini >= LIMITE or not str(m.get('modo', '')).endswith('congelar') or m.get('quieto') or m.get('sin_rotar'):
            continue
        pausa = float(m.get('congelar_s') or 0)
        if pausa < PAUSA_MIN:
            continue
        tramo = (m['src_fin'] - m['src_inicio']) / (m.get('velocidad') or 1) if m['modo'] == 'lento+congelar' else 0
        p0, p1 = ini + tramo, ini + tramo + pausa  # la pausa, en segundos del video armado
        fr = frases(carpeta_voz, b['id'], ini)
        # cortes de la pausa donde empieza cada frase
        cortes = [p0]
        for t, _ in fr:  # nunca un tramo de menos de 3 s
            if t - cortes[-1] >= TROZO[0] and p1 - t >= TROZO[0]:
                cortes.append(t)
        cortes.append(p1)
        piezas = []
        for a, z in zip(cortes, cortes[1:]):
            frase = next((f for t, f in reversed(fr) if t <= a + 0.5), fr[0][1] if fr else '')
            tema = tema_de(frase, previo)
            for largo in trozos(z - a):
                elegido = None
                for t in [tema] + [x for x in ORDEN if x != tema]:  # sin material del tema: el más cercano que haya
                    orden_t = sorted(por_tema.get(t, []), reverse=(t == 'despues'))  # el después, de lo último del grabado
                    libres = [s for s in orden_t if all(abs(s - u) > SEPARACION for u in usados)
                              and not (m['src_inicio'] - 2 <= s <= m.get('src_fin', m['src_inicio']) + 2)]
                    if libres:
                        elegido = (libres[0], t)
                        break
                if not elegido:
                    piezas = None
                    break
                usados.append(elegido[0])
                previo = elegido[1]
                piezas.append((elegido[0], int(round(largo * fps)), elegido[1]))
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
    if avisos:
        json.dump(avisos, open(AVISOS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    elif os.path.exists(AVISOS):
        os.remove(AVISOS)
    return plan
