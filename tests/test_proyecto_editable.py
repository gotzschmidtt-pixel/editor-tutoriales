"""Prueba rápida (pedido de fabian, 14/11/2026: «que la app tenga esta opción: guardar el proyecto tipo editable»):
«📦 Guardar proyecto editable» mete TODO lo necesario para seguir editando (video grabado, material extra, voces con su
alineación, guion, etiquetas, señales, subtítulos, música, testimonios…) en un .zip, deja fuera lo que la app rehace sola,
y «📂 Abrir proyecto editable» lo vuelve a abrir como un proyecto nuevo sin pisar nada (desde .zip o desde carpeta).
Uso: python tests/test_proyecto_editable.py   (sale con 1 si algo falla)
"""
import json, os, shutil, sys, tempfile, time, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'app'))
import editable  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def escribir(ruta, datos=b'x'):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'wb') as f:
        f.write(datos if isinstance(datos, bytes) else datos.encode())


GENERADOS = ['1_montaje.mp4', '3_voz.mp4', '5_etiquetas.mp4', 'FINAL.mp4', 'FINAL_480p.mp4']
VAN = ['original.mp4', 'material.mp4', 'musica.mp3', 'guion.json', 'etiquetas.json', 'senales.json', 'transcripcion.json',
       'subtitulos.json', 'edicion.json', '.alineacion_vista.json', 'original.nitidez.npz', 'voz/L01.mp3', 'voz/L01.json',
       'testimonios/testimonios.json', 'testimonios/caso1.mp4', 'tarjetas/WHATSAPP/canal.png', 'material_extra/toma 1.mov']
NO_VAN = GENERADOS + ['FINAL_antes_rehacer_20261113_FINAL.mp4', 'guardados/2026-11-13/guion.json', '.montaje_partes/p1.mp4',
                      'hojas_2s/h1.jpg', 'ia_capturas/c1.jpg', 'para_claude/x.txt', 'testimonios/_papelera/viejo.mp4', 'algo.tmp']

tmp = tempfile.mkdtemp()
try:
    proyectos = os.path.join(tmp, 'mis_proyectos')
    d = os.path.join(proyectos, 'HONOR 400 LITE')
    guion = {'bloques': [{'id': 'L01', 'texto': 'Hola'}, {'id': 'L02', 'texto': 'Chao'}]}
    for f in VAN + NO_VAN:
        escribir(os.path.join(d, f), json.dumps(guion) if f == 'guion.json' else f.encode() * 50)
    fuera = os.path.join(tmp, 'fuera')
    escribir(os.path.join(fuera, 'musica_fija.mp3'), b'fija')
    escribir(os.path.join(fuera, 'CONOCIMIENTO.md'), b'# lo aprendido')

    # 1) lo que entra y lo que no
    dentro = {z.split('/', 1)[1] for _, z in editable.lista(d, GENERADOS)}
    for f in VAN:
        ok(f in dentro, f'falta en el paquete: {f}')
    for f in NO_VAN:
        ok(f not in dentro, f'no debería ir en el paquete: {f}')
    ok('FINAL.mp4' in {z.split('/', 1)[1] for _, z in editable.lista(d, GENERADOS, con_final=True)}, 'con_final no mete FINAL.mp4')
    r = editable.resumen(d, GENERADOS)
    ok(r['archivos'] == len(VAN) and not r['falta'], f'resumen raro: {r}')

    # 2) el .zip: una carpeta con el nombre del proyecto, manifiesto, videos sin recomprimir, extras de fuera
    zipf = os.path.join(tmp, 'salida', 'HONOR 400 LITE_EDITABLE.zip')
    avances = []
    editable.empaquetar(d, zipf, GENERADOS, extras=[(os.path.join(fuera, 'musica_fija.mp3'), 'musica.mp3'),
                                                     (os.path.join(fuera, 'CONOCIMIENTO.md'), 'mis_conocimientos/CONOCIMIENTO.md'),
                                                     (os.path.join(fuera, 'no_existe.md'), 'mis_conocimientos/no_existe.md')],
                        avance=lambda h, t, a: avances.append((h, t)))
    ok(os.path.isfile(zipf) and not os.path.exists(zipf + '.part'), 'no quedó el .zip (o quedó el .part)')
    ok(avances and avances[-1][0] == avances[-1][1], 'la barra no llega al 100 %')
    with zipfile.ZipFile(zipf) as z:
        nombres = z.namelist()
        ok(all(n.startswith('HONOR 400 LITE/') for n in nombres), 'el zip no trae la carpeta del proyecto')
        man = json.loads(z.read('HONOR 400 LITE/' + editable.MANIFIESTO))
        ok(man['tipo'] == 'proyecto_editable' and man['bloques'] == 2 and man['voces'] == 1, f'manifiesto raro: {man}')
        ok(z.getinfo('HONOR 400 LITE/original.mp4').compress_type == zipfile.ZIP_STORED, 'el video se recomprime (lento)')
        ok(z.read('HONOR 400 LITE/musica.mp3') != b'fija', 'la música fija pisó la música propia del proyecto')
        ok('HONOR 400 LITE/mis_conocimientos/CONOCIMIENTO.md' in nombres, 'no viaja lo aprendido')
        ok(not any('no_existe' in n for n in nombres), 'un extra que no existe rompió o entró')

    # 3) abrirlo: proyecto nuevo con _2 (no pisa el que ya está), igual al original
    nombre, dst = editable.abrir_zip(zipf, proyectos)
    ok(nombre == 'HONOR 400 LITE_2', f'nombre al abrir: {nombre}')
    for f in VAN:
        a, b = os.path.join(d, f), os.path.join(dst, f)
        ok(os.path.exists(b) and open(a, 'rb').read() == open(b, 'rb').read(), f'al abrir no quedó igual: {f}')
    ok(os.path.exists(os.path.join(d, 'FINAL.mp4')), 'abrir tocó el proyecto original')

    # 4) un .zip con rutas que se salen de la carpeta: no escribe fuera
    malo = os.path.join(tmp, 'malo.zip')
    with zipfile.ZipFile(malo, 'w') as z:
        z.writestr('X/guion.json', '{}')
        z.writestr('X/../../afuera.txt', 'malo')
    nombre, dst = editable.abrir_zip(malo, proyectos)
    ok(not os.path.exists(os.path.join(tmp, 'afuera.txt')) and not os.path.exists(os.path.join(proyectos, 'afuera.txt')),
       'un .zip escribió fuera del proyecto')

    # 5) un .zip que no es proyecto: error claro y no deja carpeta a medias
    otro = os.path.join(tmp, 'fotos.zip')
    with zipfile.ZipFile(otro, 'w') as z:
        z.writestr('fotos/a.jpg', 'x')
    try:
        editable.abrir_zip(otro, proyectos)
        ok(False, 'abrió un .zip que no es proyecto')
    except ValueError:
        pass
    ok(not os.path.exists(os.path.join(proyectos, 'fotos')), 'dejó carpeta de un .zip rechazado')
    nombre, _ = editable.abrir_zip(otro, proyectos, exigir=False)  # «📂 Abrir proyecto» de siempre sigue abriendo cualquiera
    ok(nombre == 'fotos', f'exigir=False no abrió: {nombre}')

    # 6) abrir una CARPETA de proyecto (la que pasa Claude o se baja del Drive)
    nube = os.path.join(tmp, 'descargas', 'HONOR 400 LITE FABIAN')
    escribir(os.path.join(nube, 'guion.json'), '{"bloques": []}')
    escribir(os.path.join(nube, 'voz', 'L01.mp3'), b'voz')
    nombre, dst = editable.abrir_carpeta(nube, proyectos)
    ok(nombre == 'HONOR 400 LITE FABIAN' and os.path.exists(os.path.join(dst, 'voz', 'L01.mp3')), 'no abrió la carpeta')
    try:
        editable.abrir_carpeta(d, proyectos)
        ok(False, 'dejó abrir una carpeta que ya está en mis_proyectos')
    except ValueError:
        pass

    # 7) en segundo plano: avance, resultado y no dos a la vez
    editable.en_segundo_plano('guardar', 'p', lambda av: (av(1, 2, 'a'), time.sleep(0.3), 'listo')[2])
    try:
        editable.en_segundo_plano('guardar', 'p', lambda av: None)
        ok(False, 'dejó correr dos a la vez')
    except ValueError:
        pass
    while editable.estado()['activo']:
        time.sleep(0.05)
    e = editable.estado()
    ok(e['resultado'] == 'listo' and not e['error'] and e['porcentaje'] == 50, f'estado raro: {e}')
    editable.en_segundo_plano('abrir', 'p', lambda av: (_ for _ in ()).throw(ValueError('roto')))
    while editable.estado()['activo']:
        time.sleep(0.05)
    ok(editable.estado()['error'] == 'roto', 'el error no llega a la página')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLOS:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('OK: proyecto editable (guardar, abrir .zip y carpeta, rutas seguras, avance)')
