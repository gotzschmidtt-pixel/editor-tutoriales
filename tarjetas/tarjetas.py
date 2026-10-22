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
import argparse, json, os, re, subprocess

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--tarjetas', required=True)
    ap.add_argument('--srt')
    ap.add_argument('--salida', required=True)
    a = ap.parse_args()
    carpeta = os.path.dirname(os.path.abspath(a.tarjetas))
    datos = json.load(open(a.tarjetas, encoding='utf-8'))
    total = duracion(a.video)
    W, H = tamano(a.video)
    plan = [p for p in planificar(datos, subtitulos(a.srt), total) if os.path.isfile(os.path.join(carpeta, os.path.basename(p[2].get('archivo') or '')))]
    if not plan:
        raise SystemExit('ERROR: no hay tarjetas para poner. Sube imágenes en COMENTARIOS o WHATSAPP.')

    ins, filtros, ult = ['-i', a.video], [], '0:v'
    margen = round(H * 0.04)
    for k, (t, dur, c, g, por) in enumerate(plan, 1):
        pos = c.get('posicion') if c.get('posicion') in POSICIONES else 'abajo-derecha'
        ancho = round(W * (0.5 if pos == 'centro' else 0.32)) // 2 * 2
        ins += ['-loop', '1', '-t', f'{dur:.2f}', '-i', os.path.join(carpeta, os.path.basename(c['archivo']))]
        filtros.append(f"[{k}:v]format=rgba,scale='min({ancho},iw*{H * 0.42:.0f}/ih)':-2,"
                       f"fade=t=in:st=0:d={ENTRA}:alpha=1,fade=t=out:st={dur - ENTRA:.2f}:d={ENTRA}:alpha=1,"
                       f"setpts=PTS-STARTPTS+{t}/TB[t{k}]")
        x = {'abajo-derecha': f'W-w-{margen}', 'arriba-derecha': f'W-w-{margen}', 'centro': '(W-w)/2'}.get(pos, str(margen))
        y = {'arriba-derecha': str(margen), 'arriba-izquierda': str(margen), 'centro': '(H-h)/2'}.get(pos, f'H-h-{margen}')
        desliza = f'{round(H * 0.06)}*max(0,1-(t-{t})/{ENTRA})'  # entra subiendo un poco
        filtros.append(f"[{ult}][t{k}]overlay=x='{x}':y='{y}+{desliza}':eof_action=pass:enable='between(t,{t},{t + dur:.2f})'[v{k}]")
        ult = f'v{k}'
        print(f'{g:11s} {t:7.1f}s  {dur:.0f} s  {pos:16s} {c["archivo"]}  ({por})', flush=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                   ['-filter_complex', ';'.join(filtros), '-map', f'[{ult}]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', a.salida], check=True)
    print(f'{len(plan)} tarjetas puestas -> {a.salida}')


if __name__ == '__main__':
    main()
