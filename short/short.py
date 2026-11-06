"""Short vertical 9:16 (como «Auto Resaltar» + «Reencuadre automático» de Filmora), hecho con lo que la app ya sabe del video.

Uso (desde la carpeta del proyecto): python short.py --proyecto . --duracion 60

1. Elige las tomas: el gancho del inicio y los bloques del guion con tus ⭐ cortes importantes, las acciones (volumen, power,
   pegar, Connect, paso cuatro, Omitir…) y el resultado (sin candado, crear cuenta), sin la parte de promoción (comentarios,
   suscribirse, grupo, WhatsApp de soporte), hasta llenar la duración. Deja el plan con el porqué de cada toma en short.json.
2. Reencuadra a 9:16 siguiendo lo importante: tu cara si sales (cuadro completo en alto); si no, el teléfono (el detector de
   deteccion/ lo ve aunque tenga la pantalla negra) con el zoom justo para que entre entero; si no hay teléfono, lo que se
   mueve o cambia en la pantalla (cursor, botón) con un zoom suave. Donde marcaste un círculo, encuadra esa zona. Nunca acelera.
3. Voz: las mismas voces del video (voz/Lxx.mp3), así que no gasta créditos. Con --voz-nueva usa el guion propio del Short
   (short_guion.json: tomas con src_inicio, texto y por_que, escrito para el Short, con más gancho) y genera esa voz con
   ElevenLabs en voz_short/ (gasta ~1 crédito por letra; lo que no cambió se reutiliza). Subtítulos grandes y tu música fija.
4. Extras al final (short_extras.json, se eligen en el módulo): 🎥 un testimonio (tu video, ajustado a vertical), 🌐 tus
   páginas en pantalla y 📺 el cierre «mira el video completo» con tu texto y, si subiste uno, tu audio.
Deja SHORT.mp4 en la carpeta del proyecto.
"""
import argparse, json, os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
sys.path.insert(0, os.path.join(RAIZ, 'deteccion'))
import codificar  # noqa: E402  con la tarjeta NVIDIA o Intel si la hay
import deteccion  # noqa: E402  ve el teléfono aunque tenga la pantalla negra

W, H = 1920, 1080          # el original
SW, SH = 1080, 1920        # el Short
PASO_SEG = 0.5             # cada cuánto se mira dónde está lo importante
ZOOM_PANTALLA = 1.2        # sin cara: un poco más cerca de lo que se mueve (sin cortar el teléfono)
ZOOM_TELEFONO = 1.4        # con el teléfono a la vista: lo más cerca que se acerca, siempre que el teléfono entre entero
MIN_TOMA = 7.0             # con la voz nueva (frases cortas): cada toma dura al menos esto, para ver la acción entera
MUSICA = os.path.join(RAIZ, 'mis_musica', 'musica_fija.mp3')

PROMO = re.compile(r'coment|suscrib|facebook|grupo privado|soporte|asesor|testimon|capturas de whatsapp|nos vemos|abrazo|'
                   r'tiene un costo|d[oó]lares|stock|xiaomi unlock', re.I)
ACCION = re.compile(r'volumen|power|fastboot|men[uú]|peg|connect|conect|paso (uno|dos|tres|cuatro)|reinici|desconect|omitir|'
                    r'cable|serial', re.I)
RESULTADO = re.compile(r'candado (ya )?no|ya no (est|aparece)|libre|crear (nuestra|una|tu)?.{0,10}cuenta|entramos|'
                       r'[ée]xito|adentro', re.I)


def duracion(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def elegir(d, g, objetivo, dur_video):
    """Las tomas del Short, en el orden del video, con su porqué."""
    cands = []
    for k, b in enumerate(g['bloques']):
        mp3 = os.path.join(d, 'voz', f"{b['id']}.mp3")
        mo = b.get('montaje') or {}
        if not os.path.exists(mp3) or mo.get('src_inicio') is None or mo.get('modo') == 'imagen' or not b.get('texto', '').strip():
            continue
        t = b['texto']
        razones, puntos = [], 0
        if k == 0:
            razones.append('el gancho del inicio'); puntos += 100
        if PROMO.search(t) and k:
            continue  # en un Short no va la promoción: se queda en el video largo
        if mo.get('importante'):
            razones.append('tu corte importante ⭐'); puntos += 3
        if b.get('tipo') == 'critico' or mo.get('critico'):
            razones.append('paso clave'); puntos += 2
        if ACCION.search(t):
            razones.append('se ve la acción'); puntos += 2
        if RESULTADO.search(t):
            razones.append('se ve el resultado'); puntos += 3
        if not razones:
            continue
        acciones = len({m.group(0).lower()[:5] for m in ACCION.finditer(t)})
        puntos += min(acciones, 3)  # varias acciones en el mismo bloque: más paso a paso
        if k and float(mo['src_inicio']) < dur_video * 0.2:
            puntos -= 3  # el resumen del inicio: en el Short van los pasos de verdad
        cands.append({'k': k, 'id': b['id'], 'voz': round(duracion(mp3), 2), 'puntos': puntos, 'por_que': ', '.join(razones),
                      'src_inicio': float(mo['src_inicio']), 'texto': t})
    elegidas, total = [], 0.0
    for c in sorted(cands, key=lambda c: (-c['puntos'] / max(c['voz'], 6) if c['k'] else -1e9, c['k'])):  # más importancia por segundo
        if total + c['voz'] + 0.4 <= objetivo:
            elegidas.append(c); total += c['voz'] + 0.4
    if not any(RESULTADO.search(c['texto']) for c in elegidas):  # siempre termina mostrando que salió bien
        fin = [c for c in cands if RESULTADO.search(c['texto'])]
        if fin and len(elegidas) > 1:
            menos = min((c for c in elegidas if c['k']), key=lambda c: c['puntos'])
            elegidas.remove(menos); elegidas.append(fin[-1])
    return sorted(elegidas, key=lambda c: c['k'])


def voz_nueva(d):
    """Las tomas del guion propio del Short (short_guion.json), con su voz nueva generada en voz_short/."""
    try:
        sg = json.load(open(os.path.join(d, 'short_guion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        raise SystemExit('ERROR: falta el guion del Short (short_guion.json). Pídeselo a Claude o a la IA de la app.')
    bloques = [{'id': x['id'], 'texto': x['texto'], 'tipo': 'libre', 'humor': False,
                'montaje': {'modo': 'lento', 'src_inicio': float(x['src_inicio']), 'src_fin': float(x['src_inicio']) + 30,
                            'velocidad': 1.0, 'congelar_s': None}} for x in sg['tomas']]
    f = os.path.join(d, '.short_voz_guion.json')
    json.dump({'bloques': bloques}, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('· voz nueva del Short con ElevenLabs (solo las frases nuevas o cambiadas gastan créditos)…', flush=True)
    subprocess.run([sys.executable, os.path.join(RAIZ, 'voz', 'voz.py'), '--guion', f, '--salida', os.path.join(d, 'voz_short')],
                   check=True, cwd=d)
    return [{'k': i, 'id': x['id'], 'voz': round(duracion(os.path.join(d, 'voz_short', f"{x['id']}.mp3")), 2), 'puntos': 0,
             'por_que': x.get('por_que', ''), 'src_inicio': float(x['src_inicio']), 'texto': x['texto'], 'carpeta': 'voz_short'}
            for i, x in enumerate(sg['tomas'])]


FUENTES = [r'C:\Windows\Fonts\ariblk.ttf', r'C:\Windows\Fonts\arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']


def leer_extras(d):
    try:
        x = json.load(open(os.path.join(d, 'short_extras.json'), encoding='utf-8'))
        return x if isinstance(x, dict) else {}
    except (OSError, ValueError):
        return {}


def paginas_del_autor():
    """Las webs de «Mis páginas» (solo nombre y dirección; nada más de los ajustes)."""
    try:
        r = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('paginas', [])
        return [str(x.get('url')).strip() for x in r if isinstance(x, dict) and str(x.get('url') or '').strip()]
    except (OSError, ValueError, AttributeError):
        return []


def parte_testimonio(d, archivo, salida):
    """Tu video de testimonio en 9:16: entero al medio y, detrás, el mismo video ampliado y borroso (sin barras negras)."""
    f = os.path.join(d, archivo)
    vf = (f'[0:v]split[a][b];[a]scale={SW}:{SH}:force_original_aspect_ratio=increase,crop={SW}:{SH},boxblur=24:2[fondo];'
          f'[b]scale={SW}:{SH}:force_original_aspect_ratio=decrease[fr];[fondo][fr]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[v]')
    tiene_audio = bool(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', f],
                                      capture_output=True, text=True).stdout.strip())
    entradas = ['-i', f] + ([] if tiene_audio else ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'])
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                  ['-filter_complex', vf + f';[{0 if tiene_audio else 1}:a]aresample=44100,aformat=channel_layouts=stereo[au]',
                   '-map', '[v]', '-map', '[au]', '-shortest', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                   '-c:a', 'aac', '-b:a', '160k', salida], check=True)


def parte_final(d, ultimo, cfg, paginas, salida):
    """La tarjeta del cierre: el último cuadro del Short oscurecido, con «mira el video completo» y/o tus páginas, y tu audio."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    fuente = lambda n: next((ImageFont.truetype(f, n) for f in FUENTES if os.path.exists(f)), ImageFont.load_default())
    png = salida + '.png'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-sseof', '-0.2', '-i', ultimo, '-frames:v', '1', png], check=True)
    img = Image.open(png).convert('RGB').filter(ImageFilter.GaussianBlur(18))
    img = Image.blend(img, Image.new('RGB', img.size, (8, 8, 16)), 0.55)
    dib = ImageDraw.Draw(img)

    def partir(texto, f, ancho):
        lineas, actual = [], ''
        for p in texto.split():
            prueba = (actual + ' ' + p).strip()
            if dib.textlength(prueba, font=f) <= ancho:
                actual = prueba
            else:
                lineas.append(actual); actual = p
        return lineas + ([actual] if actual else [])
    y = 560
    caja = caja_de(miniatura_aprobada(d))
    if caja:  # su último segundo lleva la miniatura arriba al centro: el texto va debajo, nunca tapado (revisión 03/11/2026)
        y = max(y, int(caja[1] + caja[3] + 90))
    texto = str(cfg.get('final_texto') or '').strip() if cfg.get('final') else ''
    texto = ''.join(c for c in texto if ord(c) < 0x2190).strip()  # la letra no trae emojis (saldrían como cuadraditos)
    if texto:
        f = fuente(76)
        for ln in partir(texto, f, SW - 140):
            dib.text((SW / 2, y), ln, font=f, fill='white', anchor='mm', stroke_width=4, stroke_fill='black'); y += 100
        y += 40
    if paginas:
        f = fuente(58)
        for p in paginas:
            w = dib.textlength(p, font=f) + 80
            dib.rounded_rectangle([SW / 2 - w / 2, y - 48, SW / 2 + w / 2, y + 48], radius=48, fill='white')
            dib.text((SW / 2, y), p, font=f, fill=(17, 17, 17), anchor='mm'); y += 130
    img.save(png)
    audio = os.path.join(d, cfg['final_audio']) if cfg.get('final') and cfg.get('final_audio') and os.path.exists(os.path.join(d, cfg['final_audio'])) else None
    dur = max(3.0, (duracion(audio) + 0.6) if audio else float(cfg.get('final_dur') or 4))
    entradas = ['-loop', '1', '-t', f'{dur:.2f}', '-i', png] + (['-i', audio] if audio else ['-f', 'lavfi', '-t', f'{dur:.2f}', '-i', 'anullsrc=r=44100:cl=stereo'])
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                  ['-filter_complex', f"[0:v]scale={SW}:{SH},zoompan=z='min(zoom+0.0006,1.06)':d=1:s={SW}x{SH}:fps=30,format=yuv420p[v];"
                   f'[1:a]aresample=44100,aformat=channel_layouts=stereo,apad,atrim=0:{dur:.2f}[au]',
                   '-map', '[v]', '-map', '[au]', '-t', f'{dur:.2f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                   '-c:a', 'aac', '-b:a', '160k', salida], check=True)
    return dur


def marcas_autor(d):
    """[(segundo, cx, cy)] de tus círculos y flechas (para_claude_marcas.json), en píxeles del original."""
    try:
        m = json.load(open(os.path.join(d, 'para_claude_marcas.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    out = []
    for s in m.get('senales', []):
        try:
            p = [float(x) for x in str(s['segundo']).split(':')]
            t = p[0] * 60 + p[1] if len(p) == 2 else p[0]
            out.append((t, s['zona']['x'] / 100 * W, s['zona']['y'] / 100 * H))
        except (KeyError, ValueError, TypeError):
            pass
    return out


def _senales():
    sys.path.insert(0, os.path.join(RAIZ, 'senales'))
    import senales
    return senales


def senales_grabado(d):
    """Las flechas y círculos del video largo (senales.json) en segundos y píxeles de la GRABACIÓN (original.mp4):
    [{..., 'src': segundo}]. fabian, 02/11/2026: «¿por qué no se muestran flechas y círculos, sobre todo en Omitir?».
    El Short sale de la grabación y las señales solo se dibujaban encima del video largo.
    Las que traen el segundo del video largo se pasan a la grabación con los tramos del guion y se confirma que la imagen
    sea la misma (si no, se saltan: mejor sin círculo que con uno en el lugar equivocado)."""
    try:
        lista = json.load(open(os.path.join(d, 'senales.json'), encoding='utf-8'))
        bloques = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']
    except (OSError, ValueError, KeyError, TypeError):
        return []
    if not isinstance(lista, list) or not lista:
        return []
    senales = _senales()
    inicio = {b['id']: b['inicio_min'] for b in bloques if b.get('inicio_min') is not None}
    texto_original = {b['id']: b.get('texto_original') for b in bloques}
    orig = os.path.join(d, 'original.mp4')
    montado = next((os.path.join(d, f) for f in ('3_voz.mp4', '4_musica.mp4', '1_montaje.mp4') if os.path.exists(os.path.join(d, f))), None)
    out = []
    for s in lista:
        if not isinstance(s, dict) or s.get('tipo') not in ('circulo', 'flecha', 'caja') or s.get('x') is None or s.get('y') is None:
            continue
        frase = s.get('frase') or s.get('texto') or 'tu captura'
        try:
            if s.get('src_t') is not None:  # ya viene en segundos de la grabación
                out.append(dict(s, src=round(float(s['src_t']) + float(s.get('retraso') or 0), 2)))
                continue
            t, aviso = senales.en_el_video(s, inicio, texto_original, os.path.join(d, 'voz'), 0.3)
            src = senales.segundo_grabado(bloques, t) if t is not None else None
        except (ValueError, TypeError, OSError) as e:
            print(f'· flecha o círculo «{frase}»: no la pude ubicar ({e})', flush=True)
            continue
        if src is None:
            if aviso:
                print('·', aviso, flush=True)
            continue
        if montado and os.path.exists(orig):  # la misma imagen en el video largo y en la grabación
            src, parecido = senales.afinar(montado, orig, t, src, margen=1.0)
            if parecido < 0.6:
                print(f'· flecha o círculo «{frase}»: no encontré esa imagen en la grabación (parecido {parecido:.2f}), la salto', flush=True)
                continue
        out.append(dict(s, src=round(src, 2)))
    return out


def dibujar_senales(orig, senales_src, rangos, tmp):
    """Dibuja con Remotion (las mismas del video largo, con el dibujo de GPT si está) las señales que caen en los tramos
    [(s0, s1)] de la grabación que usa el Short, siguiendo lo señalado: [{'src', 'dur', 'archivo', 'x', 'y'}].
    Si Remotion falla, el Short sale igual, sin flechas (y lo avisa)."""
    usar = [s for s in senales_src if any(a - 0.5 <= s['src'] < b for a, b in rangos)]
    if not usar:
        return []
    senales = _senales()
    trabajos, hechas = [], []
    for k, s in enumerate(usar, 1):
        tr, dur = senales.trabajo(orig, s, s['src'], os.path.join(tmp, f'senal{k:02d}.mov'))
        trabajos.append(tr)
        hechas.append({'src': s['src'], 'dur': dur, 'archivo': tr['salida'], 'x': s['x'], 'y': s['y']})
    try:
        senales.dibujar(trabajos, tmp)
    except SystemExit as e:
        print(f'· AVISO: el Short sale sin flechas ni círculos: {e}', flush=True)
        return []
    print(f'· {len(hechas)} flechas y círculos del video largo van en el Short', flush=True)
    return [h for h in hechas if os.path.exists(h['archivo'])]


def con_senales(s0, dur, dibujadas, primera):
    """Para un trozo [s0, s0+dur] de la grabación: (entradas de ffmpeg, filtro, etiqueta) que pegan encima, ANTES del
    recorte vertical, las flechas y círculos que caen ahí (así siguen al recorte y al zoom). `primera` es el número de
    entrada de ffmpeg que toca a la primera señal. Sin señales: ([], '', '0:v')."""
    ins, filtro, ult = [], '', '0:v'
    for c in dibujadas:
        if c['src'] >= s0 + dur or c['src'] + c['dur'] <= s0:
            continue
        k = primera + len(ins) // 2
        off = c['src'] - s0
        pre = f'setpts=PTS+{off:.3f}/TB' if off >= 0 else f'trim=start={-off:.3f},setpts=PTS-STARTPTS'
        ins += ['-i', c['archivo']]
        filtro += f'[{k}:v]{pre}[s{k}];[{ult}][s{k}]overlay=0:0:eof_action=pass[o{k}];'
        ult = f'o{k}'
    return ins, filtro, ult


TARJETA_DICE = re.compile(r'whats|wasap|guasap', re.I)  # la voz nombra WhatsApp: ahí sale la tarjeta de soporte (logos.py)


def hay_tarjeta():
    """Si la biblioteca de logos tiene la tarjeta de soporte de WhatsApp (la que tapa el centro del Short)."""
    sys.path.insert(0, os.path.join(RAIZ, 'logos'))
    try:
        import logos
        carpeta = os.path.join(RAIZ, 'mis_conocimientos', 'logos')
        lib = json.load(open(os.path.join(carpeta, 'logos.json'), encoding='utf-8')).get('logos', [])
        return any(logos.es_tarjeta(l) and os.path.isfile(os.path.join(carpeta, l.get('archivo', ''))) for l in lib)
    except Exception:
        return False


def ventanas_tarjeta(frases_t, minimo=2.5):
    """[(desde, hasta)] del Short en que la tarjeta de WhatsApp tapa el centro, como la pone logos.py (fin_tarjeta): desde
    que la voz dice «WhatsApp» hasta que termina esa frase, mínimo 2,5 s. frases_t: [(segundo del Short en que empieza la
    voz de la frase, [(inicio, fin, palabra)])]."""
    out = []
    for t0, pal in frases_t:
        for a0, _a1, w in pal:
            if TARJETA_DICE.search(w):
                out.append((round(t0 + a0, 2), round(max(t0 + a0 + minimo, t0 + pal[-1][1] + 0.2), 2)))
                break
    return out


def sin_tapar(dibujadas, s0, inicio, ventanas):
    """Las flechas y círculos de un trozo (que empieza en el segundo `inicio` del Short y en el `s0` de la grabación) que NO
    quedarían debajo de la tarjeta de WhatsApp: una flecha tapada no se ve y confunde (Short 1 y 2 del Honor, 03/11/2026)."""
    out = []
    for c in dibujadas:
        a = inicio + (c['src'] - s0)
        if not any(a < z and a + c['dur'] > y for y, z in ventanas):
            out.append(c)
    return out


def flecha_al_enlace(tmp):
    """PNG de una flecha que apunta abajo a la izquierda, donde YouTube pone el enlace ▶ del «Video relacionado» en los
    Shorts (fabian, 02/11/2026: el cierre manda ahí). Usa la flecha de GPT del kit (mis_conocimientos/estilo_video) si está."""
    from PIL import Image, ImageDraw
    kit = os.path.join(RAIZ, 'mis_conocimientos', 'estilo_video', 'flecha.png')
    try:
        im = Image.open(kit).convert('RGBA') if os.path.exists(kit) else None
    except OSError:
        im = None
    if im is None:  # una flecha gruesa amarilla con borde negro, apuntando a la derecha
        im = Image.new('RGBA', (440, 170), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        forma = [(14, 60), (290, 60), (290, 14), (426, 85), (290, 156), (290, 110), (14, 110)]
        dr.polygon(forma, fill=(255, 210, 0, 255), outline=(0, 0, 0, 255), width=10)
    k = 330 / max(im.size)
    im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
    im = im.rotate(225, expand=True, resample=Image.BICUBIC)  # de «hacia la derecha» a «hacia abajo a la izquierda»
    im = im.crop(im.getbbox() or (0, 0, im.size[0], im.size[1]))
    out = os.path.join(tmp, 'flecha_enlace.png')
    im.save(out)
    return out


def filtro_flecha(entrada, base, desde, hasta, salida):
    """Filtro de ffmpeg que pone la flecha (entrada número `entrada`) sobre [base] entre desde y hasta, rebotando hacia el
    enlace de abajo a la izquierda, por encima de la barra de YouTube."""
    rebote = f'22*abs(sin(5*(t-{desde:.2f})))'
    return (f"[{entrada}:v]format=rgba,fade=t=in:st={desde:.2f}:d=0.3:alpha=1[fl];"
            f"[{base}][fl]overlay=x='{SW * 0.17:.0f}+{rebote}':y='{SH * 0.78:.0f}-h-{rebote}':eval=frame:shortest=1:"
            f"enable='between(t,{desde:.2f},{hasta:.2f})'[{salida}]")


# fabian, 03/11/2026 («¿Un segundo con la miniatura del video largo al final de cada Short? SÍ, PERO SOLO SI APRUEBO LA
# MINIATURA»): el último segundo del Short muestra la miniatura del video largo, solo la que aprobó en «▶️ YouTube»
# («✅ Apruebo esta miniatura» → youtube/miniatura.json con "aprobada": true). Sin esa marca el Short queda como siempre.
MINI_FINAL_S = 1.0
# arriba al centro, en parte del Short: lejos del ícono de play (abajo a la izquierda, «pos_short» x 0.24 y 0.84 en
# logos.json) y de la flecha que le apunta (filtro_flecha: desde x 0.17, termina en y 0.78), y por encima de los subtítulos
MINI_FINAL = {'ancho': 0.86, 'alto_max': 0.36, 'arriba': 0.17, 'borde': 6}


def miniatura_aprobada(d):
    """La miniatura del video largo que fabian aprobó (youtube/miniatura.json con "aprobada": true), o None. Vale solo
    para ese archivo tal como estaba al aprobarla: si se rehízo con el mismo nombre, hay que volver a aprobarla."""
    try:
        m = json.load(open(os.path.join(d, 'youtube', 'miniatura.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(m, dict) or m.get('aprobada') is not True or not m.get('archivo'):
        return None
    f = os.path.join(d, os.path.basename(str(m['archivo'])))
    if not os.path.isfile(f):
        return None
    try:
        if m.get('aprobada_mtime') is not None and abs(os.path.getmtime(f) - float(m['aprobada_mtime'])) > 1:
            return None
    except (TypeError, ValueError):
        return None
    return f


def caja_de(mini):
    """La caja (x, y, ancho, alto) de esa miniatura en el último segundo del Short, o None si no hay miniatura."""
    if not mini or not os.path.isfile(mini):
        return None
    try:
        from PIL import Image
        with Image.open(mini) as im:
            return caja_miniatura_final(im.size[0] / max(1, im.size[1]))
    except (OSError, ValueError):
        return None


def caja_miniatura_final(ancho_rel=16 / 9):
    """(x, y, ancho, alto) en píxeles del Short de la miniatura del último segundo, con su borde blanco."""
    w = SW * MINI_FINAL['ancho']
    h = w / ancho_rel
    if h > SH * MINI_FINAL['alto_max']:  # una miniatura vertical: más angosta, nunca más abajo
        h = SH * MINI_FINAL['alto_max']
        w = h * ancho_rel
    w, h = round(w / 2) * 2, round(h / 2) * 2
    return (SW - w) // 4 * 2, round(SH * MINI_FINAL['arriba'] / 2) * 2, w, h


def poner_miniatura_final(d, video, alargar=False):
    """Pone la miniatura aprobada del video largo en el último segundo del Short (arriba al centro, con borde blanco y
    entrando suave). alargar=False: encima del último segundo (los 3 Shorts resumen ya tienen 2 s de cola después de la
    frase del play); alargar=True: agrega 1 s con el último cuadro quieto (un Short normal puede terminar hablando).
    Sin miniatura aprobada no toca nada y devuelve None; si la puso, devuelve la ruta de la miniatura. Si algo falla, el
    Short queda como estaba (la miniatura es un extra: nunca tumba el armado)."""
    mini = miniatura_aprobada(d)
    if not mini or not os.path.isfile(video):
        return None
    tmp = os.path.splitext(video)[0] + '_con_miniatura.mp4'
    try:
        caja = caja_de(mini)
        if not caja:
            raise ValueError('no pude leer la miniatura')
        x, y, w, h = caja
        b = MINI_FINAL['borde']
        total = duracion(video)
        desde = round(total if alargar else max(0.0, total - MINI_FINAL_S), 3)
        fin = round(total + (MINI_FINAL_S if alargar else 0), 3)
        base = f'[0:v]tpad=stop_mode=clone:stop_duration={MINI_FINAL_S}[b]' if alargar else '[0:v]null[b]'
        filtro = (f'{base};[1:v]scale={w - 2 * b}:{h - 2 * b},pad={w}:{h}:{b}:{b}:white,format=rgba,'
                  f'fade=t=in:st={desde}:d=0.2:alpha=1[m];[b][m]overlay=x={x}:y={y}:enable=\'gte(t,{desde})\',format=yuv420p[v]')
        musica = []
        if alargar:  # en el segundo de más la música sigue desde donde iba (volumen 0.10, como en el Short) y se apaga suave
            largo_m = duracion(MUSICA) if os.path.isfile(MUSICA) else 0
            if largo_m > MINI_FINAL_S:
                desde_m = total % largo_m
                desde_m = desde_m if desde_m + MINI_FINAL_S <= largo_m else 0.0
                musica = ['-ss', f'{desde_m:.3f}', '-t', f'{MINI_FINAL_S:.3f}', '-i', MUSICA]
                filtro += (f';[2:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.10,'
                           f'afade=t=out:st=0.2:d={MINI_FINAL_S - 0.2:.2f},adelay={int(total * 1000)}:all=1[mu]'
                           f';[0:a]aresample=44100,aformat=channel_layouts=stereo,apad=pad_dur={MINI_FINAL_S}[va]'
                           ';[va][mu]amix=inputs=2:duration=first:normalize=0[a]')
            else:  # sin la música fija: el segundo de más va en silencio
                filtro += f';[0:a]apad=pad_dur={MINI_FINAL_S}[a]'
        sonido = ['-map', '[a]', '-c:a', 'aac', '-b:a', '160k'] if alargar else ['-map', '0:a?', '-c:a', 'copy']
        codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', video, '-loop', '1', '-t', f'{fin:.3f}', '-i', mini] + musica + [
                       '-filter_complex', filtro, '-map', '[v]'] + sonido +
                      ['-t', f'{fin:.3f}', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-movflags', '+faststart', tmp],
                      check=True)
        os.replace(tmp, video)
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f'· no pude poner tu miniatura al final ({e}): el Short queda sin ella', flush=True)
        return None
    print(f'· 1 s con tu miniatura aprobada al final: {os.path.basename(mini)}', flush=True)
    return mini


def seguir(cap, s0, largo, marcas, memoria=None):
    """Dónde mirar en cada momento del tramo: [(t relativo, cx, cy)], el zoom (1 con tu cara, más cerca en pantallas) y
    qué se sigue ('cara', 'telefono' o 'pantalla').

    Si el detector ve el teléfono en buena parte del tramo, se sigue al teléfono (aunque su pantalla esté negra, como en
    fastboot) con el zoom justo para que entre entero.

    Lo importante en un tutorial es lo que CAMBIA respecto del fondo: el teléfono en la mano, su pantalla, la ventana del
    programa. El fondo (la mesa, el cubo de Motorola, el cartel «Frp») queda igual en todo el tramo, así que se saca con la
    mediana de los cuadros; de lo que queda, se mira la zona con más detalle (letras, botones, iconos), no los guantes lisos."""
    import cv2, numpy as np
    import montaje
    det = montaje.detector_caras()
    cuadros, caras, telefonos = [], [], []
    n = max(2, int(largo / PASO_SEG) + 1)
    for i in range(n):
        t = min(largo, i * PASO_SEG)
        cap.set(cv2.CAP_PROP_POS_MSEC, (s0 + t) * 1000)
        ok, f = cap.read()
        if not ok:
            break
        chico = cv2.resize(f, (640, 360))
        cara = None
        if det is not None:
            det.setInputSize((640, 360))
            _, cs = det.detect(chico)
            cs = [c for c in (cs if cs is not None else []) if c[2] >= 640 * 0.03]
            if cs:
                c = max(cs, key=lambda c: c[2] * c[3])
                cara = ((c[0] + c[2] / 2) * 3, (c[1] + c[3] / 2) * 3)
        cuadros.append((t, cv2.GaussianBlur(cv2.cvtColor(chico, cv2.COLOR_BGR2GRAY), (5, 5), 0)))
        caras.append(cara)
        telefonos.append(deteccion.telefono(memoria.ver(s0 + t, f)) if memoria else None)
    if not cuadros:
        return [(0.0, W / 2, H / 2)], 1.0, 'pantalla'
    con_cara = sum(1 for c in caras if c) >= max(1, len(caras) * 0.4)
    con_tel = not con_cara and sum(1 for c in telefonos if c) >= max(1, len(telefonos) * 0.4)
    fondo = np.median(np.stack([g for _, g in cuadros]), axis=0).astype(np.uint8)
    puntos = []
    for (t, g), cara, tel in zip(cuadros, caras, telefonos):
        punto = (cara[0], cara[1], 'cara') if cara else None
        if punto is None:
            for tm, x, y in marcas:  # tu círculo manda en su segundo (±1,5 s)
                if abs(tm - (s0 + t)) <= 1.5:
                    punto = (x, y, 'marca')
        if punto is None and tel:  # el teléfono que ve el detector
            punto = (tel[0] + tel[2] / 2, tel[1] + tel[3] / 2, 'telefono')
        if punto is None and not con_tel:  # sin teléfono a la vista: lo que cambia en la pantalla
            bordes = cv2.dilate(cv2.Canny(g, 40, 120), np.ones((3, 3), np.uint8)).astype(np.float32)
            cambia = cv2.dilate((cv2.absdiff(g, fondo) > 18).astype(np.uint8), np.ones((15, 15), np.uint8))
            if cambia.mean() > 0.03:  # hay algo que se mueve sobre el fondo (el teléfono en la mano)
                # la pantalla encendida es lo CLARO de lo que se mueve: los guantes son negros y la mesa y la pared no se
                # mueven (quedan en el fondo). Su detalle (letras, iconos) suma un poco más.
                clara = (g > 150).astype(np.float32)
                peso = cambia * clara * (60 + bordes * 0.3)
            else:  # todo quieto (una ventana de la PC a pantalla completa): la parte con más detalle
                peso = bordes
            densidad = cv2.GaussianBlur(peso, (0, 0), 30)
            _, pico, _, (px, py) = cv2.minMaxLoc(densidad)
            if pico > 3:
                punto = (px * 3, py * 3, 'pantalla')
        puntos.append((t, punto))
    zoom = 1.0 if con_cara else ZOOM_PANTALLA
    # se suaviza (sin saltos bruscos): mediana de los últimos 2 s y un acercamiento lento
    import statistics
    if con_tel:  # el zoom justo para que el teléfono entre entero, con un poco de aire alrededor
        cajas = [c for c in telefonos if c]
        alto, ancho = statistics.median(c[3] for c in cajas), statistics.median(c[2] for c in cajas)
        zoom = round(max(1.0, min(ZOOM_TELEFONO, H / (alto * 1.15), H * 9 / 16 / (ancho * 1.1))), 2)
        cajas = []  # lo que tiene que quedar adentro en cada momento: tu cara, tu círculo o el teléfono
        for (t, _), cara, tel, (_, p) in zip(cuadros, caras, telefonos, puntos):
            if p and p[2] != 'telefono':
                lado = 300 if p[2] == 'cara' else 200
                cajas.append((t, [p[0] - lado / 2, p[1] - lado / 2, lado, lado]))
            else:
                cajas.append((t, tel))
        return contener(cajas, H / zoom * 9 / 16, H / zoom), zoom, 'telefono'
    validos = [p for _, p in puntos if p and (not con_cara or p[2] == 'cara')]
    cx, cy = (statistics.median(p[0] for p in validos), statistics.median(p[1] for p in validos)) if validos else (W / 2, H / 2)
    ultimos, out = [], []
    for t, p in puntos:
        if p and (not con_cara or p[2] == 'cara'):
            ultimos = (ultimos + [p])[-4:]
            mx, my = statistics.median(q[0] for q in ultimos), statistics.median(q[1] for q in ultimos)
            cx += max(-45, min(45, (mx - cx) * 0.25)); cy += max(-35, min(35, (my - cy) * 0.25))
        out.append((t, cx, cy))
    return out, zoom, 'cara' if con_cara else 'telefono' if con_tel else 'pantalla'


def contener(cajas, cw, ch, aire=0.04):
    """[(t, cx, cy)] del recuadro de cw×ch que deja entera cada caja [(t, [x, y, ancho, alto] o None)], moviéndose solo
    cuando la caja se saldría: así el teléfono nunca queda cortado y el cuadro no baila. Si una caja es más grande que el
    recuadro, se centra en ella."""
    conocidas = [i for i, (_, c) in enumerate(cajas) if c]
    if not conocidas:
        return [(t, W / 2, H / 2) for t, _ in cajas]
    out, cx, cy = [], None, None
    for i, (t, c) in enumerate(cajas):
        x, y, w, h = c or cajas[min(conocidas, key=lambda j: abs(j - i))][1]  # sin caja en ese momento: la más cercana
        mx, my = cw * aire, ch * aire
        lox, hix = x + w + mx - cw / 2, x - mx + cw / 2
        loy, hiy = y + h + my - ch / 2, y - my + ch / 2
        if lox > hix:  # no entra a lo ancho: al centro, sin moverse por unos píxeles de diferencia
            lox = hix = x + w / 2 if cx is None or abs(cx - x - w / 2) > cw * aire else cx
        if loy > hiy:
            loy = hiy = y + h / 2 if cy is None or abs(cy - y - h / 2) > ch * aire else cy
        if cx is None:
            cx, cy = (lox + hix) / 2, (loy + hiy) / 2
        cx, cy = min(max(cx, lox), hix), min(max(cy, loy), hiy)
        out.append((t, cx, cy))
    return out


def expr(claves, i_val, lo, hi):
    """Expresión de ffmpeg que va de una clave a la siguiente en línea recta (t = segundos del tramo)."""
    vals = [(t, min(max(v, lo), hi)) for t, v in ((c[0], c[i_val]) for c in claves)]
    if len(vals) == 1:
        return f'{vals[0][1]:.1f}'
    e = f'{vals[-1][1]:.1f}'
    for (t0, v0), (t1, v1) in reversed(list(zip(vals, vals[1:]))):
        e = f'if(lt(t,{t1:.2f}),{v0:.1f}+({v1 - v0:.1f})*(t-{t0:.2f})/{max(0.01, t1 - t0):.2f},{e})'
    return e


def palabras_voz(d, bid, carpeta='voz'):
    """[(inicio, fin, palabra)] de la voz de un bloque, con los tiempos por letra de ElevenLabs."""
    try:
        a = json.load(open(os.path.join(d, carpeta, f'{bid}.align.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    out, actual, ini = [], '', None
    # las etiquetas de emoción ([curious], [sighs deeply]…) no se dicen: no van en los subtítulos (salían como «[CURIOUS]»)
    texto = ''.join(a['characters'])
    etiqueta = set()
    if len(texto) == len(a['characters']):
        for m in re.finditer(r'\[[^\[\]]{0,40}\][.,]?', texto):
            etiqueta.update(range(*m.span()))
    for k, (ch, t0, t1) in enumerate(zip(a['characters'], a['character_start_times_seconds'], a['character_end_times_seconds'])):
        if ch.isspace() or k in etiqueta:
            if actual:
                out.append((ini, fin, actual)); actual = ''
            continue
        if not actual:
            ini = t0
        actual += ch; fin = t1
    if actual:
        out.append((ini, fin, actual))
    return out


def seguir_ref(cap, s0, largo, conf, d):
    """Encuadre guiado por una referencia (short_encuadres.json del proyecto): la ventana del programa se busca en cada
    momento con SIFT (aunque la cámara se mueva) y el Short se acerca a la «zona» de la que habla la voz (el registro con
    «OKAY, Finished» y el botón Erase FRP By Code), con el zoom justo para que se lea en el celular. fabian, 02/11/2026: al
    pasar a vertical la ventana quedaba cortada y no se veía el mensaje que decía la voz. None si no la encuentra."""
    import cv2, numpy as np, statistics
    ref = cv2.imread(os.path.join(d, conf['referencia']), cv2.IMREAD_GRAYSCALE)
    if ref is None:
        return None
    sift = cv2.SIFT_create()
    kr, dr = sift.detectAndCompute(ref, None)
    zx, zy, zw, zh = conf['zona']
    esquinas = np.float32([[zx, zy], [zx + zw, zy], [zx + zw, zy + zh], [zx, zy + zh]]).reshape(-1, 1, 2)
    bf = cv2.BFMatcher()
    claves, anchos = [], []
    t = 0.0
    while t <= largo:
        cap.set(cv2.CAP_PROP_POS_MSEC, (s0 + t) * 1000)
        ok, fr = cap.read()
        if ok:
            kf, df = sift.detectAndCompute(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), None)
            if df is not None and len(kf) > 10:
                buenos = [m for m, n in (p for p in bf.knnMatch(dr, df, k=2) if len(p) == 2) if m.distance < 0.7 * n.distance]
                if len(buenos) >= 20:
                    Hm, _ = cv2.findHomography(np.float32([kr[m.queryIdx].pt for m in buenos]).reshape(-1, 1, 2),
                                               np.float32([kf[m.trainIdx].pt for m in buenos]).reshape(-1, 1, 2), cv2.RANSAC, 5.0)
                    if Hm is not None:
                        q = cv2.perspectiveTransform(esquinas, Hm).reshape(-1, 2)
                        claves.append((round(t, 2), float(q[:, 0].mean()), float(q[:, 1].mean())))
                        anchos.append(float(q[:, 0].max() - q[:, 0].min()))
        t += PASO_SEG
    if len(claves) < max(2, int(largo / PASO_SEG) // 3):
        return None
    cw = min(statistics.median(anchos) * 1.15, H * 9 / 16)
    zoom = round(H / (cw * 16 / 9), 3)
    # sin saltos: mediana móvil de 3 posiciones
    suave = [(claves[i][0], statistics.median(c[1] for c in claves[max(0, i - 1):i + 2]),
              statistics.median(c[2] for c in claves[max(0, i - 1):i + 2])) for i in range(len(claves))]
    return suave, zoom, 'ventana'


def rotar_gancho(d, c, largo, dur_video, tomas):
    """El gancho del Short en trozos de 3-5 s de momentos distintos del grabado, uno por frase de la voz (montaje/rotar.py:
    antes → herramienta → cable → proceso → después). Sin datos sensibles (los tramos de difuminar_datos.json y lo que el
    mapa leyó con correo, serial, IMEI o precio) y sin repetir lo que muestran las otras tomas. None si no alcanza."""
    if largo < 8:
        return None
    import rotar
    fr = rotar.frases(os.path.join(d, c.get('carpeta', 'voz')), c['id'], 0.0)
    por_tema = rotar.candidatos(os.path.join(d, 'mapa_video.json'), dur_video)
    if not fr or not por_tema:
        return None
    try:
        tramos = json.load(open(os.path.join(d, 'difuminar_datos.json'), encoding='utf-8')).get('tramos', [])
    except (OSError, ValueError):
        tramos = []
    # los tramos del difuminado son segundos del video armado y s es un segundo del grabado: se pasan al grabado con los
    # bloques del guion que caen en cada tramo (antes se comparaban tal cual y el correo o el saldo podían colarse)
    try:
        bloques = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8')).get('bloques', [])
    except (OSError, ValueError):
        bloques = []
    privados = []
    for p0, p1 in ((float(x), float(y)) for x, y in tramos):
        antes = len(privados)
        for b in bloques:
            mo = b.get('montaje') or {}
            if b.get('inicio_min') is None or mo.get('src_inicio') is None:
                continue
            if b['inicio_min'] <= p1 and (b.get('fin_max') or b['inicio_min']) >= p0:
                fin = mo.get('src_fin') or mo['src_inicio'] + float(mo.get('congelar_s') or 0)
                privados.append((mo['src_inicio'] - 3, fin + 3))
        if len(privados) == antes:  # sin bloques con sus tiempos: el tramo tal cual, como antes
            privados.append((p0, p1))
    otros = [(x['src_inicio'] - 3, x['src_inicio'] + x['voz'] + 3) for x in tomas if x is not c]
    cortes = [0.0]
    for s, _ in fr:
        if s - cortes[-1] >= rotar.TROZO[0] and largo - s >= rotar.TROZO[0]:
            cortes.append(s)
    cortes.append(largo)
    piezas, usados, previo = [], [], None
    for a, z in zip(cortes, cortes[1:]):
        frase = next((f for s, f in reversed(fr) if s <= a + 0.5), fr[0][1])
        ult = {tt: max((m.end() for m in re.finditer(v, frase, re.I)), default=-1) for tt, (v, _) in rotar.TEMAS.items()}
        tema = max(ult, key=ult.get) if max(ult.values()) >= 0 else rotar.tema_de(frase, previo)  # «empieza bloqueado y termina libre» → después
        for dur in rotar.trozos(z - a):
            elegido = None
            for tt in [tema] + [x for x in rotar.ORDEN if x != tema]:
                for s in sorted(por_tema.get(tt, []), reverse=(tt == 'despues')):
                    if (all(abs(s - u) > rotar.SEPARACION for u in usados) and s + dur < dur_video
                            and not any(p0 - dur <= s <= p1 for p0, p1 in privados + otros)):
                        elegido = (s, tt)
                        break
                if elegido:
                    break
            if not elegido:
                return None
            usados.append(elegido[0]); previo = elegido[1]
            piezas.append((elegido[0], dur, elegido[1]))
    print(f"· {c['id']}: el gancho rota {len(piezas)} trozos: " + ', '.join(f'{t} {s:.0f}s' for s, _, t in piezas), flush=True)
    return piezas


def armar_rotado(cap, orig, piezas, marcas, memoria, mp3, retraso, largo, tmp, i, salida, dibujadas=()):
    """Cada trozo reencuadrado a 9:16 como las demás tomas, unidos, con la voz del bloque entera encima (y las flechas y
    círculos del video largo que caen en cada trozo)."""
    lista = []
    for k, pz in enumerate(piezas):
        s0, dur = pz[0], pz[1]
        claves, zoom, _ = seguir(cap, s0, dur, marcas, memoria)
        zoom = min(zoom * (pz[3] if len(pz) > 3 else 1), 3.0)  # el mismo momento, otro plano (más cerca de los botones, del cable)
        ch = round(H / zoom / 2) * 2
        cw = round(ch * 9 / 16 / 2) * 2
        cl = [(t, x - cw / 2, y - ch / 2) for t, x, y in claves]
        vf = (f"crop={cw}:{ch}:x='{expr(cl, 1, 0, W - cw)}':y='{expr(cl, 2, 0, H - ch)}',"
              f'scale={SW}:{SH},setsar=1,fps=30,format=yuv420p')
        p = os.path.join(tmp, f'p{i:02d}_{k:02d}.mp4')
        ins, filtro, ult = con_senales(s0, dur, dibujadas, 1)
        codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{dur:.3f}', '-i', orig] + ins +
                      ['-filter_complex', f'{filtro}[{ult}]{vf}[v]', '-map', '[v]', '-t', f'{dur:.3f}', '-an',
                       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', p], check=True)
        lista.append(p)
    lf = os.path.join(tmp, f'rot{i:02d}.txt')
    open(lf, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n".replace('\\', '/') for p in lista))
    audio_in = ['-i', mp3] if mp3 else ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo']  # el gancho sin voz: solo la música
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lf] + audio_in + [
                   '-filter_complex', f'[1:a]adelay={int(retraso * 1000)}:all=1,apad,atrim=0:{largo:.3f},'
                   'aresample=44100,aformat=channel_layouts=stereo[a]',
                   '-map', '0:v', '-map', '[a]', '-t', f'{largo:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                   '-c:a', 'aac', '-b:a', '160k', salida], check=True)


def poner_logos(d, tomas, video, retraso):
    """Los logos de la biblioteca (Android 15/16/17, MagicOS, parche, Google, WhatsApp…) en el segundo en que la voz del Short
    los nombra, con pop-up, de a uno, grandes y centrados POR ENCIMA de los subtítulos. Pedido de fabian (02/11/2026: «¿por
    qué no aparecen los logos?»): el video largo los tenía (logos/logos.py) y los Shorts no los llamaban."""
    carpeta_logos = os.path.join(RAIZ, 'mis_conocimientos', 'logos')
    if not os.path.isfile(os.path.join(carpeta_logos, 'logos.json')):
        return False
    bloques, t0 = [], 0.0
    for c in tomas:
        if c.get('id') and c['id'] != 'GANCHO':
            bloques.append({'id': c['id'], 'texto': c.get('texto') or 'x', 'inicio_min': round(t0, 3)})
        t0 += c['largo']
    carpetas = {c.get('carpeta', 'voz') for c in tomas if c.get('id') != 'GANCHO'}
    if len(carpetas) != 1:
        return False
    g = os.path.join(d, '.short_logos_guion.json')
    json.dump({'bloques': bloques}, open(g, 'w', encoding='utf-8'), ensure_ascii=False)
    salida = video.replace('.mp4', '_logos.mp4')
    r = subprocess.run([sys.executable, os.path.join(RAIZ, 'logos', 'logos.py'), '--video', video, '--guion', g,
                        '--voz', os.path.join(d, carpetas.pop()), '--logos', carpeta_logos, '--salida', salida,
                        '--alto', '0.30', '--centro-y', '0.3', '--queda-max', '3', '--desfase', str(retraso),
                        '--formato', 'short'], cwd=d, capture_output=True, text=True)
    print(r.stdout.strip(), flush=True)
    if r.returncode == 0 and os.path.exists(salida):
        os.replace(video, video.replace('.mp4', '_sin_logos.mp4'))  # para volver a ponerlos sin rearmar el Short
        os.replace(salida, video)
        return True
    return False


def ass_tiempo(s):
    s = max(0.0, s)
    return f'{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}'


def subtitulos(d, tomas, retraso):
    lineas = ['[Script Info]', 'ScriptType: v4.00+', 'WrapStyle: 2', f'PlayResX: {SW}', f'PlayResY: {SH}', '', '[V4+ Styles]',
              'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, '
              'StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
              'Style: S,Arial Black,126,&H00FFFFFF,&H0000D2FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,9,3,2,50,50,700,1',
              '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    t0, eventos = 0.0, []
    for c in tomas:
        pal = palabras_voz(d, c['id'], c.get('carpeta', 'voz'))
        grupos, g = [], []
        for p in pal:  # estilo C (fabian): una línea corta de 2-3 palabras, máx. ~12 letras
            if g and (len(g) == 3 or len(' '.join(x[2] for x in g + [p])) > 12):
                grupos.append(g); g = []
            g.append(p)
        if g:
            grupos.append(g)
        for grupo in grupos:  # la palabra que se dice, en amarillo y un poco más grande
            pals = [x[2].replace('{', '').replace('}', '').upper() for x in grupo]
            largo_txt = len(' '.join(pals))
            ancho = '{\\fscx%d}' % (100 * 12 // largo_txt) if largo_txt > 12 else ''  # una sola línea aunque la palabra sea larga
            for j, (a0, a1, _) in enumerate(grupo):
                fin = grupo[j + 1][0] if j + 1 < len(grupo) else a1 + 0.05
                txt = ancho + ' '.join('{\\c&H0000D2FF&\\fscy112}' + w + '{\\c&H00FFFFFF&\\fscy100}' if k == j else w
                                       for k, w in enumerate(pals))
                eventos.append([t0 + retraso + a0, t0 + retraso + fin, txt])
        t0 += c['largo']
    eventos.sort(key=lambda e: e[0])
    for k, (a0, a1, txt) in enumerate(eventos):  # nunca dos subtítulos a la vez (fabian, 02/11/2026: salían encimados)
        if k + 1 < len(eventos):
            a1 = min(a1, eventos[k + 1][0] - 0.01)
        if a1 > a0:
            lineas.append(f'Dialogue: 0,{ass_tiempo(a0)},{ass_tiempo(a1)},S,,0,0,0,,{txt}')
    return '\n'.join(lineas) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--duracion', type=float, default=60)
    ap.add_argument('--salida', default='SHORT.mp4')
    ap.add_argument('--gancho', help='segundo del grabado y duración de un gancho sin voz delante (78,3.5)')
    ap.add_argument('--bloques', help='los bloques del Short, en orden (L01,L20,L21): sin esto los elige la app')
    ap.add_argument('--voz-nueva', action='store_true', help='voz escrita para el Short (short_guion.json), gasta ElevenLabs')
    a = ap.parse_args()
    import cv2
    d = os.path.abspath(a.proyecto)
    orig = os.path.join(d, 'original.mp4')
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    dur_video = duracion(orig)
    extras = leer_extras(d)
    reservado = 0.0  # lo que ocupan el testimonio y el cierre: sale de la duración que pediste
    if extras.get('testimonio') and extras.get('testimonio_archivo') and os.path.exists(os.path.join(d, extras['testimonio_archivo'])):
        reservado += duracion(os.path.join(d, extras['testimonio_archivo']))
    if extras.get('final') or extras.get('paginas'):
        reservado += float(extras.get('final_dur') or 4)
    if miniatura_aprobada(d):  # el segundo con tu miniatura aprobada al final (03/11/2026): el Short sigue en ~60 s
        reservado += MINI_FINAL_S
    if a.voz_nueva:
        tomas = voz_nueva(d)
    else:
        if reservado:
            print(f'· {reservado:.0f} s son del testimonio, el cierre y la miniatura: elijo tomas para {max(10, a.duracion - reservado):.0f} s', flush=True)
        tomas = elegir(d, g, max(10.0, a.duracion - reservado), dur_video) if not a.bloques else [
            {'k': k, 'id': b['id'], 'voz': round(duracion(os.path.join(d, 'voz', f"{b['id']}.mp3")), 2), 'puntos': 0,
             'por_que': 'elegido para este Short', 'src_inicio': float((b.get('montaje') or {})['src_inicio']), 'texto': b['texto']}
            for k, b in enumerate(g['bloques']) if b['id'] in a.bloques.split(',')]
    if not tomas:
        raise SystemExit('ERROR: no encontré tomas con voz para el Short (falta generar la voz del video).')
    print(f'Elegí {len(tomas)} tomas para un Short de {a.duracion:.0f} s:', flush=True)
    for c in tomas:
        print(f"· {c['id']} ({c['voz']:.1f} s): {c['por_que']}", flush=True)
    marcas = marcas_autor(d)
    try:  # encuadres guiados por bloque (la ventana del programa, la zona de la que habla la voz)
        encuadres = json.load(open(os.path.join(d, 'short_encuadres.json'), encoding='utf-8'))
    except (OSError, ValueError):
        encuadres = {}
    memoria = deteccion.Memoria(orig)
    tmp = codificar.temporal('short')
    retraso = 0.15
    rangos = [(c['src_inicio'], c['src_inicio'] + max(c['voz'] + 0.4, MIN_TOMA if c.get('carpeta') == 'voz_short' else 0))
              for c in tomas]
    dibujadas = dibujar_senales(orig, senales_grabado(d), rangos, tmp)  # las flechas y círculos del video largo
    marcas += [(c['src'] + c['dur'] / 2, c['x'], c['y']) for c in dibujadas]  # el recorte deja adentro lo señalado
    cap = cv2.VideoCapture(orig)
    partes = []
    gancho = None
    if a.gancho:  # un gancho de 3-4 s del resultado (la pantalla que se consigue), antes de la voz
        gs, gd = (float(x) for x in a.gancho.split(','))
        p = os.path.join(tmp, 'gancho.mp4')
        armar_rotado(cap, orig, [(gs, gd, 'gancho', 1.15)], marcas, memoria, None, 0, gd, tmp, 99, p)
        partes.append(p)
        gancho = {'id': 'GANCHO', 'src_inicio': gs, 'largo': gd, 'zoom': 1.15, 'encuadre': 'gancho', 'por_que': 'gancho del resultado',
                  'texto': '', 'voz': 0}
    for i, c in enumerate(tomas):
        largo = round(max(c['voz'] + 0.4, MIN_TOMA if c.get('carpeta') == 'voz_short' else 0), 2)  # que se alcance a ver la acción
        s0 = min(c['src_inicio'], max(0.0, dur_video - largo - 0.1))
        piezas = rotar_gancho(d, c, largo, dur_video, tomas) if i == 0 and c['id'] == g['bloques'][0]['id'] else None
        cortes = (encuadres.get(c['id']) or {}).get('cortes')
        if not piezas and cortes:  # una toma larga del mismo paso: planos de ≤ «cortes» s seguidos, con zoom distinto (sin saltar el paso)
            import math
            n = max(1, math.ceil(largo / float(cortes)))
            zooms = (encuadres[c['id']].get('zooms') or [1.0, 1.6, 1.25])
            piezas = [(s0 + j * largo / n, largo / n, 'plano', zooms[j % len(zooms)]) for j in range(n)]
        if piezas:  # regla de fabian: el inicio rota trozos distintos de 3-5 s según lo que dice la voz
            p = os.path.join(tmp, f'p{i:02d}.mp4')
            armar_rotado(cap, orig, piezas, marcas, memoria, os.path.join(d, c.get('carpeta', 'voz'), f"{c['id']}.mp3"),
                         retraso, largo, tmp, i, p, dibujadas)
            c.update(largo=largo, src_inicio=round(s0, 2), zoom=1, encuadre='rotado')
            partes.append(p)
            continue
        guiado = seguir_ref(cap, s0, largo, encuadres[c['id']], d) if c['id'] in encuadres else None
        claves, zoom, encuadre = guiado or seguir(cap, s0, largo, marcas, memoria)
        ch = round(H / zoom / 2) * 2
        cw = round(ch * 9 / 16 / 2) * 2
        cl = [(t, x - cw / 2, y - ch / 2) for t, x, y in claves]
        c.update(largo=largo, src_inicio=round(s0, 2), zoom=zoom, encuadre=encuadre)
        vf = (f"crop={cw}:{ch}:x='{expr(cl, 1, 0, W - cw)}':y='{expr(cl, 2, 0, H - ch)}',"
              f'scale={SW}:{SH},setsar=1,fps=30,format=yuv420p')
        p = os.path.join(tmp, f'p{i:02d}.mp4')
        que = {'cara': 'tu cara', 'telefono': f'el teléfono, zoom ×{zoom:g}'}.get(encuadre, 'pantalla, con zoom')
        print(f"· armo {c['id']} ({que})…", flush=True)
        ins, filtro, ult = con_senales(s0, largo, dibujadas, 2)
        codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{largo:.3f}', '-i', orig,
                       '-i', os.path.join(d, c.get('carpeta', 'voz'), f"{c['id']}.mp3")] + ins +
                      ['-filter_complex', f'{filtro}[{ult}]{vf}[v];[1:a]adelay={int(retraso * 1000)}:all=1,apad,atrim=0:{largo:.3f},'
                       'aresample=44100,aformat=channel_layouts=stereo[a]',
                       '-map', '[v]', '-map', '[a]', '-t', f'{largo:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                       '-c:a', 'aac', '-b:a', '160k', p], check=True)
        partes.append(p)
    cap.release()
    memoria.guardar()
    if extras.get('testimonio') and extras.get('testimonio_archivo') and os.path.exists(os.path.join(d, extras['testimonio_archivo'])):
        print('· testimonio…', flush=True)
        p = os.path.join(tmp, 'testimonio.mp4')
        parte_testimonio(d, extras['testimonio_archivo'], p)
        partes.append(p)
    paginas = ([x.strip() for x in str(extras.get('paginas_texto') or '').split('·') if x.strip()] or paginas_del_autor()) if extras.get('paginas') else []
    con_cierre = bool((extras.get('final') and (extras.get('final_texto') or extras.get('final_audio'))) or paginas)
    if con_cierre:
        print('· cierre (ver el video completo / páginas)…', flush=True)
        p = os.path.join(tmp, 'final.mp4')
        parte_final(d, partes[-1], extras, paginas, p)
        partes.append(p)
    lista = os.path.join(tmp, 'lista.txt')
    open(lista, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n".replace('\\', '/') for p in partes))
    junto = os.path.join(tmp, 'junto.mp4')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', junto], check=True)
    if gancho:
        tomas.insert(0, gancho)
    open(os.path.join(d, 'short_subs.ass'), 'w', encoding='utf-8').write(subtitulos(d, tomas, retraso))
    entradas = ['-i', junto]
    if os.path.exists(MUSICA):
        entradas += ['-stream_loop', '-1', '-i', MUSICA]
        audio = '[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]'
    else:
        audio = '[0:a]anull[a]'
    print('· subtítulos y música…', flush=True)
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                  ['-filter_complex', f'[0:v]ass=short_subs.ass[v];{audio}', '-map', '[v]', '-map', '[a]',
                   '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
                   a.salida], check=True, cwd=d)
    poner_logos(d, tomas, os.path.join(d, a.salida), retraso)  # los logos de lo que nombra la voz, como en el video largo
    # la miniatura del video largo en el último segundo, solo si fabian la aprobó (03/11/2026); sin aprobar, el Short queda
    # igual. Con la tarjeta del cierre (mínimo 3 s, su texto ya va debajo) va encima de su último segundo; sin ella, 1 s más
    poner_miniatura_final(d, os.path.join(d, a.salida), alargar=not con_cierre)
    total = duracion(os.path.join(d, a.salida))  # con el testimonio, el cierre y la miniatura
    json.dump({'duracion_pedida': a.duracion, 'duracion': round(total, 1), 'formato': '9:16',
               'tomas': [{k: c[k] for k in ('id', 'src_inicio', 'largo', 'zoom', 'encuadre', 'por_que', 'texto')} for c in tomas]},
              open(os.path.join(d, 'short.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'Listo {a.salida}: {total:.0f} s, {len(tomas)} tomas, 1080×1920.', flush=True)


if __name__ == '__main__':
    main()
