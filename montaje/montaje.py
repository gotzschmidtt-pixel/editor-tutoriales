"""Arma el video según el plan de montaje del guion: cámara lenta, congelados e imágenes.

Uso: python3 montaje.py --original original.mp4 --guion guion.json --salida montaje.mp4 [--imagen mapa.png] [--calidad 1080|720|480|360]

Cada bloque del guion trae "montaje": {"modo": "lento" | "congelar" | "lento+congelar" | "imagen",
  "src_inicio": s, "src_fin": s, "velocidad": 0.8, "congelar_s": s, "imagen": "archivo.png" (opcional)}.
Los congelados usan el cuadro más quieto y nítido cerca del momento pedido (módulo nitidez) y llevan zoom lento.
--calidad menor a 1080: prueba rápida con el nombre del bloque escrito (--borrador = 720).
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
from nitidez import analizar, mejor  # noqa: E402


def run(args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + args, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--original', required=True)
    ap.add_argument('--guion', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--imagen', help='imagen por defecto para los bloques en modo "imagen"')
    ap.add_argument('--borrador', action='store_true', help='igual que --calidad 720')
    ap.add_argument('--calidad', type=int, choices=[1080, 720, 480, 360], default=1080)
    a = ap.parse_args()
    d = json.load(open(a.guion, encoding='utf-8'))
    alto = 720 if a.borrador and a.calidad == 1080 else a.calidad
    final = alto == 1080
    res = (alto * 16 // 9 // 2 * 2, alto)
    crf = '20' if final else '26'
    out = f"scale={res[0]}:{res[1]}:force_original_aspect_ratio=decrease,pad={res[0]}:{res[1]}:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p"
    fuente = next((f for f in ('C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf') if os.path.exists(f)), None)

    def rotulo(txt):
        if final or not fuente:
            return ''
        txt = txt.replace(':', '\\:').replace("'", '')
        return f",drawtext=fontfile='{fuente}':text='{txt}':x=24:y=h-52:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10"

    tmp = tempfile.mkdtemp(prefix='montaje_')
    nt = analizar(a.original, os.path.splitext(a.original)[0] + '.nitidez.npz')
    partes = []
    for b in d['bloques']:
        m, i = b['montaje'], b['id']
        lab = rotulo(f"{i}  {b.get('ancla', '')}")
        enc = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', crf]
        if m['modo'].startswith('lento'):
            f = os.path.join(tmp, f'{i}_a.mp4')
            run(['-ss', str(m['src_inicio']), '-t', str(m['src_fin'] - m['src_inicio']), '-i', a.original, '-an',
                 '-vf', f"setpts=PTS/{m.get('velocidad') or 1},{out}{lab}"] + enc + [f])
            partes.append(f)
        if m['modo'].endswith('congelar'):
            v = (m['src_inicio'] - 1, m['src_inicio'] + 3) if m['modo'] == 'congelar' else (m['src_fin'] - 3, m['src_fin'])
            t = m.get('cuadro', mejor(*nt, *v))
            png, f = os.path.join(tmp, f'{i}.png'), os.path.join(tmp, f'{i}_b.mp4')
            run(['-ss', str(t), '-i', a.original, '-frames:v', '1', png])
            nfr = int(round(m['congelar_s'] * 25))
            z = f'1+0.10*on/{nfr}' if len(partes) % 2 == 0 else f'1.10-0.10*on/{nfr}'
            run(['-i', png, '-vf', f"scale=3840:2160,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nfr}:s={res[0]}x{res[1]}:fps=25,format=yuv420p{lab}",
                 '-frames:v', str(nfr)] + enc + [f])
            partes.append(f)
        if m['modo'] == 'imagen':
            img = m.get('imagen') or a.imagen
            f = os.path.join(tmp, f'{i}_b.mp4')
            run(['-loop', '1', '-t', str(m['congelar_s']), '-i', img, '-filter_complex',
                 f"[0]split[a][b];[a]scale={res[0]}:{res[1]},boxblur=20[bg];[b]scale=-1:{res[1] - 20}[fg];[bg][fg]overlay=(W-w)/2:10,fps=25,format=yuv420p{lab}"]
                + enc + [f])
            partes.append(f)
        print(i, 'ok', flush=True)
    lista = os.path.join(tmp, 'lista.txt')
    with open(lista, 'w') as fh:
        for p in partes:
            fh.write(f"file '{p}'\n")
    run(['-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', a.salida])
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
