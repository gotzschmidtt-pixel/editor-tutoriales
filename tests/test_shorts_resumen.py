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
assert r['costo']['letras'] == 2 * resumen.letras(bueno['frases'][0]['texto']) + resumen.letras(malo['frases'][0]['texto']) + cierres
assert any('sin PC' in a for a in r['avisos']) and any('sin toma' in a for a in r['avisos'])
assert not any(a.startswith('Short 1:') for a in r['avisos']), r['avisos']
try:
    resumen.voz(d)  # sin el SI de fabian no gasta
    raise AssertionError('generó voz sin confirmar')
except PermissionError:
    pass
t = resumen.textos(d)
assert t.index('wa.me/573186888787') < t.index('Uno.') and '<' not in t and '📌' in t
shutil.rmtree(d, ignore_errors=True)
print('ok: 3 Shorts resumen (sin gastar)')
