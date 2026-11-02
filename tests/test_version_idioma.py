"""Prueba rápida de la copia de «🌐 Crear la versión» (etiquetas/version_idioma.py): copiar dos veces no falla (el
original enlazado no se copia sobre sí mismo), no se copian videos de pruebas y sí el inicio fijo.
Uso: python tests/test_version_idioma.py"""
import json, os, shutil, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
import version_idioma as v  # noqa: E402

t = tempfile.mkdtemp()
try:
    o, d = os.path.join(t, 'P'), os.path.join(t, 'P_EN')
    os.makedirs(os.path.join(o, 'prueba_inicio'))
    for n, x in (('original.mp4', b'video'), ('etiquetas.json', b'[]'), ('FINAL.mp4', b'x'), ('prueba_inicio/muestra.mp4', b'x'),
                 ('prueba_inicio/inicio.mp4', b'inicio'), ('prueba_inicio/nota.txt', b'ok')):
        open(os.path.join(o, n), 'wb').write(x)
    json.dump({'video': 'prueba_inicio/inicio.mp4', 'hasta': 10}, open(os.path.join(o, 'inicio_fijo.json'), 'w'))
    v.copiar(o, d)
    v.copiar(o, d)  # la segunda vez no debe fallar
    hay = lambda n: os.path.exists(os.path.join(d, n))
    assert hay('original.mp4') and hay('etiquetas.json') and hay('prueba_inicio/inicio.mp4') and hay('prueba_inicio/nota.txt')
    assert not hay('FINAL.mp4') and not hay('prueba_inicio/muestra.mp4')
    print('ok: la copia de la versión en otro idioma funciona dos veces seguidas y salta lo que no hace falta')
finally:
    shutil.rmtree(t, ignore_errors=True)
