"""El bloque de WhatsApp de fabian (02/11/2026) va LO PRIMERO de la descripción, una sola vez, en el idioma del video; si
ya estaba en otro lugar se mueve arriba. Las noticias (proyectos sin marca de teléfono) no lo llevan."""
import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
import youtube  # noqa: E402

d = youtube.con_contacto('Primer párrafo.\n\nSegundo párrafo.', 'es')
assert d.startswith('🌐 WhatsApp Grupo:'), d[:80]
assert d.endswith('Primer párrafo.\n\nSegundo párrafo.') and d.count('wa.me/573186888787') == 1
assert youtube.con_contacto(d, 'es') == d  # no se repite
viejo = 'Primer párrafo.\n\n' + youtube.con_contacto('', 'es') + '\n\nSegundo párrafo.'  # como quedaba antes: tras el 1er párrafo
nuevo = youtube.con_contacto(viejo, 'es')
assert nuevo.startswith('🌐 WhatsApp Grupo:') and nuevo.count('wa.me/573186888787') == 1 and '\n\n\n' not in nuevo
en = youtube.con_contacto('Only one paragraph', 'en')
assert en.startswith('🌐 WhatsApp Group:') and 'wa.me/526645320704' in en
assert youtube.con_contacto('Um', 'pt').startswith('🌐 Grupo no WhatsApp:')
print('ok: contacto al principio de la descripción')
