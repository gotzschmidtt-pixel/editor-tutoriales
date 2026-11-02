"""Prueba rápida de los arreglos de la revisión S8a (varios). Sin internet y sin gastar nada: las transcripciones van
simuladas y todo va a una carpeta temporal (tus proyectos y tus sonidos no se tocan).
- las notas de voz del tráiler se transcriben con Whisper (gratis), no con ElevenLabs Scribe;
- el diagnóstico de un paso sin IA no se lleva los fallos de la IA de otro paso;
- «📱 Pantalla derecha» toma 5 muestras por segundo justas aunque la cámara grabe a 24 fps;
- la «frase» de los insertos automáticos se encuentra en la voz (también con «xiaomiunlock.com» y en una voz de antes);
- «Flechas y círculos» sin ninguna señal que poner deja el video igual, sin un error de ffmpeg;
- «↩ El de la PC» no borra el sonido de ElevenLabs: queda guardado como .mp3.eleven.
Uso: python tests/test_revision_s8a.py   (sale con 1 si algo falla)
"""
import io, json, os, shutil, subprocess, sys, tempfile, types

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('trailer', 'diagnostico', 'pantalla', 'etiquetas', 'voz', 'mejoras'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import pistas  # noqa: E402
import diagnostico  # noqa: E402
import enderezar  # noqa: E402
from etiquetas import buscar  # noqa: E402
from texto_voz import texto_voz  # noqa: E402
import mejoras  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def alineacion(texto, paso=0.05):
    return {'characters': list(texto), 'character_start_times_seconds': [k * paso for k in range(len(texto))],
            'character_end_times_seconds': [(k + 1) * paso for k in range(len(texto))]}


tmp = tempfile.mkdtemp(prefix='s8a_')
try:
    # 1) pistas del tráiler: con clave de ElevenLabs igual se usa Whisper (Scribe solo si se pide con scribe=True)
    d = os.path.join(tmp, 'proy')
    os.makedirs(os.path.join(d, pistas.CARPETA))
    open(os.path.join(d, pistas.CARPETA, 'nota.mp3'), 'wb').write(b'x')
    usados = []
    falso = types.ModuleType('transcribir')
    falso.CLAVE = {'xi-api-key': 'k'}
    falso.audio = lambda f: f
    falso.scribe = lambda mp3, idioma: usados.append('scribe') or [{'texto': 'pagado'}]
    falso.whisper = lambda mp3, idioma, modelo: usados.append('whisper') or [{'texto': 'pega la key'}]
    sys.modules['transcribir'] = falso
    txt = pistas.transcribir_audio(d, 'nota.mp3')
    ok(usados == ['whisper'] and txt == 'pega la key', f'la nota de voz debía ir con Whisper (gratis): {usados}')
    sys.modules.pop('transcribir', None)

    # 2) diagnóstico: la voz falla con 401 y antes la IA del guion tuvo un 429 (ya reintentado)
    dd = os.path.join(tmp, 'diag')
    os.makedirs(dd)
    ev = [{'ejecucion': 'E1', 'paso': 'guion_ia', 'ok': False, 'http': 429, 'proveedor': 'Claude', 'mensaje_api': 'rate limit'},
          {'ejecucion': 'E1', 'paso': 'guion_ia', 'ok': True, 'proveedor': 'Claude'}]
    open(os.path.join(dd, 'llamadas_E1.jsonl'), 'w', encoding='utf-8').write('\n'.join(json.dumps(x) for x in ev) + '\n')
    r = diagnostico.informe(dd, 'p', 'voz', 'Generar voz', 'E1', 'ERROR: ElevenLabs respondió con error 401: invalid api key\n', 'fallo')
    ok(r and r['tipo'].startswith('C.') and 'Claude' not in r['ia'], f'la voz con clave rechazada debía ser «C»: {r}')
    ok(diagnostico.informe(dd, 'p', 'montaje', 'Montaje', 'E1', '', 'ok') is None, 'un paso sin IA que salió bien no lleva diagnóstico')

    # 3) pantalla derecha: a 24 fps la muestra k es del segundo k / 5 (antes se corría ~25 s cada 10 min)
    vid = os.path.join(tmp, 'v24.mp4')
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', '64x36', '-r', '24',
                          '-i', '-', '-c:v', 'libx264', '-qp', '0', '-pix_fmt', 'yuv444p', vid], stdin=subprocess.PIPE)
    for i in range(24 * 60):
        p.stdin.write(np.full((36, 64), 16 + (i // 24) * 3, np.uint8).tobytes())  # un brillo distinto por segundo
    p.stdin.close(); p.wait()
    viejos = (enderezar.deteccion.objetos, enderezar.deteccion.telefono, enderezar.pantalla)
    leidos = []
    enderezar.deteccion.objetos, enderezar.deteccion.telefono = (lambda c: None), (lambda o: None)
    enderezar.pantalla = lambda c, tel: leidos.append(float(c[:, :, 0].mean())) or None
    sys.stdout, real = io.StringIO(), sys.stdout
    try:
        datos = enderezar.analizar(vid)
    finally:
        sys.stdout = real
        enderezar.deteccion.objetos, enderezar.deteccion.telefono, enderezar.pantalla = viejos
    ok(len(datos) == 300 and datos[-1][0] == 59.8, f'a 24 fps debían salir 300 muestras hasta 59.8 s: {len(datos)}, {datos[-1][0] if datos else None}')
    ok(len(leidos) == 300 and abs(leidos[-1] - leidos[-5]) < 1 and leidos[-1] > leidos[-6] + 1,
       'la muestra del segundo 59 debía ser del segundo 59 del video')

    # 4) la frase de los insertos automáticos se encuentra en la voz nueva (texto_voz) y en una voz de antes (texto tal cual)
    for t in ('En xiaomiunlock.com pegas la key', 'Paso cuatro: el botón', 'herramienta , UnlockTool abre', '*Paso* uno, abre'):
        f = enderezar.frase_voz(t)
        ok(buscar(alineacion(texto_voz(t)), f) is not None, f'«{f}» no está en la voz de «{t}»')
        ok(buscar(alineacion(t), f) is not None, f'«{f}» no está en la voz vieja de «{t}»')

    # 5) Flechas y círculos sin ninguna señal que se pueda poner: el video sigue igual, sin fallar
    s = os.path.join(tmp, 'sen')
    os.makedirs(os.path.join(s, 'voz'))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=s=320x180:r=25:d=1', '-pix_fmt', 'yuv420p',
                    os.path.join(s, '5_etiquetas.mp4')], check=True)
    json.dump({'bloques': [{'id': 'L01', 'inicio_min': 0, 'texto': 'hola'}]}, open(os.path.join(s, 'guion.json'), 'w', encoding='utf-8'))
    json.dump([{'bloque': 'L08', 'frase': 'la key', 'tipo': 'flecha', 'x': 10, 'y': 10}], open(os.path.join(s, 'senales.json'), 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, os.path.join(RAIZ, 'senales', 'senales.py'), '--guion', 'guion.json', '--voz', 'voz',
                        '--senales', 'senales.json', '--video', '5_etiquetas.mp4', '--salida', '6_senales.mp4'], cwd=s,
                       capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    ok(r.returncode == 0 and os.path.exists(os.path.join(s, '6_senales.mp4')) and 'no quedó ninguna flecha' in r.stdout,
       f'sin señales que poner no debía fallar: {r.returncode} {r.stdout[-300:]} {r.stderr[-300:]}')

    # 6) «↩ El de la PC»: el sonido de ElevenLabs no se borra
    bib = os.path.join(tmp, 'mis_sonidos')
    os.makedirs(bib)
    open(os.path.join(bib, 'clic.mp3'), 'wb').write(b'pagado')
    vieja = mejoras.sonidos.BIBLIOTECA
    mejoras.sonidos.BIBLIOTECA = bib
    cuerpo = json.dumps({'nombre': 'clic'}).encode()
    h = types.SimpleNamespace(rfile=io.BytesIO(cuerpo), responder=lambda x: x, error=lambda m, c=400: {'error': m})
    try:
        res = mejoras.post(h, '/api/mejoras/sonido_quitar', {}, len(cuerpo), tmp)
    finally:
        mejoras.sonidos.BIBLIOTECA = vieja
    ok(res == {'ok': True} and not os.path.exists(os.path.join(bib, 'clic.mp3'))
       and os.path.exists(os.path.join(bib, 'clic.mp3.eleven')) and open(os.path.join(bib, 'clic.mp3.eleven'), 'rb').read() == b'pagado', f'el sonido pagado debía quedar como .mp3.eleven: {os.listdir(bib)}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión S8a (pistas con Whisper, diagnóstico por paso, pantalla a 5 por segundo, frase de insertos, '
                            'flechas vacías, sonido guardado)')
sys.exit(1 if fallos else 0)
