"""YouTube rechaza < y > en títulos y descripciones (fabian, 02/11/2026): la app los cambia por flechas y las comillas
« » por rectas; y la descripción siempre lleva capítulos, una sola vez."""
import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
import youtube  # noqa: E402

assert youtube.limpiar_yt('Ajustes > Google «ya»') == 'Ajustes → Google "ya"'
assert youtube.limpiar_yt(['a<b', 'c']) == ['a←b', 'c']
cap = '0:00 Inicio\n1:10 Paso'
d = youtube.con_capitulos('🌐 WhatsApp:\nhttps://wa.me/1\n\nPrimer párrafo.\n\nSegundo.', cap)
assert d.split('\n\n')[2].startswith('⏱️ CAPÍTULOS\n0:00 Inicio'), d
assert youtube.con_capitulos(d, cap) == d  # no se repiten
print('ok: limpiar YouTube y capítulos')
assert youtube.signos_es('Ya probaste todo? Así sí') == '¿Ya probaste todo? Así sí'
assert youtube.signos_es('¿Ya? Listo!') == '¿Ya? ¡Listo!', youtube.signos_es('¿Ya? Listo!')
assert youtube.signos_es('Honor 8 Lite | Todos 2026') == 'Honor 8 Lite | Todos 2026'
print('ok: signos de apertura en español')
