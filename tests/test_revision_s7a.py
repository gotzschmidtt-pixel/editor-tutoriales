"""Prueba rápida de los arreglos de la revisión S7a (servicios). Sin internet y sin gastar nada: todo va a una carpeta
temporal (tus proyectos, tus videos y tus ajustes no se tocan).
- «☁ Hacer en la nube» no se lleva el PIN del celular (sal y huella), el tema de avisos ni la cuenta de YouTube;
- los tiempos por letra de la voz quedan sin las etiquetas de emoción aunque emociones.py cambie el texto;
- con 0 en «cambio de imagen cada … s» o «plano cada … s» los cortes del avatar terminan (antes se colgaba);
- el montaje del avatar cuenta los cuadros sobre el tiempo total (la imagen no se adelanta a la voz);
- «HyperOS 2.0?» lleva su «¿» al inicio y no en medio del número;
- las etiquetas de YouTube no pasan de 500 letras y la descripción no pasa de 5000 bytes.
Uso: python tests/test_revision_s7a.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile, threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('voz', 'avatar', 'youtube'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import voz  # noqa: E402
import emociones  # noqa: E402
import ahorro  # noqa: E402
import youtube  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp(prefix='s7a_')
try:
    # 1. el paquete para la nube sin PIN, sin tema de avisos y sin la cuenta de YouTube
    d = os.path.join(tmp, 'proy')
    os.makedirs(d)
    open(os.path.join(d, 'original.mp4'), 'wb').write(b'x')
    aj = os.path.join(tmp, 'ajustes.json')
    json.dump({'modelo': 'm', 'celular': {'activo': True, 'sal': 'abc', 'pin_hash': 'def'}, 'avisos': {'tema': 'estudio-1'},
               'youtube': {'cliente_id': 'c'}, 'otro': {'pin_hash': 'z', 'tema': 't', 'bien': 1}}, open(aj, 'w', encoding='utf-8'))
    subprocess.run([sys.executable, os.path.join(RAIZ, 'nube', 'preparar.py'), '--proyecto', d, '--ajustes', aj,
                    '--estilos', tmp], check=True, capture_output=True)
    m = json.load(open(os.path.join(d, 'para_claude', 'parametros.json'), encoding='utf-8'))['ajustes']
    ok(m == {'modelo': 'm', 'otro': {'bien': 1}}, f'el paquete de la nube lleva datos del PIN, avisos o YouTube: {m}')

    # 2. alineación sin etiquetas aunque moderar cambie el texto
    def al_de(t):
        return {'characters': list(t), 'character_start_times_seconds': [k * 0.1 for k in range(len(t))],
                'character_end_times_seconds': [k * 0.1 + 0.1 for k in range(len(t))]}
    for texto, queda in [('[excited] ¡Tu Honor está bloqueado por la cuenta de Google!', '¡Tu Honor está bloqueado por la cuenta de Google!'),
                         ('[curious] ¿Sabías esto?', '¿Sabías esto?'), ('Hola [laughs] amigo.', 'Hola amigo.')]:
        pedido, _ = emociones.moderar(texto)
        r = voz.sin_etiquetas(al_de(pedido))
        ok(''.join(r['characters']) == queda and len(r['character_start_times_seconds']) == len(queda),
           f'alineación de {texto!r}: {"".join(r["characters"])!r}')

    # 8. con 0 los cortes terminan
    hilo = threading.Thread(target=lambda: ahorro.cortes(0, 100, [], {'rotar_inicio': 0, 'rotar': 0}), daemon=True)
    hilo.start()
    hilo.join(5)
    ok(not hilo.is_alive(), 'cortes() con 0 se cuelga')
    a = ahorro.ajustes({'rotar_inicio': 0, 'rotar': '0', 'plano_s': 0})
    ok((a['rotar_inicio'], a['rotar'], a['plano_s']) == (1.0, 1.0, 3.0), f'ajustes con 0: {a}')

    # 9. los cuadros de cada trozo suman exacto el total (antes cada -t redondeaba y se iba sumando)
    pedidos = []
    ahorro._clip_apoyo = lambda f, dd, salida, k, desde=0.0, n=None: pedidos.append(n)
    ahorro._clip_avatar = lambda f, desde, dd, salida, acercado=False, n=None: pedidos.append(n)
    ahorro.ff = lambda *x: None
    ahorro.dur = lambda f: 0
    tramos = [{'tipo': 'voz', 's': 0.0, 'e': 100.0}, {'tipo': 'avatar', 's': 100.0, 'e': 118.7}, {'tipo': 'voz', 's': 118.7, 'e': 240.0}]
    ahorro.montar(tramos, 'voz.mp3', ['av.mp4'], ['a.png', 'b.png'], os.path.join(tmp, 'x.mp4'),
                  {'final_s': 0, 'rotar_inicio': 2.0, 'rotar': 3.3, 'plano_s': 15},
                  [round(0.37 + k * 3.13, 3) for k in range(76)])
    ok(sum(pedidos) == 240 * ahorro.FPS and all(n > 0 for n in pedidos), f'cuadros del avatar ahorro: {sum(pedidos)} de {240 * ahorro.FPS}')

    # 4. signos con números de versión
    for t, bien in [('Quitar FRP Xiaomi con HyperOS 2.0?', '¿Quitar FRP Xiaomi con HyperOS 2.0?'),
                    ('Funciona en Android 15.1? Sí!', '¿Funciona en Android 15.1? ¡Sí!'),
                    ('Ya probaste todo? Así sí', '¿Ya probaste todo? Así sí')]:
        ok(youtube.signos_es(t) == bien, f'signos_es({t!r}) = {youtube.signos_es(t)!r}')

    # 7 y 13. etiquetas de 500 letras como mucho (comillas y comas cuentan), descripción en bytes e idioma de la voz
    visto = {}

    def pedir(c, metodo, url, q=None, cuerpo=None, **k):
        visto.update(cuerpo or {})
        raise youtube.ErrorYT('sin internet en la prueba')
    youtube.pedir = pedir
    video = os.path.join(tmp, 'v.mp4')
    open(video, 'wb').write(b'x')
    try:
        youtube.subir_video({}, video, {'titulo': 't', 'descripcion': 'ñ😀' * 2000, 'idioma': 'en',
                                        'etiquetas': ['quitar cuenta google honor 8 lite'] * 22})
    except youtube.ErrorYT:
        pass
    sn = visto.get('snippet') or {}
    et = sn.get('tags') or []
    ok(et and sum(len(x) + (2 if ' ' in x else 0) for x in et) + len(et) - 1 <= 500, f'etiquetas: {len(et)}')
    ok(0 < len(sn.get('description', '').encode('utf-8')) <= 5000, 'descripción de más de 5000 bytes')
    ok(sn.get('defaultAudioLanguage') == 'en' and sn.get('defaultLanguage') == 'en', f'idioma del video: {sn.get("defaultAudioLanguage")}')
    ok(visto.get('status', {}).get('privacyStatus') == 'private', 'la subida debe quedar privada por defecto')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión S7a (nube sin PIN, voz sin etiquetas, avatar sin cuelgue ni desfase, signos y límites de YouTube)')
sys.exit(1 if fallos else 0)
