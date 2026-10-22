"""Coloca cada bloque de voz en su segundo de inicio sobre el video y saca subtítulos SRT.

Uso: python3 mezclar_voz.py <video_sin_audio.mp4> <guion.json> <carpeta_voz> <salida.mp4> [desfase=0.3]
"""
import json, os, subprocess, sys

video, guion, voz, salida = sys.argv[1:5]
desfase = float(sys.argv[5]) if len(sys.argv) > 5 else 0.3
d = json.load(open(guion))
total = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video],
                             capture_output=True, text=True).stdout)


def ts(x):
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


ins, flt, labs, srt = ['-i', video], [], [], []
if os.path.getmtime(guion) > os.path.getmtime(video):
    print('AVISO: el guion cambió después de montar el video (por ejemplo, la voz alargó bloques). '
          'Vuelve a «Montar video» para que la imagen siga a la voz.', flush=True)
bl = d['bloques']
for b, sig in zip(bl, bl[1:]):  # una voz que se mete en el bloque siguiente
    real = b.get('voz_real_s')
    if real and b['inicio_min'] + desfase + real > sig['inicio_min'] + desfase - 0.05:
        print(f"AVISO: la voz de {b['id']} se pisa con la de {sig['id']}. Vuelve a «Generar voz» para que se ajuste el guion.", flush=True)
for k, b in enumerate(d['bloques'], 1):
    st = b['inicio_min'] + desfase
    ins += ['-i', f"{voz}/{b['id']}.mp3"]
    flt.append(f"[{k}:a]aresample=44100,adelay={int(st * 1000)}:all=1[a{k}]")
    labs.append(f"[a{k}]")
    al = json.load(open(f"{voz}/{b['id']}.align.json"))
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
flt.append(''.join(labs) + f"amix=inputs={len(labs)}:normalize=0,loudnorm=I=-16:TP=-1.5,apad[aout]")
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
               ['-filter_complex', ';'.join(flt), '-map', '0:v', '-map', '[aout]', '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '160k', '-t', str(total), salida], check=True)
open(salida.rsplit('.', 1)[0] + '.srt', 'w').write('\n'.join(srt))
