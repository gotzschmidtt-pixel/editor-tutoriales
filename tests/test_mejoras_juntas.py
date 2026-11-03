"""Prueba de que las mejoras 2, 3 y 4 conviven en el mismo guion (03/11/2026, al unir sus ramas). Sin internet y sin gastar
nada: el lector de texto (OCR) va simulado, las voces son tiempos falsos (no se llama a ElevenLabs) y el video es sintético.
- «Alinear» (mejora 2) no mueve un bloque del gancho (mejora 4), y sí lo movería sin la marca (así se ve que la prueba mide);
- «frenar antes de congelar» (mejora 3) no frena un bloque del gancho ni uno que corrió «Alinear» ("alineado"), ni con la
  voz real (voz.ajustar_guion) ni con la estimada (ia.revisar); un bloque igual sin esas marcas sí se frena;
- después de las dos, rotar.py pone las tomas del gancho en su pausa con los cuadros justos y montaje.py arma el video con
  los cuadros que suman sus bloques.
Uso: python tests/test_mejoras_juntas.py   (sale con 1 si algo falla)
"""
import copy, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('alinear', 'voz', 'ia', 'montaje'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
for k in ('VOZ_ID', 'VOZ_IDIOMA', 'ELEVENLABS_API_KEY'):
    os.environ.pop(k, None)
import alinear  # noqa: E402
import ia  # noqa: E402
import rotar  # noqa: E402
import voz  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def voz_de(d, bid, frases):
    """align.json falso: [(frase, desde, hasta)] con los tiempos repartidos letra por letra. Devuelve el texto dicho."""
    chars, t0s, t1s = [], [], []
    for k, (txt, a, z) in enumerate(frases):
        txt = (' ' if k else '') + txt
        for i, ch in enumerate(txt):
            chars.append(ch)
            t0s.append(round(a + (z - a) * i / len(txt), 3))
            t1s.append(round(a + (z - a) * (i + 1) / len(txt), 3))
    json.dump({'characters': chars, 'character_start_times_seconds': t0s, 'character_end_times_seconds': t1s},
              open(os.path.join(d, 'voz', bid + '.align.json'), 'w', encoding='utf-8'))
    return ''.join(chars)


def alinear_main(*args):
    viejo = sys.argv
    sys.argv = ['alinear.py'] + list(args)
    try:
        alinear.main()
    finally:
        sys.argv = viejo


tmp = tempfile.mkdtemp(prefix='mejoras_juntas_')
viejo_cwd = os.getcwd()
try:
    # 1. «Alinear» y el gancho: un video de 70 s con 7 pantallas (cada color, un texto) y el OCR simulado
    PANTALLAS = [  # (desde, color RGB, texto que «se lee»)
        (0.0, (0, 0, 0), 'Candado bloqueado'), (7.3, (255, 0, 0), 'Pantalla principal'),
        (19.3, (0, 255, 0), 'Configuracion general'), (25.3, (0, 0, 255), 'Reiniciar dispositivo'),
        (32.3, (255, 255, 0), 'Copiando archivos'), (41.3, (255, 0, 255), 'Listo terminado'),
        (47.3, (0, 255, 255), 'Pantalla final gracias')]

    def leer_textos(ocr, img):  # el OCR simulado: el texto de la pantalla del color más parecido
        b, g, r = (float(img[..., k].mean()) for k in range(3))
        return [(min(PANTALLAS, key=lambda p: sum((x - y) ** 2 for x, y in zip(p[1], (r, g, b))))[2], 0, 0, 10, 10)]
    ia.lector_ocr, ia.leer_textos = (lambda: object()), leer_textos

    def proyecto(nombre, gancho):
        d = os.path.join(tmp, nombre)
        os.makedirs(os.path.join(d, 'voz'))
        vf = ','.join(f"drawbox=x=0:y=0:w=iw:h=ih:t=fill:color=0x{r:02X}{g:02X}{b:02X}:enable='gte(t,{t0})'"
                      for t0, (r, g, b), _ in PANTALLAS[1:])
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=320x180:r=30:d=70',
                        '-vf', vf, '-c:v', 'libx264', '-g', '30', '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
        json.dump({'cuadros': [{'t': t0, 'texto': txt} for t0, _, txt in PANTALLAS]},
                  open(os.path.join(d, 'mapa_video.json'), 'w', encoding='utf-8'))
        l01 = {'id': 'L01', 'avatar': False,  # el gancho: su frase nombra una pantalla que se ve más adelante, a propósito
               'texto': voz_de(d, 'L01', [('Así queda la pantalla principal del telefono.', 0, 3.0),
                                          ('Esperamos copiando archivos.', 3.21, 6.0)]),
               'tomas': [[48.0, 52.0], [33.0, 37.0]], 'por_que': ['ya libre', 'el proceso'],
               # una pausa que no cae justo en un cuadro (6,02 s = 180,6): el último trozo pone el cuadro que falta
               'montaje': {'modo': 'lento+congelar', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0, 'congelar_s': 6.02,
                           'repetir': 'ida_vuelta'}}
        if gancho:
            l01['gancho'] = True
        bloques = [l01,
                   {'id': 'L02', 'texto': voz_de(d, 'L02', [('Abrimos la configuracion general y esperamos un momento.', 0, 7.0)]),
                    'montaje': {'modo': 'lento', 'src_inicio': 10.0, 'src_fin': 18.0, 'velocidad': 1.0}},
                   {'id': 'L03', 'texto': voz_de(d, 'L03', [('Y eso es todo por hoy amigos.', 0, 4.5)]),
                    'montaje': {'modo': 'lento', 'src_inicio': 40.0, 'src_fin': 46.0, 'velocidad': 1.0}}]
        json.dump({'bloques': bloques}, open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return d, bloques

    dc, _ = proyecto('sin_gancho', gancho=False)  # el mismo guion sin marcar el gancho: «Alinear» sí corre L01
    alinear_main('--proyecto', dc)
    g = {b['id']: b for b in json.load(open(os.path.join(dc, 'guion.json'), encoding='utf-8'))['bloques']}
    ok(g['L01']['montaje'].get('alineado') is True, f'sin "gancho", «Alinear» debería correr L01 (prueba mal armada): {g["L01"]["montaje"]}')

    d, bloques = proyecto('con_gancho', gancho=True)
    alinear_main('--proyecto', d)
    g = {b['id']: b for b in json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']}
    mo1, mo2 = g['L01']['montaje'], g['L02']['montaje']
    ok({k: mo1[k] for k in bloques[0]['montaje']} == bloques[0]['montaje'] and 'alineado' not in mo1,
       f'«Alinear» no debería mover el bloque del gancho: {mo1}')
    ok(g['L01'].get('gancho') is True and g['L01'].get('tomas') == bloques[0]['tomas'], f'el gancho conserva sus tomas: {g["L01"]}')
    ok(mo2.get('alineado') is True, f'L02 (bloque normal) sí debería quedar alineado: {mo2}')
    ok(mo2['src_inicio'] >= 1.0, f'L02 no debería pisar el tramo del gancho (0-1 s): {mo2}')

    # 2. «frenar antes de congelar» con las marcas que dejaron «Alinear» (L02) y el gancho (L01), con la voz real
    TEXTO = 'Esperamos a que termine de borrar y se reinicie el teléfono solo.'
    df = os.path.join(tmp, 'frenar')
    os.makedirs(os.path.join(df, 'voz'))
    acelerado = {'modo': 'lento+congelar', 'velocidad': 3.0, 'congelar_s': 3.7}  # como antes: ×3 + 3,7 s de pausa
    fb = []
    for k, b in enumerate((g['L01'], g['L02'], dict(copy.deepcopy(g['L02']), id='L09'))):
        b = copy.deepcopy(b)
        b.pop('voz_real_s', None)  # voz nueva: no es un bloque ya ajustado con su voz (los «fijos»)
        b['texto'] = voz_de(df, b['id'], [(TEXTO, 0, 13.0)])
        b['montaje'].update(acelerado, src_inicio=100.0 + 40 * k, src_fin=130.0 + 40 * k)
        fb.append(b)
    fb[2]['montaje'].pop('alineado')  # el testigo: el mismo bloque sin marcas sí se frena
    json.dump({'bloques': fb}, open(os.path.join(df, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    avisos = voz.ajustar_guion(os.path.join(df, 'guion.json'), os.path.join(df, 'voz'))
    r = {b['id']: b['montaje'] for b in json.load(open(os.path.join(df, 'guion.json'), encoding='utf-8'))['bloques']}
    for bid, que in (('L01', 'del gancho'), ('L02', 'corrido por «Alinear»')):
        ok(r[bid]['velocidad'] == 3.0 and r[bid]['congelar_s'] == 3.7 and not any(x.startswith(bid + ':') for x in avisos),
           f'voz.ajustar_guion no debería frenar el bloque {que}: {r[bid]} {avisos}')
    ok(r['L09']['velocidad'] < 3.0 and not r['L09'].get('congelar_s'), f'el testigo sin marcas sí se frena: {r["L09"]} {avisos}')

    # … y con la voz estimada, en la revisión del guion (antes de pagar la voz)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=64x36:r=1', '-t', '240',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', os.path.join(df, 'original.mp4')], check=True)
    ia.marcar_caras = lambda d, bloques: []  # sin el detector de caras (no baja nada)
    ia.meta_guion = lambda d, dur, idea=None: (dur, 0, 10 ** 6)  # sin el ajuste del largo total: se mira solo cada bloque
    largos = [' '.join([x] * 2 + ['y seguimos con el siguiente bloque'])  # 40 palabras: unos 16 s estimados (no caben en 10 s)
              for x in ('Ahora vemos cómo el teléfono vuelve a arrancar solo después de borrar todo lo que tenía guardado',
                        'Mientras tanto la barra de progreso avanza despacio y el programa nos muestra cada paso que hace',
                        'Aquí la pantalla se apaga un momento y después aparece el logo de la marca mientras todo carga')]
    rb = []
    for b, largo in zip(copy.deepcopy(fb), largos):
        b['texto'] = largo
        b['montaje'] = dict(b['montaje'], modo='lento', congelar_s=None)
        rb.append(b)
    datos, avisos = ia.revisar(df, 'guion', {'bloques': rb})
    r = {b['id']: b['montaje'] for b in datos['bloques']}
    for bid, que in (('L01', 'del gancho'), ('L02', 'corrido por «Alinear»')):
        ok(r[bid]['velocidad'] == 3.0 and not any(x.startswith(bid + ':') and 'más despacio' in x for x in avisos),
           f'ia.revisar no debería frenar el bloque {que}: {r[bid]} {avisos}')
    ok(r['L09']['velocidad'] < 3.0 and any(x.startswith('L09:') and 'más despacio' in x for x in avisos),
       f'ia.revisar sí frena el testigo sin marcas: {r["L09"]} {avisos}')

    # 3. después de «Alinear»: rotar.py pone las tomas del gancho con los cuadros justos y montaje.py cuenta bien los cuadros
    os.chdir(d)  # avisos_inicio.json se escribe en la carpeta del proyecto (montaje.py corre ahí)
    voz.ajustar_guion(os.path.join(d, 'guion.json'), os.path.join(d, 'voz'))  # los tiempos de cada bloque (inicio_min, fin_max)
    gl = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    for b in gl['bloques']:  # sin el detector de caras (no baja nada): las pausas, de ida y vuelta
        b['montaje']['repetir'] = 'ida_vuelta'
    json.dump(gl, open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    l01 = gl['bloques'][0]
    plan = rotar.planear(gl['bloques'], os.path.join(d, 'mapa_video.json'), os.path.join(d, 'voz'), 70.0, 30)
    ok([s for s, _ in plan.get('L01', [])][:1] == [48.0], f'la pausa del gancho debería empezar con la toma 1 de la IA (48 s): {plan}')
    ok(sum(n for _, n in plan.get('L01', [])) == int(round(l01['montaje']['congelar_s'] * 30)),
       f'los trozos del gancho deberían sumar justo los cuadros de su pausa ({l01["montaje"]["congelar_s"]} s): {plan}')
    hecho = subprocess.run([sys.executable, os.path.join(RAIZ, 'montaje', 'montaje.py'), '--original', 'original.mp4', '--guion',
                            'guion.json', '--salida', '1_montaje.mp4', '--calidad', '360'], cwd=d, capture_output=True, text=True,
                           timeout=240)
    ok(hecho.returncode == 0, f'montaje.py falló: {hecho.stderr[-400:]}')
    if hecho.returncode == 0:
        n = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                            'stream=nb_read_frames', '-of', 'csv=p=0', os.path.join(d, '1_montaje.mp4')],
                           capture_output=True, text=True).stdout.strip()
        total = int(round(float(gl['bloques'][-1]['fin_max']) * 30))
        ok(n == str(total), f'el montaje debería tener justo los cuadros de sus bloques ({total}): {n}')
finally:
    os.chdir(viejo_cwd)
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: las mejoras conviven (el gancho no lo mueve «Alinear» ni lo frena la mejora 3, lo alineado '
                         'no se frena, y las tomas y el montaje cuentan los cuadros justos)')
sys.exit(1 if fallos else 0)
