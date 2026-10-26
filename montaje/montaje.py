"""Arma el video según el plan de montaje del guion: cámara lenta, congelados e imágenes.

Uso: python3 montaje.py --original original.mp4 --guion guion.json --salida montaje.mp4 [--imagen mapa.png] [--calidad 1080|720|480|360]

Cada bloque del guion trae "montaje": {"modo": "lento" | "congelar" | "lento+congelar" | "imagen",
  "src_inicio": s, "src_fin": s, "velocidad": 0.8, "congelar_s": s, "imagen": "archivo.png" (opcional)}.
Las pausas («congelar») ya no son una foto: repiten la escena en movimiento (ida y vuelta, algo lenta) con zoom suave,
alrededor del cuadro más nítido del momento pedido. Con "quieto": true en el montaje del bloque, vuelve a ser un cuadro fijo.
--calidad menor a 1080: prueba rápida con el nombre del bloque escrito (--borrador = 720).
--estabilizar: quita el temblor de la cámara en mano de cada tramo (vid.stab si ffmpeg lo trae; si no, deshake).
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador
from nitidez import analizar, mejor  # noqa: E402


VENTANA = 2.4       # segundos de escena que se repiten (ida y vuelta) en vez de congelar un cuadro
LENTO_ESCENA = 0.7  # la repetición va un poco más lenta para que se note menos


EN_CURSO = 'montaje_en_curso.mp4'  # lo que va del montaje, para verlo en la app mientras se arma


def voz_al_dia(carpeta_voz, bid, texto):
    """¿El mp3 de este bloque dice el texto actual del guion? Si no, no se mete en el preview,
    para que el «montaje mientras se arma» nunca suene con la voz de un guion anterior."""
    try:
        al = json.load(open(os.path.join(carpeta_voz, f'{bid}.align.json'), encoding='utf-8'))
        return ''.join(al['characters']).strip() == (texto or '').strip()
    except (OSError, ValueError, KeyError, TypeError):
        return False


def avance(partes, tmp, destino, voces=()):
    """Une lo que va hecho en un video que la app puede reproducir, con la voz de esos bloques encima
    (así se puede ir escuchando mientras se arma). Si alguien lo está mirando y Windows no deja reemplazarlo,
    se intenta en el bloque siguiente."""
    lista, nuevo = os.path.join(tmp, 'avance.txt'), os.path.join(tmp, 'avance.mp4')
    with open(lista, 'w', encoding='utf-8') as fh:
        fh.writelines(f"file '{p}'\n" for p in partes)
    voces = [(t, f) for t, f in voces if os.path.exists(f)]
    try:
        if voces:
            ins, flt = ['-f', 'concat', '-safe', '0', '-i', lista], []
            for k, (t, f) in enumerate(voces, 1):
                ins += ['-i', f]
                flt.append(f"[{k}:a]aresample=44100,adelay={int(t * 1000)}:all=1[a{k}]")
            flt.append(''.join(f'[a{k}]' for k in range(1, len(voces) + 1)) + f"amix=inputs={len(voces)}:normalize=0,apad[aout]")
            run(ins + ['-filter_complex', ';'.join(flt), '-map', '0:v', '-map', '[aout]', '-c:v', 'copy',
                       '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', nuevo])
        else:
            run(['-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', '-movflags', '+faststart', nuevo])
        os.replace(nuevo, destino)
    except (OSError, subprocess.CalledProcessError):
        pass


def run(args):
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + args, check=True)


_VIDSTAB = None


def hay_vidstab():
    global _VIDSTAB
    if _VIDSTAB is None:
        r = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True)
        _VIDSTAB = 'vidstabtransform' in r.stdout
    return _VIDSTAB


def estabilizar(f, enc):
    """Quita el temblor de la cámara en mano de un tramo ya cortado (la acelera la app: ×2 un temblor se nota el doble).
    vid.stab mide el movimiento y lo suaviza con un recorte de 4 %; sin vid.stab, el deshake que trae todo ffmpeg.
    Si falla, el tramo queda como estaba."""
    tmp, trf = f + '.est.mp4', f + '.trf'
    try:
        if hay_vidstab():
            # ffmpeg en Windows no entiende «C:» dentro de un filtro: el .trf va con su nombre, desde su carpeta
            cwd = os.path.dirname(f)
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', os.path.basename(f), '-vf',
                            f'vidstabdetect=shakiness=8:accuracy=9:stepsize=12:result={os.path.basename(trf)}', '-f', 'null', '-'],
                           cwd=cwd, check=True, capture_output=True)
            codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', os.path.basename(f), '-vf',
                           f'vidstabtransform=input={os.path.basename(trf)}:smoothing=20:zoom=4:interpol=linear,format=yuv420p']
                          + enc + [os.path.basename(tmp)], check=True, cwd=cwd)
        else:
            run(['-i', f, '-vf', 'deshake,format=yuv420p'] + enc + [tmp])
        os.replace(tmp, f)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f'· no pude estabilizar {os.path.basename(f)} ({e}); queda como estaba', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--original', required=True)
    ap.add_argument('--guion', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--imagen', help='imagen por defecto para los bloques en modo "imagen"')
    ap.add_argument('--borrador', action='store_true', help='igual que --calidad 720')
    ap.add_argument('--calidad', type=int, choices=[1080, 720, 480, 360], default=1080)
    ap.add_argument('--estabilizar', action='store_true', help='quita el temblor de la cámara en mano')
    a = ap.parse_args()
    d = json.load(open(a.guion, encoding='utf-8'))
    alto = 720 if a.borrador and a.calidad == 1080 else a.calidad
    final = alto == 1080
    res = (alto * 16 // 9 // 2 * 2, alto)
    crf = '20' if final else '26'
    # framerate (no fps): al pasar a 25 cuadros por segundo un video de 30 o 60, o un tramo acelerado o lento, fps se salta
    # cuadros de forma despareja (2, 2, 3, 2…) y el movimiento tiembla; framerate arma cada cuadro en su momento exacto
    out = f"scale={res[0]}:{res[1]}:force_original_aspect_ratio=decrease,pad={res[0]}:{res[1]}:(ow-iw)/2:(oh-ih)/2,framerate=fps=25,format=yuv420p"
    fuente = next((f for f in ('C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf') if os.path.exists(f)), None)

    def rotulo(txt):
        if final or not fuente:
            return ''
        txt = txt.replace(':', '\\:').replace("'", '')
        return f",drawtext=fontfile='{fuente}':text='{txt}':x=24:y=h-52:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10"

    dur_original = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.original],
                                        capture_output=True, text=True, check=True).stdout)
    tmp = tempfile.mkdtemp(prefix='montaje_')
    nt = analizar(a.original, os.path.splitext(a.original)[0] + '.nitidez.npz')
    partes, voces = [], []
    carpeta_voz = os.path.join(os.path.dirname(os.path.abspath(a.guion)), 'voz')
    for b in d['bloques']:
        m, i = b['montaje'], b['id']
        lab = rotulo(f"{i}  {b.get('ancla', '')}")
        enc = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', crf]
        if m['modo'].startswith('lento'):
            f = os.path.join(tmp, f'{i}_a.mp4')
            run(['-ss', str(m['src_inicio']), '-t', str(m['src_fin'] - m['src_inicio']), '-i', a.original, '-an',
                 '-vf', f"setpts=PTS/{m.get('velocidad') or 1},{out}{lab}"] + enc + [f])
            if a.estabilizar:
                estabilizar(f, enc)
            partes.append(f)
        if m['modo'].endswith('congelar'):
            v = (m['src_inicio'] - 1, m['src_inicio'] + 3) if m['modo'] == 'congelar' else (m['src_fin'] - 3, m['src_fin'])
            t = m.get('cuadro', mejor(*nt, *v))
            f = os.path.join(tmp, f'{i}_b.mp4')
            nfr = int(round(m['congelar_s'] * 25))
            if m.get('quieto'):  # cuadro fijo con zoom lento (como antes)
                png = os.path.join(tmp, f'{i}.png')
                run(['-ss', str(t), '-i', a.original, '-frames:v', '1', png])
                z = f'1+0.10*on/{nfr}' if len(partes) % 2 == 0 else f'1.10-0.10*on/{nfr}'
                # zoompan mueve el recorte de a 1 píxel entero: sobre una imagen 4 veces más grande el zoom sale suave, sin temblar
                run(['-i', png, '-vf', f"scale={max(3840, res[0] * 4)}:-2,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nfr}:s={res[0]}x{res[1]}:fps=25,format=yuv420p{lab}",
                     '-frames:v', str(nfr)] + enc + [f])
            else:
                # la escena se repite en movimiento (ida y vuelta, un poco lenta) en vez de una foto quieta:
                # tras un tramo, arranca hacia atrás desde el último cuadro, así el empalme no salta
                tras_tramo = m['modo'] == 'lento+congelar'
                s1 = m['src_fin'] if tras_tramo else min(t + VENTANA / 2, dur_original)
                s0 = max(0.0, s1 - VENTANA)
                ida = os.path.join(tmp, f'{i}_ida.mp4')
                orden = '[rv][f]' if tras_tramo else '[f][rv]'
                run(['-ss', f'{s0:.2f}', '-t', f'{s1 - s0:.2f}', '-i', a.original, '-an', '-filter_complex',
                     f"[0]setpts=PTS/{LENTO_ESCENA},{out},split[f][r];[r]reverse[rv];{orden}concat=n=2:v=1:a=0[o]", '-map', '[o]'] + enc + [ida])
                if a.estabilizar:
                    estabilizar(ida, enc)
                # sin zoom encima: zoompan sobre video a su tamaño redondea el recorte a píxeles enteros y la imagen
                # tiembla (y ampliarla 4 veces cuadro a cuadro sería muy lento); el movimiento de la escena ya la mantiene viva
                run(['-stream_loop', '-1', '-i', ida, '-vf', f"fps=25,format=yuv420p{lab}",
                     '-frames:v', str(nfr)] + enc + [f])
            partes.append(f)
        if m['modo'] == 'imagen':
            img = m.get('imagen') or a.imagen
            f = os.path.join(tmp, f'{i}_b.mp4')
            run(['-loop', '1', '-t', str(m['congelar_s']), '-i', img, '-filter_complex',
                 f"[0]split[a][b];[a]scale={res[0]}:{res[1]},boxblur=20[bg];[b]scale=-1:{res[1] - 20}[fg];[bg][fg]overlay=(W-w)/2:10,fps=25,format=yuv420p{lab}"]
                + enc + [f])
            partes.append(f)
        mp3 = os.path.join(carpeta_voz, f'{i}.mp3')
        if not (b.get('texto') or '').strip():
            print(i, 'ok', flush=True)  # bloque sin voz a propósito
        elif b.get('inicio_min') is not None and voz_al_dia(carpeta_voz, i, b.get('texto', '')):
            print(i, 'ok', flush=True)
            voces.append((b['inicio_min'] + 0.3, mp3))  # el mismo desfase que «Poner la voz»
        else:  # en la vista en vivo este bloque va callado: se dice por qué, para no confundirlo con un fallo del audio
            print(i, 'ok · en la vista en vivo va sin voz: ' + (
                'todavía no tiene voz' if not os.path.exists(mp3) else
                'su voz es de otro texto (el guion que se monta no es el mismo con el que se hizo la voz)'
                if b.get('inicio_min') is not None else 'el guion no trae sus tiempos de voz (falta «Generar voz»)'), flush=True)
        avance(partes, tmp, os.path.join(os.path.dirname(os.path.abspath(a.salida)), EN_CURSO), voces)
    lista = os.path.join(tmp, 'lista.txt')
    with open(lista, 'w', encoding='utf-8') as fh:
        for p in partes:
            fh.write(f"file '{p}'\n")
    if len(codificar.USADOS) > 1:  # la tarjeta falló a mitad: tramos de dos codificadores, se igualan en vez de pegarlos tal cual
        run(['-f', 'concat', '-safe', '0', '-i', lista, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', crf, a.salida])
    else:
        run(['-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', a.salida])
    shutil.rmtree(tmp)
    try:
        os.remove(os.path.join(os.path.dirname(os.path.abspath(a.salida)), EN_CURSO))
    except OSError:
        pass


if __name__ == '__main__':
    main()
