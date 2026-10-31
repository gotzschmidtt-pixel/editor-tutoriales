"""Coloca cada bloque de voz en su segundo de inicio sobre el video y saca subtítulos SRT.

Uso: python3 mezclar_voz.py <video_sin_audio.mp4> <guion.json> <carpeta_voz> <salida.mp4> [desfase=0.3]
"""
import json, os, subprocess, sys

video, guion, voz, salida = sys.argv[1:5]
desfase = float(sys.argv[5]) if len(sys.argv) > 5 else 0.3
d = json.load(open(guion, encoding='utf-8'))
total = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video],
                             capture_output=True, text=True).stdout)


def ts(x):
    ms = int(round(x * 1000))  # redondeado una sola vez: 61,9996 s da 00:01:02,000 y no «,1000»
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


ins, flt, labs, srt = ['-i', video], [], [], []
if os.path.getmtime(guion) > os.path.getmtime(video):
    print('AVISO: el guion cambió después de montar el video (por ejemplo, la voz alargó bloques). '
          'Vuelve a «Montar video» para que la imagen siga a la voz.', flush=True)
bl = d['bloques']
for b, sig in zip(bl, bl[1:]):  # una voz que se mete en el bloque siguiente
    real = b.get('voz_real_s')
    if real and b['inicio_min'] + desfase + real > sig['inicio_min'] + desfase - 0.05:
        print(f"AVISO: la voz de {b['id']} se pisa con la de {sig['id']}. Vuelve a «Generar voz» para que se ajuste el guion.", flush=True)
k = 0
for b in d['bloques']:
    if not str(b.get('texto') or '').strip():
        continue  # tramo sin voz
    k += 1
    st = b['inicio_min'] + desfase
    ins += ['-i', f"{voz}/{b['id']}.mp3"]
    flt.append(f"[{k}:a]aresample=44100,adelay={int(st * 1000)}:all=1[a{k}]")
    labs.append(f"[a{k}]")
    al = json.load(open(f"{voz}/{b['id']}.align.json", encoding='utf-8'))
    ch, s0, e0 = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    i, L = 0, len(ch)
    while i < L:  # frases de ~45 caracteres, cortando en espacios o puntuación
        j, corte = i, None
        while j < L and (j - i < 45 or corte is None):
            if ch[j] == ' ':
                corte = j
            if ch[j] in '.?!;' and j - i > 15:
                corte = j + 1
                break
            j += 1
        if j >= L:
            corte = L
        txt = ''.join(ch[i:corte]).strip()
        if txt:
            srt.append(f"{len(srt) + 1}\n{ts(st + s0[i])} --> {ts(st + e0[corte - 1])}\n{txt}\n")
        i = corte
        while i < L and ch[i] == ' ':
            i += 1
carpeta = os.path.dirname(os.path.abspath(guion))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sonidos'))
import sonidos  # noqa: E402  «🔊 Efectos de sonido»: clic en los botones, whoosh en los cortes (si los activaste)
if sonidos.activo(carpeta):
    ev = [e for e in sonidos.plan(carpeta) if e['t'] < total]
    e_in, e_fl, e_lab = sonidos.filtros(ev, k + 1, sonidos.ajustes(carpeta)['volumen'])
    if e_lab:
        ins += e_in
        flt += e_fl
        labs.append(e_lab)
        print(f'· {len(ev)} efectos de sonido', flush=True)
flt.append(''.join(labs) + f"amix=inputs={len(labs)}:normalize=0,loudnorm=I=-16:TP=-1.5,aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,apad[aout]")
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
               ['-filter_complex', ';'.join(flt), '-map', '0:v', '-map', '[aout]', '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '160k', '-t', str(total), salida], check=True)
open(salida.rsplit('.', 1)[0] + '.srt', 'w', encoding='utf-8').write('\n'.join(srt))
