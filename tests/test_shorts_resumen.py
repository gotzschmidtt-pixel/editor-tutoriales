"""«📱 3 Shorts resumen» sin gastar: la IA simulada propone los 3 guiones, la app valida las reglas de fabian, muestra el
costo y la voz NO se genera sin confirmación."""
import json, os, shutil, sys, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'short'))
import resumen  # noqa: E402

d = tempfile.mkdtemp()
json.dump({'bloques': [{'id': 'L01', 'texto': 'Tu Honor pide la cuenta.', 'montaje': {'src_inicio': 18}}]},
          open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'))
frase = 'Sirve para Android quince, dieciséis, diecisiete o superior, y MagicOS nueve, diez u once, con cualquier parche. '
bueno = {'gancho': 'antes_despues', 'frases': [{'texto': '[curious] ' + frase * 7, 'tomas': [[18, 22]]}],
         'titulos': {'es': 'Título <uno>', 'en': 'Title', 'pt': 'Título'}, 'descripciones': {'es': 'Uno.', 'en': 'One.', 'pt': 'Um.'}}
malo = dict(bueno, frases=[{'texto': 'Hazlo sin PC. ' * 60, 'tomas': []}])
r = resumen.proponer(d, llamar=lambda p: json.dumps({'shorts': [bueno, bueno, malo]}))
assert 'Android quince' in resumen.prompt(d) and 'NUNCA' in resumen.prompt(d)
# cada Short termina con su cierre fijo, que rota (fabian, 02/11/2026): se agrega o reemplaza la última frase
assert [s['frases'][-1]['texto'] for s in r['shorts']] == [resumen.cierre(1), resumen.cierre(2), resumen.cierre(3)]
cierres = sum(resumen.letras(resumen.cierre(n)) for n in (1, 2, 3))
extras = sum(resumen.letras(t['es']) for _, t in resumen.EXTRAS)  # páginas y testimonios: una sola voz para los 3
assert r['costo']['letras'] == (2 * resumen.letras(bueno['frases'][0]['texto']) + resumen.letras(malo['frases'][0]['texto'])
                                + cierres + extras), r['costo']
# antes del cierre, en todos: la frase de las páginas oficiales y la de los testimonios de WhatsApp (fabian, 03/11/2026)
for n, s_ in enumerate(r['shorts'], 1):
    assert [f.get('id') for f in s_['frases'][-3:]] == ['WEBS', 'TESTIMONIOS', None], s_['frases'][-3:]
    assert resumen.ids(s_, n)[-3:] == ['WEBS', 'TESTIMONIOS', f'S{n}F2'] and resumen.ids(s_, n)[0] == f'S{n}F1'
web = r['shorts'][0]['frases'][-3]['texto']
assert 'GSM Prime punto co' in web and 'Xiaomi Unlock punto com' in web
assert 'descripción del tutorial completo' in r['shorts'][0]['frases'][-2]['texto']  # en el Short el enlace no se toca
antes = json.dumps(r, sort_keys=True)
assert json.dumps(resumen.poner_extras(r), sort_keys=True) == antes  # no se repiten ni se mueven
viejo = {'shorts': [{'frases': [{'texto': 'Uno con cualquier parche.', 'tomas': [[18, 22]]},
                                {'texto': resumen.cierre(1), 'tomas': [[40, 44]]}]}]}  # un guion de antes del 03/11
resumen.poner_extras(viejo)
assert [f.get('id') for f in viejo['shorts'][0]['frases']] == [None, 'WEBS', 'TESTIMONIOS', None]
assert resumen.ids(viejo['shorts'][0], 1) == ['S1F1', 'WEBS', 'TESTIMONIOS', 'S1F2']  # las voces ya hechas siguen sirviendo
n_ = resumen.letras('Uno con cualquier parche. ' + resumen.cierre(1))  # el largo ideal no cuenta las frases fijas
assert f'Short 1: {n_} letras' in ' '.join(resumen.validar(viejo)), resumen.validar(viejo)
assert [c['id'] for c in resumen._sin_logo([{'id': 'S1F1'}, {'id': 'WEBS'}])] == ['S1F1', 'GANCHO']  # sin logo de Xiaomi
from PIL import Image  # noqa: E402
with Image.open(resumen.banner_webs(d)) as im:
    assert im.mode == 'RGBA' and im.size[0] <= 1080 - 80 and im.getpixel((0, 0))[3] == 0, im.size
assert any('sin PC' in a for a in r['avisos']) and any('sin toma' in a for a in r['avisos'])
assert not any(a.startswith('Short 1:') for a in r['avisos']), r['avisos']
try:
    resumen.voz(d)  # sin el SI de fabian no gasta
    raise AssertionError('generó voz sin confirmar')
except PermissionError:
    pass
t = resumen.textos(d)
# la descripción (fabian, 03/11/2026): primero la línea del video y enseguida el WhatsApp
assert 'DESCRIPCIÓN:\nUno.\n\n🌐 WhatsApp Grupo:' in t and t.index('Uno.') < t.index('wa.me/573186888787'), t[:400]
assert 'DESCRIPCIÓN:\nOne.\n\n🌐 WhatsApp Group:' in t and 'DESCRIPCIÓN:\nUm.\n\n🌐 Grupo no WhatsApp:' in t
assert '<' not in t and '📌' in t
shutil.rmtree(d, ignore_errors=True)
print('ok: 3 Shorts resumen (sin gastar)')
