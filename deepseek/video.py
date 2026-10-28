"""De tu video a FINAL.mp4 con una IA de chat que corre comandos (DeepSeek, Claude, etc.), usando esta misma app.

La IA no edita video: escribe el guion, las etiquetas y el tráiler en JSON. Todo lo demás (transcripción, capturas, mapa
del video, voz de ElevenLabs, montaje con repetición en vez de foto fija, música, etiquetas, tráiler) lo hace la app, con
sus mismos pasos y parámetros. Este script habla con la app (http://localhost:8765) y la abre si no está abierta.

Uso (desde la carpeta editor-tutoriales):
  python deepseek/video.py preparar "C:\\ruta\\video.mp4" --nombre "Mi video" [--idea "datos seguros del video"]
      crea el proyecto, sube el video, transcribe (Scribe si la app tiene la clave de ElevenLabs; si no, Whisper) y deja el encargo:
      ia_prompt_guion.txt, ia_capturas/ (capturas, mapa y hojas), hojas_2s/ (un cuadro cada 2 s, 30 por hoja) y acciones/
      (cuadros grandes cada 0,5 s donde el autor dice que hace algo)
  python deepseek/video.py entregar guion respuesta.json --nombre "Mi video"
      la app corrige el guion (tiempos, largo, orden) y lo guarda en guion.json; muestra el resumen y los avisos
  python deepseek/video.py preguntas [trailer] --nombre "Mi video"
      tus preguntas del guion (o del tráiler) con lo que el autor contestó en la app
  python deepseek/video.py armar --nombre "Mi video" --confirmo-creditos
      voz (ElevenLabs, GASTA créditos), montaje, subtítulos y música → FINAL.mp4 sin extras
  python deepseek/video.py encargo etiquetas|trailer --nombre "Mi video"
      deja ia_prompt_<tarea>.txt para escribir las etiquetas o el tráiler (después: entregar etiquetas|trailer archivo.json)
  python deepseek/video.py extras etiquetas trailer --nombre "Mi video" [--confirmo-creditos]
      pone los extras sobre el video (el tráiler y nuevos_modelos gastan ElevenLabs). El tráiler va aparte y al final:
      primero el video aprobado; después encargo trailer → entregar trailer → el autor lo revisa en «🎬 Tráiler»
  python deepseek/video.py exportar 480 720 --nombre "Mi video"
  python deepseek/video.py estado --nombre "Mi video"
  python deepseek/video.py clave
      comprueba la clave de ElevenLabs guardada en la app y dice cuántos créditos quedan (no gasta créditos)

No usa claves: la app las lee de app/ajustes.json, que este script nunca abre ni muestra.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = f"http://localhost:{os.environ.get('PUERTO', 8765)}"
PROYECTOS = os.path.join(RAIZ, 'mis_proyectos')
GASTAN = {'trailer', 'nuevos_modelos'}  # extras que generan voz con ElevenLabs


def api(ruta, datos=None, cuerpo=None, largo=None, **q):
    url = URL + ruta + ('?' + urllib.parse.urlencode(q) if q else '')
    if datos is not None:
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=cuerpo, method='POST' if cuerpo is not None else 'GET')
    if largo is not None:
        req.add_header('Content-Length', str(largo))
    try:
        r = json.load(urllib.request.urlopen(req, timeout=3600))
    except urllib.error.HTTPError as e:
        try:
            r = json.load(e)
        except ValueError:
            r = {'error': f'HTTP {e.code}'}
    if isinstance(r, dict) and r.get('error'):
        raise SystemExit('ERROR de la app: ' + r['error'])
    return r


def abrir_app():
    try:
        api('/api/latido')
        return
    except (urllib.error.URLError, OSError):
        pass
    print('Abro la app en segundo plano…', flush=True)
    sin_ventana = {'creationflags': 0x08000000} if os.name == 'nt' else {}
    subprocess.Popen([sys.executable, os.path.join(RAIZ, 'app', 'app.py')], cwd=RAIZ,
                     env=dict(os.environ, SIN_NAVEGADOR='1', PYTHONUTF8='1'), **sin_ventana)
    for _ in range(60):
        time.sleep(1)
        try:
            api('/api/latido')
            return
        except (urllib.error.URLError, OSError):
            pass
    raise SystemExit('La app no abrió. Ábrela con iniciar.bat y vuelve a correr este comando.')


def correr(p, paso, datos=None):
    """Lanza un paso de la app y espera a que termine, mostrando su avance."""
    api('/api/ejecutar', datos or {}, p=p, paso=paso)
    visto = ''
    while True:
        time.sleep(3)
        e = api('/api/estado', p=p)
        t = e.get('trabajo') or {}
        linea = t.get('linea') or ''
        if t.get('proyecto') == p:
            if linea and linea != visto:
                print(f"[{t.get('paso')} · {t.get('total_s', 0)} s] {linea}", flush=True)
                visto = linea
            continue
        if e.get('fallo'):
            f = e['fallo']
            raise SystemExit(f"FALLÓ el paso «{f.get('paso')}»: {f.get('msg')}\n"
                             "Mira el registro.txt y la carpeta diagnosticos del proyecto. No lo reintentes a ciegas.")
        return e


def carpeta(nombre):
    return os.path.join(PROYECTOS, nombre)


def leer(d, f):
    try:
        return open(os.path.join(d, f), encoding='utf-8').read()
    except OSError:
        return ''


def hojas_2s(d):
    """El método con que Claude escribió los guiones a mano: un cuadro cada 2 s de TODO el video, 320 px, con el segundo
    escrito, en hojas de 6 × 5 (un minuto por hoja)."""
    out = os.path.join(d, 'hojas_2s')
    os.makedirs(out, exist_ok=True)
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                        os.path.join(d, 'original.mp4')], capture_output=True, text=True)
    dur = float(r.stdout.strip() or 0)
    hechas = 0
    for k, ini in enumerate(range(0, int(dur) + 1, 60), 1):
        f = os.path.join(out, f'hoja_{k:02d}_{ini // 60:02d}min.jpg')
        hechas += 1
        if os.path.exists(f):
            continue
        texto = "%{eif\\:t+" + str(ini) + "\\:d}s"
        base = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(ini), '-t', '60', '-i', os.path.join(d, 'original.mp4')]
        r = subprocess.run(base + ['-vf', f"fps=1/2,scale=320:-1,drawtext=text='{texto}':x=5:y=5:fontsize=22:fontcolor=yellow:"
                                          "box=1:boxcolor=black,tile=6x5", '-frames:v', '1', f], capture_output=True)
        if r.returncode:  # un ffmpeg sin fuentes para escribir el segundo: la hoja sale igual (cuadro k = segundo ini + 2k)
            subprocess.run(base + ['-vf', 'fps=1/2,scale=320:-1,tile=6x5', '-frames:v', '1', f], check=True)
    return out, hechas


# palabras con las que el autor narra una ACCIÓN (sin tildes): ahí se mira con detalle, porque es justo lo que el mapa
# (que marca cuándo cambia la pantalla, o sea el resultado) y las miniaturas de 320 px no muestran bien
ACCION = re.compile(r'^(presion|aprie|puls|power|volum|vol$|clic|click|dale|damos|toca|toque|exit$|recov|dfu|conect|descon|'
                    r'solt|suelt|manten|boton|bypas|start|reini|enviam|peg|escri|ingres|selec|elij|elegi|abri|abre|cerr|'
                    r'instal|flash|cable|parpad)')


def hojas_acciones(d, antes=2.0, despues=4.0, paso=0.5, ancho=480, maximo=80):
    """Donde el autor dice que hace algo («presiono», «power», «le damos clic», «exit», «DFU»): un cuadro cada medio
    segundo, a 480 px, de 2 s antes a 4 s después, en una hoja de 4 × 3 con el segundo escrito. Así la IA ve la acción
    con detalle. Gratis: sale de la transcripción y de ffmpeg. Deja acciones/acciones.txt con qué dice en cada hoja."""
    try:
        palabras = json.load(open(os.path.join(d, 'transcripcion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return None, 0
    def normal(x):
        return ''.join(c for c in unicodedata.normalize('NFD', str(x).lower()) if unicodedata.category(c) != 'Mn')
    momentos = []
    for w in palabras:
        if ACCION.match(re.sub(r'[^a-z0-9]', '', normal(w.get('texto', '')))):
            t = float(w['inicio'])
            if momentos and t - momentos[-1][1] <= despues:  # varias palabras de la misma acción: una sola hoja más larga
                momentos[-1][1] = t
            else:
                momentos.append([t, t])
    out = os.path.join(d, 'acciones')
    os.makedirs(out, exist_ok=True)
    indice = []
    for k, (t0, t1) in enumerate(momentos[:maximo], 1):
        ini = max(0.0, t0 - antes)
        largo = min(t1 + despues, ini + 12 * paso * 2) - ini  # hasta 2 hojas de 12 cuadros por acción
        dicho = ' '.join(w['texto'] for w in palabras if t0 - 3 <= float(w['inicio']) <= t1 + 3)
        for h in range(int(largo // (12 * paso)) + (1 if largo % (12 * paso) else 0)):
            a = ini + h * 12 * paso
            nombre = f'accion_{k:02d}_{int(a) // 60}m{int(a) % 60:02d}s{"" if h == 0 else "_b"}.jpg'
            f = os.path.join(out, nombre)
            if not os.path.exists(f):
                texto = "%{eif\\:t+" + f'{a:.1f}' + "\\:d}s"  # el segundo entero de la grabación
                base = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{a:.2f}', '-t', f'{12 * paso:.2f}', '-i',
                        os.path.join(d, 'original.mp4')]
                r = subprocess.run(base + ['-vf', f"fps={1 / paso},scale={ancho}:-1,drawtext=text='{texto}':x=6:y=6:fontsize=26:"
                                                  "fontcolor=yellow:box=1:boxcolor=black,tile=4x3", '-frames:v', '1', f], capture_output=True)
                if r.returncode:
                    subprocess.run(base + ['-vf', f'fps={1 / paso},scale={ancho}:-1,tile=4x3', '-frames:v', '1', f], capture_output=True)
            if os.path.exists(f):
                indice.append(f'{int(a) // 60}:{int(a) % 60:02d}–{int(a + 12 * paso) // 60}:{int(a + 12 * paso) % 60:02d}  {nombre}  «{dicho}»')
    open(os.path.join(out, 'acciones.txt'), 'w', encoding='utf-8').write(
        'Hojas de acciones: 12 cuadros cada medio segundo (de izquierda a derecha y de arriba abajo), donde el autor dice\n'
        'que hace algo. Busca aquí el segundo exacto de la ACCIÓN (no del resultado en pantalla).\n\n' + '\n'.join(indice) + '\n')
    return out, len(indice)


def resumen_guion(d):
    g = json.loads(leer(d, 'guion.json') or '{}')
    b = g.get('bloques') if isinstance(g, dict) else g
    if not b:
        return 'guion.json vacío'
    palabras = sum(len(str(x.get('texto', '')).split()) for x in b)
    dur = g.get('duracion_s') if isinstance(g, dict) else None
    humor = sum(1 for x in b if x.get('humor') is True)
    modos = {}
    for x in b:
        m = (x.get('montaje') or {}).get('modo', '?')
        modos[m] = modos.get(m, 0) + 1
    fijas = sum(1 for x in b if (x.get('montaje') or {}).get('quieto'))
    out = [f'{len(b)} bloques · {palabras} palabras · humor en {humor} bloques · montaje {modos}']
    if dur:
        out.append(f'duración estimada {int(dur) // 60}:{int(dur) % 60:02d} · {palabras / dur:.2f} palabras por segundo')
    if fijas:
        out.append(f'OJO: {fijas} bloques con "quieto": true (foto fija); quítalo salvo que el autor lo pidió')
    final, gf = os.path.join(d, 'FINAL.mp4'), os.path.join(d, 'guion.json')
    if os.path.exists(final) and os.path.getmtime(gf) > os.path.getmtime(final):
        out.append('OJO: el guion cambió después del último FINAL.mp4; vuelve a armar (la voz se rehace solo en los '
                   'bloques cuyo texto cambió)')
    return '\n'.join(out)


def huella(d):
    """Hash de los bloques del guion.json actual (ids y textos): la voz y el montaje cambian tiempos, no textos, así que
    solo cambia si alguien editó lo que dice la voz o quitó o agregó bloques."""
    try:
        g = json.loads(leer(d, 'guion.json') or 'null')
    except ValueError:
        return None
    b = g.get('bloques') if isinstance(g, dict) else g
    if not b:
        return None
    return hashlib.sha256(json.dumps([[x.get('id'), x.get('texto')] for x in b], ensure_ascii=False).encode()).hexdigest()


MARCA = '.deepseek_entrega.json'  # los textos del guion (y el tráiler) tal como quedaron en la última entrega de la IA


def huella_trailer(d):
    """Hash del trailer.json actual sin las notas: cambia si el autor movió, quitó o agregó tomas o cambió textos."""
    try:
        t = json.loads(leer(d, 'trailer.json') or 'null')
    except ValueError:
        return None
    if not isinstance(t, dict):
        return None
    clips = [[c.get('fase'), c.get('ventana'), c.get('dur')] for c in t.get('clips') or [] if isinstance(c, dict)]
    return hashlib.sha256(json.dumps([t.get('titulo'), t.get('subtitulo'), t.get('voz'), clips], ensure_ascii=False).encode()).hexdigest()


def marcar(d, **k):
    try:
        m = json.loads(leer(d, MARCA) or '{}')
    except ValueError:
        m = {}
    m.update(k)
    open(os.path.join(d, MARCA), 'w', encoding='utf-8').write(json.dumps(m))


def trailer_del_autor(d):
    """True si el autor cambió el tráiler en la app después de la última entrega de la IA."""
    try:
        marca = json.loads(leer(d, MARCA) or '{}').get('trailer')
    except ValueError:
        marca = None
    return bool(marca) and marca != huella_trailer(d)


def cambio_del_autor(d, archivo=None):
    """True si los textos del guion.json cambiaron desde la última entrega de la IA (el autor lo editó en la app).
    Sin marca (entregas de antes de este cambio): si guion.json es más nuevo que el archivo que se quiere entregar."""
    try:
        marca = json.loads(leer(d, MARCA) or '{}').get('guion')
    except ValueError:
        marca = None
    if marca:
        return marca != huella(d)
    g = os.path.join(d, 'guion.json')
    return bool(archivo and os.path.exists(g) and os.path.getmtime(g) > os.path.getmtime(archivo) + 2)


def texto_preguntas(d, tarea='guion'):
    """Las preguntas del guion (preguntas_guion.json) o del tráiler (preguntas_trailer.json) con lo que contestó el autor."""
    try:
        lista = json.loads(leer(d, f'preguntas_{tarea}.json') or '[]')
    except ValueError:
        lista = []
    if not lista:
        return ('Sin preguntas guardadas (ponlas en "preguntas" de tu respuesta: hasta 10, de datos e ideas).' if tarea == 'trailer' else
                'Sin preguntas guardadas (ponlas en "preguntas" de respuesta_guion.json: hasta 15 de datos y hasta 10 ideas para mejorar).')
    out = [f'Preguntas al autor sobre el {"tráiler" if tarea == "trailer" else "guion"} ({len(lista)}):']
    for k, x in enumerate(lista, 1):
        r = str(x.get('respuesta') or '').strip()
        out.append(f"{k}. [{x.get('tipo')} · {x.get('bloque') or '-'}] {x.get('pregunta')}"
                   + (f'\n   RESPUESTA: {r}' if r else '\n   (sin responder)'))
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('accion', choices=['preparar', 'entregar', 'preguntas', 'armar', 'encargo', 'extras', 'exportar', 'estado', 'clave'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--nombre', help='nombre del proyecto (carpeta en mis_proyectos); no hace falta para «clave»')
    ap.add_argument('--idea', help='datos seguros del video para la IA (se guardan en idea.txt)')
    ap.add_argument('--parti-del-guion-actual', action='store_true',
                    help='entregar guion: tu archivo ya incluye lo que el autor editó en la app (guion_editado_por_autor.json)')
    ap.add_argument('--confirmo-creditos', action='store_true', help='el autor aprobó gastar créditos de ElevenLabs')
    a = ap.parse_args()
    if a.accion != 'clave' and not a.nombre:
        ap.error('falta --nombre "NOMBRE DEL PROYECTO"')
    abrir_app()
    if a.accion == 'clave':  # ¿sirve la clave de ElevenLabs guardada en la app y cuántos créditos quedan? No gasta créditos
        try:
            r = api('/api/probar_eleven', {})
        except SystemExit:
            raise SystemExit('La app abierta es una versión vieja sin «Comprobar clave»: ciérrala y vuelve a correr este comando.')
        print(('OK: ' if r.get('ok') else 'ERROR: ') + r.get('mensaje', ''))
        if r.get('quedan') is not None:
            print(f'CREDITOS_ELEVENLABS={r["quedan"]}')
        return
    p = api('/api/proyecto', {'nombre': a.nombre})['nombre']
    d = carpeta(p)

    if a.accion == 'preparar':
        if not a.args or not os.path.isfile(a.args[0]):
            raise SystemExit('Falta la ruta del video: preparar "C:\\ruta\\video.mp4" --nombre "..."')
        video = a.args[0]
        orig = os.path.join(d, 'original.mp4')
        if os.path.exists(orig) and os.path.getsize(orig) == os.path.getsize(video):
            print('El video ya estaba subido.')
        else:
            print(f'Subo el video ({os.path.getsize(video) / 1e6:.0f} MB)…', flush=True)
            with open(video, 'rb') as fh:
                api('/api/subir', cuerpo=fh, largo=os.path.getsize(video), p=p, tipo='original')
        if a.idea:
            api('/api/json', cuerpo=a.idea.encode('utf-8'), p=p, f='idea.txt')
        if not os.path.exists(os.path.join(d, 'transcripcion.srt')):
            # Scribe de ElevenLabs si la app tiene la clave (unos $0,05 por video de 14 min): en IOS27_FRP acertó DFU, ECID,
            # 3uTools y Bypass Hello Screen, que Whisper escribía mal y corrían los tramos. Sin clave, Whisper en esta PC.
            print('Transcribo tu voz (ElevenLabs Scribe si la app tiene la clave; si no, Whisper en esta PC)…', flush=True)
            correr(p, 'transcribir', {'motor': 'auto'})
        print('Armo el encargo del guion (capturas, mapa del video y hojas)…', flush=True)
        correr(p, 'ia', {'tarea': 'guion', 'modo': 'prompt'})
        out, n = hojas_2s(d)
        print('Saco cuadros grandes donde dices que haces algo (presiono, power, clic, exit, DFU…)…', flush=True)
        out_ac, n_ac = hojas_acciones(d)
        print(f'\nLISTO. Lee en este orden:\n  1. {os.path.join(d, "ia_prompt_guion.txt")}  (el encargo exacto: reglas, '
              f'transcripción, mapa)\n  2. las imágenes de {os.path.join(d, "ia_capturas")} (y su carpeta hojas)\n'
              f'  3. las {n} hojas de {out} (un cuadro cada 2 s, con el segundo escrito)\n'
              + (f'  4. {os.path.join(out_ac, "acciones.txt")} y sus {n_ac} hojas de acciones (cuadros grandes cada 0,5 s donde '
                 'dices que haces algo): de ahí sale el segundo exacto de cada acción\n' if n_ac else '')
              + 
              'Cumple las REGLAS DEL AUTOR de AGENTS.md (eventos y ve_inicio/ve_fin). Escribe el JSON {"eventos": [...], "bloques": [...], "preguntas": [...]} en un archivo y entrégalo con:\n'
              f'  python deepseek/video.py entregar guion respuesta.json --nombre "{p}"')

    elif a.accion == 'entregar':
        if len(a.args) != 2 or a.args[0] not in ('guion', 'etiquetas', 'trailer'):
            raise SystemExit('Uso: entregar guion|etiquetas|trailer archivo.json --nombre "..."')
        tarea, archivo = a.args
        if tarea == 'guion' and cambio_del_autor(d, archivo) and not a.parti_del_guion_actual:
            copia = os.path.join(d, 'guion_editado_por_autor.json')
            shutil.copyfile(os.path.join(d, 'guion.json'), copia)
            raise SystemExit('NO ENTREGADO: el autor editó el guion en la app después de tu última entrega, y entregar tu archivo '
                             f'borraría sus cambios. Su versión está en {copia}: parte de ella (sus textos mandan), aplica '
                             'solo lo que falte (sus respuestas: python deepseek/video.py preguntas --nombre "..."), guárdala '
                             'como tu respuesta y entrega con --parti-del-guion-actual.')
        if tarea == 'trailer' and trailer_del_autor(d) and not a.parti_del_guion_actual:
            copia = os.path.join(d, 'trailer_editado_por_autor.json')
            shutil.copyfile(os.path.join(d, 'trailer.json'), copia)
            raise SystemExit('NO ENTREGADO: el autor cambió el tráiler en «🎬 Tráiler» después de tu última entrega. Su versión está '
                             f'en {copia}: parte de ella (sus tomas mandan), aplica solo lo que falte (sus respuestas: python '
                             'deepseek/video.py preguntas trailer --nombre "..."), y entrega con --parti-del-guion-actual.')
        txt = open(archivo, encoding='utf-8').read()
        api('/api/pegar', cuerpo=txt.encode('utf-8'), p=p)
        correr(p, 'ia', {'tarea': tarea, 'modo': 'revisar'})
        if tarea == 'guion':
            marcar(d, guion=huella(d))
        if tarea == 'trailer':
            marcar(d, trailer=huella_trailer(d))
        print(f'Guardado {tarea}.json (corregido por la app).')
        if tarea == 'guion':
            print(resumen_guion(d))
            for f in ('mejoras_guion.txt', 'revision_guion.txt'):
                if leer(d, f).strip():
                    print(f'\n--- {f} ---\n' + leer(d, f).strip()[:4000])
            print(texto_preguntas(d))
            print(f'\nAhora dile al autor que el guion ya está en la app: proyecto «{p}» → «📝 Ver y editar guion». Ahí lo lee, '
                  'lo edita y contesta tus preguntas (o te las contesta en el chat). Cuando diga que respondió: '
                  f'python deepseek/video.py preguntas --nombre "{p}", corrige y vuelve a entregar. '
                  'No armes hasta que diga que sí (la voz gasta créditos de ElevenLabs).')
        if tarea == 'trailer':
            print(texto_preguntas(d, 'trailer'))
            print(f'\nAhora dile al autor que el tráiler está en la app: proyecto «{p}» → «🎬 Tráiler». Ahí ve cada toma con su '
                  'imagen, la cambia y contesta tus preguntas. Cuando diga que respondió: '
                  f'python deepseek/video.py preguntas trailer --nombre "{p}", corrige y vuelve a entregar. '
                  'No lo armes hasta que diga que sí (la frase de voz gasta créditos de ElevenLabs).')

    elif a.accion == 'preguntas':
        if a.args[:1] == ['trailer']:
            print(texto_preguntas(d, 'trailer'))
            if trailer_del_autor(d):
                print('\nOJO: el autor también cambió el tráiler en la app. Parte de mis_proyectos/<nombre>/trailer.json, no de tu archivo viejo.')
        else:
            print(texto_preguntas(d))
        if not a.args and cambio_del_autor(d):
            print('\nOJO: el autor también editó el guion en la app. Parte de mis_proyectos/<nombre>/guion.json, no de tu archivo viejo.')

    elif a.accion == 'armar':
        if not a.confirmo_creditos:
            raise SystemExit('La voz gasta créditos de ElevenLabs (solo los bloques nuevos o cambiados). Pregúntale al autor; '
                             'si dice que sí, repite con --confirmo-creditos.')
        correr(p, 'todo', {'sin_ia': True})
        print('LISTO: ' + os.path.join(d, 'FINAL.mp4') + ' (sin extras). Revisa avisos en registro.txt.')
        print(resumen_guion(d))

    elif a.accion == 'encargo':
        if len(a.args) != 1 or a.args[0] not in ('etiquetas', 'trailer'):
            raise SystemExit('Uso: encargo etiquetas|trailer --nombre "..."')
        correr(p, 'ia', {'tarea': a.args[0], 'modo': 'prompt'})
        print(f'Encargo en {os.path.join(d, "ia_prompt_" + a.args[0] + ".txt")} (y capturas en ia_capturas). '
              f'Después: entregar {a.args[0]} respuesta.json --nombre "{p}"')

    elif a.accion == 'extras':
        solo = a.args or ['etiquetas']  # el tráiler va aparte: solo si se pide (y ya está en trailer.json)
        if 'trailer' in solo and not leer(d, 'trailer.json').strip():
            raise SystemExit('Todavía no hay trailer.json. Primero: encargo trailer → entregar trailer → el autor lo revisa en «🎬 Tráiler».')
        if GASTAN & set(solo) and not a.confirmo_creditos:
            raise SystemExit(f'{", ".join(sorted(GASTAN & set(solo)))} gasta créditos de ElevenLabs. Pregúntale al autor; '
                             'si dice que sí, repite con --confirmo-creditos.')
        correr(p, 'extras', {'sin_ia': True, 'solo': solo})
        print('LISTO: ' + os.path.join(d, 'FINAL.mp4'))

    elif a.accion == 'exportar':
        alturas = [int(x) for x in a.args] or [480]
        correr(p, 'exportar', {'alturas': alturas})
        print('LISTO: ' + ', '.join(os.path.join(d, f'FINAL_{h}p.mp4') for h in alturas))

    elif a.accion == 'estado':
        e = api('/api/estado', p=p)
        print(json.dumps({'trabajo': e.get('trabajo'), 'fallo': e.get('fallo'),
                          'listos': [x['id'] for x in e.get('pasos', []) if x.get('listo')]}, ensure_ascii=False, indent=1))
        print(resumen_guion(d))


if __name__ == '__main__':
    main()
