"""Prueba de la respuesta 8 de fabian (03/11/2026). A «¿Los pasos clave siempre a velocidad normal? (Solo el segundo exacto
del dato: PIN, key, botones)» contestó «SÍ, INCLUSIVE PASOS CLAVE PODRÍAMOS HACERLO UN POQUITÍN MÁS LENTO».
- voz/pasos_clave.py ubica el momento exacto del dato en la transcripción («pegamos la key», «volumen más y power»), sin
  contar lo que se dice como aviso («no toques ningún botón»), y lo marca en el montaje del bloque ("datos");
- el dato va a ×0,9 y lo demás del tramo más rápido, y el tramo dura lo mismo (la voz y el guion siguen cuadrando);
- un paso clave sin el dato ubicado ya no se acelera (tope ×1, antes ×1,5) y, si su voz no cabe, primero va a ×0,9;
- «Generar voz» (voz.ajustar_guion) y la revisión del guion (ia.revisar) bajan lo que iba más rápido y recalculan los
  tiempos (inicio_min) con los largos nuevos; el encargo a la IA pide 0.9 y nunca más de 1;
- el montaje (video sintético con el número de cuadro pintado en gris) muestra el dato a ×0,9 sin mezclar cuadros, lo
  demás más rápido, cada bloque en su cuadro y el video entero dura lo que dice el guion;
- etiquetas, señales, «Alinear», el control de imágenes y el editor de guion cuentan el tiempo igual que el montaje.
Sin internet y sin gastar nada: voces con tiempos falsos, todo en una carpeta temporal (tus proyectos no se tocan).
Uso: python tests/test_dato_sin_acelerar.py   (sale con 1 si algo falla)
"""
import contextlib, io, json, os, re, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('voz', 'ia', 'montaje', 'alinear', 'senales'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ.pop('ELEVENLABS_API_KEY', None)
import pasos_clave as pc  # noqa: E402
import voz  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def cerca(a, b, tol=1e-6):
    return abs(a - b) <= tol


def palabras(*grupos):
    """[(segundo, 'frase')] → transcripción palabra por palabra (0,35 s por palabra)."""
    out = []
    for t, frase in grupos:
        for k, w in enumerate(frase.split()):
            out.append({'texto': w, 'inicio': round(t + 0.35 * k, 2), 'fin': round(t + 0.35 * k + 0.3, 2)})
    return out


TRANSCRIPCION = palabras((10.0, 'Ahora pegamos la key en el campo.'),
                         (30.0, 'Mientras carga no toques ningún botón.'),
                         (50.0, 'Mantenemos volumen más y power.'),
                         (70.0, 'Esperamos que termine de cargar.'),
                         (85.0, 'Mientras tanto les cuento que la key la compran en la página.'))
tmp = tempfile.mkdtemp(prefix='dato sin acelerar ')
try:
    d = os.path.join(tmp, 'proyecto')
    os.makedirs(os.path.join(d, 'voz'))
    json.dump(TRANSCRIPCION, open(os.path.join(d, 'transcripcion.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    # 1) dónde está el dato, según lo que dices
    m = pc.momentos(d)
    ok(len(m) == 3, f'debería encontrar 3 momentos (la key, volumen + power y la key nombrada, no el «no toques ningún botón»): {m}')
    ok([x[2] for x in m] == [True, True, False], f'pegar la key y apretar botones es lo que haces; nombrar la key, no: {m}')
    if len(m) == 3:
        # «pegamos» se dice en 10,35 s y «key» termina en 11,35 s: desde 1 s antes hasta 2 s después, en uno solo
        ok(cerca(m[0][0], 9.35, 0.01) and cerca(m[0][1], 13.35, 0.01), f'la key: desde 1 s antes hasta 2 s después: {m[0]}')
        ok(cerca(m[1][0], 49.35, 0.01) and cerca(m[1][1], 53.7, 0.01), f'volumen y power: {m[1]}')
        ok(cerca(m[2][0], 86.1, 0.01), f'la key nombrada (en 87,1 s): {m[2]}')
    ok(pc.momentos(os.path.join(tmp, 'no existe')) == [], 'sin transcripción no hay momentos')

    def bl(i, a, z, v=1.0, texto='Pegamos la key que compramos.', **extra):
        b_extra = {k: extra.pop(k) for k in ('gancho', 'tipo') if k in extra}
        return {'id': i, 'texto': texto, **b_extra, 'montaje': {'modo': 'lento', 'src_inicio': a, 'src_fin': z, 'velocidad': v, **extra}}

    bloques = [bl('L01', 5.0, 20.0, critico=True), bl('L02', 45.0, 60.0, gancho=True), bl('L03', 45.0, 60.0, cara=True),
               bl('L04', 45.0, 60.0, importante=True, critico=True), bl('L05', 45.0, 60.0, 4.0, texto='Esperamos.'),
               bl('L06', 45.0, 60.0, texto=''), bl('L07', 25.0, 40.0, 3.0, texto='Mientras carga.'),
               bl('L08', 80.0, 95.0, 4.0, texto='Mientras carga.'), bl('L09', 80.0, 95.0, tipo='critico')]
    cambiados = pc.marcar(bloques, m)
    ok(bloques[0]['montaje'].get('datos') == [m[0][:2]], f"L01 debería tener el dato de la key: {bloques[0]['montaje']}")
    ok(bloques[4]['montaje'].get('datos') == [m[1][:2]], f"L05 (una espera) también lleva su dato: {bloques[4]['montaje']}")
    ok(bloques[8]['montaje'].get('datos') == [m[2][:2]], f"L09 (paso clave) cuenta la key solo nombrada: {bloques[8]['montaje']}")
    for k in (1, 2, 3, 5, 6, 7):
        ok('datos' not in bloques[k]['montaje'], f"{bloques[k]['id']} no debería llevar datos (gancho, cara, ⭐, sin voz o sin dato): {bloques[k]}")
    ok(cambiados == ['L01', 'L05', 'L09'] and pc.marcar(bloques, m) == [], f'marcar dos veces no cambia nada más: {cambiados}')

    # 2) topes y piezas: el dato a ×0,9, lo demás más rápido, el tramo dura lo mismo
    ok(pc.tope({'critico': True}) == 1.0 and voz.tope_velocidad({'critico': True}) == 1.0,
       'un paso clave sin el dato ubicado ya no se acelera (antes ×1,5)')
    ok(pc.tope({'paso': True}) == 2.0 and pc.tope({}) == 6.0 and pc.tope({'cara': True}) == 1.0 and pc.tope({'importante': True}) == 1.0,
       'los demás topes de fabian siguen igual')
    mo1 = bloques[0]['montaje']
    t1 = pc.tope(mo1)
    ok(1.2 <= t1 <= 1.3, f'L01 con su dato puede ir hasta ~×1,26 (el dato a ×0,9 y lo demás a ×1,5): ×{t1}')
    for v in (0.95, 1.0, 1.1, t1, 1.4, 1.5):
        ps = pc.piezas(dict(mo1, velocidad=v))
        largo = sum((x1 - x0) / vk for x0, x1, vk in ps)
        ok(cerca(largo, 15.0 / v, 1e-6), f'×{v}: las piezas duran {largo:.4f} s y el tramo {15.0 / v:.4f} s')
        ok(cerca(ps[0][0], 5.0) and cerca(ps[-1][1], 20.0) and all(cerca(a[1], b[0]) for a, b in zip(ps, ps[1:])),
           f'×{v}: las piezas no cubren el tramo de punta a punta: {ps}')
        vd = min(vk for *_, vk in ps)
        if v <= t1:
            ok(len(ps) == 3 and cerca(vd, 0.9) and max(vk for *_, vk in ps) <= 1.5 + 1e-9,
               f'×{v}: el dato debería ir a ×0,9 y lo demás a ×1,5 como mucho: {ps}')
        else:  # más rápido que su tope (un guion de antes): lo demás va todavía más rápido y el dato no pasa de ×1
            ok(vd <= 1.0 + 1e-9, f'×{v}: aunque el bloque vaya rápido, el dato no pasa de ×1: {ps}')
    ok(pc.piezas(dict(mo1, velocidad=0.85)) == [(5.0, 20.0, 0.85)], 'a ×0,85 todo el tramo va parejo (ya es más lento que ×0,9)')
    ok(pc.piezas({'modo': 'lento', 'src_inicio': 5.0, 'src_fin': 20.0, 'velocidad': 1.3}) == [(5.0, 20.0, 1.3)],
       'sin datos, una sola pieza')
    for t in (0.0, 3.0, 4.5, 7.7, 12.0, 15.0 / 1.1):
        s = pc.en_grabacion(dict(mo1, velocidad=1.1), t)
        ok(cerca(pc.en_bloque(dict(mo1, velocidad=1.1), s), t, 1e-6), f'en_grabacion y en_bloque no son inversos en {t}')
    ok(pc.piso({'critico': True}) == 0.9 and pc.piso({}) == 1.0 and pc.piso({'cara': True, 'critico': True}) == 1.0,
       'el piso: ×0,9 en un paso clave, ×1 en lo demás y con tu cara')

    # 3) frenar antes de congelar: un paso clave a ×1 con pausa va a ×0,9 y el bloque dura lo mismo
    b = {'id': 'L08', 'texto': 'Escribimos el PIN de cuatro números.', 'montaje': {'modo': 'lento+congelar', 'src_inicio': 100.0,
                                                                                      'src_fin': 106.0, 'velocidad': 1.0, 'congelar_s': 3.0, 'critico': True}}
    antes = voz.largo_bloque(b['montaje'])
    hecho = voz.frenar_tramo(b)
    ok(b['montaje']['velocidad'] == 0.9 and 'más despacio' in hecho, f'el paso clave debería ir a ×0,9: {b["montaje"]} {hecho}')
    ok(abs(voz.largo_bloque(b['montaje']) - antes) <= 0.011, f'el bloque debería durar lo mismo: {antes} → {voz.largo_bloque(b["montaje"])}')
    b2 = {'id': 'L09', 'texto': 'Esperamos.', 'montaje': {'modo': 'lento+congelar', 'src_inicio': 100.0, 'src_fin': 106.0,
                                                          'velocidad': 1.0, 'congelar_s': 3.0}}
    ok(voz.frenar_tramo(b2) == '' and b2['montaje']['velocidad'] == 1.0, f'un bloque común a ×1 no se frena: {b2}')

    # 4) «Generar voz»: marca los datos, baja lo que iba rápido y los tiempos siguen cuadrando
    g = os.path.join(d, 'guion.json')
    json.dump({'bloques': [bl('L01', 5.0, 20.0, 1.5, critico=True),  # con su dato: baja a su tope
                           bl('L02', 21.0, 28.0, 1.5, critico=True, texto='Copiamos el código.'),  # sin dato dicho: a ×1
                           bl('L03', 45.0, 69.0, 4.0, texto='Esperamos a que entre en modo recuperación.'),
                           bl('L04', 70.0, 80.0, 1.5, texto='Listo.'),
                           # de tipo «clave» sin la marca del guion y con imagen de más: no se acelera para acortarlo
                           bl('L05', 100.0, 112.0, 1.0, tipo='clave', texto='Tocamos el botón de aceptar.')]},
              open(g, 'w', encoding='utf-8'), ensure_ascii=False)
    for bid, s in {'L01': 8.0, 'L02': 5.0, 'L03': 6.0, 'L04': 5.5, 'L05': 3.0}.items():
        json.dump({'characters': list('hola'), 'character_start_times_seconds': [0] * 4, 'character_end_times_seconds': [s] * 4},
                  open(os.path.join(d, 'voz', f'{bid}.align.json'), 'w'))
    avisos = voz.ajustar_guion(g, os.path.join(d, 'voz'))
    r = {x['id']: x for x in json.load(open(g, encoding='utf-8'))['bloques']}
    ok(r['L01']['montaje'].get('datos') and r['L01']['montaje']['velocidad'] <= pc.tope(r['L01']['montaje']),
       f"L01: el dato no puede ir acelerado: {r['L01']['montaje']}")
    ok(min(vk for *_, vk in pc.piezas(r['L01']['montaje'])) <= 0.9 + 1e-9, f"L01: el dato debería ir a ×0,9: {pc.piezas(r['L01']['montaje'])}")
    ok(r['L02']['montaje']['velocidad'] <= 1.0 and 'datos' not in r['L02']['montaje'], f"L02: un paso clave no se acelera: {r['L02']['montaje']}")
    ok(any('L02' in x and 'no puede ir acelerado' in x for x in avisos), f'debería avisar que frenó el paso clave: {avisos}')
    dato3 = pc.piezas(r['L03']['montaje'])
    ok(r['L03']['montaje'].get('datos') and min(vk for *_, vk in dato3) <= 0.9 + 1e-9 and max(vk for *_, vk in dato3) <= 6.0 + 1e-9,
       f"L03 (espera con volumen y power): el dato a ×0,9 y lo demás hasta ×6: {r['L03']['montaje']} {dato3}")
    ok(r['L04']['montaje']['velocidad'] == 1.5 and 'datos' not in r['L04']['montaje'], f"L04 (sin dato) sigue igual: {r['L04']['montaje']}")
    ok(r['L05']['montaje']['velocidad'] <= 1.0, f"L05 (tipo «clave»): no se acelera para quitar la imagen de más: {r['L05']['montaje']}")
    ok(voz.tope_velocidad(voz.de_paso_clave(r['L05'])) == 1.0 and pc.marcar([dict(r['L05'], montaje=dict(r['L05']['montaje'],
       src_inicio=80.0, src_fin=95.0))], m) == ['L05'], 'un bloque de tipo «clave» cuenta como paso clave (como ia.es_critico)')
    t = 0.0
    for x in r.values():  # cada bloque empieza donde termina el anterior, con los largos nuevos
        ok(cerca(x['inicio_min'], round(t, 2), 0.011), f"{x['id']}: inicio_min {x['inicio_min']} y debería ser {t:.2f}")
        ok(x['fin_max'] - x['inicio_min'] >= x['voz_real_s'] + voz.DESFASE - 0.01, f"{x['id']}: la voz no cabe en su bloque: {x}")
        t += voz.largo_bloque(x['montaje'])
    otra = os.path.join(d, 'short_otro.json')  # el guion de otra cosa (Short, tráiler) no se toca
    shutil.copyfile(g, otra)
    ok(voz.con_datos(json.load(open(otra, encoding='utf-8')), otra) == [], 'solo el guion del video lleva datos')

    # 5) la revisión del guion (antes de la voz) hace lo mismo y el encargo a la IA pide 0.9
    import ia  # noqa: E402
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=64x36:r=1', '-t', '150',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
    ia.marcar_caras = lambda d, bloques: []  # sin el detector de caras (no baja nada)
    ia.meta_guion = lambda d, dur, idea=None: (dur, 0, 10 ** 6)
    ia.verificar_orden = lambda d, bloques: []
    texto = ('Ahora pegamos la key que compramos en la página, letra por letra y sin espacios, porque una sola letra mal '
             'y no sirve, así que la copiamos tal cual')
    datos, av = ia.revisar(d, 'guion', {'bloques': [
        {'id': 'L01', 'tipo': 'critico', 'texto': texto, 'montaje': {'modo': 'lento', 'src_inicio': 5.0, 'src_fin': 20.0, 'velocidad': 1.5}},
        {'id': 'L02', 'tipo': 'critico', 'texto': 'Copiamos el código que nos dio la app y lo ponemos aquí abajo.',
         'montaje': {'modo': 'lento', 'src_inicio': 21.0, 'src_fin': 28.0, 'velocidad': 1.5}}]})
    m1, m2 = datos['bloques'][0]['montaje'], datos['bloques'][1]['montaje']
    ok(m1.get('datos') and m1['velocidad'] <= pc.tope(m1) and min(vk for *_, vk in pc.piezas(m1)) <= 0.9 + 1e-9,
       f'la revisión: el dato de L01 a ×0,9: {m1} {av}')
    ok(m2['velocidad'] <= 1.0, f'la revisión: L02 (paso clave sin dato ubicado) ya no va a ×1,5: {m2} {av}')
    t = 0.0
    for x in datos['bloques']:
        ok(cerca(x['inicio_min'], round(t, 1), 0.051), f"revisión, {x['id']}: inicio_min {x['inicio_min']} y debería ser {t:.1f}")
        t += ia.largo_bloque(x['montaje'])
    fuente = open(os.path.join(RAIZ, 'ia', 'ia.py'), encoding='utf-8').read()
    ok(ia.VEL_CRITICO == 1.0 and ia.VEL_DATO == 0.9, f'VEL_CRITICO {ia.VEL_CRITICO}, VEL_DATO {ia.VEL_DATO}')
    ok('máximo 1.5' not in fuente and fuente.count('velocidad {VEL_DATO:g}') >= 2, 'el encargo y la autorrevisión deben pedir 0.9 (nunca más de 1)')

    # 6) los que cuentan el tiempo dentro del bloque lo hacen igual que el montaje
    import alinear, senales  # noqa: E402
    mo = dict(mo1, velocidad=1.1)
    bloque_s = [{'id': 'L01', 'inicio_min': 4.0, 'montaje': mo}]
    for t in (0.5, 4.0, 6.0, 9.5):
        s = pc.en_grabacion(mo, t)
        ok(cerca(alinear.en_tramo(mo, t), s, 1e-9) and cerca(ia.en_grabacion(mo, t)[0], s, 1e-9), f'«Alinear» o ia no cuentan igual en {t}')
        ok(cerca(senales.segundo_grabado(bloque_s, 4.0 + t), round(s, 2), 0.006) and cerca(senales.segundo_montado(bloque_s, s), 4.0 + t, 1e-6),
           f'las señales no cuentan igual en {t}')
    import encuadres  # noqa: E402
    pz = [p for p in encuadres.piezas_del_guion([{'id': 'L01', 'montaje': mo}]) if p['parte'] == 'a'][0]
    ok(cerca(pz['src'](6.0), pc.en_grabacion(mo, 6.0)), 'los encuadres no cuentan igual')
    import montaje  # noqa: E402
    ok(montaje.cadena_tramo({'modo': 'lento', 'src_inicio': 1, 'src_fin': 2, 'velocidad': 1.37}, 'OUT', 'LENTO') == 'setpts=PTS/1.37,OUT',
       'sin datos, el tramo acelerado va con la misma cadena de siempre (los tramos guardados no se rehacen)')
    ok(montaje.cadena_tramo({'modo': 'lento', 'src_inicio': 1, 'src_fin': 2, 'velocidad': 0.9}, 'OUT', 'LENTO') == 'setpts=PTS/0.9,LENTO',
       'más lento que lo grabado, sin «framerate» (no mezcla cuadros)')
    etq = open(os.path.join(RAIZ, 'etiquetas', 'etiquetas.py'), encoding='utf-8').read()
    ok('pasos_clave.en_bloque(mo, s)' in etq, 'las etiquetas de tus capturas tienen que contar el tiempo como el montaje')
    if shutil.which('node'):  # el editor de guion («Frase por frase») hace las mismas cuentas
        html = open(os.path.join(RAIZ, 'app', 'guion.html'), encoding='utf-8').read()
        js = '\n'.join(re.search(r'(?ms)^' + re.escape(x) + r'.*?^}\n', html).group(0) for x in
                       ('function ventanasDato(m)', 'function piezasTramo(m)', 'function enGrabacion(m, t)'))
        casos = [dict(mo1, velocidad=v) for v in (0.95, 1.0, 1.1, 1.3, 1.4, 3.0)] + [r['L03']['montaje']]
        f = os.path.join(tmp, 'guion_js.js')
        open(f, 'w', encoding='utf-8').write('const VEL_DATO = 0.9;\n' + js + f'\nconst casos = {json.dumps(casos)};\n'
                                             'console.log(JSON.stringify(casos.map(m => [piezasTramo(m), [0.5, 3, 7.5].map(t => enGrabacion(m, t)[0])])));')
        res = json.loads(subprocess.run(['node', f], capture_output=True, text=True, encoding='utf-8', check=True).stdout)
        for c, (ps_js, en_js) in zip(casos, res):
            ps = pc.piezas(c)
            ok(len(ps) == len(ps_js) and all(cerca(a, b, 1e-9) for p, q in zip(ps, ps_js) for a, b in zip(p, q)),
               f'el editor reparte distinto que el montaje: {ps} / {ps_js}')
            dentro = [(t, e) for t, e in zip((0.5, 3, 7.5), en_js) if t <= (c['src_fin'] - c['src_inicio']) / c['velocidad']]
            ok(all(cerca(pc.en_grabacion(c, t), e, 1e-9) for t, e in dentro), f'el editor cuenta distinto: {en_js} ({c})')

    # 7) el montaje de verdad: el número de cuadro va pintado en gris (dos cuadros: unidades y grupos de 25)
    import cv2  # noqa: E402
    import numpy as np  # noqa: E402
    montaje._DETECTOR.append(None)  # sin el detector de caras (no se baja nada de internet)
    FPS = 30
    dm = os.path.join(tmp, 'montaje')
    os.makedirs(dm)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    "nullsrc=s=160x90:r=30:d=20,format=yuv420p,geq=lum='if(lt(X,W/2),16+8*mod(N,25),16+8*floor(N/25))':cb=128:cr=128",
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '0', os.path.join(dm, 'original.mp4')], check=True)

    def leer(f):
        cap, out = cv2.VideoCapture(f), []
        while True:
            okc, c = cap.read()
            if not okc:
                break
            h, w = c.shape[:2]
            out.append((float(c[int(h * .3):int(h * .7), int(w * .1):int(w * .4)].mean()),
                        float(c[int(h * .3):int(h * .7), int(w * .6):int(w * .9)].mean())))
        cap.release()
        return np.array(out)
    src = leer(os.path.join(dm, 'original.mp4'))
    n = np.arange(len(src))
    # de gris a número (calibrado con la grabación misma: así no importa cómo convierte los colores el lector)
    ka, kb = np.polyfit(n % 25, src[:, 0], 1)
    ha, hb = np.polyfit(n // 25, src[:, 1], 1)

    def cuadro(x):
        lo, hi = (x[:, 0] - kb) / ka, (x[:, 1] - hb) / ha
        # los grupos de 25 son enteros salvo en un cuadro mezclado justo al pasar de grupo (ahí la mezcla sigue la cuenta)
        return lo + 25 * np.where(np.abs(hi - np.round(hi)) < 0.2, np.round(hi), hi)
    ok(np.abs(cuadro(src) - n).max() < 0.3, 'no pude leer el número de cuadro de la grabación sintética')
    guion = [{'id': 'L01', 'ancla': 'uno', 'texto': '', 'montaje': {'modo': 'lento', 'src_inicio': 1.0, 'src_fin': 5.0, 'velocidad': 1.0}},
             {'id': 'L02', 'ancla': 'la key', 'texto': '', 'montaje': {'modo': 'lento', 'src_inicio': 6.0, 'src_fin': 16.0, 'velocidad': 1.0,
                                                                     'critico': True, 'datos': [[9.0, 12.0]]}},
             {'id': 'L03', 'ancla': 'lento', 'texto': '', 'montaje': {'modo': 'lento', 'src_inicio': 16.5, 'src_fin': 19.5, 'velocidad': 0.9}}]
    t = 0.0
    for x in guion:
        x['inicio_min'] = round(t, 2)
        t += montaje.largo_tramo(x['montaje'])
        x['fin_max'] = round(t, 2)
    json.dump({'bloques': guion}, open(os.path.join(dm, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    antes, argv, salida = os.getcwd(), sys.argv, io.StringIO()
    os.chdir(dm)
    try:
        sys.argv = ['montaje.py', '--original', 'original.mp4', '--guion', 'guion.json', '--salida', '1_montaje.mp4', '--calidad', '360']
        with contextlib.redirect_stdout(salida):
            montaje.main()
    finally:
        sys.argv = argv
        os.chdir(antes)
    log = salida.getvalue()
    ok('L02 · el dato (0:09.0–0:12.0) va a ×0,90 y lo demás del tramo a ×1,05' in log, f'el paso debería decir cómo va el dato:\n{log}')
    ok('AVISO montaje' not in log and not os.path.exists(os.path.join(dm, montaje.AVISOS_MONTAJE)), f'el montaje avisó:\n{log}')
    vid = leer(os.path.join(dm, '1_montaje.mp4'))
    ok(abs(len(vid) - round(t * FPS)) <= 1, f'el video tiene {len(vid)} cuadros y el guion dice {round(t * FPS)}')
    num = cuadro(vid) if len(vid) else np.zeros(0)

    def pendiente(desde, hasta):
        k = np.arange(desde, hasta)
        return float(np.polyfit(k, num[desde:hasta], 1)[0])
    # L02 empieza en el cuadro 120; su dato, 2,857 s después (6,0–9,0 a ×1,05): cuadros 206 a 305
    ok(len(num) >= 515, f'el video armado quedó corto: {len(num)} cuadros')
    if len(num) >= 515:
        ok(abs(num[120] - 6.0 * FPS) <= 1.5 and abs(num[420] - 16.5 * FPS) <= 1.5,
           f'L02 o L03 no empiezan en su cuadro: L02 muestra el {num[120]:.1f} (debería 180), L03 el {num[420]:.1f} (495)')
        p_dato, p_antes, p_despues = pendiente(210, 302), pendiente(124, 202), pendiente(310, 414)
        ok(abs(p_dato - 0.9) <= 0.02, f'el dato debería ir a ×0,9 y va a ×{p_dato:.3f}')
        ok(abs(p_antes - 1.05) <= 0.03 and abs(p_despues - 1.05) <= 0.03, f'lo demás debería ir a ×1,05: ×{p_antes:.3f} y ×{p_despues:.3f}')
        ok(abs(num[206] - 9.0 * FPS) <= 1.5, f'el dato debería empezar en el segundo 9 de la grabación: cuadro {num[206]:.1f}')
        enteros = lambda x: float(np.mean(np.abs(x - np.round(x)) <= 0.25))  # noqa: E731
        ok(enteros(num[210:302]) >= 0.9 and enteros(num[425:515]) >= 0.9,
           f'a ×0,9 los cuadros no se mezclan (se repiten): {enteros(num[210:302]):.0%} y {enteros(num[425:515]):.0%} enteros')
        ok(abs(pendiente(425, 515) - 0.9) <= 0.02, f'L03 a ×0,9 va a ×{pendiente(425, 515):.3f}')
        print(f'montaje: el dato va a ×{p_dato:.3f} ({enteros(num[210:302]):.0%} de cuadros sin mezclar), lo demás a ×{p_antes:.3f} '
              f'y ×{p_despues:.3f}; L03 a ×{pendiente(425, 515):.3f}; {len(vid)} cuadros (guion {round(t * FPS)})')

    # 8) con cambio de encuadre (la misma toma hace más de 15 s) las piezas también llegan justo a sus cuadros
    out = 'scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,framerate=fps=30,fps=30,format=yuv420p'
    cadena = montaje.cadena_tramo(guion[1]['montaje'], out, out.replace('framerate=fps=30,', ''))
    ok(cadena.startswith('split=3') and 'concat=n=3' in cadena, f'el tramo con su dato debería ir en 3 piezas: {cadena}')
    hechos = montaje.con_encuadres(['-ss', '6.0', '-t', '10.0', '-i', os.path.join(dm, 'original.mp4'), '-an'], cadena,
                                   [(0.0, 4.0, 1.0, 0.5, 0.5), (4.0, 10.0, 1.35, 0.5, 0.5)], FPS, (640, 360), 'format=yuv420p',
                                   ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26'], os.path.join(dm, 'enc'), 300)
    ok([montaje.cuadros_de(f) for f in hechos] == [120, 180], f'los encuadres no llegan a sus cuadros: {[montaje.cuadros_de(f) for f in hechos]}')
    num = cuadro(leer(hechos[0]))
    ok(len(num) == 120 and abs(float(np.polyfit(np.arange(90, 118), num[90:118], 1)[0]) - 0.9) <= 0.03,
       'con cambio de encuadre el dato también va a ×0,9')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLAS:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: el dato (PIN, key, botones) nunca va acelerado: a ×0,9, lo demás más rápido y el bloque dura lo mismo; '
      'pasos clave sin dato ubicado a ×1 como mucho; voz, revisión, montaje y editor cuentan igual')
