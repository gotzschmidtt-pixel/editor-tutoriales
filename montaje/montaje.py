"""Arma el video según el plan de montaje del guion: cámara lenta, congelados e imágenes.

Uso: python3 montaje.py --original original.mp4 --guion guion.json --salida montaje.mp4 [--imagen mapa.png] [--calidad 1080|720|480|360]

Cada bloque del guion trae "montaje": {"modo": "lento" | "congelar" | "lento+congelar" | "imagen",
  "src_inicio": s, "src_fin": s, "velocidad": 0.8, "congelar_s": s, "imagen": "archivo.png" (opcional)}.
Las pausas («congelar») ya no son una foto: repiten la escena en movimiento (ida y vuelta, algo lenta) con zoom suave,
alrededor del cuadro más nítido del momento pedido. Con "quieto": true en el montaje del bloque, vuelve a ser un cuadro fijo.
Si en ese tramo se ve una cara, se repite solo hacia adelante con un fundido (en reversa se nota que retrocede);
"repetir": "adelante" o "ida_vuelta" en el montaje del bloque lo fuerza.
--calidad menor a 1080: prueba rápida con el nombre del bloque escrito (--borrador = 720).
--estabilizar: quita el temblor de la cámara en mano de cada tramo (vid.stab si ffmpeg lo trae; si no, deshake).
"""
import argparse, glob, hashlib, json, os, shutil, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador
from nitidez import analizar, mejor  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'mejorar'))
import mejorar  # noqa: E402  «✨ Mejorar imagen» (Real-ESRGAN) en las pausas quietas, si lo pediste
from texto_voz import texto_voz  # noqa: E402  lo que de verdad se mandó a ElevenLabs


VENTANA = 2.4       # segundos de escena que se repiten (ida y vuelta) en vez de congelar un cuadro
LENTO_ESCENA = 0.7  # la repetición va un poco más lenta para que se note menos
FUNDIDO = 0.4       # con una cara en la escena: se repite solo hacia adelante, con este fundido en cada vuelta

# Detector de caras YuNet (OpenCV), ~230 KB: se baja una sola vez a descargas_app/modelos. Una cara en reversa se nota
# (parece que el video retrocede); en pantallas y manos el ida y vuelta no se nota y sigue igual.
MODELO_CARA = os.path.join(RAIZ, 'descargas_app', 'modelos', 'face_detection_yunet_2023mar.onnx')
URL_MODELO_CARA = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
_DETECTOR = []


def detector_caras():
    if not _DETECTOR:
        _DETECTOR.append(None)
        try:
            import cv2
            if not os.path.exists(MODELO_CARA):
                import urllib.request
                os.makedirs(os.path.dirname(MODELO_CARA), exist_ok=True)
                datos = urllib.request.urlopen(URL_MODELO_CARA, timeout=60).read()
                open(MODELO_CARA + '.tmp', 'wb').write(datos)
                os.replace(MODELO_CARA + '.tmp', MODELO_CARA)
            _DETECTOR[0] = cv2.FaceDetectorYN.create(MODELO_CARA, '', (320, 320), 0.8)
        except Exception as e:  # sin detector, las pausas quedan como siempre (ida y vuelta)
            print(f'(sin detector de caras: {e}; las pausas van de ida y vuelta)', flush=True)
    return _DETECTOR[0]


def cara_en(cap, t):
    """¿Hay una cara (de al menos ~3 % del ancho) en el cuadro del segundo t?"""
    import cv2
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, cuadro = cap.read()
    if not ok:
        return False
    h, w = cuadro.shape[:2]
    cuadro = cv2.resize(cuadro, (640, max(1, round(h * 640 / w))))
    det = detector_caras()
    det.setInputSize((cuadro.shape[1], cuadro.shape[0]))
    _, caras = det.detect(cuadro)
    return caras is not None and any(c[2] >= 640 * 0.03 for c in caras)


def tramo_con_cara(video, s0, s1):
    """Si se ve una cara en algún punto de [s0, s1] (comienzo, medio o final): (hay cara al final, comienzo del pedazo
    final que sigue igual, con o sin cara), para repetir solo ese pedazo y no mezclar la cara con la escena de al lado.
    Si no se ve ninguna cara, None (la pausa queda como siempre)."""
    if detector_caras() is None:
        return None
    import cv2
    cap = cv2.VideoCapture(video)
    try:
        if not any(cara_en(cap, t) for t in (s0 + 0.1, (s0 + s1) / 2, max(s0, s1 - 0.1))):
            return None
        t = max(s0, s1 - 0.1)
        al_final = cara_en(cap, t)
        inicio = s1
        while t >= s0 and cara_en(cap, t) == al_final:
            inicio, t = t, t - 0.2
        return al_final, max(s0, min(inicio, s1 - 0.6))  # al menos 0,6 s de escena para que la repetición no sea un tic
    finally:
        cap.release()


EN_CURSO = 'montaje_en_curso.mp4'  # lo que va del montaje, para verlo en la app mientras se arma
PARTES = '.montaje_partes'  # tramos ya hechos: si el montaje se corta, o cambias un solo bloque, no se rehacen los demás


def huella_archivo(f):
    try:
        st = os.stat(f)
        return [os.path.abspath(f), st.st_size, int(st.st_mtime)]
    except (OSError, TypeError):
        return None


def voz_al_dia(carpeta_voz, bid, texto):
    """¿El mp3 de este bloque dice el texto actual del guion? Si no, no se mete en el preview,
    para que el «montaje mientras se arma» nunca suene con la voz de un guion anterior."""
    try:
        al = json.load(open(os.path.join(carpeta_voz, f'{bid}.align.json'), encoding='utf-8'))
        dicho = ''.join(al['characters']).strip()
        return dicho in ((texto or '').strip(), texto_voz(texto))
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


def cuadros_por_segundo(f):
    """Los cuadros por segundo del video armado, según la grabación: 30 para teléfonos (30 o 60), 24 para cine, 25 si no.
    Con 60 → 25 se pierden cuadros de forma despareja y el pulso de la mano se ve a saltos (el temblor se duplica);
    60 → 30 toma uno de cada dos, parejo."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=avg_frame_rate',
                            '-of', 'csv=p=0', f], capture_output=True, text=True, check=True).stdout.strip()
        n, d = r.split('/') if '/' in r else (r, 1)
        x = float(n) / float(d)
    except (OSError, ValueError, ZeroDivisionError, subprocess.CalledProcessError):
        return 25
    for base in (30, 24, 25):
        if any(abs(x - base * k) < 0.6 for k in (1, 2, 4)):
            return base
    return 25


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
            # la transformación la hace el ffmpeg que trae vid.stab (el de NVIDIA no lee los .trf: «Cannot parse localmotion»,
            # y su fallo pasaba todo el resto del montaje al procesador); después se codifica como los demás tramos
            mid = f + '.est0.mkv'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', os.path.basename(f), '-vf',
                            f'vidstabtransform=input={os.path.basename(trf)}:smoothing=20:zoom=4:interpol=linear,format=yuv420p',
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '8', os.path.basename(mid)],
                           check=True, cwd=cwd, capture_output=True)  # sus avisos no se mezclan con «Lxx ok»
            codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', os.path.basename(mid)] + enc + [os.path.basename(tmp)],
                          check=True, cwd=cwd, capture_output=True)
            os.remove(mid)
        else:
            run(['-i', f, '-vf', 'deshake,format=yuv420p'] + enc + [tmp])
        os.replace(tmp, f)
    except (OSError, subprocess.CalledProcessError) as e:
        detalle = (getattr(e, 'stderr', b'') or b'').decode('utf-8', 'replace').strip().splitlines()[-1:]
        print(f'· no pude estabilizar {os.path.basename(f)} ({e}{": " + detalle[0] if detalle else ""}); queda como estaba', flush=True)


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
    FPS = cuadros_por_segundo(a.original)
    # framerate (no fps): en un tramo acelerado o lento, fps se salta cuadros de forma despareja (2, 2, 3, 2…) y el
    # movimiento tiembla; framerate arma cada cuadro en su momento exacto
    out = f"scale={res[0]}:{res[1]}:force_original_aspect_ratio=decrease,pad={res[0]}:{res[1]}:(ow-iw)/2:(oh-ih)/2,framerate=fps={FPS},format=yuv420p"
    fuente = next((f for f in ('C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf') if os.path.exists(f)), None)

    def rotulo(txt):
        if final or not fuente:
            return ''
        txt = txt.replace('\\', '').replace(':', '\\:').replace("'", '')  # «batería al 100%» rompía drawtext: va con expansion=none
        return f",drawtext=fontfile='{fuente.replace(':', chr(92) + ':')}':expansion=none:text='{txt}':x=24:y=h-52:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10"

    dur_original = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.original],
                                        capture_output=True, text=True, check=True).stdout)
    tmp = codificar.temporal('montaje')
    nt = analizar(a.original, os.path.splitext(a.original)[0] + '.nitidez.npz')
    partes, voces = [], []
    carpeta_voz = os.path.join(os.path.dirname(os.path.abspath(a.guion)), 'voz')
    cache = os.path.join(os.path.dirname(os.path.abspath(a.salida)), PARTES)
    os.makedirs(cache, exist_ok=True)
    usadas = set()
    proyecto = os.path.dirname(os.path.abspath(a.salida))
    base_huella = [2, alto, crf, FPS, a.estabilizar, huella_archivo(a.original), huella_archivo(a.imagen)]
    for b in d['bloques']:
        m, i = b['montaje'], b['id']
        lab = rotulo(f"{i}  {b.get('ancla', '')}")
        enc = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', crf]
        cara, ventana, tocada = False, None, False
        if m['modo'].endswith('congelar') and not m.get('quieto') and round((m.get('congelar_s') or 0) * FPS) >= 1:
            # el tramo que se repite en la pausa; con una cara, va solo hacia adelante («repetir»: «adelante» o
            # «ida_vuelta» en el montaje del bloque lo fuerza)
            v = (m['src_inicio'] - 1, m['src_inicio'] + 3) if m['modo'] == 'congelar' else (m['src_fin'] - 3, m['src_fin'])
            t = m.get('cuadro', mejor(*nt, *v))
            s1 = m['src_fin'] if m['modo'] == 'lento+congelar' else min(t + VENTANA / 2, dur_original)
            ventana = (max(0.0, s1 - VENTANA), s1)
            if m.get('repetir') == 'adelante':
                cara = True
            elif m.get('repetir') != 'ida_vuelta':
                r = tramo_con_cara(a.original, *ventana)
                if r is not None:
                    cara, ventana, tocada = r[0], (r[1], s1), True
        cambio = cara or tocada  # solo cambia la clave de las pausas tocadas: las demás no se rehacen
        nitido = bool(m.get('quieto') and mejorar.quieres(proyecto))  # «✨ Mejorar imagen»: solo cambia la clave de las pausas quietas
        clave = hashlib.sha1(json.dumps(base_huella + [m, lab, huella_archivo(m.get('imagen'))] + ([cara, ventana] if cambio else []) + (['esrgan'] if nitido else []),
                                        sort_keys=True, default=str).encode()).hexdigest()[:12]
        hecho = os.path.join(cache, f'{i}_{clave}.json')
        try:
            info = json.load(open(hecho, encoding='utf-8'))
            guardadas = [os.path.join(cache, x) for x in info['partes']]
            if all(os.path.getsize(x) > 0 for x in guardadas):
                partes += guardadas
                codificar.USADOS.update(info.get('codificadores', []))
                usadas.update([os.path.basename(hecho)] + info['partes'])
                print(i, 'ok (ya estaba hecho, no se rehace)', flush=True)
                avance(partes, tmp, os.path.join(os.path.dirname(os.path.abspath(a.salida)), EN_CURSO), voces)
                continue
        except (OSError, ValueError, KeyError, TypeError):
            pass
        antes, cod_antes = len(partes), set(codificar.USADOS)
        codificar.USADOS.clear()
        if m['modo'].startswith('lento'):
            f = os.path.join(tmp, f'{i}_a.mp4')
            run(['-ss', str(m['src_inicio']), '-t', str(m['src_fin'] - m['src_inicio']), '-i', a.original, '-an',
                 '-vf', f"setpts=PTS/{m.get('velocidad') or 1},{out}{lab}"] + enc + [f])
            if a.estabilizar:
                estabilizar(f, enc)
            partes.append(f)
        if m['modo'].endswith('congelar') and round((m.get('congelar_s') or 0) * FPS) >= 1:
            # una pausa de menos de un cuadro daba un tramo vacío que, al unir, desarmaba los tiempos de todo lo siguiente
            v = (m['src_inicio'] - 1, m['src_inicio'] + 3) if m['modo'] == 'congelar' else (m['src_fin'] - 3, m['src_fin'])
            t = m.get('cuadro', mejor(*nt, *v))
            f = os.path.join(tmp, f'{i}_b.mp4')
            nfr = int(round(m['congelar_s'] * FPS))
            if m.get('quieto'):  # cuadro fijo con zoom lento (como antes)
                png = os.path.join(tmp, f'{i}.png')
                run(['-ss', str(t), '-i', a.original, '-frames:v', '1', png])
                if nitido:
                    mejorar.si_quieres(png, proyecto)
                z = f'1+0.10*on/{nfr}' if len(partes) % 2 == 0 else f'1.10-0.10*on/{nfr}'
                # zoompan mueve el recorte de a 1 píxel entero: sobre una imagen 4 veces más grande el zoom sale suave, sin temblar
                run(['-i', png, '-vf', f"scale={max(3840, res[0] * 4)}:-2,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nfr}:s={res[0]}x{res[1]}:fps={FPS},format=yuv420p{lab}",
                     '-frames:v', str(nfr)] + enc + [f])
            else:
                # la escena se repite en movimiento (ida y vuelta, un poco lenta) en vez de una foto quieta:
                # tras un tramo, arranca hacia atrás desde el último cuadro, así el empalme no salta
                tras_tramo = m['modo'] == 'lento+congelar'
                s0, s1 = ventana
                ida = os.path.join(tmp, f'{i}_ida.mp4')
                if cara:
                    # con una cara, en reversa se nota que el video retrocede: se repite solo hacia adelante, y el final
                    # de cada vuelta se funde con su comienzo para que la repetición no salte
                    L = (s1 - s0) / LENTO_ESCENA
                    D = min(FUNDIDO, L / 3)
                    print(i, '· pausa con cara: se repite hacia adelante (sin retroceder)', flush=True)
                    filtro = (f"[0]setpts=PTS/{LENTO_ESCENA},{out},split[a][b];[a]trim=start={D:.3f},setpts=PTS-STARTPTS[m];"
                              f"[b]trim=end={D:.3f},setpts=PTS-STARTPTS[h];[m][h]xfade=transition=fade:duration={D:.3f}:offset={L - 2 * D:.3f}[o]")
                else:
                    orden = '[rv][f]' if tras_tramo else '[f][rv]'
                    filtro = f"[0]setpts=PTS/{LENTO_ESCENA},{out},split[f][r];[r]reverse[rv];{orden}concat=n=2:v=1:a=0[o]"
                run(['-ss', f'{s0:.2f}', '-t', f'{s1 - s0:.2f}', '-i', a.original, '-an', '-filter_complex', filtro, '-map', '[o]'] + enc + [ida])
                if a.estabilizar:
                    estabilizar(ida, enc)
                # sin zoom encima: zoompan sobre video a su tamaño redondea el recorte a píxeles enteros y la imagen
                # tiembla (y ampliarla 4 veces cuadro a cuadro sería muy lento); el movimiento de la escena ya la mantiene viva
                run(['-stream_loop', '-1', '-i', ida, '-vf', f"fps={FPS},format=yuv420p{lab}",
                     '-frames:v', str(nfr)] + enc + [f])
            partes.append(f)
        if m['modo'] == 'imagen':
            img = m.get('imagen') or a.imagen
            f = os.path.join(tmp, f'{i}_b.mp4')
            run(['-loop', '1', '-t', str(m['congelar_s']), '-i', img, '-filter_complex',
                 f"[0]split[a][b];[a]scale={res[0]}:{res[1]},boxblur=20[bg];[b]scale=-1:{res[1] - 20}[fg];[bg][fg]overlay=(W-w)/2:10,fps={FPS},format=yuv420p{lab}"]
                + enc + [f])
            partes.append(f)
        # los tramos de este bloque pasan a la carpeta de tramos hechos; el .json se escribe al final, así un corte a
        # mitad de bloque nunca deja un tramo a medias marcado como hecho
        nombres = []
        for k in range(antes, len(partes)):
            nombre = f'{i}_{clave}_{k - antes}.mp4'
            os.replace(partes[k], os.path.join(cache, nombre))
            partes[k] = os.path.join(cache, nombre)
            nombres.append(nombre)
        json.dump({'partes': nombres, 'codificadores': sorted(codificar.USADOS)}, open(hecho, 'w', encoding='utf-8'))
        usadas.update([os.path.basename(hecho)] + nombres)
        codificar.USADOS.update(cod_antes)
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
    for viejo in glob.glob(os.path.join(cache, '*')):  # se guardan solo los tramos de este guion, para la próxima vez
        if os.path.basename(viejo) not in usadas:
            try:
                os.remove(viejo)
            except OSError:
                pass
    try:
        os.remove(os.path.join(os.path.dirname(os.path.abspath(a.salida)), EN_CURSO))
    except OSError:
        pass


if __name__ == '__main__':
    main()
