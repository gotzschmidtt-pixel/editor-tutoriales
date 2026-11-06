"""Tomas de la pantalla de la PC en los «📱 3 Shorts resumen», sin ffmpeg ni OCR de verdad: qué momento elige según la voz, que no
use nada después de un intento fallido, los círculos, el zoom en el comando y que sin material.mp4 todo siga igual."""
import json, os, shutil, sys, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'short'))
import material_pc as mp  # noqa: E402
import resumen  # noqa: E402


def linea(texto, x0, y0, x1, y1):
    return [texto, x0, y0, x1, y1]


PROGRAMA = [linea('Read Fastboot Info', .5, .3, .6, .32), linea('Erase FRP By Code', .47, .42, .55, .44), linea('Clear Log', .5, .46, .6, .48)]
DATOS = [linea('Device Model: MTN-NX3', .3, .36, .4, .38), linea('Device Firmware: X', .3, .39, .4, .41),
         linea('Device Fastboot SN:', .31, .59, .39, .61), linea('SERIAL0000000000', .31, .61, .39, .62)]
WEB = [linea('Honor FRP Unlock Key Code (Instant)', .24, .33, .6, .36), linea('Key:', .52, .49, .54, .53), linea('SGUC', .52, .54, .62, .56)]
CUADROS = [{'t': 40, 'c': PROGRAMA}, {'t': 70, 'c': PROGRAMA + DATOS},
           {'t': 200, 'c': [linea('Place Order', .2, .5, .3, .52)]}, {'t': 210, 'c': [linea('Place Order', .2, .5, .3, .52)]},
           {'t': 212, 'c': [linea('Place Order', .2, .5, .3, .52)]}, {'t': 214, 'c': [linea('Place Order', .2, .5, .3, .52)]},
           {'t': 216, 'c': [linea('Place Order', .2, .5, .3, .52)]}, {'t': 218, 'c': [linea('Place Order', .2, .5, .3, .52)]},
           {'t': 818, 'c': WEB}, {'t': 860, 'c': PROGRAMA},
           {'t': 888, 'c': PROGRAMA + [linea('SGUCFOUK75TGJ721', .56, .42, .64, .44)]},
           {'t': 998, 'c': PROGRAMA + [linea('FAILED', .3, .3, .35, .32), linea('Device Model', .3, .35, .4, .37), linea('Device Firmware', .3, .4, .4, .42)]}]

m = mp.momentos(CUADROS)
assert m['leer']['src'] == 66 and m['datos']['src'] == 71, m
assert m['key']['src'] == 819, m['key']
assert m['pega']['src'] == 886.5, m['pega']  # 1,5 s antes de que aparezca la KEY pegada
assert m['web']['src'] == 200
assert m['datos']['senales'][0]['tipo'] == 'circulo' and abs(m['datos']['senales'][0]['cy'] - .605) < .01, m['datos']
assert m['key']['senales'] and m['key2']['senales'] == m['key']['senales']
# nada después de un intento fallido: si solo hay datos tras el FAILED, no se usan
assert 'leer' not in mp.momentos([{'t': 5, 'c': [linea('FAILED', 0, 0, .1, .1)]}, CUADROS[1]])

# la voz decide la toma; el clic y el OKAY siguen en la cámara
fr = [{'texto': 'El programa lee el serial con Read Fastboot Info.', 'tomas': [[175, 179]]},
      {'texto': 'Con ese serial se genera una KEY única desde el servidor.', 'tomas': [[310, 314]]},
      {'texto': 'Pegas la KEY, clic en Erase FRP By Code, y OKAY, Finished.', 'tomas': [[437, 441], [472, 476]]},
      {'id': 'WEBS', 'texto': 'Y visita nuestras páginas.', 'tomas': [[56, 60]]},
      {'texto': 'Con el teléfono apagado conectas el cable.', 'tomas': [[56, 60]]}]
assert mp.elegir(fr, m) == 4
assert [x['src'] for x in fr[0]['tomas']] == [66, 71]
assert [x['src'] for x in fr[1]['tomas']] == [819, 823]
assert fr[2]['tomas'][0]['src'] == 886.5 and fr[2]['tomas'][1] == [472, 476]
assert all(mp.es_pc(x) for x in fr[3]['tomas']) and fr[4]['tomas'] == [[56, 60]]
antes = json.dumps(fr)
assert mp.elegir(fr[:4], m) == 0 and json.dumps(fr) == antes  # no pisa lo ya elegido (o lo que fabian cambió)

# los pasos clave de la cámara se acercan
assert mp.RE_ACERCAR.search('Ya aparece Omitir') and mp.RE_ACERCAR.search('OKAY, Finished') and not mp.RE_ACERCAR.search('Conectas el cable')

d = tempfile.mkdtemp()
try:
    # sin material.mp4 no cambia nada
    r = {'shorts': [{'frases': [{'texto': 'Pegas la KEY', 'tomas': [[1, 2]]}]}]}
    assert mp.poner(d, r) == 0 and r['shorts'][0]['frases'][0]['tomas'] == [[1, 2]] and 'pc_elegido' not in r

    # poner_extras no se cae con tomas de la PC y no las usa como relleno de cámara
    g = {'shorts': [{'frases': [{'texto': 'a', 'tomas': [mp.toma_pc(5, .5, .5, .6, .5), [10, 12]]}, {'texto': resumen.cierre(1), 'tomas': [[20, 22]]}]}]}
    resumen.poner_extras(g)
    extras = [f for f in g['shorts'][0]['frases'] if f.get('id')]
    assert len(extras) == 2 and all(isinstance(t, list) for f in extras for t in f['tomas']), extras

    # el comando del trozo: lee material.mp4, con zoom y con el círculo en el segundo justo
    open(os.path.join(d, mp.MATERIAL), 'wb').close()
    import short, codificar, subprocess as sp
    llamadas = []
    original = codificar.run, sp.run
    codificar.run = lambda c, **k: llamadas.append(c)
    sp.run = lambda c, **k: type('R', (), {'stdout': '2878,1522\n', 'returncode': 0})()
    try:
        sn = mp.circulo(10, .35, .6, .06)
        toma = dict(mp.toma_pc(8, .4, .5, .4, .3), senales=[sn])
        resumen.trozo_pc(d, toma, 8.0, 4.0, 'x.mp4', {mp.clave_senal(sn): 'c.mov'})
        c = ' '.join(map(str, llamadas[0]))
        assert mp.MATERIAL in c and 'zoompan' in c and 'c.mov' in c and 'setpts=PTS+2.000' in c, c
        llamadas.clear()
        resumen.trozo_pc(d, mp.toma_pc(8, .4, .5, .4, .3), 8.0, 4.0, 'x.mp4')
        assert 'c.mov' not in ' '.join(map(str, llamadas[0]))
    finally:
        codificar.run, sp.run = original
finally:
    shutil.rmtree(d, ignore_errors=True)

html = open(os.path.join(RAIZ, 'app', 'shorts_resumen.html'), encoding='utf-8').read()
assert 'ponerPc' in html and "'PC ' + x.src" in html and 'Con pantalla de la PC' in html
print('ok: las tomas de la PC salen de lo que dice la voz, con zoom y círculo, y sin material.mp4 todo sigue igual')
