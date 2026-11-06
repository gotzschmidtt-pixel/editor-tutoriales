"""La descripción de fabian (regla nueva del 03/11/2026: «¿Una línea sobre el video antes de tu bloque de contacto? SÍ»):
primero UNA línea que dice de qué trata el video, enseguida el bloque de WhatsApp (una sola vez, en el idioma del video) y
después el resto. Si el bloque estaba arriba (la regla vieja) o en otro lugar, se mueve debajo de la línea. Los capítulos
van después del primer párrafo que sigue al contacto, nunca dentro del bloque. Las noticias no llevan el bloque (eso lo
decide app.yt_contacto). Necesita mis_conocimientos/youtube_canal/contacto_descripcion.json (sin él no hay bloque).
Uso: python tests/test_contacto_descripcion.py"""
import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
import youtube  # noqa: E402

if not os.path.isfile(youtube.CONTACTO):
    sys.exit('FALTA ' + youtube.CONTACTO + ': enlaza tu conocimiento (GUIONES-IA) como mis_conocimientos para esta prueba.')

LINEA = 'Quita la cuenta Google de tu Honor Magic 8 Lite con PC.'
d = youtube.con_contacto(LINEA + '\n\nPrimer párrafo.\n\nSegundo párrafo.', 'es')
partes = d.split('\n\n')
assert partes[0] == LINEA, d[:120]  # la línea del video, sola, arriba
assert partes[1].startswith('🌐 WhatsApp Grupo:'), d[:200]  # enseguida el contacto
assert d.endswith('Primer párrafo.\n\nSegundo párrafo.') and d.count('wa.me/573186888787') == 1
assert youtube.con_contacto(d, 'es') == d  # no se repite ni se mueve otra vez

# como quedaba con la regla vieja (contacto en la primera línea): se arregla solo
viejo = youtube.con_contacto('', 'es') + '\n\n' + LINEA + '\n\nSegundo párrafo.'
nuevo = youtube.con_contacto(viejo, 'es')
assert nuevo.startswith(LINEA + '\n\n🌐 WhatsApp Grupo:') and nuevo.count('wa.me/573186888787') == 1 and '\n\n\n' not in nuevo, nuevo
assert youtube.con_contacto(nuevo, 'es') == nuevo

# un párrafo entero en una línea: arriba solo su primera frase; el resto del párrafo va después del contacto
largo = ('Hoy te enseño a quitar la cuenta de Google de tu Honor sin perder tiempo y sin entregarlo a nadie. '
         'Sirve para Android 15, 16 y 17 con cualquier parche de seguridad, y lo hacemos con una PC sencilla.')
x = youtube.con_contacto(largo, 'es').split('\n\n')
assert x[0] == 'Hoy te enseño a quitar la cuenta de Google de tu Honor sin perder tiempo y sin entregarlo a nadie.', x[0]
assert x[1].startswith('🌐') and x[-1].startswith('Sirve para Android 15'), x
# si la descripción empieza con un enlace o un hashtag no hay línea del video: el contacto va primero
assert youtube.con_contacto('https://gsmprime.co\n\nTexto.', 'es').startswith('🌐 WhatsApp Grupo:')
assert youtube.linea_del_video('#Honor #FRP') == ('', '#Honor #FRP')

# un rótulo con su enlace debajo («📥 Descarga aquí…:»): no se separa de su enlace; arriba va el título del video
rot = '📥 Descarga aquí la herramienta:\nhttps://gsmprime.co/honor\n\nMás texto.'
TIT = 'Quitar, Eliminar Cuenta Google Honor Magic 8 Lite'
r = youtube.con_contacto(rot, 'es', TIT).split('\n\n')
assert r[0] == TIT and r[1].startswith('🌐 WhatsApp Grupo:'), r
assert r[-2] == '📥 Descarga aquí la herramienta:\nhttps://gsmprime.co/honor' and r[-1] == 'Más texto.', r
assert youtube.con_contacto('\n\n'.join(r), 'es', TIT) == '\n\n'.join(r)  # otra pasada no cambia nada
assert youtube.con_contacto(rot, 'es').startswith('🌐 WhatsApp Grupo:')  # sin título: el contacto primero, el rótulo entero
assert '📥 Descarga aquí la herramienta:\nhttps://gsmprime.co/honor' in youtube.con_contacto(rot, 'es')
# sin «:» pero con el enlace o una lista en la línea siguiente: también es un rótulo
assert youtube.linea_del_video('Descarga la herramienta\nhttps://x.co', TIT) == (TIT, 'Descarga la herramienta\nhttps://x.co')
assert youtube.linea_del_video('Lo que necesitas\n- Una PC', TIT)[0] == TIT
assert youtube.linea_del_video('https://x.co\n\nTexto.', TIT) == (TIT, 'https://x.co\n\nTexto.')
assert youtube.linea_del_video(LINEA + '\n\nOtro.', TIT) == (LINEA, 'Otro.')  # si la primera sirve, se usa esa

# inglés y portugués: su línea y su bloque
en = youtube.con_contacto('Remove the Google account from your Honor.\n\nOne more paragraph.', 'en')
assert en.startswith('Remove the Google account from your Honor.\n\n🌐 WhatsApp Group:') and 'wa.me/526645320704' in en
pt = youtube.con_contacto('Remova a conta Google do seu Honor.', 'pt')
assert pt.startswith('Remova a conta Google do seu Honor.\n\n🌐 Grupo no WhatsApp:'), pt[:120]
assert youtube.con_contacto('', 'pt').startswith('🌐 Grupo no WhatsApp:')  # sin texto: solo el bloque

# los capítulos: después del primer párrafo que sigue al contacto (antes caían dentro del bloque, tras «📞 Para más detalles…»)
cap = '0:00 Inicio\n1:10 Paso uno'
c = youtube.con_capitulos(d, cap)
p = c.split('\n\n')
i = next(k for k, t in enumerate(p) if t.startswith('⏱️ CAPÍTULOS'))
assert p[0] == LINEA and p[i - 1] == 'Primer párrafo.' and all('wa.me/' not in t for t in p[i:]), c
assert youtube.con_capitulos(c, cap) == c  # no se repiten
solo = youtube.con_capitulos(youtube.con_contacto(LINEA, 'es'), cap)  # sin más texto: al final, debajo del contacto
assert solo.split('\n\n')[0] == LINEA and solo.endswith('⏱️ CAPÍTULOS\n' + cap), solo
print('ok: una línea del video, enseguida el contacto y los capítulos después (es, en, pt)')
