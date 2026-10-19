"""Tráiler de inicio ANTES · DURANTE · DESPUÉS (la firma de fabian) hecho con Remotion.

Para cada clip del plan busca, dentro de su ventana del video original, el momento más
nítido y quieto (módulo nitidez) y corta ahí. Luego Remotion pone los sellos animados, los
destellos, el zoom y la placa final; se le agrega una frase con la voz de Mauricio y música.

Uso:
  python3 trailer.py --video original.mp4 --plan plan.json --salida trailer.mp4 \
      [--unir video_final.mp4 --final con_trailer.mp4] [--srt subs.srt]

plan.json: ver ejemplos/pico2_trailer.json. "voz" es opcional (cuesta ~1 crédito por carácter).
Con --unir pega el tráiler delante del video y, con --srt, corre los subtítulos.
"""
import argparse, json, os, re, shutil, subprocess, sys, urllib.request

# En tu PC: define la variable ELEVENLABS_API_KEY. En el entorno de Claude la clave la pone el proxy.
CLAVE = {'xi-api-key': os.environ['ELEVENLABS_API_KEY']} if os.environ.get('ELEVENLABS_API_KEY') else {}

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REMOTION = os.path.join(RAIZ, 'remotion')
PUB = os.path.join(REMOTION, 'public', 'trailer')
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
from nitidez import analizar, mejor  # noqa: E402

VOZ_ID = '94zOad0g7T7K4oa7zhDq'  # Mauricio
CIERRE = 2.4


def ff(args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + args, check=True)


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True, check=True).stdout)


def voz(texto, destino):
    body = json.dumps({'text': texto, 'model_id': 'eleven_v4', 'voice_settings': {'stability': 0.5}}).encode()
    req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{VOZ_ID}?output_format=mp3_44100_128',
                                 data=body, headers={'Content-Type': 'application/json', **CLAVE})
    open(destino, 'wb').write(urllib.request.urlopen(req, timeout=120).read())


def correr_srt(srt, seg, destino):
    def mover(m):
        h, mi, s, ms = map(int, m.groups())
        t = h * 3600 + mi * 60 + s + ms / 1000 + seg
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round(t % 1 * 1000)) % 1000:03d}"
    open(destino, 'w').write(re.sub(r'(\d\d):(\d\d):(\d\d),(\d\d\d)', mover, open(srt).read()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--unir')
    ap.add_argument('--final')
    ap.add_argument('--srt')
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    shutil.rmtree(PUB, ignore_errors=True); os.makedirs(PUB)
    nt = analizar(a.video, os.path.join(PUB, 'original.nitidez.npz'))

    clips = []
    for k, c in enumerate(plan['clips'], 1):
        t0, t1 = c['ventana']
        centro = mejor(*nt, t0, t1)
        ini = min(max(t0, centro - c['dur'] / 2), max(t0, t1 - c['dur']))
        ff(['-ss', str(ini), '-t', str(c['dur'] + 0.2), '-i', a.video, '-an', '-vf',
            'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=25,format=yuv420p',
            '-c:v', 'libx264', '-crf', '16', '-preset', 'veryfast', os.path.join(PUB, f'c{k}.mp4')])
        clips.append({'src': f'trailer/c{k}.mp4', 'dur': c['dur'], 'fase': c['fase']})
        print(f"{c['fase']:8s} {ini:6.1f}s")
    total = sum(c['dur'] for c in clips) + CIERRE

    # audio: música con entrada fuerte y salida suave; la voz encima, con la música agachada
    mus = plan.get('musica')
    filtros, ins = [], []
    if mus:
        ins += ['-ss', str(mus.get('desde', 0)), '-i', mus['pista']]
        filtros.append(f"[0:a]atrim=0:{total},afade=t=in:d=0.3,afade=t=out:st={total - 1.2}:d=1.2,volume=0.55[m]")
    if plan.get('voz'):
        # la voz se guarda junto a la salida y se reutiliza mientras el texto no cambie
        vf = os.path.splitext(a.salida)[0] + '.voz.mp3'
        previo = open(vf + '.txt').read() if os.path.exists(vf) and os.path.exists(vf + '.txt') else None
        if previo != plan['voz']:
            voz(plan['voz'], vf); open(vf + '.txt', 'w').write(plan['voz'])
        iv = ins.count('-i'); ins += ['-i', vf]
        filtros.append(f"[{iv}:a]adelay=300:all=1,apad[v]")
        if mus:
            filtros.append('[v]asplit=2[v1][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=5:release=300[md];'
                           '[v1][md]amix=inputs=2:normalize=0:duration=longest[x]')
        else:
            filtros.append('[v]anull[x]')
    elif mus:
        filtros.append('[m]anull[x]')
    props = {'clips': clips, 'titulo': plan['titulo'], 'subtitulo': plan.get('subtitulo')}
    if filtros:
        filtros.append(f"[x]atrim=0:{total},loudnorm=I=-15:TP=-1.5[a]")
        ff(ins + ['-filter_complex', ';'.join(filtros), '-map', '[a]', '-ar', '48000', os.path.join(PUB, 'audio.wav')])
        props['audio'] = 'trailer/audio.wav'

    env = dict(os.environ)
    chrome = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
    if os.path.exists(chrome):
        env.setdefault('REMOTION_CHROME', chrome)
    subprocess.run(['npx', 'remotion', 'render', 'src/index.ts', 'Trailer', os.path.abspath(a.salida),
                    '--props', json.dumps(props), '--crf', '18'], cwd=REMOTION, env=env, check=True)

    if a.unir and a.final:
        n = duracion(a.salida)
        ff(['-i', a.salida, '-i', a.unir, '-filter_complex',
            '[0:v]fps=25,format=yuv420p,setsar=1[v0];[1:v]fps=25,format=yuv420p,setsar=1[v1];'
            '[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]',
            '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k', a.final])
        if a.srt:
            correr_srt(a.srt, n, os.path.splitext(a.final)[0] + '.srt')
        print(f'tráiler {n:.1f}s pegado delante: {a.final}')


if __name__ == '__main__':
    main()
