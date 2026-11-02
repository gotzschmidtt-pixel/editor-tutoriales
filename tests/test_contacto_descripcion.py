"""El bloque de WhatsApp de fabian (02/11/2026) va después del primer párrafo de la descripción, una sola vez, en el idioma
del video; las noticias (proyectos sin marca de teléfono) no lo llevan."""
import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
import youtube  # noqa: E402

d = youtube.con_contacto('Primer párrafo.\n\nSegundo párrafo.', 'es')
assert d.startswith('Primer párrafo.\n\n🌐 WhatsApp Grupo:'), d[:80]
assert d.endswith('Segundo párrafo.') and d.count('wa.me/573186888787') == 1
assert youtube.con_contacto(d, 'es') == d  # no se repite
en = youtube.con_contacto('Only one paragraph', 'en')
assert 'Support Mexico' in en and 'wa.me/526645320704' in en
assert 'Suporte Europa (Espanha)' in youtube.con_contacto('Um', 'pt')
print('ok: contacto en la descripción')
