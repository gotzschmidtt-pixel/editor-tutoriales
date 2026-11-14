"""Prueba de «🩹 Qué se corrige del original» (fabian, 13/11/2026). SIN internet y SIN gastar.
Un proyecto inventado «HONOR 400 LITE» con una transcripción que tiene los 7 errores del tutorial Honor 400 Lite, y un
video chico con «frpunlock.co/files» en pantalla:
- encuentra el intento fallido (vol más → vol menos), la web en la voz y en pantalla, el otro modelo dicho como si fuera
  este (pero NO el de la lista «sirve desde el Honor 600 Lite»), «en unos minutos» por la KEY (pero NO «esperamos unos
  segundos a que prenda»), los testimonios largos, los comentarios y las esperas;
- el informe sale como lo escribe fabian; lo desmarcado no se aplica;
- al aplicar: cortes y acelerados en acortar.json (y «Acortar» los respeta al volver a buscar), el testimonio en
  testimonios.json con su trozo de 25 s, la placa tapa la web (con el lector de pantalla, si está) y queda el respaldo;
- la IA del guion recibe las correcciones y el texto del guion se arregla solo.
Uso: python tests/test_corregir_original.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('correcciones', 'acortar'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import corregir_original as co  # noqa: E402
fallos = []


def ok(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond:
        fallos.append(msg)


# (segundo, frase) de una grabación inventada de 15 min
FRASES = [
    (2, 'Hola amigos, aquí tenemos un Honor 400 Lite con cuenta de Google.'),
    (10, 'Este método sirve para todos los modelos desde el Honor 600 Lite y el Magic 8 Pro Lite.'),
    (40, 'El programa lo descargan en nuestra página www.frpunlock.com gratis.'),
    (60, 'Mandan su serial y en unos minutos tenemos la key del servidor.'),
    (120, 'Ahora lo vamos a apagar.'),
    (130, 'Con el teléfono apagado vamos a presionar la tecla de vol más y conecto el cable.'),
    (150, 'Esperamos unos segundos.'),
    (175, 'Me disculpan, me equivoqué, es vol menos, otra vez vamos.'),
    (190, 'Bueno, son cosas que pasan cuando uno graba en vivo.'),
    (205, 'Vol menos y conectamos el cable y entramos en modo fastboot.'),
    (240, 'Ahora leemos el serial con el programa, esperamos unos segundos a que prenda.'),
    (300, 'Únanse a nuestro canal en WhatsApp donde subimos todos los testimonios.'),
    (315, 'Este es un cliente de Pakistán, ahí está la conversación real.'),
    (330, 'Miren aquí está el después, nuestros clientes nos han compartido sus fotos.'),
    (350, 'Hay cientos de testimonios para que tengan confianza en nuestro canal.'),
    (370, 'También en Facebook subimos los testimonios de clientes.'),
    (400, 'Vamos a la acción, pegamos la key en el programa.'),
    (430, 'Le damos clic y el dispositivo se va a reiniciar.'),
    (440, 'Listo, se reinicia y se está formateando.'),
    (455, 'Esperemos a que termine de formatear, todavía cargando.'),
    (470, 'Sigue cargando el logo, esperamos.'),
    (500, 'Si tienen alguna duda pueden escribirnos en los comentarios.'),
    (512, 'Cualquier duda en los comentarios les vamos a responder.'),
    (524, 'Miren cuántas personas nos escriben en los comentarios.'),
    (560, 'Ya hemos realizado el proceso a este Honor Magic 8 Lite exitosamente.'),
    (600, 'Seleccionamos el idioma, la región y aceptamos todo.'),
    (612, 'No nos conectamos a una red wifi, le damos más tarde.'),
    (625, 'Más tarde, continuar y finalizar.'),
    (660, 'Y como ven ya no pide la cuenta de Google.'),
    (880, 'Eso fue todo, nos vemos en el próximo video.'),
]
DUR = 900


def proyecto(base):
    d = os.path.join(base, 'HONOR 400 LITE')
    os.makedirs(d)
    pal = []
    for s, f in FRASES:
        ws = f.split()
        for k, w in enumerate(ws):
            pal.append({'texto': w, 'inicio': s + k * 0.35, 'fin': s + k * 0.35 + 0.3})
    json.dump(pal, open(os.path.join(d, 'transcripcion.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    # lo que se lee en pantalla (mapa del video): la barra con la web prohibida de 40 a 70 s
    cuadros = [{'t': 0.0, 'texto': 'Verificar cuenta'}, {'t': 40.0, 'texto': 'https://frpunlock.co/files | Descargas'},
               {'t': 70.0, 'texto': 'HONOR FRP Key'}, {'t': 300.0, 'texto': 'WhatsApp | Canal'}, {'t': 400.0, 'texto': 'Erase FRP By Code'}]
    json.dump({'cuadros': cuadros}, open(os.path.join(d, 'mapa_video.json'), 'w', encoding='utf-8'))
    fuente = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf') if os.path.exists(f)), None)
    texto = (f"fontfile='{fuente.replace(':', chr(92) + ':')}':" if fuente else '') + \
        "text='frpunlock.co/files':fontsize=40:fontcolor=black:box=1:boxcolor=white:x=60+t:y=40:enable='between(t,40,70)'"
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c=gray:s=640x360:r=5:d={DUR}',
                    '-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo', '-t', str(DUR), '-vf', 'drawtext=' + texto,
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', os.path.join(d, 'original.mp4')], check=True)
    return d


def main():
    base = tempfile.mkdtemp()
    co.CONOCIMIENTOS = os.path.join(base, 'sin_conocimientos')  # las reglas de aquí, no las privadas
    try:
        d = proyecto(base)
        ok(co.marca_y_modelo(d) == ('HONOR', 'honor 400 lite'), f'marca y modelo del proyecto: {co.marca_y_modelo(d)}')
        datos = co.buscar(d)
        L = datos['correcciones']
        por = lambda t: [c for c in L if c['tipo'] == t]
        print(co.informe(datos))
        f = por('intento_fallido')
        ok(len(f) == 1 and 125 <= f[0]['inicio'] <= 135 and 195 <= f[0]['fin'] <= 206 and 'vol' in f[0]['resumen'],
           f"intento fallido de vol más a vol menos: {[(c['inicio'], c['fin'], c['resumen']) for c in f]}")
        w = por('web_prohibida')
        ok(any(c['donde'] == 'voz' and 40 <= c['inicio'] < 45 for c in w), 'la web prohibida en la voz')
        ok(any(c['donde'] == 'pantalla' and c['inicio'] == 40 and c['fin'] == 70 for c in w), 'la web prohibida en pantalla (40-70 s)')
        m = por('modelo_equivocado')
        ok(len(m) == 1 and 559 <= m[0]['inicio'] <= 565 and m[0]['seguridad'] == 'alta',
           f"«a este Honor Magic 8 Lite» sí; la lista del comienzo no: {[(c['inicio'], c['dijo']) for c in m]}")
        p = por('promesa_tiempo')
        ok(len(p) == 1 and 60 <= p[0]['inicio'] <= 64 and 'horas' in p[0]['correccion'],
           f"«en unos minutos» por la key (y no «esperamos unos segundos»): {[(c['inicio'], c['dice']) for c in p]}")
        t = por('testimonio_largo')
        ok(len(t) == 1 and 298 <= t[0]['inicio'] <= 301 and t[0]['fin'] >= 372, f"testimonios largos: {[(c['inicio'], c['fin']) for c in t]}")
        c_ = por('comentarios')
        ok(len(c_) == 1 and 498 <= c_[0]['inicio'] <= 501, f"comentarios a mitad del video: {[(c['inicio'], c['fin']) for c in c_]}")
        e = por('espera_larga')
        ok(any(c['que'] == 'reinicio y formateo' and 435 <= c['inicio'] <= 445 for c in e), f"espera de formateo (no desde «se va a reiniciar»): {[(c['inicio'], c['que']) for c in e]}")
        ok(any(c['que'] == 'configuración' and 595 <= c['inicio'] <= 605 for c in e), 'espera de configuración')
        ok(not any(c['tipo'] == 'comentarios' and c['inicio'] > 800 for c in L), 'el «nos vemos» del cierre no se toca')
        ok(len(por('paginas_min_1_2')) == 1, 'regla fija: el original no nombra tus páginas entre el minuto 1 y 2')
        ok(os.path.exists(os.path.join(d, co.INFORME)) and 'Qué se corrige del original' in open(os.path.join(d, co.INFORME), encoding='utf-8').read(),
           'deja QUE_SE_CORRIGE.md')

        # desmarco la espera de configuración: no se aplica
        conf = next(c for c in L if c['tipo'] == 'espera_larga' and c['que'] == 'configuración')
        conf['usar'] = False
        json.dump(datos, open(os.path.join(d, co.ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False)
        co.aplicar(d)
        plan = json.load(open(os.path.join(d, 'acortar.json'), encoding='utf-8'))
        ids = {x['id'] for x in plan['tramos']}
        ok(f[0]['id'] in ids and t[0]['id'] in ids and c_[0]['id'] in ids, 'cortes aprobados en acortar.json')
        ok(conf['id'] not in ids, 'lo desmarcado no se aplica')
        tes = json.load(open(os.path.join(d, 'testimonios', 'testimonios.json'), encoding='utf-8'))['TESTIMONIOS']
        ok(len(tes) == 1 and tes[0]['origen'] == 'correccion' and os.path.exists(os.path.join(d, 'testimonios', tes[0]['archivo'])),
           'el trozo de testimonios va al cierre')
        largo = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                      os.path.join(d, 'testimonios', tes[0]['archivo'])], capture_output=True, text=True).stdout)
        ok(23 <= largo <= 27, f'el trozo dura ~25 s ({largo:.1f})')
        co.aplicar(d)  # aplicar dos veces no duplica
        tes = json.load(open(os.path.join(d, 'testimonios', 'testimonios.json'), encoding='utf-8'))['TESTIMONIOS']
        ok(len(tes) == 1, 'aplicar dos veces no duplica el testimonio')

        try:
            import rapidocr_onnxruntime  # noqa: F401
            hay_ocr = True
        except ImportError:
            hay_ocr = False
        if hay_ocr:
            ok(os.path.exists(os.path.join(d, co.RESPALDO)), 'queda original_sin_corregir.mp4')
            ok(co.cajas_web(d, os.path.join(d, co.RESPALDO), 50, 52, ['frpunlock']), 'en el respaldo la web se sigue leyendo')
            ok(not co.cajas_web(d, os.path.join(d, 'original.mp4'), 42, 68, ['frpunlock']), 'la placa tapa la web en original.mp4')
        else:
            print('· sin el lector de pantalla (rapidocr): no pruebo la placa')

        import acortar  # «Acortar» al volver a buscar no pierde las correcciones
        tramos = acortar.con_correcciones(d, [{'id': 'A01', 'inicio': 180.0, 'fin': 260.0, 'tipo': 'silencio', 'accion': 'cortar', 'usar': True}])
        ok(any(x['id'] == f[0]['id'] for x in tramos) and all(not (x['tipo'] == 'silencio' and x['inicio'] < f[0]['fin'] - 0.5) for x in tramos),
           f"Acortar respeta las correcciones: {[(x['id'], x['inicio'], x['fin']) for x in tramos]}")

        txt = co.texto_para_ia(d)
        ok('CORRECCIONES DEL ORIGINAL' in txt and 'horas' in txt, 'la IA del guion recibe las correcciones')
        b = [{'id': 'L1', 'texto': 'Descárgalo en frp unlock punto com.'},
             {'id': 'L2', 'texto': 'La Key llega en unos minutos desde el servidor.'},
             {'id': 'L3', 'texto': 'Ya lo hicimos con este Honor Magic 8 Lite.'},
             {'id': 'L4', 'texto': 'Sirve para todos los modelos desde el Honor 600 Lite.'},
             {'id': 'L5', 'texto': 'Esperamos unos segundos a que prenda.'}]
        av = co.correcciones_guion(d, b)
        ok('frp' not in b[0]['texto'].lower() and 'Xiaomi Unlock' in b[0]['texto'], f"guion: web → tus páginas ({b[0]['texto']})")
        ok('minutos' not in b[1]['texto'] and 'horas' in b[1]['texto'], f"guion: minutos → horas ({b[1]['texto']})")
        ok('Honor 400 Lite' in b[2]['texto'], f"guion: otro modelo → el del proyecto ({b[2]['texto']})")
        ok(b[3]['texto'].endswith('Honor 600 Lite.') and b[4]['texto'] == 'Esperamos unos segundos a que prenda.' and len(av) == 3,
           'guion: la lista de modelos y «unos segundos a que prenda» no se tocan')

        # regla fija: páginas entre el minuto 1 y 2 (voz en el guion + placa en etiquetas)
        g = [{'id': f'L{k:02d}', 'texto': 'palabra ' * 25} for k in range(1, 15)]  # ~11 s cada uno, 2,5 min
        largo = lambda x: len(x['texto'].split()) / 2.5 + 1
        av = co.paginas_min_1_2(g, largo, d)
        con = [x['id'] for x in g if 'Xiaomi Unlock' in x['texto']]
        t0 = sum(largo(x) for x in g[:int(con[0][1:]) - 1]) if con else -1
        ok(len(con) == 1 and 50 <= t0 <= 105 and av, f'el guion agrega tus páginas en un bloque del minuto 1-2 ({con}, empieza en {t0:.0f} s)')
        ok(co.paginas_min_1_2(g, largo, d) == [], 'si ya las nombra, no las repite')
        noticia = os.path.join(base, 'MOVISTAR_NOTICIA')
        os.makedirs(noticia)
        g2 = [{'id': f'L{k:02d}', 'texto': 'palabra ' * 25} for k in range(1, 9)]
        ok(co.paginas_min_1_2(g2, largo, noticia) == [], 'en una noticia (sin marca) no se agregan')
        bl = [{'id': 'L01', 'inicio_min': 0, 'texto': 'hola'}, {'id': 'L07', 'inicio_min': 70.0, 'texto': 'Visita G S M Prime punto co.'}]
        e = co.etiqueta_paginas(bl, [])
        ok(e and e['bloque'] == 'L07' and e['tipo'] == 'web' and 'XIAOMIUNLOCK' in e['texto'], f'placa de tus páginas en el minuto 1-2: {e}')
        ok(co.etiqueta_paginas(bl, [{'tipo': 'web', 't': 80}]) is None, 'si ya hay una placa web en ese minuto no se duplica')
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print('\nTODO BIEN' if not fallos else f'\nFALLAN {len(fallos)}')
    sys.exit(1 if fallos else 0)


if __name__ == '__main__':
    main()
