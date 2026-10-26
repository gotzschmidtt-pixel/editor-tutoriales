"""De tu video a FINAL.mp4 con una IA de chat que corre comandos (DeepSeek, Claude, etc.), usando esta misma app.

La IA no edita video: escribe el guion, las etiquetas y el tráiler en JSON. Todo lo demás (transcripción, capturas, mapa
del video, voz de ElevenLabs, montaje con repetición en vez de foto fija, música, etiquetas, tráiler) lo hace la app, con
sus mismos pasos y parámetros. Este script habla con la app (http://localhost:8765) y la abre si no está abierta.

Uso (desde la carpeta editor-tutoriales):
  python deepseek/video.py preparar "C:\\ruta\\video.mp4" --nombre "Mi video" [--idea "datos seguros del video"]
      crea el proyecto, sube el video, transcribe con Whisper (gratis), y deja el encargo del guion:
      ia_prompt_guion.txt, ia_capturas/ (capturas, mapa y hojas) y hojas_2s/ (un cuadro cada 2 s, 30 por hoja)
  python deepseek/video.py entregar guion respuesta.json --nombre "Mi video"
      la app corrige el guion (tiempos, largo, orden) y lo guarda en guion.json; muestra el resumen y los avisos
  python deepseek/video.py preguntas --nombre "Mi video"
      tus preguntas del guion con lo que el autor contestó en la app
  python deepseek/video.py armar --nombre "Mi video" --confirmo-creditos
      voz (ElevenLabs, GASTA créditos), montaje, subtítulos y música → FINAL.mp4 sin extras
  python deepseek/video.py encargo etiquetas|trailer --nombre "Mi video"
      deja ia_prompt_<tarea>.txt para escribir las etiquetas o el tráiler (después: entregar etiquetas|trailer archivo.json)
  python deepseek/video.py extras etiquetas trailer --nombre "Mi video" [--confirmo-creditos]
      pone los extras sobre el video (el tráiler y nuevos_modelos gastan ElevenLabs)
  python deepseek/video.py exportar 480 720 --nombre "Mi video"
  python deepseek/video.py estado --nombre "Mi video"

No usa claves: la app las lee de app/ajustes.json, que este script nunca abre ni muestra.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

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


MARCA = '.deepseek_entrega.json'  # los textos del guion tal como quedaron en la última entrega de la IA


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


def texto_preguntas(d):
    """Las preguntas del guion (preguntas_guion.json) con lo que contestó el autor en la app."""
    try:
        lista = json.loads(leer(d, 'preguntas_guion.json') or '[]')
    except ValueError:
        lista = []
    if not lista:
        return 'Sin preguntas guardadas (ponlas en "preguntas" de respuesta_guion.json: hasta 15 de datos y hasta 10 ideas para mejorar).'
    out = [f'Preguntas al autor ({len(lista)}):']
    for k, x in enumerate(lista, 1):
        r = str(x.get('respuesta') or '').strip()
        out.append(f"{k}. [{x.get('tipo')} · {x.get('bloque') or '-'}] {x.get('pregunta')}"
                   + (f'\n   RESPUESTA: {r}' if r else '\n   (sin responder)'))
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('accion', choices=['preparar', 'entregar', 'preguntas', 'armar', 'encargo', 'extras', 'exportar', 'estado'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--nombre', required=True, help='nombre del proyecto (carpeta en mis_proyectos)')
    ap.add_argument('--idea', help='datos seguros del video para la IA (se guardan en idea.txt)')
    ap.add_argument('--parti-del-guion-actual', action='store_true',
                    help='entregar guion: tu archivo ya incluye lo que el autor editó en la app (guion_editado_por_autor.json)')
    ap.add_argument('--confirmo-creditos', action='store_true', help='el autor aprobó gastar créditos de ElevenLabs')
    a = ap.parse_args()
    abrir_app()
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
            print('Transcribo con Whisper en esta PC (no gasta créditos)…', flush=True)
            correr(p, 'transcribir', {'motor': 'whisper'})
        print('Armo el encargo del guion (capturas, mapa del video y hojas)…', flush=True)
        correr(p, 'ia', {'tarea': 'guion', 'modo': 'prompt'})
        out, n = hojas_2s(d)
        print(f'\nLISTO. Lee en este orden:\n  1. {os.path.join(d, "ia_prompt_guion.txt")}  (el encargo exacto: reglas, '
              f'transcripción, mapa)\n  2. las imágenes de {os.path.join(d, "ia_capturas")} (y su carpeta hojas)\n'
              f'  3. las {n} hojas de {out} (un cuadro cada 2 s, con el segundo escrito)\n'
              'Escribe el JSON {"bloques": [...], "preguntas": [...]} en un archivo y entrégalo con:\n'
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
        txt = open(archivo, encoding='utf-8').read()
        api('/api/pegar', cuerpo=txt.encode('utf-8'), p=p)
        correr(p, 'ia', {'tarea': tarea, 'modo': 'revisar'})
        if tarea == 'guion':
            open(os.path.join(d, MARCA), 'w', encoding='utf-8').write(json.dumps({'guion': huella(d)}))
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

    elif a.accion == 'preguntas':
        print(texto_preguntas(d))
        if cambio_del_autor(d):
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
        solo = a.args or ['etiquetas', 'trailer']
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
