"""Prueba rápida de los arreglos de la revisión S4 (resto de la app). Sin internet y sin gastar nada: GPT, ElevenLabs y
los pasos largos van simulados, y tus ajustes y proyectos no se tocan (todo va a una carpeta temporal).
- con tráiler, el FINAL lleva el inicio fijo y los datos difuminados (y el tráiler también se difumina, entero);
- «▶ Ver con voz» de una IA del tráiler no gasta ElevenLabs sin confirmar;
- «Guardar y seguir con todo» copia el FINAL antes de borrarlo;
- la miniatura con título de GPT dibuja el título nuevo si lo cambias;
- el avatar se monta con los tramos de los audios que fueron a HeyGen;
- «🎨 Generar» de miniaturas de referencia nunca manda más variantes que las de la cuenta (1 a 4).
Uso: python tests/test_revision_s4.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile

import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('app', 'miniatura', 'avatar'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ['SIN_NAVEGADOR'] = '1'
import app  # noqa: E402
import ahorro  # noqa: E402
import miniatura as mini  # noqa: E402
import referencias as mr  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def crear(d, nombres):
    for n in nombres:
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), 'w').write('{}')


tmp = tempfile.mkdtemp()
app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
app.PROYECTOS = os.path.join(tmp, 'proyectos')
json.dump({}, open(app.AJUSTES, 'w'))
try:
    # 1) tráiler: el FINAL sale del video con inicio fijo y datos difuminados, y el tráiler también se difumina
    d = os.path.join(app.PROYECTOS, 'honor')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4', '8_testimonios.mp4', '8_testimonios.srt', 'trailer.json'])
    c = app.comandos('trailer', d, {})
    ok(len(c) == 1 and c[0][c[0].index('--unir') + 1] == '8_testimonios.mp4' and '--difuminar' not in c[0],
       f'sin inicio fijo ni difuminado, el tráiler se une como antes: {c}')
    crear(d, ['inicio_fijo.json', 'difuminar_datos.json'])
    c = app.comandos('trailer', d, {})
    plano = [' '.join(os.path.basename(x) for x in cmd) for cmd in c]
    tr = c[-1]
    ok(any('inicio_fijo.py --entrada FINAL_sin_trailer.mp4' in x for x in plano), f'falta el inicio fijo con tráiler: {plano}')
    ok(any('difuminar_datos.py --entrada FINAL_sin_trailer.mp4' in x for x in plano), f'falta difuminar con tráiler: {plano}')
    ok(tr[tr.index('--unir') + 1] == 'FINAL_sin_trailer.mp4' and tr[tr.index('--srt') + 1] == '8_testimonios.srt' and '--difuminar' in tr,
       f'el tráiler debe unirse a la base privada, con los subtítulos de testimonios, y difuminarse: {tr}')

    # difuminar_datos.py --todo: busca en todo el video aunque los tramos no lo cubran (así se revisa el tráiler)
    dd = os.path.join(tmp, 'difuminar')
    os.makedirs(os.path.join(dd, 'ref'))
    img = cv2.GaussianBlur((np.random.default_rng(1).random((360, 640)) * 255).astype(np.uint8), (0, 0), 1.5)
    cv2.imwrite(os.path.join(dd, 'ref', 'cab.png'), cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-loop', '1', '-i', os.path.join('ref', 'cab.png'), '-f', 'lavfi', '-i',
                    'anullsrc=r=48000:cl=stereo', '-t', '1', '-r', '25', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-shortest',
                    '-c:a', 'aac', 'v.mp4'], cwd=dd, check=True)
    json.dump({'referencias': [{'imagen': 'ref/cab.png', 'zonas': [[100, 100, 200, 60]]}], 'tramos': [[100, 200]], 'minimo': 20},
              open(os.path.join(dd, 'difuminar_datos.json'), 'w'))
    dif = os.path.join(RAIZ, 'privacidad', 'difuminar_datos.py')
    r1 = subprocess.run([sys.executable, dif, '--entrada', 'v.mp4', '--salida', 'o.mp4'], cwd=dd, capture_output=True, text=True)
    r2 = subprocess.run([sys.executable, dif, '--entrada', 'v.mp4', '--salida', 'o.mp4', '--todo'], cwd=dd, capture_output=True, text=True)
    ok('en 0 cuadros' in r1.stdout and r2.returncode == 0 and 'en 0 cuadros' not in r2.stdout,
       f'--todo debe difuminar fuera de los tramos: {r1.stdout.strip()} / {r2.stdout.strip()} {r2.stderr[-300:]}')

    # 2) «▶ Ver con voz» de una IA del tráiler: sin SI no gasta; sin voz o con la frase ya hecha, sí arranca
    json.dump({'voz': 'Así se quita la cuenta', 'clips': []}, open(os.path.join(d, 'trailer_gpt.json'), 'w', encoding='utf-8'))
    ok(app.gasto_sin_confirmar(d, 'trailer_version', ['trailer_version'], {'v': 'gpt'}), 'con voz nueva debe pedir SI')
    ok(app.gasto_sin_confirmar(d, 'trailer_version', ['trailer_version'], {'v': 'gpt', 'sin_voz': True}) is None, 'sin voz no gasta')
    ok(app.gasto_sin_confirmar(d, 'trailer_version', ['trailer_version'], {'v': 'gpt', 'confirmo': 'SI'}) is None, 'con SI arranca')
    open(os.path.join(d, 'trailer_gpt.voz.mp3'), 'wb').write(b'x')
    open(os.path.join(d, 'trailer_gpt.voz.mp3.txt'), 'w', encoding='utf-8').write('Así se quita la cuenta')
    ok(app.gasto_sin_confirmar(d, 'trailer_version', ['trailer_version'], {'v': 'gpt'}) is None, 'la misma frase ya hecha no se vuelve a pagar')

    # 3) «Guardar y seguir con todo» (voz + montaje…): el FINAL queda copiado antes de borrarlo
    d = os.path.join(app.PROYECTOS, 'rehacer')
    crear(d, ['original.mp4', 'guion.json'])
    open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'final con arreglos')
    open(os.path.join(d, 'FINAL_EN.mp4'), 'wb').write(b'version en ingles')  # no se borra al rehacer: no se copia cada vez
    viejos = (app.comandos, app.asegurar_librerias, app.asegurar_node)
    app.comandos, app.asegurar_librerias, app.asegurar_node = (lambda *a: []), (lambda *a: None), (lambda *a: None)
    try:
        app.TRABAJO.update(proyecto='rehacer')
        app.correr('rehacer', ['voz', 'montaje'], {})
    finally:
        app.comandos, app.asegurar_librerias, app.asegurar_node = viejos
        app.TRABAJO.update(proyecto=None)
    copias = [f for f in os.listdir(d) if f.startswith('FINAL_antes_rehacer_')]
    ok(not os.path.exists(os.path.join(d, 'FINAL.mp4')) and copias and
       open(os.path.join(d, copias[0]), 'rb').read() == b'final con arreglos', f'el FINAL debe quedar copiado antes de borrarlo: {os.listdir(d)}')
    ok(len(copias) == 1 and os.path.exists(os.path.join(d, 'FINAL_EN.mp4')),
       f'solo se copia el FINAL que se borra (FINAL_EN.mp4 no se duplica en cada «Hacer todo»): {copias}')

    # 4) miniatura con título de GPT: cambiar el título dibuja el título nuevo (y no reutiliza el viejo)
    d = os.path.join(tmp, 'mini')
    os.makedirs(d)
    dibujados, puestos = [], []
    mini.traducciones_titulo = lambda d_, lineas: {i: [x.upper() for x in lineas] for i in ('es', 'en', 'pt')}
    mini.titulo_gpt = lambda partes, estilo, salida: (dibujados.append(' '.join(partes)), open(salida, 'wb').write(b'png'))
    mini.etiqueta_gpt = lambda *a, **k: None
    mini.componer_mixta = lambda escena, lineas, marca, idioma, f, estilo, png, esq: puestos.append(open(png, 'rb') and os.path.basename(png))
    base = os.path.join(d, 'miniatura_mixta')
    for texto in (['HONOR', 'SIN CUENTA GOOGLE'], ['HONOR', 'FRP 2026']):
        mini.miniaturas_mixtas(d, [], texto, base, idiomas=('es',), titulo_por_gpt=True, escena=np.zeros((4, 4, 3), np.uint8))
    ok(dibujados == ['HONOR SIN CUENTA GOOGLE', 'HONOR FRP 2026'] and len(set(puestos)) == 2,
       f'con otro título GPT debe dibujar el nuevo: {dibujados} {puestos}')

    # 5) avatar: «🎬 Montar» usa los tramos de los audios que fueron a HeyGen aunque después cambies el Ritmo
    d = os.path.join(tmp, 'avatar')
    c_av = os.path.join(d, 'avatar_ahorro')
    os.makedirs(os.path.join(c_av, 'heygen'))
    exportado = {'tramos': [{'tipo': 'voz', 's': 0, 'e': 45}, {'tipo': 'avatar', 's': 45, 'e': 90}, {'tipo': 'voz', 's': 90, 'e': 120}],
                 'frases_s': [0, 45, 90], 'ajustes': {}}
    ahora = {'tramos': [{'tipo': 'voz', 's': 0, 'e': 30}, {'tipo': 'avatar', 's': 30, 'e': 75}, {'tipo': 'voz', 's': 75, 'e': 120}],
             'frases_s': [0, 30, 75], 'ajustes': {'gancho_s': 30}}
    json.dump(exportado, open(os.path.join(c_av, 'plan_exportado.json'), 'w'))
    json.dump(ahora, open(os.path.join(c_av, 'plan.json'), 'w'))
    for f in ('voz_completa.mp3', os.path.join('heygen', 'avatar_01.mp4')):
        open(os.path.join(c_av, f), 'wb').write(b'x')
    os.makedirs(os.path.join(d, 'apoyo'))
    open(os.path.join(d, 'apoyo', 'toma.mp4'), 'wb').write(b'x')
    usados = []
    viejo_montar = ahorro.montar
    ahorro.montar = lambda tramos, *a, **k: usados.append(tramos)
    try:
        ahorro.montar_proyecto(d)
    finally:
        ahorro.montar = viejo_montar
    ok(usados and usados[0][1]['s'] == 45, f'el avatar debe montarse en el tramo de HeyGen (45-90 s): {usados}')

    # 6) miniaturas de referencia: variantes vacías, 0 o de más quedan entre 1 y 4
    pedidos = []
    viejo_correr = mr._correr
    mr._correr = lambda h, d_, *args, **k: pedidos.append(args[args.index('--variantes') + 1])

    class H:
        def __init__(self, cuerpo):
            self.rfile = __import__('io').BytesIO(cuerpo)

        def error(self, m, *a):
            pedidos.append('error')
    try:
        for v in (0, '', None, 9, 3):
            cuerpo = json.dumps({'confirmo': True, 'ideas': [1, 2], 'variantes': v}).encode()
            mr.post(H(cuerpo), '/api/miniref/generar', {}, len(cuerpo), tmp)
    finally:
        mr._correr = viejo_correr
    ok(pedidos == ['1', '2', '2', '4', '3'], f'variantes fuera de 1-4: {pedidos}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión S4 (tráiler privado, voz del tráiler, copia del FINAL, título de miniatura, avatar, variantes)')
sys.exit(1 if fallos else 0)
