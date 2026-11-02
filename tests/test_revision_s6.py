"""Prueba rápida de los arreglos de la revisión S6 (montaje y Shorts). Sin internet y sin gastar nada: la IA de la
traducción va simulada y todo va a una carpeta temporal (tus proyectos no se tocan).
- la rotación del inicio no se cae con una pausa «congelar» sin src_fin, y una prueba de unos bloques no toca el aviso rojo;
- el gancho del Short no usa un trozo de la grabación que en el video armado va difuminado;
- las etiquetas de emoción ([curious]) no salen en los subtítulos del Short;
- «Varios Shorts» con gancho: el título no sale vacío;
- la cuarta etiqueta seguida ya no se dibuja encima de la primera;
- la versión en otro idioma copia los videos de testimonios, nuevos modelos, el material de los insertos y la música, y el
  difuminado busca en todo el video; una marca vieja de una creación cortada ya no la bloquea;
- un inserto con una frase que no está se salta solo (los demás siguen) y en la versión traducida se busca en el original;
- los subtítulos no se corren si el FINAL no lleva tráiler aunque exista trailer.mp4;
- «3 Shorts resumen» con una frase sin tomas avisa claro antes de armar.
Uso: python tests/test_revision_s6.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('montaje', 'short', 'etiquetas', 'subtitulos'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import rotar  # noqa: E402
import short  # noqa: E402
import varios  # noqa: E402
import etiquetas  # noqa: E402
import version_idioma as vi  # noqa: E402
import subtitulos  # noqa: E402
import resumen  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def alineacion(texto, paso=0.06):
    return {'characters': list(texto), 'character_start_times_seconds': [k * paso for k in range(len(texto))],
            'character_end_times_seconds': [(k + 1) * paso for k in range(len(texto))]}


def video(f, segundos):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c=black:s=64x36:d={segundos}', '-f', 'lavfi',
                    '-i', f'anullsrc=r=44100:cl=stereo', '-t', str(segundos), '-c:v', 'libx264', '-c:a', 'aac', f], check=True)


tmp = tempfile.mkdtemp(prefix='revision_s6_')
antes = os.getcwd()
try:
    # 1) rotar.planear: «congelar» con src_fin vacío (como guion_pico_largo.json) no se cae; la prueba no toca los avisos
    d = os.path.join(tmp, 'rotar')
    os.makedirs(os.path.join(d, 'voz'))
    os.chdir(d)
    json.dump({'cuadros': [{'t': t, 'texto': 'verifica tu cuenta de google'} for t in (100, 120, 140, 160, 180, 200)]},
              open('mapa_video.json', 'w', encoding='utf-8'))
    bloques = [{'id': 'L03', 'inicio_min': 5.0, 'montaje': {'modo': 'congelar', 'src_inicio': 10, 'src_fin': None, 'congelar_s': 16}}]
    open(rotar.AVISOS, 'w').write('[{"aviso": "de antes"}]')
    try:
        plan = rotar.planear(bloques, 'mapa_video.json', 'voz', 600.0, 30, guardar_avisos=False)
        ok('L03' in plan, f'la pausa congelar no rotó: {plan}')
    except TypeError as e:
        fallos.append(f'rotar.planear se cae con src_fin vacío: {e}')
    ok(os.path.exists(rotar.AVISOS), 'una prueba de unos bloques borró avisos_inicio.json')
    os.chdir(antes)

    # 2) el gancho del Short no usa el trozo del grabado que en el FINAL va difuminado (otro reloj)
    d = os.path.join(tmp, 'gancho')
    os.makedirs(os.path.join(d, 'voz'))
    frase = 'Tu cuenta de Google bloqueada. '
    json.dump(alineacion(frase * 4), open(os.path.join(d, 'voz', 'L01.align.json'), 'w', encoding='utf-8'))
    json.dump({'cuadros': [{'t': t, 'texto': 'verifica tu cuenta'} for t in (720, 760, 800, 840)]},
              open(os.path.join(d, 'mapa_video.json'), 'w', encoding='utf-8'))
    json.dump({'tramos': [[315, 446]]}, open(os.path.join(d, 'difuminar_datos.json'), 'w', encoding='utf-8'))
    json.dump({'bloques': [{'id': 'L01', 'inicio_min': 0, 'fin_max': 8, 'montaje': {'modo': 'lento', 'src_inicio': 20, 'src_fin': 28}},
                           {'id': 'L20', 'inicio_min': 320, 'fin_max': 340,
                            'montaje': {'modo': 'lento+congelar', 'src_inicio': 712, 'src_fin': 724, 'congelar_s': 4}}]},
              open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'))
    c = {'id': 'L01', 'src_inicio': 20, 'voz': 7.0}
    piezas = short.rotar_gancho(d, c, 9.0, 900.0, [c]) or []
    ok(piezas and all(not (700 <= s <= 730) for s, _, _ in piezas), f'el gancho usó el trozo difuminado (720 s): {piezas}')

    # 3) subtítulos del Short sin las etiquetas de emoción
    json.dump(alineacion('[curious] ¿Tu Honor pide la cuenta? [sighs deeply]. Bueno'),
              open(os.path.join(d, 'voz', 'S1F1.align.json'), 'w', encoding='utf-8'))
    pal = [p for _, _, p in short.palabras_voz(d, 'S1F1')]
    ok(pal == ['¿Tu', 'Honor', 'pide', 'la', 'cuenta?', 'Bueno'], f'palabras del Short con etiquetas: {pal}')
    ass = short.subtitulos(d, [{'id': 'S1F1', 'largo': 5}], 0.1)
    ok('CURIOUS' not in ass and 'SIGHS' not in ass, 'el subtítulo del Short muestra la etiqueta de emoción')

    # 4) «Varios Shorts» con gancho delante: el título sale de la primera toma con texto
    t = varios.titulo([{'id': 'GANCHO', 'texto': ''}, {'id': 'L20', 'texto': 'Ahora tocamos el botón verde y esperamos'}])
    ok(t == 'Ahora tocamos el botón verde y', f'título del Short con gancho: «{t}»')

    # 5) la cuarta etiqueta seguida no cae encima de la primera
    items = [{'texto': x, 't': t, 'dur': 3.5} for x, t in (('AliExpress', 30), ('Mercado Libre', 31.5), ('Colombia', 33), ('Waveshare', 35))]
    g = etiquetas.agrupar(items)
    ok(len(g) == 2 and g[1]['ini'] >= g[0]['fin'] - 0.01, f'la cuarta etiqueta se encima: {[(x["ini"], x["fin"]) for x in g]}')
    ok(all(i['t'] >= x['ini'] for x in g for i in x['items']), 'una etiqueta empieza antes que su pila')

    # 6) versión en otro idioma: copia lo que hace falta y el difuminado busca en todo el video
    o, dst = os.path.join(tmp, 'HONOR 8 LITE'), os.path.join(tmp, 'HONOR 8 LITE_EN')
    for sub in ('testimonios', 'nuevos_modelos', 'difuminar_datos'):
        os.makedirs(os.path.join(o, sub))
    for n, x in (('original.mp4', b'v'), ('pantalla_celular.mp4', b'p'), ('musica.mp3', b'm'), ('FINAL.mp4', b'x'),
                 ('testimonios/cliente1.mp4', b't'), ('testimonios/narr_1.mp3', b'n'), ('nuevos_modelos/honor600.mp4', b'h'),
                 ('difuminar_datos/cabecera.png', b'c')):
        open(os.path.join(o, n), 'wb').write(x)
    json.dump([{'material': 'pantalla_celular.mp4', 'bloque': 'L15', 'frase': 'Descargar Files'}],
              open(os.path.join(o, 'insertos.json'), 'w', encoding='utf-8'))
    json.dump({'referencias': [{'imagen': 'difuminar_datos/cabecera.png', 'zonas': [[0, 0, 5, 5]]}], 'tramos': [[315, 446]]},
              open(os.path.join(o, 'difuminar_datos.json'), 'w', encoding='utf-8'))
    json.dump({'bloques': [{'id': 'L01', 'texto': 'Hola'}]}, open(os.path.join(o, 'guion.json'), 'w', encoding='utf-8'))
    vi.copiar(o, dst)
    hay = lambda n: os.path.exists(os.path.join(dst, n))
    for n in ('testimonios/cliente1.mp4', 'nuevos_modelos/honor600.mp4', 'pantalla_celular.mp4', 'musica.mp3'):
        ok(hay(n), f'la versión no copió {n}')
    ok(not hay('FINAL.mp4') and not hay('testimonios/narr_1.mp3'), 'la versión copió el FINAL o la voz en español del testimonio')
    conf = json.load(open(os.path.join(dst, 'difuminar_datos.json'), encoding='utf-8'))
    ok(not conf.get('tramos') and conf.get('referencias'), f'la versión copió los tramos del difuminado del video en español: {conf}')
    shutil.rmtree(dst)

    # 7) una marca vieja de una creación cortada no bloquea para siempre (la IA va simulada: no gasta ni sale a internet)
    os.makedirs(dst)
    open(os.path.join(dst, '.creando_version'), 'w').close()
    viejo = time.time() - 3600
    os.utime(os.path.join(dst, '.creando_version'), (viejo, viejo))
    aj = os.path.join(tmp, 'ajustes.json')
    json.dump({}, open(aj, 'w'))
    traducir_antes = vi.traducir_guion
    vi.traducir_guion = lambda guion, idioma, ajustes, extras=None: ([], {})
    argv = sys.argv
    sys.argv = ['version_idioma.py', '--proyecto', o, '--idioma', 'en', '--ajustes', aj]
    try:
        vi.main()
        ok(os.path.exists(os.path.join(dst, 'guion.json')), 'la versión no se creó con una marca vieja')
    except SystemExit as e:
        fallos.append(f'una marca vieja sigue bloqueando la versión: {e}')
    finally:
        sys.argv, vi.traducir_guion = argv, traducir_antes
    # una marca reciente sí frena el segundo clic
    d7 = os.path.join(tmp, 'Otro')
    shutil.copytree(o, d7)
    os.makedirs(d7 + '_EN')
    open(os.path.join(d7 + '_EN', '.creando_version'), 'w').close()
    sys.argv = ['version_idioma.py', '--proyecto', d7, '--idioma', 'en', '--ajustes', aj]
    try:
        vi.main()
        fallos.append('una marca reciente (otra creación en curso) no frenó el segundo clic')
    except SystemExit as e:
        ok('Ya se está creando' in str(e), f'mensaje raro con la marca reciente: {e}')
    finally:
        sys.argv = argv

    # 8) insertos: una frase que no está salta ese inserto y el video sigue (antes se caía todo el paso)
    d = os.path.join(tmp, 'insertos')
    os.makedirs(os.path.join(d, 'voz'))
    json.dump({'bloques': [{'id': 'L15', 'inicio_min': 10, 'texto': 'Download Files', 'texto_original': 'Descargar Files'}]},
              open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'))
    json.dump(alineacion('Download Files'), open(os.path.join(d, 'voz', 'L15.align.json'), 'w', encoding='utf-8'))
    json.dump([{'material': 'pantalla.mp4', 'src_t': 1, 'bloque': 'L15', 'frase': 'otra cosa', 'dur': 2, 'claves': []}],
              open(os.path.join(d, 'insertos.json'), 'w', encoding='utf-8'))
    open(os.path.join(d, '1_montaje.mp4'), 'wb').write(b'video')
    r = subprocess.run([sys.executable, os.path.join(RAIZ, 'insertos', 'insertos.py'), '--guion', 'guion.json', '--voz', 'voz',
                        '--insertos', 'insertos.json', '--video', '1_montaje.mp4', '--salida', '2_insertos.mp4'],
                       cwd=d, capture_output=True, text=True, encoding='utf-8', errors='replace')
    ok(r.returncode == 0 and os.path.exists(os.path.join(d, '2_insertos.mp4')), f'insertos se cae con una frase que no está: {r.stderr[-300:]}')
    sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
    ok(etiquetas.buscar(alineacion('Download Files'), 'Descargar Files', 'Descargar Files') is not None,
       'en la versión traducida la frase en español no se encuentra')

    # 9) subtítulos: con trailer.mp4 pero el FINAL sin tráiler no se corren; con el FINAL con tráiler, sí
    d = os.path.join(tmp, 'subs')
    os.makedirs(d)
    video(os.path.join(d, '4_musica.mp4'), 4)
    video(os.path.join(d, 'trailer.mp4'), 2)
    shutil.copyfile(os.path.join(d, '4_musica.mp4'), os.path.join(d, 'FINAL.mp4'))
    ok(subtitulos.offset_de(d, os.path.join(d, 'FINAL.mp4')) == 0.0, 'los subtítulos se corren aunque el FINAL no lleve tráiler')
    video(os.path.join(d, 'FINAL.mp4'), 6)
    ok(abs(subtitulos.offset_de(d, os.path.join(d, 'FINAL.mp4')) - 2) < 0.2, 'con el tráiler al inicio los subtítulos ya no se corren')

    # 10) «3 Shorts resumen»: una frase sin tomas avisa antes de armar (antes: «division by zero» a mitad)
    d = os.path.join(tmp, 'resumen')
    os.makedirs(d)
    json.dump({'shorts': [{'frases': [{'texto': 'Hola', 'tomas': [[18, 22]]}, {'texto': 'Chau', 'tomas': []}]}]},
              open(os.path.join(d, resumen.ARCHIVO), 'w', encoding='utf-8'))
    try:
        resumen.armar(d, cuales=(1,))
        fallos.append('armó los Shorts con una frase sin tomas')
    except ValueError as e:
        ok('frase 2' in str(e) and 'tomas' in str(e), f'aviso poco claro: {e}')
    except Exception as e:  # antes: «division by zero» (o ffmpeg) a mitad del armado
        fallos.append(f'una frase sin tomas no avisa antes de armar: {type(e).__name__}: {e}'[:200])
finally:
    os.chdir(antes)
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLA:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: revisión S6 (rotación del inicio, gancho sin datos, subtítulos del Short, versión en otro idioma, insertos, '
      'subtítulos con tráiler, Shorts resumen)')
