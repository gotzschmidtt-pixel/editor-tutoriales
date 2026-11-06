"""Prueba rápida (pedido de fabian, 06/11/2026: «un botón en la app para sincronizar PC1 y PC2»):
«🔄 Sincronizar» pasa, además de mis_conocimientos, la música, el kit de estilo y lo liviano de mis_proyectos (portadas,
miniaturas, _entregas y textos) entre dos PCs, por un repositorio git. Nunca videos, audios de proyecto ni zips.
Simula las dos PCs con dos carpetas y un repositorio local vacío.
Uso: python tests/test_sincronizar_pcs.py   (sale con 1 si algo falla)
"""
import os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
import conocimiento as cono  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def escribir(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'wb') as f:
        f.write(datos)


def usar_pc(raiz):
    cono.RAIZ = raiz
    cono.CARPETA = os.path.join(raiz, 'mis_conocimientos')
    cono.PRINCIPAL = os.path.join(cono.CARPETA, 'CONOCIMIENTO.md')


tmp = tempfile.mkdtemp()
try:
    remoto = os.path.join(tmp, 'remoto.git')
    subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', remoto], check=True)
    pc1, pc2 = os.path.join(tmp, 'pc1'), os.path.join(tmp, 'pc2')
    for pc in (pc1, pc2):
        os.makedirs(os.path.join(pc, 'mis_conocimientos'))

    # PC2 (laptop) tiene la música, el kit de estilo, una portada, un video y un zip de entrega
    escribir(os.path.join(pc2, 'mis_musica', 'musica_fija.mp3'), b'ID3 musica')
    escribir(os.path.join(pc2, 'remotion', 'public', 'estilo', 'flecha.png'), b'PNG flecha')
    escribir(os.path.join(pc2, 'mis_proyectos', 'HONOR 8 LITE', 'shorts_webs', 'portadas_es', 'portada_A.png'), b'PNG A')
    escribir(os.path.join(pc2, 'mis_proyectos', 'HONOR 8 LITE', 'shorts_webs', 'SHORT_1.mp4'), b'video')
    escribir(os.path.join(pc2, 'mis_proyectos', 'HONOR 8 LITE', 'capturas', 'cuadro_001.png'), b'PNG cuadro')
    escribir(os.path.join(pc2, 'mis_proyectos', 'HONOR 8 LITE', 'textos_youtube.txt'), b'titulo')
    escribir(os.path.join(pc2, 'mis_proyectos', '_entregas', 'CLAUDE_para_PC1.md'), b'reglas')
    escribir(os.path.join(pc2, 'mis_proyectos', '_entregas', 'APP.zip'), b'zip')
    escribir(os.path.join(pc2, 'mis_conocimientos', 'CONOCIMIENTO.md'), b'# Conocimiento\n')

    usar_pc(pc2)
    msg = cono.sincronizar(remoto)
    ok('5 subido' in msg, f'PC2 debía subir 5 archivos de material: {msg}')

    usar_pc(pc1)
    msg = cono.sincronizar(remoto)
    ok('5 bajado' in msg, f'PC1 debía bajar 5 archivos de material: {msg}')
    for rel, debe in [('mis_musica/musica_fija.mp3', True), ('remotion/public/estilo/flecha.png', True),
                      ('mis_proyectos/HONOR 8 LITE/shorts_webs/portadas_es/portada_A.png', True),
                      ('mis_proyectos/HONOR 8 LITE/textos_youtube.txt', True),
                      ('mis_proyectos/_entregas/CLAUDE_para_PC1.md', True),
                      ('mis_proyectos/HONOR 8 LITE/shorts_webs/SHORT_1.mp4', False),
                      ('mis_proyectos/HONOR 8 LITE/capturas/cuadro_001.png', False),
                      ('mis_proyectos/_entregas/APP.zip', False)]:
        ok(os.path.exists(os.path.join(pc1, *rel.split('/'))) == debe, f'en PC1 {rel} debía {"llegar" if debe else "NO llegar"}')

    # PC1 cambia la portada y agrega otra: llegan a PC2; la segunda vez sin cambios no sube nada
    escribir(os.path.join(pc1, 'mis_proyectos', 'HONOR 8 LITE', 'shorts_webs', 'portadas_es', 'portada_A.png'), b'PNG A v2')
    escribir(os.path.join(pc1, 'mis_proyectos', 'MOTO G', 'miniaturas', 'final.jpg'), b'JPG')
    msg = cono.sincronizar(remoto)
    ok('2 subido' in msg, f'PC1 debía subir 2: {msg}')
    msg = cono.sincronizar(remoto)
    ok('subido' not in msg and 'bajado' not in msg, f'sin cambios no debía pasar nada: {msg}')
    usar_pc(pc2)
    msg = cono.sincronizar(remoto)
    ok('2 bajado' in msg, f'PC2 debía bajar 2: {msg}')
    with open(os.path.join(pc2, 'mis_proyectos', 'HONOR 8 LITE', 'shorts_webs', 'portadas_es', 'portada_A.png'), 'rb') as f:
        ok(f.read() == b'PNG A v2', 'la portada cambiada en PC1 no llegó a PC2')

    # la misma imagen cambiada en las dos PCs no rompe la sincronización (queda la de la PC que sincroniza)
    escribir(os.path.join(pc2, 'mis_musica', 'musica_fija.mp3'), b'ID3 de PC2')
    cono.sincronizar(remoto)
    usar_pc(pc1)
    escribir(os.path.join(pc1, 'mis_musica', 'musica_fija.mp3'), b'ID3 de PC1')
    try:
        cono.sincronizar(remoto)
    except ValueError as e:
        fallos.append(f'un archivo cambiado en las dos PCs rompió la sincronización: {e}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

for f in fallos:
    print('✗', f)
print('✓ sincronizar PC1 y PC2: todo bien' if not fallos else f'{len(fallos)} fallo(s)')
sys.exit(1 if fallos else 0)
