"""Prueba de las respuestas de fabian sobre títulos y miniaturas (03/11/2026). SIN internet y SIN gastar (la IA simulada):
- el año de títulos y miniaturas sale de la fecha: 2026 hasta el 14 de diciembre, 2027 desde el 15 (sello, esquinas,
  búsquedas, ejemplos para la IA y lo que se revisa antes de gastar);
- «Sin PC» por PROCESO (procesos_pc.json nuevo, y el formato viejo por marca sigue sirviendo): solo la cuenta Mi de Xiaomi
  y la liberación de bandas de iPhone; en el título solo AL INICIO; «Sin PC Avanzada» sí en Honor;
- Honor sin «Todos los Modelos» (ni «All Models» ni «Todos os Modelos»); «Gratis» solo si el proyecto dice que es gratis;
- títulos con dos verbos al inicio («Quitar, Eliminar…») se dejan tal cual;
- lo mismo en los títulos de «▶️ YouTube» (ia_youtube), en «🔎 Investigar el tema», en los Shorts resumen y en las ideas de
  textos de la miniatura (titulos.py).
Uso: python tests/test_reglas_titulo.py   (sale con 1 si algo falla)
"""
import contextlib, datetime, io, json, os, sys, tempfile, types, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('conocimiento', 'miniatura', 'youtube', 'short'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def sin_red(*a, **k):  # nada de esta prueba sale a internet
    raise AssertionError('la prueba intentó usar la red de verdad')


urllib.request.urlopen = sin_red

# la IA de texto, simulada: guarda los pedidos y contesta lo que le toque a cada prueba
PEDIDOS, RESPUESTA = [], {}
ia_falsa = types.ModuleType('ia')
ia_falsa.ErrorIA = type('ErrorIA', (Exception,), {})
ia_falsa.llamar = lambda aj, prompt, imagenes: (PEDIDOS.append(prompt), json.dumps(RESPUESTA))[1]
ia_falsa.extraer_json = lambda t: json.loads(t)
sys.modules['ia'] = ia_falsa

import reglas_titulo as rt  # noqa: E402

tmp = tempfile.mkdtemp()
PROCESOS = os.path.join(tmp, 'procesos_pc.json')
json.dump({'honor': True, 'procesos': [
    {'id': 'xiaomi_mi_account', 'pc': False, 'marcas': ['xiaomi'], 'palabras': ['mi account', 'cuenta mi', 'unlock code'],
     'basta': 'el unlock code o el IMEI'},
    {'id': 'iphone_liberacion_bandas', 'pc': False, 'marcas': ['iphone'], 'palabras': ['liberacion de bandas', 'bandas'],
     'basta': 'el IMEI y el número de serie'},
    {'id': 'xiaomi_cuenta_google', 'pc': True, 'marcas': ['xiaomi'], 'palabras': ['cuenta google', 'frp']},
    {'id': 'iphone_icloud', 'pc': True, 'marcas': ['iphone'], 'palabras': ['icloud', 'bypass', 'hello']},
    {'id': 'honor', 'pc': True, 'marcas': ['honor'], 'palabras': ['honor']}]}, open(PROCESOS, 'w', encoding='utf-8'))
rt.PROCESOS_PC = PROCESOS
NOV = datetime.date(2026, 11, 3)

# 1) el año por la fecha
for dia, esperado in ((datetime.date(2026, 11, 3), 2026), (datetime.date(2026, 12, 14), 2026), (datetime.date(2026, 12, 15), 2027),
                      (datetime.date(2027, 1, 2), 2027), (datetime.date(2027, 12, 15), 2028)):
    ok(rt.anio(dia) == esperado, f'el año del {dia} debería ser {esperado}, no {rt.anio(dia)}')

# 2) PC por proceso; el formato viejo (por marca) y sin archivo
casos = [('XIAOMI', 'Eliminar la cuenta Mi con el unlock code', False), ('XIAOMI', 'cuenta google frp con usb redirector', True),
         ('APPLE', 'liberación de bandas del iPhone 13', False), ('IPHONE', 'bypass icloud hello', True), ('HONOR', '', True),
         ('SAMSUNG', 'samsung sin pc por servidor', True), ('XIAOMI', '', True), ('', 'iPhone 15: liberar las bandas', False),
         ('TU CELULAR', 'Xiaomi Redmi Note 13: quitar la cuenta Mi', False)]
for marca, texto, pc in casos:
    ok(rt.necesita_pc(marca, texto) is pc, f'«{marca} / {texto}»: ¿usa PC? debería ser {pc}')
ok(rt.necesita_pc('XIAOMI', 'cuenta mi y cuenta google, cuenta google, frp') is True, 'gana el proceso que más se nombra')
viejo = os.path.join(tmp, 'viejo.json')
json.dump({'honor': True, 'xiaomi': False}, open(viejo, 'w'))
rt.PROCESOS_PC = viejo
ok(rt.necesita_pc('HONOR') is True and rt.necesita_pc('XIAOMI', 'cualquier cosa') is False and rt.necesita_pc('SAMSUNG') is True,
   'el formato viejo por marca sigue sirviendo')
rt.PROCESOS_PC = os.path.join(tmp, 'no_existe.json')
ok(rt.necesita_pc('XIAOMI', 'cuenta mi') is True, 'sin procesos_pc.json todo usa PC (nunca se promete «SIN PC» de más)')
rt.PROCESOS_PC = PROCESOS

# 3) el revisor de títulos
HONOR_FRP = 'Honor 400: eliminar la cuenta de Google con la key, cuesta unos pocos dólares'
MI = 'Xiaomi: eliminar la cuenta Mi con el unlock code'
casos = [
    ('HONOR', 'Quitar, Desbloquear, Eliminar Cuenta Google Honor con PC |Todos Los Modelos - Nuevo Método 2025', HONOR_FRP,
     'Quitar, Desbloquear, Eliminar Cuenta Google Honor con PC | Nuevo Método 2026'),
    ('HONOR', 'Quitar Cuenta Google Honor en Minutos con un click - Todos los Modelos Método 2055', HONOR_FRP,
     'Quitar Cuenta Google Honor en Minutos con un click - Método 2026'),
    ('HONOR', 'Eliminar Cuenta Google Honor Sin PC - Android 16 2027', HONOR_FRP, 'Eliminar Cuenta Google Honor - Android 16 2026'),
    ('HONOR', 'Remove Google Account Honor Without PC | All Models - New Method 2026', HONOR_FRP, 'Remove Google Account Honor | New Method 2026'),
    ('HONOR', 'Remover Conta Google Honor Para Todos os Modelos 2026', HONOR_FRP, 'Remover Conta Google Honor 2026'),
    ('HONOR', 'Sin PC Avanzada - Eliminar Cuenta Google Honor 8 Lite 2026', HONOR_FRP, None),
    ('HONOR', 'Quitar, Eliminar Cuenta Google Honor en 1 Clic 2026', HONOR_FRP, None),
    ('XIAOMI', 'Eliminar Cuenta Mi Xiaomi Permanente - Sin PC - Explicado Paso a Paso', MI, 'Sin PC - Eliminar Cuenta Mi Xiaomi Permanente - Explicado Paso a Paso'),
    ('XIAOMI', 'Sin PC - Eliminar Cuenta Mi Xiaomi Todos los Modelos 2026', MI, None),
    ('XIAOMI', 'Quitar, Eliminar Cuenta Google Xiaomi Sin Computadora 🖥️ 2025-2026', 'Xiaomi frp cuenta google usb redirector',
     'Quitar, Eliminar Cuenta Google Xiaomi 2026'),
    ('IPHONE', 'iPhone no disponible: Eliminar Pin y iCloud Gratis - Método 2026', 'bypass icloud, el registro cuesta unos dólares',
     'iPhone no disponible: Eliminar Pin y iCloud - Método 2026'),
    ('IPHONE', 'Bypass Hello Gratis Sin Registro 2026', 'bypass hello: este método es gratis, no pagas nada', None),
]
for marca, titulo, proyecto, esperado in casos:
    nuevo, avisos = rt.revisar_titulo(titulo, marca, proyecto, hoy=NOV)
    ok(nuevo == (esperado or titulo), f'«{titulo}» → «{nuevo}» (esperaba «{esperado or titulo}»)')
    ok(bool(avisos) == bool(esperado), f'«{titulo}»: avisos {avisos}')
dic = rt.revisar_titulo('Eliminar Cuenta Google Honor 2026', 'HONOR', HONOR_FRP, hoy=datetime.date(2026, 12, 15))[0]
ok(dic == 'Eliminar Cuenta Google Honor 2027', f'desde el 15 de diciembre el título nuevo va con 2027: {dic}')
nuevo, _ = rt.revisar_titulo('HONOR|SIN PC', 'HONOR', HONOR_FRP, hoy=NOV, miniatura=True)
ok('PC' not in nuevo, f'texto de miniatura de Honor con «SIN PC»: {nuevo}')
ok(rt.revisar_titulo('CUENTA MI SIN PC', 'XIAOMI', MI, hoy=NOV, miniatura=True)[0] == 'CUENTA MI SIN PC',
   'en la miniatura de la cuenta Mi, «SIN PC» puede ir en cualquier lado')

# 4) las reglas para la IA
r = rt.para_ia('HONOR', HONOR_FRP, hoy=NOV)
for txt in ('dos verbos', '2026', 'usa PC', 'Sin PC Avanzada', 'Todos los Modelos', 'Gratis'):
    ok(txt in r, f'a las reglas de Honor para la IA les falta «{txt}»')
r = rt.para_ia('XIAOMI', MI, hoy=NOV)
ok('SOLO al inicio' in r and 'unlock code' in r and 'Todos los Modelos' not in r, f'las reglas de la cuenta Mi: {r}')

# 5) miniatura.py: antes de gastar (sin PC por proceso, el año) y lo que la app pone sola
import miniatura as mini  # noqa: E402
mini.anio = lambda hoy=None: 2026  # la prueba no depende del día en que se corra
for textos, marca, pc, frena in ((['HONOR', 'SIN PC'], 'HONOR', None, True), (['HONOR', 'SIN PC AVANZADA'], 'HONOR', None, False),
                                 (['XIAOMI', 'SIN PC'], 'XIAOMI', False, False), (['XIAOMI', 'SIN PC'], 'XIAOMI', None, True),
                                 (['HONOR', 'NEW 2027'], 'HONOR', None, True), (['HONOR', 'MÉTODO 2026'], 'HONOR', None, False)):
    try:
        mini.revisar_textos(textos, marca, pc)
        ok(not frena, f'{textos} ({marca}, pc={pc}) debería frenar antes de gastar')
    except SystemExit as e:
        ok(frena and 'No se gastó nada' in str(e), f'{textos} ({marca}, pc={pc}) no debería frenar: {e}')
p_pc = mini.prompt_canal(['HONOR', 'SIN CUENTA GOOGLE'], 'es', marca='HONOR', pc=True)
p_sin = mini.prompt_canal(['XIAOMI', 'SIN PC'], 'es', marca='XIAOMI', pc=False)
ok('nunca escribas «SIN PC»' in p_pc and 'nunca escribas «SIN PC»' not in p_sin, 'el aviso de «SIN PC» a GPT va según el proceso')
d = os.path.join(tmp, 'HONOR 400 FRP')
os.makedirs(d)
json.dump({'bloques': [{'id': 'L01', 'texto': 'Método 2025 para quitar la cuenta de Google del Honor.'}]},
          open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'))
ok(mini.textos(d)[2][0] == 'HONOR 2026', f'la 3.ª miniatura gratis lleva el año de hoy, no el del guion: {mini.textos(d)[2]}')
ok(mini.SELLO['es'] == ('MÉTODO', 'GARANTIZADO'), 'el año del sello se pone al dibujarlo (anio()), no queda fijo')

# 6) «▶️ YouTube» → «✨ Proponer con IA»: el pedido lleva las reglas y la app corrige lo que la IA se saltó
import ia_youtube  # noqa: E402
aj = os.path.join(tmp, 'ajustes.json')
json.dump({'modelo': 'simulado', 'url': 'http://simulado'}, open(aj, 'w'))
os.makedirs(os.path.join(d, 'youtube'))
json.dump({'bloques': [{'id': 'L01', 's': 0, 'texto': 'hola'}], 'idea': 'Honor 400, la key cuesta unos dólares'},
          open(os.path.join(d, 'youtube', 'entrada_metadatos.json'), 'w', encoding='utf-8'))
RESPUESTA.clear()
RESPUESTA.update(titulos=[{'titulo': 'Eliminar Cuenta Google Honor 400 Sin PC - Todos los Modelos 2027', 'por_que': 'el más visto'},
                          {'titulo': 'Quitar, Eliminar Cuenta Google Honor 400 en 1 Clic 2026', 'por_que': 'dos verbos'}], elegido=0)
PEDIDOS.clear()
rt.anio = lambda hoy=None: 2026
sys.argv = ['ia_youtube.py', '--proyecto', d, '--tarea', 'metadatos', '--ajustes', aj]
with contextlib.redirect_stdout(io.StringIO()):
    ia_youtube.main()
m = json.load(open(os.path.join(d, 'youtube', 'metadatos.json'), encoding='utf-8'))
ok(m['titulos'][0]['titulo'] == 'Eliminar Cuenta Google Honor 400 - 2026', f"título 1 corregido: {m['titulos'][0]['titulo']}")
ok('La app corrigió' in m['titulos'][0]['por_que'] and 'Todos los Modelos' in m['titulos'][0]['por_que'],
   f"lo corregido se dice debajo del título: {m['titulos'][0]['por_que']}")
ok(m['titulos'][1] == {'titulo': 'Quitar, Eliminar Cuenta Google Honor 400 en 1 Clic 2026', 'por_que': 'dos verbos'},
   f"el título que ya cumple queda igual: {m['titulos'][1]}")
ok(PEDIDOS and 'REGLAS DEL AUTOR PARA LOS TÍTULOS' in PEDIDOS[-1] and 'dos verbos' in PEDIDOS[-1], 'al pedido le faltan las reglas')

# 7) «🔎 Investigar el tema»: el año de las búsquedas y las ideas de título revisadas
import investigar  # noqa: E402
investigar.autocompletar = lambda *a, **k: []
ok(any(s.endswith('frp 2026') for s in investigar.tema(d)[2]), f'las búsquedas usan el año de hoy: {investigar.tema(d)[2]}')
RESPUESTA.clear()
RESPUESTA.update(palabras_clave=['honor frp', 'quitar cuenta google honor sin pc'],
                 ideas_titulo=['Sin PC - Eliminar Cuenta Google Honor Todos los Modelos 2026', 'Eliminar Cuenta Google Honor 400 Gratis'])
sys.argv = ['investigar.py', '--proyecto', d, '--ajustes', aj]
with contextlib.redirect_stdout(io.StringIO()):
    investigar.main()
inv = json.load(open(os.path.join(d, 'youtube', 'investigacion.json'), encoding='utf-8'))['resumen']
ok(inv['palabras_clave'] == ['honor frp'], f"palabras clave sin «sin pc»: {inv['palabras_clave']}")
ok(inv['ideas_titulo'] == ['Eliminar Cuenta Google Honor 2026', 'Eliminar Cuenta Google Honor 400'], f"ideas de título: {inv['ideas_titulo']}")
ok('REGLAS DEL AUTOR PARA LOS TÍTULOS' in PEDIDOS[-1], 'al pedido de la investigación le faltan las reglas')

# 8) los títulos de los 3 Shorts resumen
import resumen  # noqa: E402
txt = resumen.textos(d, {'shorts': [{'gancho': 'antes_despues', 'titulos': {
    'es': 'Honor 400 Gratis: Adiós Cuenta Google, Todos los Modelos', 'en': 'Honor 400 Free FRP All Models', 'pt': 'Honor 400 FRP'},
    'descripciones': {'es': 'Uno.', 'en': 'One.', 'pt': 'Um.'}}]})
ok('TÍTULO: Honor 400: Adiós Cuenta Google\n' in txt and txt.count('TÍTULO: Honor 400 FRP\n') == 2,
   'los títulos de los Shorts salen con las reglas (sin «Gratis» ni «Todos los Modelos»): '
   + ' | '.join(x for x in txt.splitlines() if x.startswith('TÍTULO')))
ok('{reglas_titulo' not in resumen.prompt(d) and 'REGLAS DEL AUTOR PARA LOS TÍTULOS' in resumen.prompt(d), 'el pedido de los Shorts lleva las reglas')

# 9) «💡 Sugerir con IA» en «🖼 Miniatura» (titulos.py): lo que la IA propone pasa por las reglas
import titulos  # noqa: E402
RESPUESTA.clear()
RESPUESTA.update(titulos=[{'es': ['HONOR', 'SIN PC'], 'en': ['HONOR', 'NO PC'], 'pt': ['HONOR', 'SEM PC']},
                          {'es': ['HONOR 400', 'TODOS LOS MODELOS 2027'], 'en': ['HONOR 400', 'ALL MODELS 2027'], 'pt': ['HONOR 400', 'TODOS OS MODELOS 2027']},
                          {'es': ['HONOR', 'ELIM. CUENTA'], 'en': ['HONOR', 'REMOVE ACCOUNT'], 'pt': ['HONOR', 'REMOVER CONTA']}],
                 esquinas=[{'es': 'NEW 2027', 'en': 'NEW 2027', 'pt': 'NOVO 2027'}, {'es': 'GRATIS', 'en': 'FREE', 'pt': 'GRÁTIS'}])
sys.argv = ['titulos.py', '--proyecto', d, '--ajustes', aj]
salida = io.StringIO()
with contextlib.redirect_stdout(salida):
    titulos.main()
t = json.loads(salida.getvalue().strip().splitlines()[-1])
ok([x['es'] for x in t['titulos']] == [['HONOR 400', '2026'], ['HONOR', 'ELIM. CUENTA']], f"títulos de miniatura: {[x['es'] for x in t['titulos']]}")
ok(t['titulos'][0]['en'] == ['HONOR 400', '2026'], f"la traducción también: {t['titulos'][0]}")
ok([x['es'] for x in t['esquinas']] == ['NEW 2026'], f"esquinas: {t['esquinas']}")
ok('NEW 2026' in PEDIDOS[-1] and 'NEW 2027' not in PEDIDOS[-1] and 'REGLAS DEL AUTOR PARA LOS TEXTOS DE LA MINIATURA' in PEDIDOS[-1],
   'el pedido de textos de miniatura lleva el año de hoy y las reglas')

if fallos:
    print('FALLÓ:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: títulos y miniaturas con las reglas de fabian (03/11/2026)')
