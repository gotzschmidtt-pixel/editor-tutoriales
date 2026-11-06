"""Revisión de «Alinear cada frase con su pantalla» dentro de «▶ Hacer todo» (03/11/2026). Sin internet y sin gastar nada:
el lector de texto (OCR) va simulado sobre un video sintético de colores y tus ajustes no se tocan (todo en una carpeta
temporal).
- una pausa sola («congelar») entre dos tramos es vecina: el tramo de antes no se corre por encima de ella;
- la pausa que repite un momento de un tramo sigue dentro de ese tramo (si no, se veía algo de antes, fuera de orden);
- un tramo no se corre encima de un «⭐ corte importante» de cortes_importantes.json (va entero y a ×1), aunque el
  bloque no esté marcado "importante";
- el último bloque llega hasta donde ya llegaba (antes perdía hasta 2 s de su final);
- si ajustes.json está trabado (Windows) al anotar los videos que solo avisan, «Hacer todo» no se corta.
Uso: python tests/test_alinear_pausas_estrellas.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('alinear', 'voz', 'ia', 'app'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ['SIN_NAVEGADOR'] = '1'
for k in ('VOZ_ID', 'VOZ_IDIOMA', 'ELEVENLABS_API_KEY'):
    os.environ.pop(k, None)
import alinear  # noqa: E402
import ia  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp(prefix='alinear_pausas_')
try:
    # 1) ajustar(): la frase dice algo que se ve 30 s más adelante (en 130 s)
    rev = [('frase uno', 1.0, 101.0, 'uno', 100.0), ('frase dos', 6.0, 106.0, 'dos', 130.0)]
    normal = lambda **x: {'id': 'L09', 'montaje': dict({'modo': 'lento', 'src_inicio': 100.0, 'src_fin': 112.0, 'velocidad': 1.0}, **x)}
    n = alinear.ajustar(normal(), rev, 95.0, 140.0)
    ok(n and n['src_fin'] > 120, f'sin ⭐ ni pausas el tramo sí se corre: {n}')
    ok(alinear.ajustar(normal(), rev, 95.0, 140.0, [{'inicio': 125.0, 'fin': 128.0}]) is None,
       'no se corre encima de un ⭐ que ningún bloque mostraba (quedaba acelerado)')
    ok(alinear.ajustar(normal(), rev, 95.0, 140.0, [{'inicio': 104.0, 'fin': 106.0}]) is None,
       'un bloque que muestra un ⭐ no se toca aunque no esté marcado "importante"')
    n = alinear.ajustar(normal(), rev, 95.0, 140.0, [{'inicio': 300.0, 'fin': 310.0}])
    ok(n is not None, f'un ⭐ lejos no lo frena: {n}')
    una = [('frase', 1.0, 101.0, 'x', 110.0)]  # una sola frase: el tramo pasa a empezar en 109 s
    ok(alinear.ajustar(normal(), una, 95.0, 140.0, (), [101.0]) is None,
       'la pausa que repite un momento del tramo (101 s) tiene que seguir dentro del tramo corrido')
    n = alinear.ajustar(normal(), una, 95.0, 140.0, (), [111.0])
    ok(n and n['src_inicio'] <= 111.0 <= n['src_fin'], f'si la pausa sigue dentro, sí se corre: {n}')

    # 2) de punta a punta: un video de 70 s con 8 pantallas (cada color, un texto) y el OCR simulado
    PANTALLAS = [  # (desde, color RGB, texto que «se lee»)
        (0.0, (0, 0, 0), 'Candado bloqueado'), (7.3, (255, 0, 0), 'Pantalla principal'),
        (19.3, (0, 255, 0), 'Configuracion general'), (25.3, (0, 0, 255), 'Reiniciar dispositivo'),
        (32.3, (255, 255, 0), 'Copiando archivos'), (41.3, (255, 0, 255), 'Listo terminado'),
        (52.3, (0, 255, 255), 'Ultima pantalla'), (60.3, (255, 255, 255), 'Gracias por mirar')]
    video = os.path.join(tmp, 'original.mp4')
    vf = ','.join(f"drawbox=x=0:y=0:w=iw:h=ih:t=fill:color=0x{r:02X}{g:02X}{b:02X}:enable='gte(t,{t0})'"
                  for t0, (r, g, b), _ in PANTALLAS[1:])
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=160x90:r=10:d=70',
                    '-vf', vf, '-c:v', 'libx264', '-g', '10', '-pix_fmt', 'yuv420p', video], check=True)

    def leer_textos(ocr, img):  # el OCR simulado: el texto de la pantalla del color más parecido
        b, g, r = (float(img[..., k].mean()) for k in range(3))
        return [(min(PANTALLAS, key=lambda p: sum((x - y) ** 2 for x, y in zip(p[1], (r, g, b))))[2], 0, 0, 10, 10)]
    ia.lector_ocr, ia.leer_textos = (lambda: object()), leer_textos

    def proyecto(nombre, bloques, estrellas=None):
        """Carpeta con el video, el guion y un align.json falso por bloque (no se llama a ElevenLabs)."""
        d = os.path.join(tmp, nombre)
        os.makedirs(os.path.join(d, 'voz'))
        shutil.copy(video, d)
        for b in bloques:
            frases = b.pop('frases')
            chars, t0s, t1s = [], [], []
            for k, (txt, a, z) in enumerate(frases):
                txt = (' ' if k else '') + txt
                for i, ch in enumerate(txt):
                    chars.append(ch)
                    t0s.append(round(a + (z - a) * i / len(txt), 3))
                    t1s.append(round(a + (z - a) * (i + 1) / len(txt), 3))
            json.dump({'characters': chars, 'character_start_times_seconds': t0s, 'character_end_times_seconds': t1s},
                      open(os.path.join(d, 'voz', b['id'] + '.align.json'), 'w', encoding='utf-8'))
            b['texto'] = ''.join(chars)
        json.dump({'bloques': bloques}, open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if estrellas:
            json.dump(estrellas, open(os.path.join(d, 'cortes_importantes.json'), 'w', encoding='utf-8'))
        viejo = sys.argv
        sys.argv = ['alinear.py', '--proyecto', d]
        try:
            alinear.main()
        finally:
            sys.argv = viejo
        return ({b['id']: b['montaje'] for b in json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']},
                open(os.path.join(d, 'alineacion.txt'), encoding='utf-8').read())

    lento = lambda a, z: {'modo': 'lento', 'src_inicio': a, 'src_fin': z, 'velocidad': 1.0}
    g, txt = proyecto('pausas', [
        {'id': 'L01', 'frases': [('Este es el candado bloqueado.', 0, 3.0)], 'montaje': lento(0.0, 6.0)},
        # «reiniciar dispositivo» se ve desde 25,3 s, pero entre medio está la pausa L03 (21 s)
        {'id': 'L02', 'frases': [('Ahora tocamos reiniciar dispositivo y esperamos.', 0, 5.0)], 'montaje': lento(12.0, 18.0)},
        {'id': 'L03', 'frases': [('Mira la configuracion general un momento.', 0, 3.0)],
         'montaje': {'modo': 'congelar', 'src_inicio': 21.0, 'congelar_s': 4.0}},
        # «listo terminado» se ve desde 41,3 s; la pausa L04b (35 s) repite un momento de este tramo
        {'id': 'L04', 'frases': [('Ahora sale listo terminado.', 0, 2.0)], 'montaje': lento(30.0, 40.0)},
        {'id': 'L04b', 'frases': [('Fijate bien en esto.', 0, 2.0)], 'montaje': {'modo': 'congelar', 'src_inicio': 35.0, 'congelar_s': 3.0}},
        # el último: «ultima pantalla» se ve desde 52,3 s; el tramo llega hasta 69,5 s
        {'id': 'L05', 'frases': [('Y llegamos a la ultima pantalla.', 0, 2.0)], 'montaje': lento(44.0, 69.5)}])
    ok(g['L02']['src_fin'] <= 21.0 and 'alineado' not in g['L02'],
       f'L02 no se corre por encima de la pausa L03 (21 s), que quedaría mostrando algo de antes: {g["L02"]}')
    ok(g['L03'] == {'modo': 'congelar', 'src_inicio': 21.0, 'congelar_s': 4.0} or g['L03']['src_inicio'] == 21.0,
       f'la pausa L03 no se mueve: {g["L03"]}')
    ok(g['L04']['src_inicio'] <= 35.0 <= g['L04']['src_fin'],
       f'la pausa L04b (35 s) sigue dentro del tramo de L04: {g["L04"]}')
    ok('L04: «Ahora sale listo terminado.» nombra «listo terminado»' in txt,
       f'lo que no pudo correr queda como aviso en alineacion.txt: {txt}')
    ok(g['L05'].get('alineado') and g['L05']['src_inicio'] >= 52.0 and 69.0 <= g['L05']['src_fin'] <= 69.5,
       f'el último bloque se corre y llega hasta donde ya llegaba (69,5 s), no hasta la última lectura (68 s): {g["L05"]}')

    g, txt = proyecto('estrella', [
        {'id': 'L01', 'frases': [('Este es el candado bloqueado.', 0, 3.0)], 'montaje': lento(0.0, 6.0)},
        {'id': 'L02', 'frases': [('Ahora tocamos reiniciar dispositivo y esperamos.', 0, 5.0)], 'montaje': lento(12.0, 18.0)},
        {'id': 'L04', 'frases': [('Esperamos copiando archivos.', 0, 3.0)], 'montaje': lento(33.0, 40.0)}],
        [{'inicio': 26.0, 'fin': 30.0, 'nota': 'entrar a Recovery'}])
    ok(g['L02'] == lento(12.0, 18.0), f'L02 no se corre encima del ⭐ de 26 a 30 s: {g["L02"]}')
    ok('L02: «Ahora tocamos reiniciar dispositivo' in txt and 'no se ve; aparece en' in txt,
       f'la frase queda como aviso para que la veas: {txt}')

    # 3) la app: ajustes.json trabado al anotar los videos que solo avisan
    import app  # noqa: E402
    app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
    json.dump({'modelo': 'x'}, open(app.AJUSTES, 'w'))
    reemplazar = app.os.replace

    def trabado(a, b):  # como Windows cuando otro programa tiene abierto ajustes.json
        raise PermissionError(13, 'El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso')
    app.os.replace = trabado
    try:
        c = app.comandos('alinear', os.path.join(tmp, 'VIDEO A'), {})
    except OSError as e:
        c = None
        ok(False, f'con ajustes.json trabado «Hacer todo» se cortaba: {e}')
    finally:
        app.os.replace = reemplazar
    ok(c and '--solo-revisar' in c[0], f'igual va en modo solo avisar: {c}')
    ok(json.load(open(app.AJUSTES, encoding='utf-8')) == {'modelo': 'x'}, 'ajustes.json queda como estaba')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: «Alinear» respeta las pausas, los ⭐ y el final del último bloque')
sys.exit(1 if fallos else 0)
