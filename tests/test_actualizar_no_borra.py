"""Prueba rápida (pedido de fabian, 02/11/2026: pulsó «Actualizar» y la app rehízo el video y borró su FINAL con arreglos):
- los botones «↻ Actualizar» solo refrescan la vista (llaman a refrescar(), nunca a rehacer ni a /api/actualizar);
- «🔁 Rehacer video» está aparte, en el menú Proyecto, y no es el botón principal;
- antes de rehacer, los finales se copian a FINAL_antes_rehacer_… (app/respaldo.py) y el aviso nombra las capas que no
  se vuelven a poner solas.
Uso: python tests/test_actualizar_no_borra.py   (sale con 1 si algo falla)
"""
import os, re, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'app'))
import respaldo  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


html = open(os.path.join(RAIZ, 'app', 'index.html'), encoding='utf-8').read()
botones = re.findall(r'<button[^>]*>[^<]*Actualizar</button>', html)
ok(botones, 'no encontré los botones «Actualizar»')
for b in botones:
    ok('refrescar()' in b and 'actualizarProyecto' not in b, f'«Actualizar» no debe rehacer el video: {b[:120]}')
rehacer = re.findall(r'<button[^>]*actualizarProyecto\(\)[^>]*>([^<]*)</button>', html)
ok(rehacer and all('Rehacer' in t for t in rehacer), f'el que rehace tiene que llamarse «Rehacer video»: {rehacer}')
ok(not re.search(r'class="principal"[^>]*actualizarProyecto', html), '«Rehacer video» no debe ser el botón principal')
ok("api(`/api/capas_por_fuera" in html, 'el aviso de «Rehacer» debe nombrar las capas puestas por fuera')

app = open(os.path.join(RAIZ, 'app', 'app.py'), encoding='utf-8').read()
i = app.index("if ruta == '/api/actualizar':")
ok(app.index('respaldo.respaldar(d)', i) < app.index('borrar_seguro', i), 'el respaldo tiene que ir ANTES de borrar')

with tempfile.TemporaryDirectory() as d:
    for n in ('FINAL.mp4', 'FINAL_EN.mp4', 'FINAL_480p.mp4', 'FINAL_antes_giro.mp4'):
        open(os.path.join(d, n), 'wb').write(n.encode())
    open(os.path.join(d, 'inicio_fijo.json'), 'w').write('{"video": "prueba_inicio/x.mp4", "hasta": 79.3}')
    copias = respaldo.respaldar(d, fecha='20261102_0130')
    ok(sorted(copias) == ['FINAL_antes_rehacer_20261102_0130_FINAL.mp4', 'FINAL_antes_rehacer_20261102_0130_FINAL_480p.mp4',
                          'FINAL_antes_rehacer_20261102_0130_FINAL_EN.mp4'], f'copias: {copias}')
    ok(open(os.path.join(d, copias[0]), 'rb').read() == b'FINAL.mp4', 'la copia no es igual al original')
    c = respaldo.capas_por_fuera(d)
    ok(any('inicio fijo' in x for x in c['solas']), f'el inicio fijo se vuelve a poner solo: {c}')
    ok(any('inglés' in x for x in c['a_mano']) and any('giro' in x for x in c['a_mano']), f'debe avisar lo que no se rehace solo: {c}')

print('\n'.join(fallos) or 'ok: «Actualizar» no borra nada y «Rehacer video» respalda antes')
sys.exit(1 if fallos else 0)
