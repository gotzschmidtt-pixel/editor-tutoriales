"""Prueba del estilo «Xiaomi gráficos» (fabian, 13/11/2026: «TEN EN CUENTA ESTE TIPO DE ESTILO PARA PRÓXIMAS MINIATURAS PARA
HACERLAS DESDE GPT»). SIN internet y SIN gastar: la IA de imágenes va simulada.
- con estilo xiaomi_graficos, miniaturas_gpt manda sus fotos + las referencias de referencias/xiaomi_graficos (la hoja E
  primero) + la hoja de la mascota, y NO las del canal;
- el pedido trae el fondo azul, el guante, las píldoras, el logo Mi entre las palabras y los prohibidos;
- «SIN PC» solo si el proceso no usa PC (Honor nunca); las esquinas pasan a ser las píldoras (PASO A PASO no);
- el estilo «canal» sigue igual (fondo NEGRO);
- la app (mejoras.py) pasa --estilo solo con xiaomi_graficos.
Uso: python tests/test_miniaturas_xiaomi_graficos.py   (sale con 1 si algo falla)
"""
import os, sys, tempfile, urllib.request
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'miniatura'))
import miniatura as mini  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def sin_red(*a, **k):
    raise AssertionError('la prueba intentó usar la red de verdad')


urllib.request.urlopen = sin_red
mini.pedir_imagen = sin_red
# sin mis_conocimientos/procesos_pc.json: la cuenta Mi de Xiaomi va sin PC, lo demás con PC (como en ese archivo)
mini.reglas_titulo.necesita_pc = lambda marca, texto='': str(marca).upper() != 'XIAOMI'


def imagen(f):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    cv2.imwrite(f, np.full((90, 160, 3), (80, 30, 10), np.uint8))
    return f


with tempfile.TemporaryDirectory() as tmp:
    mini.XIAOMI_GRAFICOS = os.path.join(tmp, 'xiaomi_graficos')
    for x in mini.REFS_XIAOMI_GRAFICOS + mini.MASCOTA_XIAOMI:
        imagen(os.path.join(mini.XIAOMI_GRAFICOS, x))
    mini.LOGOS_DIR = os.path.join(tmp, 'sin_logos')
    d = os.path.join(tmp, 'XIAOMI REDMI NOTE 14 CUENTA MI')
    fotos = [imagen(os.path.join(d, f'foto_miniatura_{k}.jpg')) for k in ('antes', 'despues')]
    enviados = []
    mini.imagen_gpt = lambda prompt, refs, **k: (enviados.append((prompt, list(refs))), np.zeros((864, 1536, 3), np.uint8))[1]
    import canal_referencia
    canal_referencia.elegir = lambda *a, **k: (_ for _ in ()).throw(AssertionError('no debe elegir las del canal'))

    info = {}
    hechas = mini.miniaturas_gpt(d, fotos, ['QUITAR CUENTA MI', 'TODOS LOS MODELOS'], os.path.join(d, 'm'), 'XIAOMI',
                                 idiomas=('es', 'en'), esquinas=('SIN PC|POR SERVIDOR', ''), estilo='xiaomi_graficos', info=info)
    ok(hechas == ['m_es.jpg', 'm_en.jpg'], f'una por idioma: {hechas}')
    prompt, refs = enviados[0]
    nombres = [os.path.basename(x) for x in refs]
    ok(refs[:2] == fotos, f'primero sus fotos: {nombres}')
    ok(nombres[2] == 'E_10_lo_mejor_xiaomi.jpg' and nombres[-1] == mini.MASCOTA_XIAOMI[0] and len(nombres) == 2 + 3 + 1,
       f'3 de estilo (la hoja E primero) y la mascota: {nombres}')
    for frase in ('azul', 'guante de nitrilo azul', 'PÍLDORAS', 'logo naranja Mi', '«SIN PC»', '«POR SERVIDOR»',
                  'esquina de abajo a la derecha', 'robado', 'Imagen 6: la mascota'):
        ok(frase in prompt, f'el pedido trae «{frase}»')
    ok('fondo NEGRO' not in prompt, 'en este estilo el fondo no es negro')
    ok(info.get('estilo') == 'xiaomi_graficos' and info.get('refs_canal') == [], f'info: {info}')

    # Honor usa PC: nunca «SIN PC», ni aunque venga en las esquinas; PASO A PASO no es píldora
    p = mini.prompt_xiaomi_graficos(['HONOR', 'SIN CUENTA GOOGLE'], 'es', pildoras=('SIN PC', 'PASO A PASO'), marca='HONOR', pc=True)
    ok(p.count('«SIN PC»') == 1 and 'PÍLDORAS' in p and '«PASO A PASO»' not in p and 'nunca escribas «SIN PC»' in p and '«TODOS LOS MODELOS»' in p, f'Honor sin «SIN PC»: {p[-600:]}')
    enviados.clear()
    mini.miniaturas_gpt(d, fotos, ['QUITAR CUENTA MI'], os.path.join(d, 'n'), 'XIAOMI', idiomas=('es',),
                        esquinas=('PASO A PASO', ''), estilo='xiaomi_graficos')
    ok('«PASO A PASO»' not in enviados[0][0], 'la esquina por defecto no se vuelve píldora')

    # el estilo del canal no cambió
    ok('fondo NEGRO' in mini.prompt_canal(['HONOR', 'SIN CUENTA GOOGLE'], 'es', marca='HONOR'), 'el estilo canal sigue negro')

# la app pasa --estilo
sys.path.insert(0, os.path.join(RAIZ, 'mejoras'))
try:
    src = open(os.path.join(RAIZ, 'mejoras', 'mejoras.py'), encoding='utf-8').read()
    ok("['--estilo', 'xiaomi_graficos'] if op.get('estilo') == 'xiaomi_graficos'" in src, 'mejoras.py pasa --estilo')
    html = open(os.path.join(RAIZ, 'app', 'miniatura.html'), encoding='utf-8').read()
    ok('value="xiaomi_graficos"' in html and "estilo: $('#estilo').value" in html and 'final.estilo' in html,
       'el panel tiene el selector y la final repite el estilo')
except OSError as e:
    fallos.append(str(e))

if fallos:
    print('FALLÓ:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('OK: estilo Xiaomi gráficos')
