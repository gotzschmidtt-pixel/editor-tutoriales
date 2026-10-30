"""Logos (Android 15, 16, 17, MagicOS 9, 10, 11…) encima del video en el segundo en que la voz los nombra.

Los logos son de fabian y sirven para todos los videos: mis_conocimientos/logos/logos.json (se sincroniza con la otra PC).
Cada logo tiene su "nombre" («Android 15») y sus "palabras" («android quince»). Con los tiempos por letra de la voz se busca
cuándo se dice cada uno; en «Android quince, dieciséis o diecisiete» salen los tres, uno al lado del otro, cada uno cuando se
nombra, y se van juntos. Van arriba a la derecha, chicos, para no tapar el teléfono. Un mismo logo no se repite antes de 30 s.
Tablas y textos van en español, inglés y portugués («idiomas» en logos.json: pedido de fabian, 30/10/2026): en la versión
del video en otro idioma sale la suya.

Uso (la app lo llama sola, paso «Logos»):
  python logos.py --video 4_musica.mp4 --guion guion.json --voz voz --logos ../../mis_conocimientos/logos --salida 7b_logos.mp4 [--capa .capas/logos.json]
"""
import argparse, json, os, re, subprocess, sys, unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador

DESFASE = 0.3     # la voz entra 0,3 s después del inicio del bloque (mezclar_voz.py)
JUNTOS = 4.0      # menciones a menos de esto van en la misma fila
QUEDA = 2.8       # segundos que siguen en pantalla después de la última mención de la fila
NO_REPETIR = 30.0
ALTO = 0.19       # alto de cada logo, en parte del alto del video (las insignias anchas, al mismo alto)
ENTRA = 0.3
NUMEROS = {'nueve': 9, 'diez': 10, 'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15, 'dieciseis': 16,
           'diecisiete': 17, 'dieciocho': 18, 'diecinueve': 19, 'veinte': 20,
           # la versión del video en inglés o en portugués («Android fifteen», «Android quinze»)
           'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
           'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
           'nove': 9, 'dez': 10, 'onze': 11, 'doze': 12, 'treze': 13, 'quatorze': 14, 'catorze': 14, 'quinze': 15,
           'dezesseis': 16, 'dezessete': 17, 'dezoito': 18, 'dezenove': 19, 'vinte': 20}
FAMILIA = re.compile(r'\b(android|magic ?os)\b')
NUMERO = re.compile(r'\b(\d{1,2}|' + '|'.join(NUMEROS) + r')\b')


def normal(t):
    """minúsculas y sin tildes, letra por letra (el largo no cambia: los tiempos siguen sirviendo)."""
    return ''.join(unicodedata.normalize('NFD', c)[0].lower() for c in t)


def clave(nombre):
    """«Android 15» → ('android', 15); «MagicOS 9» → ('magicos', 9); sin número → None."""
    m = re.fullmatch(r'\s*(android|magic ?os)\s*(\d{1,2})\s*', normal(nombre or ''))
    return (m.group(1).replace(' ', ''), int(m.group(2))) if m else None


def menciones(texto, logos):
    """[(posición de la letra, logo)] de lo que nombra un texto."""
    t = normal(texto)
    por_clave = {clave(l.get('nombre')): l for l in logos if clave(l.get('nombre'))}
    out = []
    for m in FAMILIA.finditer(t):
        fam = m.group(1).replace(' ', '')
        fin = len(t)
        for corte in (t.find('.', m.end()), t.find('?', m.end()), t.find('!', m.end())):
            if corte >= 0:
                fin = min(fin, corte)
        sig = FAMILIA.search(t, m.end())  # «Android 15, 16 y MagicOS 9»: los números de MagicOS no son de Android
        fin = min(fin, sig.start()) if sig else fin
        for n in NUMERO.finditer(t, m.end(), min(fin, m.end() + 70)):
            v = int(n.group(1)) if n.group(1).isdigit() else NUMEROS[n.group(1)]
            if (fam, v) in por_clave:
                out.append((n.start(), por_clave[(fam, v)]))
    for l in logos:  # los logos sin número (una web, una marca): por sus palabras
        if clave(l.get('nombre')):
            continue
        for p in l.get('palabras') or []:
            for m in re.finditer(r'\b' + re.escape(normal(p)) + r'\b', t):
                out.append((m.start(), l))
    return out


def plan(guion, carpeta_voz, logos):
    """[(segundo, logo)] de todo el video, con los tiempos reales de la voz."""
    out = []
    for b in guion['bloques']:
        if not str(b.get('texto') or '').strip() or b.get('inicio_min') is None:
            continue
        try:
            al = json.load(open(os.path.join(carpeta_voz, f"{b['id']}.align.json"), encoding='utf-8'))
        except (OSError, ValueError):
            continue
        txt, t0 = ''.join(al['characters']), al['character_start_times_seconds']
        for pos, l in menciones(txt, logos):
            out.append((round(b['inicio_min'] + DESFASE + t0[min(pos, len(t0) - 1)], 2), l))
    out.sort(key=lambda x: x[0])
    filas, visto, veces = [], {}, {}
    for t, l in out:
        if t - visto.get(l['archivo'], -999) < NO_REPETIR:
            continue
        if veces.get(l['archivo'], 0) >= int(l.get('max_veces') or 99):  # «Honor» se dice todo el rato: su logo sale una vez
            continue
        visto[l['archivo']] = t
        veces[l['archivo']] = veces.get(l['archivo'], 0) + 1
        if filas and t - filas[-1][-1][0] <= JUNTOS and len(filas[-1]) < 4:
            filas[-1].append((t, l))
        else:
            filas.append([(t, l)])
    return filas


def duracion(v):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', v],
                                capture_output=True, text=True, check=True).stdout)


def tamano(v):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', v],
                       capture_output=True, text=True, check=True).stdout
    w, h = r.strip().split(',')[:2]
    return int(w), int(h)


def proporcion(png):
    """ancho / alto del PNG: las insignias de marcas y webs son anchas, los logos de versión casi cuadrados."""
    try:
        w, h = tamano(png)
        return min(4.0, max(0.5, w / h))
    except Exception:
        return 1.0


def del_idioma(logo, carpeta, idioma):
    """El archivo del logo en el idioma del video: "idiomas": {"en": "x_en.png", "pt": "x_pt.png"}; si no hay, el de siempre."""
    otro = (logo.get('idiomas') or {}).get(idioma)
    return otro if otro and os.path.isfile(os.path.join(carpeta, otro)) else logo['archivo']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--guion', required=True)
    ap.add_argument('--voz', required=True)
    ap.add_argument('--logos', required=True, help='carpeta con logos.json y los PNG')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--capa', help='no codifica: deja la capa en este .json; capas/capas.py la pega junto con las demás')
    a = ap.parse_args()
    try:
        lib = json.load(open(os.path.join(a.logos, 'logos.json'), encoding='utf-8'))
    except (OSError, ValueError):
        print('No hay biblioteca de logos (mis_conocimientos/logos/logos.json): no pongo nada.')
        return
    logos = [l for l in lib.get('logos', []) if os.path.isfile(os.path.join(a.logos, l.get('archivo', '')))]
    try:  # versión del video en otro idioma (idioma_video.json, como la voz y las etiquetas): sus tablas y textos traducidos
        idioma = json.load(open(os.path.join(os.path.dirname(os.path.abspath(a.guion)), 'idioma_video.json'), encoding='utf-8')).get('idioma') or 'es'
    except (OSError, ValueError, AttributeError):
        idioma = 'es'
    filas = plan(json.load(open(a.guion, encoding='utf-8')), a.voz, logos)
    if not filas:
        print('La voz no nombra ninguno de tus logos: no pongo nada.')
        return
    total = duracion(a.video)
    W, H = tamano(a.video)
    caja = round(H * ALTO) // 2 * 2
    margen, hueco = round(H * 0.045), round(H * 0.015)
    ins, filtros, ult, piezas = ['-i', a.video], [], '0:v', []
    for fila in filas:
        hasta = min(total - 0.1, fila[-1][0] + QUEDA)
        for k, (t, l) in enumerate(fila):
            if t >= hasta - 0.5:
                continue
            dur = hasta - t
            png = os.path.abspath(os.path.join(a.logos, del_idioma(l, a.logos, idioma)))
            # de derecha a izquierda: cada uno con su ancho (al mismo alto), separados por el hueco
            anchos = [round(caja * (proporcion(os.path.join(a.logos, del_idioma(o, a.logos, idioma))) if proporcion(os.path.join(a.logos, del_idioma(o, a.logos, idioma))) > 1.3 else 1)) // 2 * 2 for _, o in fila]
            ancho = anchos[k]
            x = W - margen - sum(anchos[k:]) - (len(fila) - 1 - k) * hueco
            piezas.append({'args': ['-loop', '1', '-t', f'{dur:.2f}', '-i', png],
                           'pre': f"format=rgba,scale={ancho}:{caja}:force_original_aspect_ratio=decrease,"
                                  f"pad={ancho}:{caja}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
                                  f"fade=t=in:st=0:d={ENTRA}:alpha=1,fade=t=out:st={max(0, dur - ENTRA):.2f}:d={ENTRA}:alpha=1,"
                                  f"setpts=PTS-STARTPTS+{t}/TB",
                           'overlay': f"x={x}:y={margen}:eof_action=pass:enable='between(t,{t},{hasta:.2f})'"})
            n = len(piezas)
            ins += piezas[-1]['args']
            filtros.append(f"[{n}:v]{piezas[-1]['pre']}[l{n}];[{ult}][l{n}]overlay={piezas[-1]['overlay']}[v{n}]")
            ult = f'v{n}'
            print(f"{t:7.1f}s  {l.get('nombre') or l['archivo']}", flush=True)
    if not piezas:
        print('Los logos caían al final del video: no pongo nada.')
        return
    if a.capa:  # se pega después junto con etiquetas, flechas y tarjetas: una sola codificación
        sys.path.insert(0, os.path.join(RAIZ, 'capas'))
        import capas
        capas.guardar(a.capa, piezas, crf=18)
        print(f'{len(piezas)} logos listos para pegar')
        return
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                  ['-filter_complex', ';'.join(filtros), '-map', f'[{ult}]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'medium',
                   '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', a.salida], check=True)
    print(f'{len(piezas)} logos puestos -> {a.salida}')


if __name__ == '__main__':
    main()
