"""Prueba rápida de los 3 arreglos pendientes de la revisión. Sin internet y sin gastar nada: los pasos largos van simulados,
y tus ajustes y proyectos no se tocan (todo va a una carpeta temporal).
- «✨ Agregar extras» copia el FINAL con tus arreglos a mano antes de borrarlo, y no suma otra copia en cada vuelta;
Uso: python tests/test_revision_pendientes.py   (sale con 1 si algo falla)
"""
import json, os, shutil, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'app'))
os.environ['SIN_NAVEGADOR'] = '1'
import app  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def crear(d, nombres):
    for n in nombres:
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), 'w').write('{}')


def correr(proyecto, pasos, opciones, hace_final=None):
    """Corre los pasos con los comandos simulados: no hacen nada, salvo el paso del final, que escribe FINAL.mp4 con
    `hace_final` (como si la app lo armara)."""
    viejos = (app.comandos, app.asegurar_librerias, app.asegurar_node)

    def comandos(paso, d, op):
        if paso in ('final_sin_trailer', 'trailer') and hace_final is not None:
            return [[sys.executable, '-c', f'open("FINAL.mp4", "wb").write({hace_final!r})']]
        return []
    app.comandos, app.asegurar_librerias, app.asegurar_node = comandos, (lambda *a: None), (lambda *a: None)
    try:
        app.TRABAJO.update(proyecto=proyecto)
        app.correr(proyecto, list(pasos), dict(opciones))
    finally:
        app.comandos, app.asegurar_librerias, app.asegurar_node = viejos
        app.TRABAJO.update(proyecto=None)


tmp = tempfile.mkdtemp(prefix='pendientes_')
app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
app.PROYECTOS = os.path.join(tmp, 'proyectos')
json.dump({}, open(app.AJUSTES, 'w'))
try:
    # P1) «✨ Agregar extras» borra el FINAL para volver a armarlo: antes queda copiado si tiene arreglos a mano
    d = os.path.join(app.PROYECTOS, 'extras')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4', '8_testimonios.mp4'])
    open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'final con arreglos a mano')
    open(os.path.join(d, 'FINAL_EN.mp4'), 'wb').write(b'version en ingles')
    copias = lambda: sorted(f for f in os.listdir(d) if f.startswith('FINAL_antes_rehacer_'))
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True})  # el paso siguiente falla: no deja FINAL nuevo
    ok(not os.path.exists(os.path.join(d, 'FINAL.mp4')) and not os.path.exists(os.path.join(d, '8_testimonios.mp4')),
       f'«Agregar extras» debe quitar el FINAL y los extras viejos: {sorted(os.listdir(d))}')
    ok(len(copias()) == 1 and open(os.path.join(d, copias()[0]), 'rb').read() == b'final con arreglos a mano',
       f'el FINAL con arreglos a mano debe quedar copiado antes de borrarlo: {copias()}')
    ok(os.path.exists(os.path.join(d, 'FINAL_EN.mp4')) and not any('FINAL_EN' in f for f in copias()),
       f'solo se copia el FINAL que se borra (FINAL_EN.mp4 ni se toca ni se copia): {copias()}')
    # la app arma el FINAL; «Agregar extras» otra vez (o «▶ Ponerlas en el video»): ese FINAL no se copia, la app lo rehace
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app')
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app, otra vuelta')
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app, tercera vuelta')
    ok(len(copias()) == 1, f'el FINAL que armó la app y nadie tocó no se copia en cada vuelta: {copias()}')
    ok(open(os.path.join(d, 'FINAL.mp4'), 'rb').read() == b'final de la app, tercera vuelta', 'el FINAL nuevo debe quedar')
    # le haces otro arreglo a mano y vuelves a agregar extras (en el mismo minuto): se copia sin pisar la copia anterior
    open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'otro arreglo a mano, mas largo')
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app')
    contenidos = sorted(open(os.path.join(d, f), 'rb').read() for f in copias())
    ok(contenidos == [b'final con arreglos a mano', b'otro arreglo a mano, mas largo'],
       f'cada FINAL con arreglos a mano queda copiado, sin pisar el anterior: {copias()} {contenidos}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLÓ:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('OK: los 3 arreglos pendientes funcionan.')
