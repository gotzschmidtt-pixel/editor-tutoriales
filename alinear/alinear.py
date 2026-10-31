"""Que cada frase de la voz caiga sobre la pantalla que nombra (pedido de fabian, 30/10/2026: «que no vuelva a suceder»).

Va DESPUÉS de la voz (con sus tiempos reales) y ANTES del montaje. Gratis: todo en tu PC.
1. Lee el texto de la pantalla de toda la grabación, un cuadro cada 2 s (OCR), y lo guarda en ocr_pantalla.json
   (la primera vez tarda unos minutos; después es instantáneo).
2. Por cada frase de cada bloque busca lo que nombra de la pantalla («No copiar», «Ajustes», «Configurar más tarde»…).
   Si en el segundo en que la voz lo dice esa pantalla no se ve, pero sí aparece un poco antes o después dentro del tramo
   del bloque, corre el tramo (inicio y velocidad) para que caiga justo ahí, sin pisar los bloques vecinos.
3. Lo que no puede arreglar solo lo deja en alineacion.txt y lo avisa (la app pausa «Hacer todo» para que lo veas).

    python alinear.py --proyecto CARPETA [--guion guion.json] [--solo-revisar]
"""
import argparse, json, os, re, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
import cv2  # noqa: E402

PASO = 2.0       # un cuadro de OCR cada 2 s de la grabación
TOLERA = (2.5, 3.5)  # se acepta si la pantalla está desde 2,5 s antes hasta 3,5 s después de que la voz la nombra
VEL = (0.6, 6.0)
VEL_CRITICO = 1.5
COMUNES = set('''para como esta este esto estos estas pero porque cuando donde desde hasta sobre entre ahora aqui alli
ya hay muy mas menos todo toda todos todas nada algo cada otro otra otros otras mismo misma bien solo sola tambien
vamos damos dale darle damos hacemos tenemos podemos puedes quieres quiere tiene tienen hace hacer poner sale salen
vez veces ver ves vemos verifica dice decir telefono celular equipo proceso paso pasos minutos segundos rapido
nuestro nuestra luego despues antes primero segundo tercero simplemente totalmente perfecto listo lista''' .split())


def norm(s):
    s = unicodedata.normalize('NFKD', str(s).lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def indice(d, avance=print):
    """{segundo: texto normalizado de la pantalla}, cada PASO s de toda la grabación (en caché)."""
    import ia
    f = os.path.join(d, 'ocr_pantalla.json')
    try:
        idx = {float(k): v for k, v in json.load(open(f, encoding='utf-8')).items()}
    except (OSError, ValueError):
        idx = {}
    cap = cv2.VideoCapture(os.path.join(d, 'original.mp4'))
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
    faltan = [round(k * PASO, 1) for k in range(int(total / PASO) + 1) if round(k * PASO, 1) not in idx]
    if faltan:
        ocr = ia.lector_ocr()
        if ocr is None:
            return idx
        avance(f'Leo la pantalla de tu video ({len(faltan)} cuadros, solo la primera vez)…')
        chico, texto = None, ''
        for n, s in enumerate(faltan, 1):
            cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
            ok, c = cap.read()
            if ok:
                g = cv2.resize(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), (96, 54)).astype('int16')
                if chico is None or abs(g - chico).mean() > 3.5:  # la imagen cambió: se lee de nuevo (si no, es la misma pantalla)
                    c = cv2.resize(c, (1280, int(c.shape[0] * 1280 / c.shape[1])))
                    texto = norm(' '.join(t for t, *_ in ia.leer_textos(ocr, c)))
                    chico = g
                idx[s] = texto
            if n % 25 == 0 or n == len(faltan):
                avance(f'· pantalla leída {int(100 * n / len(faltan))} %')
                json.dump({str(k): v for k, v in sorted(idx.items())}, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
    cap.release()
    return idx


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
    return any(cand in idx.get(round(k * PASO, 1), '') for k in range(int((s - TOLERA[0]) / PASO), int((s + TOLERA[1]) / PASO) + 1))


def revisar_bloque(idx, b, frases, lo, hi, mo=None):
    """[(frase, t_bloque, segundo_que_se_ve, cand, segundo_donde_está | None)] de las frases que nombran algo de la pantalla."""
    import voz
    mo = mo or b['montaje']
    zona = [s for s in idx if lo - 1 <= s <= hi + 1]
    if not zona:
        return []
    cuenta = {}
    for s in zona:
        for p in set(idx[s].split()):
            cuenta[p] = cuenta.get(p, 0) + 1
    fijas = {p for p, n in cuenta.items() if n > 0.4 * len(zona)}  # lo que está siempre (la PC, la marca): no sirve de pista
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


def ajustar(b, revision, lo, hi):
    """Corre inicio y velocidad del tramo para que las frases caigan donde está su pantalla. Devuelve el montaje nuevo o None."""
    mo = dict(b['montaje'])
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
    tope = VEL_CRITICO if (b.get('tipo') == 'critico' or mo.get('critico') or mo.get('importante')) and v0 <= VEL_CRITICO else VEL[1]
    v = min(tope, max(VEL[0], v))
    a = sum(s - v * t for t, s in pts) / len(pts)
    a = max(lo, a)
    largo = max((mo['src_fin'] - mo['src_inicio']) / v0, max(t for t, _ in pts) + 1.0)
    fin = min(hi, a + v * largo)
    if fin - a < 1:
        return None
    mo.update(src_inicio=round(a, 1), src_fin=round(fin, 1), velocidad=round(v, 2))
    if mo['modo'].startswith('lento'):
        mo['modo'], mo['congelar_s'] = 'lento+congelar', 0
    return mo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--guion', default='guion.json')
    ap.add_argument('--solo-revisar', action='store_true', help='no cambia el guion: solo dice qué frases no caen en su pantalla')
    a = ap.parse_args()
    import ia, voz
    d = os.path.abspath(a.proyecto)
    ruta = os.path.join(d, a.guion)
    g = json.load(open(ruta, encoding='utf-8'))
    idx = indice(d, lambda x: print(x, flush=True))
    if not idx:
        print('· no pude leer la pantalla del video: no reviso la alineación', flush=True)
        return
    bl = [b for b in g['bloques'] if (b.get('montaje') or {}).get('modo', '').startswith('lento') and b['montaje'].get('src_fin')]
    orden = sorted(bl, key=lambda b: b['montaje']['src_inicio'])
    arreglados, quedan, informe = [], [], []
    for i, b in enumerate(orden):
        lo = orden[i - 1]['montaje']['src_fin'] if i else 0.0
        hi = orden[i + 1]['montaje']['src_inicio'] if i + 1 < len(orden) else max(idx)
        frases = ia.frases_bloque(d, b)
        rev = revisar_bloque(idx, b, frases, lo, hi)
        malas = [r for r in rev if r[4] is not None]
        if not malas:
            continue
        nuevo = None if a.solo_revisar else ajustar(b, rev, lo, hi)
        if nuevo:
            despues = [r for r in revisar_bloque(idx, b, frases, lo, hi, nuevo) if r[4] is not None]
            if len(despues) < len(malas):
                b['montaje'].update(nuevo)
                arreglados.append(b['id'])
                informe.append(f"{b['id']}: corrí el tramo a {nuevo['src_inicio']:.1f}–{nuevo['src_fin']:.1f} ×{nuevo['velocidad']} "
                               f"para que {len(malas) - len(despues)} frase(s) caigan sobre su pantalla")
                malas = despues
        for frase, t, s, c, donde in malas:
            quedan.append(b['id'])
            informe.append(f"{b['id']}: «{frase[:70]}» nombra «{c}», pero en {int(s // 60)}:{s % 60:04.1f} no se ve; "
                           f"aparece en {int(donde // 60)}:{donde % 60:04.1f}")
    if arreglados:
        json.dump(g, open(ruta, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        for x in voz.ajustar_guion(ruta, os.path.join(d, 'voz')):
            informe.append(x)
    open(os.path.join(d, 'alineacion.txt'), 'w', encoding='utf-8').write(
        'Cada frase de la voz contra la pantalla que nombra (OCR, gratis)\n\n' + ('\n'.join(informe) or 'Todo en su lugar.') + '\n')
    for x in informe:
        print('· ' + x, flush=True)
    if quedan:
        print(f'AVISO: {len(set(quedan))} bloque(s) con frases que no caen sobre su pantalla: {", ".join(sorted(set(quedan)))} '
              '(mira alineacion.txt)', flush=True)
    print(f'Listo: {len(arreglados)} tramo(s) corregido(s) solos, {len(set(quedan))} para revisar.', flush=True)


if __name__ == '__main__':
    main()
