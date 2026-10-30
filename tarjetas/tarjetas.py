"""Tarjetas de COMENTARIOS y de WHATSAPP encima del video, en el momento justo.

En la app subes tus imágenes (PNG con fondo transparente se ve mejor) en dos grupos:
  COMENTARIOS  la invitación a comentar (un «¡déjame tu duda abajo!», una flecha a los comentarios…)
  WHATSAPP     tus tarjetas de WhatsApp para que te escriban

Cada tarjeta entra con un deslizamiento suave, se queda unos segundos y sale. Si su momento es
«auto», se busca en los subtítulos (3_voz.srt) cuándo la voz habla de comentar o de WhatsApp; si la
voz no lo dice, las de COMENTARIOS van al comienzo y las de WHATSAPP cerca del final. Nunca se
pisan entre sí. El video no cambia de duración y el audio queda igual.

Uso:
  python tarjetas.py --video 6_senales.mp4 --tarjetas tarjetas/tarjetas.json --srt 3_voz.srt --salida 7_tarjetas.mp4
tarjetas.json: {"COMENTARIOS": [{"archivo": "x.png", "momento": "auto" | "1:25" | "inicio" | "mitad" | "final",
                 "dur": 6, "posicion": "abajo-derecha"}], "WHATSAPP": [...]}
"""
import argparse, json, os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador

GRUPOS = ['COMENTARIOS', 'WHATSAPP']
# lo que dice la voz cuando invita a comentar o a escribir por WhatsApp
DISPARA = {'COMENTARIOS': r'coment|tus dudas',
           'WHATSAPP': r'whats|wasap|guasap|wsp|escr[ií]be(me|nos)'}
POSICIONES = {'abajo-derecha', 'abajo-izquierda', 'arriba-derecha', 'arriba-izquierda', 'centro'}
DUR = 6.0
ENTRA = 0.45  # segundos que tarda en entrar y en salir


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True, check=True).stdout)


def tamano(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                        '-of', 'csv=p=0', f], capture_output=True, text=True, check=True).stdout
    w, h = r.strip().split(',')[:2]
    return int(w), int(h)


def segundos(txt):
    if txt is None or str(txt).strip() == '':
        return None
    if isinstance(txt, (int, float)):
        return float(txt)
    m = re.fullmatch(r'(?:(\d+):)?(\d+):(\d{1,2}(?:\.\d+)?)', str(txt).strip())
    if m:
        h, mi, s = m.groups()
        return int(h or 0) * 3600 + int(mi) * 60 + float(s)
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*s?', str(txt).strip())
    return float(m.group(1).replace(',', '.')) if m else None


def subtitulos(srt):
    """[(inicio, texto)] del .srt."""
    if not srt or not os.path.exists(srt):
        return []
    out = []
    for bloque in re.split(r'\n\s*\n', open(srt, encoding='utf-8', errors='replace').read()):
        m = re.search(r'(\d\d):(\d\d):(\d\d)[,.](\d{3})\s*-->', bloque)
        if m:
            h, mi, s, ms = map(int, m.groups())
            out.append((h * 3600 + mi * 60 + s + ms / 1000, bloque[m.end():].split('\n', 1)[-1].strip()))
    return out


def planificar(tarjetas, subs, total):
    """Le da a cada tarjeta su segundo de entrada. Devuelve [(inicio, dur, tarjeta, grupo, por_que)]."""
    pedidas = []
    for g in GRUPOS:
        dichos = [t for t, txt in subs if re.search(DISPARA[g], txt, re.I)]
        dichos = [t for k, t in enumerate(dichos) if k == 0 or t - dichos[k - 1] > 20]  # una vez por invitación
        for k, c in enumerate(tarjetas.get(g, [])):
            dur = min(max(float(segundos(c.get('dur')) or DUR), 2.0), 20.0)
            m = str(c.get('momento') or 'auto').strip().lower()
            s = segundos(m)
            if s is not None:
                t, por = s, 'segundo que pusiste'
            elif m == 'inicio':
                t, por = min(8.0, total * 0.05), 'inicio'
            elif m == 'mitad':
                t, por = total * 0.5, 'mitad'
            elif m == 'final':
                t, por = total - dur - 3, 'final'
            elif k < len(dichos):
                t, por = dichos[k], 'la voz lo menciona'
            elif g == 'COMENTARIOS':
                t, por = [total * 0.12, total * 0.55, total * 0.8][k % 3], 'auto (no lo dice la voz)'
            else:
                t, por = [total - dur - 3, total * 0.45, total * 0.25][k % 3], 'auto (no lo dice la voz)'
            pedidas.append((min(max(t, 0.5), max(0.5, total - dur - 0.5)), dur, c, g, por))
    plan = []
    for t, dur, c, g, por in sorted(pedidas, key=lambda x: x[0]):
        for t0, d0, *_ in plan:  # si choca con otra, entra cuando la anterior ya salió
            if t < t0 + d0 + 0.5 and t + dur > t0 - 0.5:
                t = t0 + d0 + 0.5
        if t + dur > total - 0.2:
            print(f'· {g}: «{c.get("archivo")}» no cabe en el video, la salto')
            continue
        plan.append((round(t, 2), dur, c, g, por))
    return sorted(plan, key=lambda x: x[0])


MARCO = os.path.join(RAIZ, 'mis_conocimientos', 'estilo_video', 'marco_tarjeta.png')  # el marco de GPT 2.5 (fabian, 30/10/2026)


def con_marco(ruta, carpeta_tmp):
    """La captura dentro del marco de GPT (estirado solo en los lados: las esquinas no se deforman). Sin el kit, la de siempre."""
    if not os.path.exists(MARCO):
        return ruta
    try:
        import numpy as np
        from PIL import Image, ImageDraw
        m = Image.open(MARCO).convert('RGBA')
        a = np.array(m)[..., 3]
        h, w = a.shape
        cy, cx = h // 2, w // 2
        izq = next(x for x in range(cx, 0, -1) if a[cy, x] > 128)
        der = next(x for x in range(cx, w) if a[cy, x] > 128)
        arr = next(y for y in range(cy, 0, -1) if a[y, cx] > 128)
        aba = next(y for y in range(cy, h) if a[y, cx] > 128)
        L, R, T, B = izq + 1, w - der, arr + 1, h - aba  # lo que es marco de cada lado (no se estira)
        foto = Image.open(ruta).convert('RGBA')
        fw, fh = foto.size
        k = max(0.05, 0.06 * min(fw, fh) / max(1, L))  # el borde, un 6 % del lado corto de la captura
        l, r, tt, b = [max(1, round(v * k)) for v in (L, R, T, B)]
        W2, H2 = fw + l + r - round(0.35 * (l + r)), fh + tt + b - round(0.35 * (tt + b))  # el borde pisa un poco la captura
        lienzo = Image.new('RGBA', (W2, H2), (0, 0, 0, 0))
        # la captura en el medio, con las puntas redondeadas
        ox, oy = (W2 - fw) // 2, (H2 - fh) // 2
        masc = Image.new('L', foto.size, 0)
        ImageDraw.Draw(masc).rounded_rectangle((0, 0, fw - 1, fh - 1), round(0.04 * min(fw, fh)), fill=255)
        lienzo.paste(foto, (ox, oy), masc)
        # el marco en 9 pedazos
        cajas_src = {'esq': [(0, 0, L, T), (w - R, 0, w, T), (0, h - B, L, h), (w - R, h - B, w, h)]}
        destino = [(0, 0), (W2 - r, 0), (0, H2 - b), (W2 - r, H2 - b)]
        tam = [(l, tt), (r, tt), (l, b), (r, b)]
        for c, d, s in zip(cajas_src['esq'], destino, tam):
            lienzo.alpha_composite(m.crop(c).resize(s, Image.LANCZOS), d)
        lados = [((L, 0, w - R, T), (l, 0), (W2 - l - r, tt)), ((L, h - B, w - R, h), (l, H2 - b), (W2 - l - r, b)),
                 ((0, T, L, h - B), (0, tt), (l, H2 - tt - b)), ((w - R, T, w, h - B), (W2 - r, tt), (r, H2 - tt - b))]
        for c, d, s in lados:
            if s[0] > 0 and s[1] > 0:
                lienzo.alpha_composite(m.crop(c).resize(s, Image.LANCZOS), d)
        out = os.path.join(carpeta_tmp, 'marco_' + os.path.splitext(os.path.basename(ruta))[0] + '.png')
        lienzo.save(out)
        return out
    except Exception as e:  # si algo falla, la tarjeta va igual, sin marco
        print(f'· no pude ponerle el marco a {os.path.basename(ruta)} ({e})', flush=True)
        return ruta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--tarjetas', required=True)
    ap.add_argument('--srt')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--capa', help='no codifica: deja la capa en este .json; capas/capas.py la pega junto con las demás')
    a = ap.parse_args()
    carpeta = os.path.dirname(os.path.abspath(a.tarjetas))
    datos = json.load(open(a.tarjetas, encoding='utf-8'))
    total = duracion(a.video)
    W, H = tamano(a.video)
    plan = [p for p in planificar(datos, subtitulos(a.srt), total) if os.path.isfile(os.path.join(carpeta, os.path.basename(p[2].get('archivo') or '')))]
    if not plan:
        raise SystemExit('ERROR: no hay tarjetas para poner. Sube imágenes en COMENTARIOS o WHATSAPP.')

    ins, filtros, ult, piezas = ['-i', a.video], [], '0:v', []
    margen = round(H * 0.04)
    tmp_marcos = os.path.join(os.path.dirname(os.path.abspath(a.salida)), '.tarjetas_marco')  # las capturas ya enmarcadas
    os.makedirs(tmp_marcos, exist_ok=True)
    for k, (t, dur, c, g, por) in enumerate(plan, 1):
        pos = c.get('posicion') if c.get('posicion') in POSICIONES else 'abajo-derecha'
        ancho = round(W * (0.5 if pos == 'centro' else 0.32)) // 2 * 2
        x = {'abajo-derecha': f'W-w-{margen}', 'arriba-derecha': f'W-w-{margen}', 'centro': '(W-w)/2'}.get(pos, str(margen))
        y = {'arriba-derecha': str(margen), 'arriba-izquierda': str(margen), 'centro': '(H-h)/2'}.get(pos, f'H-h-{margen}')
        desliza = f'{round(H * 0.06)}*max(0,1-(t-{t})/{ENTRA})'  # entra subiendo un poco
        imagen = con_marco(os.path.abspath(os.path.join(carpeta, os.path.basename(c['archivo']))), tmp_marcos)
        piezas.append({'args': ['-loop', '1', '-t', f'{dur:.2f}', '-i', imagen],
                       'pre': f"format=rgba,scale='min({ancho},iw*{H * 0.42:.0f}/ih)':-2,"
                              f"fade=t=in:st=0:d={ENTRA}:alpha=1,fade=t=out:st={dur - ENTRA:.2f}:d={ENTRA}:alpha=1,"
                              f"setpts=PTS-STARTPTS+{t}/TB",
                       'overlay': f"x='{x}':y='{y}+{desliza}':eof_action=pass:enable='between(t,{t},{t + dur:.2f})'"})
        ins += piezas[-1]['args']
        filtros.append(f"[{k}:v]{piezas[-1]['pre']}[t{k}];[{ult}][t{k}]overlay={piezas[-1]['overlay']}[v{k}]")
        ult = f'v{k}'
        print(f'{g:11s} {t:7.1f}s  {dur:.0f} s  {pos:16s} {c["archivo"]}  ({por})', flush=True)
    if a.capa:  # se pega después junto con etiquetas y flechas: una sola codificación
        sys.path.insert(0, os.path.join(RAIZ, 'capas'))
        import capas
        capas.guardar(a.capa, piezas, crf=18)
        print(f'{len(plan)} tarjetas listas para pegar')
        return
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                   ['-filter_complex', ';'.join(filtros), '-map', f'[{ult}]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', a.salida], check=True)
    print(f'{len(plan)} tarjetas puestas -> {a.salida}')


if __name__ == '__main__':
    main()
