"""«🔎 Revisar el video terminado»: antes de subirlo, la IA mira FINAL.mp4 como lo vería un espectador y avisa lo que se nota.

Hoy los controles revisan el guion; esto revisa el RESULTADO:
  1. En tu PC (gratis): silencios largos, tramos en negro, imagen congelada demasiado tiempo y saltos de volumen.
  2. Con la IA de «⚙ Ajustes IA» (con visión): hojas de cuadros del video (uno cada pocos segundos, con su minuto:segundo)
     y los subtítulos de cada momento. La IA busca lo que un espectador notaría: una etiqueta o un círculo que tapa el botón,
     una voz que habla de DFU mientras se ve la pantalla de inicio, un texto mal escrito en pantalla, una toma borrosa,
     datos privados a la vista (IMEI, correo, número), un paso que no se entiende.
Deja revision_final.json (y revision_final.md para leer) con cada aviso, su minuto y qué hacer. No cambia el video.

Uso: python revisar_final.py --proyecto . --ajustes app/ajustes.json [--video FINAL.mp4] [--sin-ia] [--cada 5]
"""
import argparse, json, os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'ia'))

SRTS = ['FINAL.srt', '9_modelos.srt', '8_testimonios.srt', '3_voz.srt']
VIDEOS = ['FINAL.mp4', '9_modelos.mp4', '8_testimonios.mp4', '7_tarjetas.mp4', '6_senales.mp4', '5_etiquetas.mp4', '4_musica.mp4', '3_voz.mp4']
POR_HOJA = 16
MAX_CUADROS = 128


def mmss(s):
    return f'{int(s // 60)}:{int(s % 60):02d}'


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True).stdout.strip() or 0)


def leer_srt(f):
    out = []
    try:
        txt = open(f, encoding='utf-8', errors='replace').read()
    except OSError:
        return out
    for bloque in re.split(r'\n\s*\n', txt):
        m = re.search(r'(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)\s*\n(.*)', bloque, re.S)
        if m:
            g = [int(x) for x in m.groups()[:8]]
            out.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000,
                        ' '.join(m.group(9).split())))
    return out


def detectar(video, filtro, clave_ini, clave_fin=None):
    """Corre un detector de ffmpeg (silencedetect, blackdetect, freezedetect) y devuelve [(inicio, fin)]."""
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', video] + filtro + ['-f', 'null', '-'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    ini = [float(x) for x in re.findall(clave_ini + r'\s*:?\s*([\d.]+)', r.stderr)]
    fin = [float(x) for x in re.findall((clave_fin or 'zzz') + r'\s*:?\s*([\d.]+)', r.stderr)] if clave_fin else []
    return list(zip(ini, fin + [None] * (len(ini) - len(fin))))


def controles_pc(video):
    avisos = []
    dur = duracion(video)
    for a, b in detectar(video, ['-vn', '-af', 'silencedetect=noise=-40dB:d=3'], 'silence_start', 'silence_end'):
        b = b if b is not None else dur
        if b - a >= 3 and a > 1 and b < dur - 1:
            avisos.append({'t': round(a, 1), 'tipo': 'silencio', 'gravedad': 'media' if b - a < 6 else 'alta',
                           'que': f'{b - a:.0f} s sin voz ni música', 'sugerencia': 'acorta ese tramo o agrega una frase'})
    for a, b in detectar(video, ['-an', '-vf', 'blackdetect=d=0.6:pix_th=0.08'], 'black_start', 'black_end'):
        if a > 0.5:
            avisos.append({'t': round(a, 1), 'tipo': 'negro', 'gravedad': 'alta',
                           'que': f'pantalla en negro {((b or a + 0.6) - a):.1f} s', 'sugerencia': 'quita el tramo en negro o tápalo con otra toma'})
    for a, b in detectar(video, ['-an', '-vf', 'fps=5,scale=320:-2,freezedetect=n=0.002:d=9'], 'freeze_start', 'freeze_end'):
        avisos.append({'t': round(a, 1), 'tipo': 'congelado', 'gravedad': 'media',
                       'que': f'la imagen no se mueve {((b or a + 9) - a):.0f} s', 'sugerencia': 'usa una pausa en movimiento o un inserto'})
    return avisos


def hojas(video, cada, carpeta, subs):
    import cv2
    import ia
    dur = duracion(video)
    paso = max(cada, dur / MAX_CUADROS)
    os.makedirs(carpeta, exist_ok=True)
    for f in os.listdir(carpeta):
        os.remove(os.path.join(carpeta, f))
    cap = cv2.VideoCapture(video)
    tiempos, archivos = [], []
    t = 1.0
    while t < dur - 0.5:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, c = cap.read()
        if ok:
            f = os.path.join(carpeta, f'c_{len(archivos):03d}.jpg')
            cv2.imwrite(f, cv2.resize(c, (480, int(480 * c.shape[0] / c.shape[1]))), [cv2.IMWRITE_JPEG_QUALITY, 82])
            tiempos.append(t); archivos.append(f)
        t += paso
    cap.release()
    lista = []
    for k in range(0, len(archivos), POR_HOJA):
        im = ia.rejilla(archivos[k:k + POR_HOJA], [mmss(x) for x in tiempos[k:k + POR_HOJA]], 4, 384)
        if im is None:
            continue
        f = os.path.join(carpeta, f'hoja_{k // POR_HOJA + 1:02d}.jpg')
        cv2.imwrite(f, im, [cv2.IMWRITE_JPEG_QUALITY, 80])
        lista.append((f'hoja {k // POR_HOJA + 1}: cuadros de {mmss(tiempos[k])} a {mmss(tiempos[min(k + POR_HOJA, len(tiempos)) - 1])}', f))
    for f in archivos:
        os.remove(f)
    return lista, paso


def encargo(d, subs, avisos_pc, paso, n_hojas):
    lineas = '\n'.join(f'[{mmss(a)}] {t}' for a, _, t in subs)[:30000]
    try:
        idea = open(os.path.join(d, 'idea.txt'), encoding='utf-8').read()[:1500]
    except OSError:
        idea = ''
    return f"""Eres el editor que revisa un video tutorial de YouTube TERMINADO antes de publicarlo. Tienes {n_hojas} hojas con un
cuadro cada {paso:.0f} segundos (cada uno con su minuto:segundo) y los subtítulos con lo que dice la voz en cada momento.
{('De qué trata el video (lo dice el autor): ' + idea) if idea else ''}

SUBTÍTULOS ([minuto:segundo] lo que dice la voz):
{lineas}

Lo que ya encontró la PC (no lo repitas): {json.dumps(avisos_pc, ensure_ascii=False)[:2000]}

Busca SOLO lo que un espectador notaría y que conviene arreglar antes de publicar:
- una etiqueta, flecha, círculo o tarjeta que tapa el botón, el texto o la parte del teléfono que se está explicando;
- la voz habla de algo (DFU, Recovery, un botón, un mensaje) mientras la imagen muestra otra cosa;
- un texto en pantalla (etiqueta, título) mal escrito o que no coincide con lo que se dice;
- una toma borrosa, muy oscura o temblorosa en un paso importante;
- datos privados a la vista: IMEI, número de serie, correo, teléfono, contraseña, dirección;
- un paso que se salta o no se entiende; un final que corta de golpe.
No inventes: si no estás seguro, no lo pongas. Máximo 15 avisos, del más grave al menos grave.
Responde SOLO con un objeto JSON {{"avisos": [{{"t": segundos, "tipo": "tapa"|"desfase"|"texto"|"imagen"|"privado"|"paso"|"otro",
"gravedad": "alta"|"media"|"baja", "que": "lo que se ve mal, corto", "sugerencia": "qué hacer, corto"}}], "resumen": "una frase"}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--video')
    ap.add_argument('--sin-ia', action='store_true')
    ap.add_argument('--cada', type=float, default=5.0, help='segundos entre cuadros que mira la IA')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    video = os.path.join(d, a.video) if a.video else next((os.path.join(d, v) for v in VIDEOS if os.path.exists(os.path.join(d, v))), None)
    if not video or not os.path.exists(video):
        raise SystemExit('ERROR: todavía no hay video armado para revisar. Pulsa «▶ Hacer todo».')
    srt = next((os.path.join(d, s) for s in ([os.path.splitext(os.path.basename(video))[0] + '.srt'] + SRTS)
                if os.path.exists(os.path.join(d, s))), None)
    subs = leer_srt(srt) if srt else []
    print(f'Reviso {os.path.basename(video)} ({duracion(video) / 60:.1f} min)…', flush=True)
    avisos = controles_pc(video)
    print(f'· en la PC: {len(avisos)} avisos (silencios, negro, imagen quieta)', flush=True)
    resumen, ia_usada = '', None
    aj = {}
    try:
        aj = json.load(open(a.ajustes, encoding='utf-8'))
    except (OSError, ValueError):
        pass
    if not a.sin_ia and aj.get('modelo') and aj.get('url'):
        import ia
        caps, paso = hojas(video, a.cada, os.path.join(d, 'ia_capturas', 'revision_final'), subs)
        print(f'· la IA mira {len(caps)} hojas de cuadros con los subtítulos…', flush=True)
        try:
            datos = ia.extraer_json(ia.llamar(aj, encargo(d, subs, avisos, paso, len(caps)), caps))
        except SystemExit as e:
            print(f'· la IA no pudo revisar ({e}); quedan los avisos de la PC', flush=True)
            datos = None
        if isinstance(datos, dict):
            for x in datos.get('avisos') or []:
                try:
                    avisos.append({'t': round(float(x.get('t', 0)), 1), 'tipo': str(x.get('tipo') or 'otro')[:20],
                                   'gravedad': x.get('gravedad') if x.get('gravedad') in ('alta', 'media', 'baja') else 'media',
                                   'que': str(x.get('que') or '')[:300], 'sugerencia': str(x.get('sugerencia') or '')[:300], 'de': 'IA'})
                except (TypeError, ValueError, AttributeError):
                    continue
            resumen = str(datos.get('resumen') or '')[:400]
            ia_usada = aj.get('modelo')
    elif not a.sin_ia:
        print('· sin IA elegida en «⚙ Ajustes IA»: solo los controles de la PC', flush=True)
    orden = {'alta': 0, 'media': 1, 'baja': 2}
    avisos.sort(key=lambda x: (orden.get(x['gravedad'], 1), x['t']))
    salida = {'video': os.path.basename(video), 'ia': ia_usada, 'resumen': resumen, 'avisos': avisos}
    json.dump(salida, open(os.path.join(d, 'revision_final.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    md = [f"# Revisión de {salida['video']}", '', resumen, '']
    md += [f"- **{mmss(x['t'])}** · {x['gravedad']} · {x['que']} → {x['sugerencia']}" for x in avisos] or ['Sin avisos: listo para subir.']
    open(os.path.join(d, 'revision_final.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    for x in avisos:
        print(f"· {mmss(x['t'])} [{x['gravedad']}] {x['que']} → {x['sugerencia']}", flush=True)
    print(f'Listo: {len(avisos)} avisos en revision_final.md', flush=True)


if __name__ == '__main__':
    main()
