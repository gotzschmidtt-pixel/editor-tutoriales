"""Prueba rápida de la revisión del guion (ia/ia.py), sin red ni gastos (la IA se simula):
- una respuesta como «tarda unos 3 minutos» (en «Datos confirmados por el autor:») no cambia la duración buscada del video;
- «Responder y corregir» manda a la IA solo las respuestas nuevas (las ya aplicadas no se repiten);
- las respuestas cortas («Sí», «15») quedan como datos confirmados en idea.txt;
- dos bloques con el mismo id se renombran (la voz de uno pisaba la del otro y se pagaba en cada «Generar voz»).
Uso: python tests/test_guion_respuestas.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
import ia  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp(prefix='guion_resp_')
try:
    # duración buscada: solo lo que escribió el autor
    idea = 'Video del Honor 8 Lite.\n\nDatos confirmados por el autor:\n- ¿Cuánto tarda en reiniciar? unos 3 minutos\n'
    open(os.path.join(tmp, 'idea.txt'), 'w', encoding='utf-8').write(idea)
    ok(ia.meta_guion(tmp, 860)[0] == 860, 'una respuesta «unos 3 minutos» no debería cambiar la duración buscada')
    open(os.path.join(tmp, 'idea.txt'), 'w', encoding='utf-8').write('Que dure unos 10 minutos.\n\n' + idea.split('\n\n', 1)[1])
    ok(ia.meta_guion(tmp, 860)[0] == 600, '«que dure unos 10 minutos» del autor debería mandar')
    ok(ia.minutos_pedidos('de 5 a 7 min.').group(1) == '5', '«de 5 a 7 min.» debería contar')
    ok(ia.minutos_pedidos('pon 3 minimo') is None, '«3 minimo» no es una duración')
    for txt in ('que dure 10 mins', 'unos 10 minutitos', '10min'):  # como antes de la revisión: también cuentan
        ok(ia.minutos_pedidos(txt) and ia.minutos_pedidos(txt).group(1) == '10', f'«{txt}» debería contar como 10 minutos')

    # respuestas: solo las nuevas, y las cortas quedan como dato confirmado
    open(os.path.join(tmp, 'idea.txt'), 'w', encoding='utf-8').write('Sí funciona con Android 15\n')
    preguntas = [{'tipo': 'mejora', 'bloque': 'L05', 'pregunta': '¿Explico por qué quitar la batería?',
                  'respuesta': 'Sí, en una frase', 'hecha': True},
                 {'tipo': 'dato', 'bloque': 'L02', 'pregunta': '¿Se suelta el botón al ver el logo?', 'respuesta': 'Sí'},
                 {'tipo': 'dato', 'bloque': 'L03', 'pregunta': '¿Qué versión?', 'respuesta': '15'}]
    json.dump(preguntas, open(os.path.join(tmp, 'preguntas_guion.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    pedidos = []
    ia.llamar = lambda aj, texto, caps: (pedidos.append(texto), '{"bloques": []}')[1]  # la IA simulada: no cambia nada
    ia.conocimiento.aprender_de_proyecto = lambda d: 0
    guion = {'bloques': [{'id': 'L02', 'texto': 'Mantén el botón.', 'montaje': {}},
                         {'id': 'L03', 'texto': 'Funciona en Android.', 'montaje': {}}]}
    ia.corregir_con_respuestas(tmp, {}, guion)
    ok(len(pedidos) == 1 and 'batería' not in pedidos[0], 'la respuesta ya aplicada no debería mandarse otra vez a la IA')
    ok('¿Se suelta el botón' in pedidos[0], 'la respuesta nueva sí debería mandarse')
    nueva = open(os.path.join(tmp, 'idea.txt'), encoding='utf-8').read()
    ok('- ¿Se suelta el botón al ver el logo? Sí' in nueva, 'la respuesta «Sí» debería quedar como dato confirmado')
    ok('- ¿Qué versión? 15' in nueva, 'la respuesta «15» debería quedar como dato confirmado')
    try:
        ia.corregir_con_respuestas(tmp, {}, guion)
        ok(False, 'sin respuestas nuevas debería avisar que no hay respuestas')
    except SystemExit as e:
        ok('no hay respuestas' in str(e), f'sin respuestas nuevas, error inesperado: {e}')
    ok(len(pedidos) == 1, 'sin respuestas nuevas no debería hacerse otro pedido a la IA')

    # ids repetidos
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=5', '-t', '60', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', os.path.join(tmp, 'original.mp4')], check=True)
    ia.marcar_caras = lambda d, bloques: []  # sin el detector de caras (no baja nada)

    def bloque(i, texto, a, z):
        return {'id': i, 'texto': texto, 'montaje': {'modo': 'lento', 'src_inicio': a, 'src_fin': z, 'velocidad': 1.0}}
    datos = {'bloques': [bloque('L01', 'Hola, hoy vemos cómo quitar la cuenta de Google.', 0, 5),
                         bloque('L05', 'Conectamos el cable al computador.', 5, 12),
                         bloque('L05', 'El programa detecta el teléfono enseguida.', 12, 20),
                         bloque('L05b', 'Pulsamos el botón de iniciar el proceso.', 20, 30)]}
    datos, avisos = ia.revisar(tmp, 'guion', datos)
    ids = [b['id'] for b in datos['bloques']]
    ok(len(set(ids)) == len(ids), f'los ids deberían ser únicos: {ids}')
    ok(ids == ['L01', 'L05', 'L05c', 'L05b'], f'el id repetido debería renombrarse sin pisar otro: {ids}')
    ok(any('lo renombré' in x for x in avisos), 'debería avisar que renombró el id repetido')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: respuestas, duración buscada e ids del guion')
sys.exit(1 if fallos else 0)
