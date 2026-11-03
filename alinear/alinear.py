"""Que cada frase de la voz caiga sobre la pantalla que nombra (pedido de fabian, 30/10/2026: «que no vuelva a suceder»).

Va DESPUÉS de la voz (con sus tiempos reales) y ANTES del montaje, dentro de «▶ Hacer todo» y de «Solo los bloques»
(desde el 03/11/2026; se apaga en «⚙ Ajustes IA»). Gratis: todo en tu PC.
1. Lee el texto de la pantalla de toda la grabación, un cuadro cada 2 s (OCR), y lo guarda en ocr_pantalla.json
   (la primera vez tarda unos minutos; después es instantáneo). Cerca (±3 s) de las frases que quedan dudosas vuelve a
   leer cada 0,5 s, solo ahí: más precisión sin que la primera pasada tarde más.
2. Por cada frase de cada bloque busca lo que nombra de la pantalla («No copiar», «Ajustes», «Configurar más tarde»…).
   Si en el segundo en que la voz lo dice esa pantalla no se ve, pero sí aparece un poco antes o después dentro del tramo
   del bloque, corre el tramo (inicio y velocidad) para que caiga justo ahí, sin pisar los bloques vecinos y sin pasar los
   topes de fabian (×1 con su cara o en un ⭐, ×1,5 en los pasos clave, ×2 en los de configuración). Antes de escribir deja
   guion.json.antes_alinear y marca cada bloque que corrió con "alineado": true. Los bloques del gancho ("gancho": true,
   el primer minuto) no se tocan.
3. Lo que no puede arreglar solo lo deja en alineacion.txt y lo avisa (la app pausa «Hacer todo» para que lo veas).
   Con --solo-revisar no cambia nada: solo dice qué haría (la app lo corre así en los 2 primeros videos).

    python alinear.py --proyecto CARPETA [--guion guion.json] [--solo-revisar]
"""
import argparse, json, os, re, shutil, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
sys.path.insert(0, os.path.join(RAIZ, 'importantes'))
import cv2  # noqa: E402

PASO = 2.0       # un cuadro de OCR cada 2 s de la grabación
# se acepta si la pantalla está desde 1 s antes hasta 1,5 s después de que la voz la nombra (03/11/2026: con 2,5 y 3,5 s
# una frase podía caer 3 s tarde y contaba como bien)
TOLERA = (1.0, 1.5)
FINO = 0.5       # cerca de una frase dudosa se vuelve a leer la pantalla cada 0,5 s…
CERCA = 3.0      # …desde 3 s antes hasta 3 s después de que la voz la dice
VEL = (0.6, 6.0)
COMUNES = set('''para como esta este esto estos estas pero porque cuando donde desde hasta sobre entre ahora aqui alli
ya hay muy mas menos todo toda todos todas nada algo cada otro otra otros otras mismo misma bien solo sola tambien
vamos damos dale darle damos hacemos tenemos podemos puedes quieres quiere tiene tienen hace hacer poner sale salen
vez veces ver ves vemos verifica dice decir telefono celular equipo proceso paso pasos minutos segundos rapido
nuestro nuestra luego despues antes primero segundo tercero simplemente totalmente perfecto listo lista''' .split())


def norm(s):
    s = unicodedata.normalize('NFKD', str(s).lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def grueso(s):
    """¿Es un cuadro de la pasada de cada 2 s? (los de cada 0,5 s se suman después, solo cerca de las frases dudosas)"""
    return abs(s / PASO - round(s / PASO)) < 0.01


def leer(d, idx, segundos, avance=print, titulo='', parecido=3.5):
    """Lee el texto de la pantalla en esos segundos de la grabación y lo suma a idx (y a ocr_pantalla.json). Si la imagen
    casi no cambió desde el cuadro anterior (diferencia menor que `parecido`), es la misma pantalla y no se lee de nuevo.
    Devuelve False si no hay lector de texto."""
    import ia
    ocr = ia.lector_ocr()
    if ocr is None:
        return False
    if titulo:
        avance(titulo)
    f = os.path.join(d, 'ocr_pantalla.json')
    cap = cv2.VideoCapture(os.path.join(d, 'original.mp4'))
    chico, texto = None, ''
    for n, s in enumerate(segundos, 1):
        cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
        ok, c = cap.read()
        if ok:
            g = cv2.resize(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), (96, 54)).astype('int16')
            if chico is None or abs(g - chico).mean() > parecido:  # la imagen cambió: se lee de nuevo (si no, es la misma pantalla)
                c = cv2.resize(c, (1280, int(c.shape[0] * 1280 / c.shape[1])))
                texto = norm(' '.join(t for t, *_ in ia.leer_textos(ocr, c)))
                chico = g
            idx[s] = texto
        if n % 25 == 0 or n == len(segundos):
            avance(f'· pantalla leída {int(100 * n / len(segundos))} %')
            json.dump({str(k): v for k, v in sorted(idx.items())}, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
    cap.release()
    return True


def indice(d, avance=print):
    """{segundo: texto normalizado de la pantalla}, cada PASO s de toda la grabación (en caché)."""
    f = os.path.join(d, 'ocr_pantalla.json')
    try:
        idx = {float(k): v for k, v in json.load(open(f, encoding='utf-8')).items()}
    except (OSError, ValueError):
        idx = {}
    cap = cv2.VideoCapture(os.path.join(d, 'original.mp4'))
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
    cap.release()
    # «< total»: un cuadro justo en el final no se puede leer y se volvía a pedir (y a cargar el lector) en cada vuelta
    faltan = [round(k * PASO, 1) for k in range(int(total / PASO) + 1) if k * PASO < total and round(k * PASO, 1) not in idx]
    if faltan:
        leer(d, idx, faltan, avance, f'Leo la pantalla de tu video ({len(faltan)} cuadros, solo la primera vez)…')
    return idx


def alrededor(s, fin):
    """Los segundos, cada FINO, desde CERCA antes hasta CERCA después de s (dentro de la grabación)."""
    c, n = round(s / FINO) * FINO, int(CERCA / FINO)
    return [round(c + k * FINO, 1) for k in range(-n, n + 1) if 0 <= c + k * FINO <= fin]


def candidatos(frase):
    """Grupos de 1 a 3 palabras de la frase que podrían estar escritos en la pantalla."""
    w = norm(frase).split()
    out = []
    for n in (3, 2, 1):
        for i in range(len(w) - n + 1):
            g = w[i:i + n]
            if all(x in COMUNES or len(x) < 3 for x in g):
                continue
            if n == 1 and (len(g[0]) < 5 or g[0] in COMUNES):
                continue
            out.append(' '.join(g))
    return out


def en_tramo(mo, t):
    """Segundo de la grabación que se ve t s después de que empieza el bloque (en la pausa, el final del tramo)."""
    v = mo.get('velocidad') or 1
    largo = (mo['src_fin'] - mo['src_inicio']) / v
    return mo['src_inicio'] + min(t, largo) * v if t <= largo else mo['src_fin'] - 1.2


def se_ve(idx, cand, s):
    """¿Se lee `cand` en la pantalla desde TOLERA[0] s antes hasta TOLERA[1] s después del segundo s? (con los cuadros de
    cada 2 s siempre cae al menos uno en esa ventana; cerca de las frases dudosas hay además uno cada 0,5 s)"""
    return any(cand in v for k, v in idx.items() if s - TOLERA[0] - 1e-6 <= k <= s + TOLERA[1] + 1e-6)


def revisar_bloque(idx, b, frases, lo, hi, mo=None):
    """[(frase, t_bloque, segundo_que_se_ve, cand, segundo_donde_está | None)] de las frases que nombran algo de la pantalla."""
    import voz
    mo = mo or b['montaje']
    zona = [s for s in idx if lo - 1 <= s <= hi + 1]
    if not zona:
        return []
    gruesa = [s for s in zona if grueso(s)] or zona  # los cuadros extra de cada 0,5 s no cuentan para «lo que está siempre»
    cuenta = {}
    for s in gruesa:
        for p in set(idx[s].split()):
            cuenta[p] = cuenta.get(p, 0) + 1
    fijas = {p for p, n in cuenta.items() if n > 0.4 * len(gruesa)}  # lo que está siempre (la PC, la marca): no sirve de pista
    out = []
    for frase, t0, _ in frases:
        t = voz.DESFASE + t0
        s = en_tramo(mo, t)
        cands = [c for c in candidatos(frase) if not set(c.split()) <= fijas and any(c in idx[z] for z in zona)]
        if not cands:
            continue
        c = cands[0]  # el más largo (los de 3 palabras van primero)
        donde = None if se_ve(idx, c, s) else min((z for z in zona if c in idx[z]), key=lambda z: abs(z - s))
        out.append((frase, t, s, c, donde))
    return out


def ajustar(b, revision, lo, hi, estrellas=(), pausas=()):
    """Corre inicio y velocidad del tramo para que las frases caigan donde está su pantalla. Devuelve el montaje nuevo o None.
    Respeta los topes de fabian (los mismos de la voz, voz.tope_velocidad) y no sale de lo..hi (lo que dejan libre los
    bloques vecinos). 03/11/2026: en la prueba, un paso de configuración y un bloque con su cara quedaban a ×4,29 y ×6, y un
    tramo de 12 s se estiraba a 45 s. `estrellas`: los «⭐ cortes importantes» (cortes_importantes.json); `pausas`: el
    segundo de cada pausa sola («congelar») del guion."""
    import importantes, voz
    mo = dict(b['montaje'])
    if mo.get('importante') or b.get('gancho'):  # «⭐ corte importante»: va entero y a ×1; el gancho (primer minuto) va aparte
        return None
    if importantes.toca(mo, estrellas):  # un ⭐ que el bloque muestra aunque no quedó marcado: tampoco se toca
        return None
    pts = [(t, donde if donde is not None else s) for _, t, s, _, donde in revision]
    if not any(donde is not None for *_, donde in revision):
        return None
    v0 = mo.get('velocidad') or 1
    if len(pts) >= 2 and max(p[0] for p in pts) - min(p[0] for p in pts) > 2:
        n = len(pts)
        mt, ms = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
        v = sum((t - mt) * (s - ms) for t, s in pts) / max(1e-6, sum((t - mt) ** 2 for t, _ in pts))
    else:
        v = v0
    critico = mo.get('critico') or b.get('tipo') == 'critico'
    tope = voz.tope_velocidad(dict(mo, critico=True) if critico else mo)
    # con su cara, siempre a ×1 (ni acelerada ni en cámara lenta, como en la voz); lo demás, de ×0,6 a su tope
    v = 1.0 if mo.get('cara') else min(tope, max(VEL[0], v))
    a = max(lo, sum(s - v * t for t, s in pts) / len(pts))
    largo = max((mo['src_fin'] - mo['src_inicio']) / v0, max(t for t, _ in pts) + 1.0)
    fin = min(hi, a + v * largo)  # nunca entra en el tramo del bloque siguiente
    a, fin = max(lo, round(a, 1)), min(hi, round(fin, 1))  # el redondeo tampoco pisa a los vecinos
    if fin - a < 1:
        return None
    # corrido no puede quedar encima de un ⭐ (va entero y a ×1): en la revisión del 03/11/2026 un tramo normal se corrió
    # sobre un ⭐ que ningún bloque mostraba y lo dejó a ×5,33. Así no se toca y la frase queda como aviso
    if importantes.toca(dict(mo, src_inicio=a, src_fin=fin), estrellas):
        return None
    # la pausa que repite un momento de este tramo tiene que seguir dentro: si no, después del tramo corrido se veía algo
    # de antes, fuera de orden (revisión 03/11/2026)
    if any(mo['src_inicio'] < p < mo['src_fin'] and not a <= p <= fin for p in pausas):
        return None
    mo.update(src_inicio=a, src_fin=fin, velocidad=round(v, 2), alineado=True)
    if mo['modo'].startswith('lento'):
        mo['modo'], mo['congelar_s'] = 'lento+congelar', 0
    return mo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--guion', default='guion.json')
    ap.add_argument('--solo-revisar', action='store_true', help='no cambia el guion: solo dice qué frases no caen en su pantalla')
    a = ap.parse_args()
    import ia, importantes, voz
    d = os.path.abspath(a.proyecto)
    ruta = os.path.join(d, a.guion)
    g = json.load(open(ruta, encoding='utf-8'))
    avance = lambda x: print(x, flush=True)
    idx = indice(d, avance)
    if not idx:
        print('· no pude leer la pantalla del video: no reviso la alineación', flush=True)
        return
    todos = list(g['bloques'])
    completo = os.path.join(d, 'guion.json')
    if os.path.abspath(ruta) != completo and os.path.exists(completo):
        # «Solo los bloques» (guion_prueba.json): los vecinos de verdad están en el guion completo, y tampoco se pisan
        try:
            propios = {b.get('id') for b in g['bloques']}
            todos += [b for b in json.load(open(completo, encoding='utf-8'))['bloques'] if b.get('id') not in propios]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    mios = {id(b) for b in g['bloques']}
    bl = [b for b in todos if (b.get('montaje') or {}).get('modo', '').startswith('lento') and b['montaje'].get('src_fin')]
    orden = sorted(bl, key=lambda b: b['montaje']['src_inicio'])
    fin_video = max((k for k in idx if grueso(k)), default=max(idx))
    # las pausas solas («congelar») también son vecinas: un tramo corrido por encima de una pausa que estaba fuera de él la
    # dejaba mostrando algo de antes, fuera de orden (revisión 03/11/2026). Las que caen dentro de su tramo no son límite:
    # repiten a propósito un momento de ese tramo, y ajustar() cuida que sigan dentro
    pausas = [b['montaje']['src_inicio'] for b in todos if (b.get('montaje') or {}).get('modo') == 'congelar'
              and isinstance(b['montaje'].get('src_inicio'), (int, float))]
    estrellas = importantes.leer(d)  # «⭐ cortes importantes»: un tramo no se corre encima de ellos

    def limites(i):  # lo que dejan libre los bloques de al lado (se mira en el momento: el anterior pudo correrse)
        mo = orden[i]['montaje']
        lo = orden[i - 1]['montaje']['src_fin'] if i else 0.0
        # el último llega hasta el final de lo leído, o hasta donde ya llegaba (antes perdía hasta 2 s de su final)
        hi = orden[i + 1]['montaje']['src_inicio'] if i + 1 < len(orden) else max(fin_video, mo['src_fin'])
        return (max([lo] + [p for p in pausas if p <= mo['src_inicio']]),
                min([hi] + [p for p in pausas if p >= mo['src_fin']]))

    gancho = [b['id'] for b in orden if id(b) in mios and b.get('gancho')]
    if gancho:
        print(f'· no toco {len(gancho)} bloque(s) del gancho (el primer minuto va aparte): {", ".join(gancho)}', flush=True)
    revisar = [(i, b, ia.frases_bloque(d, b)) for i, b in enumerate(orden) if id(b) in mios and not b.get('gancho')]
    # frases dudosas (su pantalla no se ve justo cuando la voz la nombra): se vuelve a leer cada 0,5 s solo a su alrededor
    fino = set()
    for i, b, frases in revisar:
        for _, _, s, _, donde in revisar_bloque(idx, b, frases, *limites(i)):
            if donde is not None:
                fino.update(alrededor(s, fin_video))
    fino = sorted(x for x in fino if x not in idx)
    if fino:
        leer(d, idx, fino, avance, f'Miro de cerca las frases dudosas: un cuadro cada {FINO:g} s ({len(fino)} cuadros)…', parecido=1.0)
    arreglados, quedan, informe = [], [], []
    for i, b, frases in revisar:
        lo, hi = limites(i)
        rev = revisar_bloque(idx, b, frases, lo, hi)
        malas = [r for r in rev if r[4] is not None]
        if not malas:
            continue
        nuevo = ajustar(b, rev, lo, hi, estrellas, pausas)
        if nuevo:
            despues = [r for r in revisar_bloque(idx, b, frases, lo, hi, nuevo) if r[4] is not None]
            if len(despues) < len(malas):
                tramo = f"{nuevo['src_inicio']:.1f}–{nuevo['src_fin']:.1f} ×{nuevo['velocidad']}"
                if a.solo_revisar:  # los primeros videos: solo dice lo que haría, para compararlo con lo que corriges a mano
                    informe.append(f"{b['id']}: (solo aviso, no lo toqué) correría el tramo a {tramo} para que "
                                   f"{len(malas) - len(despues)} frase(s) caigan sobre su pantalla")
                else:
                    b['montaje'].update(nuevo)
                    arreglados.append(b['id'])
                    informe.append(f"{b['id']}: corrí el tramo a {tramo} para que {len(malas) - len(despues)} frase(s) "
                                   "caigan sobre su pantalla")
                    malas = despues
        for frase, t, s, c, donde in malas:
            quedan.append(b['id'])
            informe.append(f"{b['id']}: «{frase[:70]}» nombra «{c}», pero en {int(s // 60)}:{s % 60:04.1f} no se ve; "
                           f"aparece en {int(donde // 60)}:{donde % 60:04.1f}")
    if arreglados:
        shutil.copyfile(ruta, ruta + '.antes_alinear')  # el guion como estaba antes de correr los tramos, para comparar o volver
        json.dump(g, open(ruta, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        for x in voz.ajustar_guion(ruta, os.path.join(d, 'voz')):
            informe.append(x)
    cabeza = 'Cada frase de la voz contra la pantalla que nombra (OCR, gratis)\n'
    if a.solo_revisar:
        cabeza += 'Modo solo avisar: no toqué el guion. Compara lo que propongo con lo que corrijas a mano.\n'
    open(os.path.join(d, 'alineacion.txt'), 'w', encoding='utf-8').write(
        cabeza + '\n' + ('\n'.join(informe) or 'Todo en su lugar.') + '\n')
    for x in informe:
        print('· ' + x, flush=True)
    if a.solo_revisar:
        print('· modo solo avisar: no toqué el guion (compara alineacion.txt con lo que corrijas a mano)', flush=True)
    if quedan:
        print(f'AVISO: {len(set(quedan))} bloque(s) con frases que no caen sobre su pantalla: {", ".join(sorted(set(quedan)))} '
              '(mira alineacion.txt)', flush=True)
    print(f'Listo: {len(arreglados)} tramo(s) corregido(s) solos, {len(set(quedan))} para revisar.', flush=True)


if __name__ == '__main__':
    main()
