"""TESTIMONIOS: mete en el video tus videos de clientes reales, en el momento justo.

En la app subes uno o más videos de testimonios. Cada uno entra entero (o el tramo que elijas) como un corte
del video, sin tapar nada: el video se pausa, se ve el testimonio y sigue donde iba. Nunca corta a la voz a
mitad de frase: el corte va en la pausa entre dos subtítulos.

Audio del testimonio: por defecto suena el audio propio del clip. Si le escribes un «texto» al testimonio, en su
lugar habla tu voz principal (la misma de ElevenLabs) narrando lo que se ve, y el audio del cliente se silencia.
El segmento dura lo que dure esa narración (si es más larga que el clip, se congela el último cuadro para rellenar).

Momento «auto»: se busca en los subtítulos (3_voz.srt) cuándo la voz habla de clientes, opiniones, confianza o
testimonios, y el testimonio entra justo después de esa frase. Si la voz no lo dice, entra antes del cierre.
También puedes escribir un segundo (4:30) o «inicio», «mitad», «final».

Uso:
  python testimonios.py --video 7_tarjetas.mp4 --testimonios testimonios/testimonios.json --srt 3_voz.srt --salida 8_testimonios.mp4
testimonios.json: {"TESTIMONIOS": [{"archivo": "x.mp4", "momento": "auto", "desde": "0:05", "hasta": "0:40", "texto": "Mira esta reseña de un cliente..."}]}
Deja también 8_testimonios.srt con los subtítulos corridos (para el tráiler y el video final).
"""
import argparse, base64, json, os, re, subprocess, time, urllib.error, urllib.request

DISPARA = r'testimon|client|opini|confian|rese[ñn]a|satisfech|contentos'
CIERRE = r'eso fue todo|gracias por (acompa|ver)|nos vemos|hasta (la|el) pr[oó]xim'


def probar(f):
    r = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height,r_frame_rate',
                                   '-of', 'json', f], capture_output=True, text=True, check=True).stdout)
    v = next((s for s in r.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not v:
        raise SystemExit(f'ERROR: {os.path.basename(f)} no tiene imagen de video.')
    n, d = (v.get('r_frame_rate') or '25/1').split('/')
    fps = float(n) / float(d or 1) if float(d or 1) else 25.0
    return {'dur': float(r['format']['duration']), 'w': int(v['width']), 'h': int(v['height']),
            'fps': fps if 10 <= fps <= 120 else 25.0, 'audio': any(s.get('codec_type') == 'audio' for s in r.get('streams', []))}


def segundos(x, defecto=None):
    """«1:25», «85», «85.5» → segundos. Vacío → defecto."""
    x = str(x if x is not None else '').strip().replace(',', '.')
    if not x:
        return defecto
    try:
        if ':' in x:
            m, s = x.rsplit(':', 1)
            return int(m) * 60 + float(s)
        return float(x)
    except ValueError:
        raise SystemExit(f'ERROR: «{x}» no es un tiempo válido (escribe 1:25 o 85).')


def leer_srt(f):
    if not f or not os.path.exists(f):
        return []
    t = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    out = []
    for b in re.split(r'\n\s*\n', open(f, encoding='utf-8', errors='replace').read().strip()):
        m = re.search(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)', b)
        if m:
            out.append((t(*m.groups()[:4]), t(*m.groups()[4:]), ' '.join(b[m.end():].split())))
    return out


def en_pausa(t, subs, dur):
    """El fin de subtítulo más cercano a t: ahí la voz está callada y el corte no se nota."""
    if not subs:
        return min(max(t, 0), dur)
    return min((b for _, b, _ in subs), key=lambda b: abs(b - t))


def momento(m, subs, dur, usados):
    m = str(m or 'auto').strip().lower()
    if m == 'inicio':
        return en_pausa(min(30, dur * 0.1), subs, dur)
    if m == 'mitad':
        return en_pausa(dur / 2, subs, dur)
    cierre = next((a for a, _, x in subs if re.search(CIERRE, x, re.I) and a > dur * 0.6), None)
    if cierre:  # justo antes de la despedida: en la pausa después de la frase anterior
        final = max((b for _, b, _ in subs if b <= cierre + 0.05), default=0.0)
        if cierre - final > 3:  # la voz ya estaba callada antes de despedirse
            final = max(0.0, cierre - 0.3)
    else:
        final = en_pausa(dur - 20, subs, dur)
    if m == 'final':
        return final
    if m != 'auto':
        return en_pausa(segundos(m), subs, dur)
    for _, b, x in subs:  # la primera vez que la voz habla de clientes u opiniones y que no se usó
        if re.search(DISPARA, x, re.I) and all(abs(b - u) > 5 for u in usados):
            return b
    return final


def _clave_eleven():
    """La clave de ElevenLabs: la variable de entorno o la guardada con el botón 🔑 de la app."""
    k = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if k:
        return k
    aj = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'ajustes.json')
    try:
        return json.load(open(aj, encoding='utf-8')).get('elevenlabs', '').strip()
    except (OSError, ValueError):
        return ''


def dur_mp3(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                       capture_output=True, text=True)
    return float(r.stdout or 0)


def narrar(carpeta, bid, texto, voz, modelo, estabilidad):
    """Genera (y reutiliza) la voz principal que narra un testimonio. Devuelve (mp3, duración).
    Solo vuelve a pedirla a ElevenLabs si cambió el texto, la voz, el modelo o la estabilidad; si no, no gasta créditos."""
    mp3 = os.path.join(carpeta, f'narr_{bid}.mp3')
    firma = {'texto': texto, 'voz': voz, 'modelo': modelo, 'estabilidad': estabilidad}
    meta = os.path.join(carpeta, f'narr_{bid}.json')
    if os.path.exists(mp3) and os.path.exists(meta):
        try:
            if json.load(open(meta, encoding='utf-8')) == firma:
                return mp3, dur_mp3(mp3)
        except ValueError:
            pass
    clave = _clave_eleven()
    if not clave:
        raise SystemExit('ERROR: para narrar los testimonios con tu voz principal falta la clave de ElevenLabs. '
                         'Pulsa «🔑 Clave ElevenLabs» arriba a la derecha, pégala y guarda.')
    body = json.dumps({'text': texto, 'model_id': modelo, 'language_code': 'es',
                       'voice_settings': {'stability': estabilidad}}).encode()
    req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_128',
                                 data=body, headers={'Content-Type': 'application/json', 'xi-api-key': clave})
    datos = None
    for intento in range(3):  # si se corta la conexión, reintenta en vez de fallar
        try:
            datos = urllib.request.urlopen(req, timeout=180).read()
            break
        except urllib.error.HTTPError as e:
            raise SystemExit(f'ERROR al narrar «{bid}»: {e.code} {e.read()[:300]}')
        except urllib.error.URLError as e:
            if intento == 2:
                raise SystemExit(f'ERROR: no se pudo conectar a ElevenLabs para narrar «{bid}» ({e.reason}). '
                                 'Revisa tu internet y vuelve a pulsar «Rehacer».')
            print(f'narración {bid}: se cortó la conexión ({e.reason}); reintento {intento + 2} de 3...', flush=True)
            time.sleep(2 * (intento + 1))
    open(mp3, 'wb').write(datos)
    json.dump(firma, open(meta, 'w', encoding='utf-8'), ensure_ascii=False)
    return mp3, dur_mp3(mp3)


def mover_srt(subs, cortes, destino):
    """Los subtítulos después de cada testimonio se corren lo que dura el testimonio."""
    def hms(t):
        return f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round(t % 1 * 1000)) % 1000:03d}'
    with open(destino, 'w', encoding='utf-8') as f:
        for k, (a, b, x) in enumerate(subs, 1):
            corre = sum(d for t, d in cortes if a >= t - 0.01)
            f.write(f'{k}\n{hms(a + corre)} --> {hms(b + corre)}\n{x}\n\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--testimonios', required=True)
    ap.add_argument('--srt', default='3_voz.srt')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--voz', default='94zOad0g7T7K4oa7zhDq', help='misma voz que la narración principal (voz.py)')
    ap.add_argument('--modelo', default='eleven_v4')
    ap.add_argument('--estabilidad', type=float, default=0.5)
    a = ap.parse_args()
    base = probar(a.video)
    carpeta = os.path.dirname(os.path.abspath(a.testimonios))
    lista = json.load(open(a.testimonios, encoding='utf-8')).get('TESTIMONIOS', [])
    subs = leer_srt(a.srt)
    W, H, F = base['w'] + base['w'] % 2, base['h'] + base['h'] % 2, base['fps']

    cortes, usados = [], []
    for t in lista:
        f = os.path.join(carpeta, os.path.basename(t.get('archivo') or ''))
        if not os.path.isfile(f):
            print(f"AVISO: no encontré el testimonio {t.get('archivo')}, lo salto"); continue
        info = probar(f)
        desde = min(max(segundos(t.get('desde'), 0) or 0, 0), info['dur'] - 0.5)
        hasta = min(segundos(t.get('hasta'), info['dur']) or info['dur'], info['dur'])
        if hasta - desde < 0.5:
            print(f"AVISO: el tramo de {t.get('archivo')} es muy corto, lo salto"); continue
        en = momento(t.get('momento'), subs, base['dur'], usados)
        usados.append(en)
        clip_dur = hasta - desde
        texto = ' '.join((t.get('texto') or '').split())
        narr, dur = None, clip_dur
        if texto:  # el narrador (tu voz principal) cuenta el testimonio y el audio del cliente se silencia
            bid = re.sub(r'\W+', '', os.path.splitext(os.path.basename(f))[0]) or f'testi{len(cortes) + 1}'
            narr, ndur = narrar(carpeta, bid, texto, a.voz, a.modelo, a.estabilidad)
            dur = max(clip_dur, ndur + 0.6)  # el segmento dura lo que la narración, con un respiro al final
        cortes.append({'en': en, 'f': f, 'desde': desde, 'clip_dur': clip_dur, 'dur': dur, 'audio': info['audio'], 'narr': narr})
        print(f"testimonio {os.path.basename(f)} ({dur:.0f} s{', narrado' if narr else ''}) entra en {int(en // 60)}:{int(en % 60):02d}")
    if not cortes:
        raise SystemExit('ERROR: no hay testimonios para poner. Sube tus videos en el panel «Testimonios».')
    cortes.sort(key=lambda c: c['en'])

    ins, fil, partes, previo, ni = ['-i', a.video], [], [], 0.0, 1  # ni: próxima entrada de ffmpeg (0 es a.video)
    ajuste = (f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,'
              f'fps={F:.3f},format=yuv420p,setsar=1')
    for c in cortes:
        if c['en'] > previo + 0.05:  # tramo del video antes del testimonio
            n = len(partes)
            fil.append(f"[0:v]trim={previo}:{c['en']},setpts=PTS-STARTPTS,{ajuste}[v{n}];"
                       f"[0:a]atrim={previo}:{c['en']},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{n}]")
            partes.append(n)
        D = c['dur']
        iv = ni; ins += ['-ss', str(c['desde']), '-t', str(c['clip_dur']), '-i', c['f']]; ni += 1
        n = len(partes)
        extra = max(0.0, D - c['clip_dur'])  # si la narración dura más que el clip, congelo el último cuadro para rellenar
        pad = f",tpad=stop_mode=clone:stop_duration={extra:.3f}" if extra > 0.05 else ""
        fil.append(f"[{iv}:v]setpts=PTS-STARTPTS,{ajuste}{pad},fade=t=in:d=0.3,fade=t=out:st={max(0, D - 0.3):.2f}:d=0.3[v{n}]")
        if c.get('narr'):  # narración con tu voz principal; el audio del cliente va en silencio
            ia = ni; ins += ['-i', c['narr']]; ni += 1
            fil.append(f"[{ia}:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-1.5,apad,atrim=0:{D:.3f},"
                       f"afade=t=in:d=0.3,afade=t=out:st={max(0, D - 0.4):.2f}:d=0.4[a{n}]")
        elif c['audio']:
            fil.append(f"[{iv}:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{D:.3f},"
                       f"afade=t=in:d=0.3,afade=t=out:st={max(0, D - 0.4):.2f}:d=0.4,loudnorm=I=-16:TP=-1.5,aresample=48000[a{n}]")
        else:
            fil.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{D:.3f}[a{n}]")
        partes.append(n)
        previo = c['en']
    if base['dur'] > previo + 0.05:
        n = len(partes)
        fil.append(f"[0:v]trim={previo},setpts=PTS-STARTPTS,{ajuste}[v{n}];"
                   f"[0:a]atrim={previo},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{n}]")
        partes.append(n)
    fil.append(''.join(f'[v{n}][a{n}]' for n in partes) + f'concat=n={len(partes)}:v=1:a=1[v][a]')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-stats', '-y'] + ins +
                   ['-filter_complex', ';'.join(fil), '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', a.salida], check=True)
    if subs:
        mover_srt(subs, [(c['en'], c['dur']) for c in cortes], os.path.splitext(a.salida)[0] + '.srt')
    print(f"Listo {a.salida}: {len(cortes)} testimonio(s), {sum(c['dur'] for c in cortes):.0f} s más de video")


if __name__ == '__main__':
    main()
