import json, subprocess, os
SRC = "/mnt/project-files/COMO SOLDAR RASPBERRY OSCAR .mp4"
MAPA = "/mnt/project-files/guion-pico/mapa_pines_pico2.png"
import sys
FINAL = len(sys.argv) > 1
W = "./trabajo/" + ("final" if FINAL else "render")
os.makedirs(W, exist_ok=True)
d = json.load(open('/mnt/project-files/guion-pico/guion_pico_largo.json'))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
RES = (1920, 1080) if FINAL else (1280, 720)
OUT = f"scale={RES[0]}:{RES[1]}:force_original_aspect_ratio=decrease,pad={RES[0]}:{RES[1]}:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p"
def label(txt):
    if FINAL: return ""
    txt = txt.replace(":", "\\:").replace("'", "")
    return f",drawtext=fontfile={FONT}:text='{txt}':x=24:y=h-52:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10"
def run(args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y"] + args, check=True)
parts = []
for b in d['bloques']:
    m = b['montaje']; i = b['id']; lab = label(f"{i}  {b['ancla']}")
    segs = []
    if m['modo'].startswith('lento'):
        f = f"{W}/{i}_a.mp4"
        run(["-ss", str(m['src_inicio']), "-t", str(m['src_fin'] - m['src_inicio']), "-i", SRC, "-an",
             "-vf", f"setpts=PTS/{m['velocidad']},{OUT}{lab}", "-c:v", "libx264", "-preset", "veryfast", "-crf", ("20" if FINAL else "26"), f])
        segs.append(f)
    if m['modo'] == 'congelar' or m['modo'].endswith('congelar'):
        t = m['src_inicio'] if m['modo'] == 'congelar' else m['src_fin'] - 0.5
        f = f"{W}/{i}_b.mp4"
        run(["-ss", str(t), "-i", SRC, "-frames:v", "1", f"{W}/{i}.png"])
        run(["-loop", "1", "-t", str(m['congelar_s']), "-i", f"{W}/{i}.png",
             "-vf", f"{OUT}{lab}", "-c:v", "libx264", "-preset", "veryfast", "-crf", ("20" if FINAL else "26"), f])
        segs.append(f)
    if m['modo'] == 'imagen':
        f = f"{W}/{i}_b.mp4"
        run(["-loop", "1", "-t", str(m['congelar_s']), "-i", MAPA, "-filter_complex",
             f"[0]split[a][b];[a]scale={RES[0]}:{RES[1]},boxblur=20[bg];[b]scale=-1:{RES[1]-20}[fg];[bg][fg]overlay=(W-w)/2:10,fps=25,format=yuv420p{lab}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", ("20" if FINAL else "26"), f])
        segs.append(f)
    parts += segs
with open(f"{W}/lista.txt", "w") as fh:
    for p in parts: fh.write(f"file '{p}'\n")
os.makedirs("/mnt/project-files/guion-pico", exist_ok=True)
run(["-f", "concat", "-safe", "0", "-i", f"{W}/lista.txt", "-c", "copy", f"{W}/borrador.mp4"])
print(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "default=nw=1", f"{W}/borrador.mp4"], capture_output=True, text=True).stdout)
