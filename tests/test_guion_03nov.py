"""Prueba rápida de lo que contestó fabian el 03/11/2026 sobre el guion del tutorial largo, sin videos tuyos, sin red y sin
gastar nada (no se llama a ninguna IA; los videos son sintéticos de ffmpeg):
- el gancho dura de 30 a 40 s (antes unos 45, con aviso recién a los 60): el encargo lo pide, la revisión del guion y la
  del montaje avisan si pasa de 40 s, y el modo avatar ahorro deja el gancho sin cara en ~35 s;
- en los procesos con PC (Honor, Motorola, Xiaomi cuenta Google…) el guion aclara al principio que basta una PC sencilla,
  o un café internet, o una prestada de un amigo o familiar; nunca en los dos procesos sin PC (cuenta Mi de Xiaomi y
  liberación de bandas de iPhone) ni en una noticia; la revisión avisa si falta, si está de más o si dice «sin PC»;
- lo que NO hay que hacer va dentro del paso donde aplica, y el porqué solo en los pasos delicados;
- los testimonios van dentro del cierre, en 1-2 frases, y solo si el proyecto tiene testimonios reales.
Uso: python tests/test_guion_03nov.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
sys.path.insert(0, os.path.join(RAIZ, 'avatar'))
import ia  # noqa: E402
import rotar  # noqa: E402
import ahorro  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def proyecto(nombre, idea=''):
    d = os.path.join(tmp, nombre)
    os.makedirs(d)
    shutil.copy(video, os.path.join(d, 'original.mp4'))
    if idea:
        open(os.path.join(d, 'idea.txt'), 'w', encoding='utf-8').write(idea)
    return d


def bloque(bid, texto, gancho=False):
    b = {'id': bid, 'texto': texto, 'montaje': {'modo': 'lento', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0}}
    if gancho:
        b['gancho'] = True
    return b


PC_SI = ('Así queda tu Honor, libre y sin la cuenta. No necesitas una PC avanzada: basta una PC sencilla. '
         'Si no tienes, un café internet o pídela prestada a un amigo o familiar.')
PASOS = [bloque(f'L{k:02d}', ' '.join(['palabra'] * 60) + '.') for k in range(2, 8)]  # ~24 s cada uno

tmp = tempfile.mkdtemp(prefix='guion_03nov_')
viejo_cwd = os.getcwd()
try:
    video = os.path.join(tmp, 'original.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=5', '-t', '60', '-c:v',
                    'libx264', '-pix_fmt', 'yuv420p', video], check=True)
    honor = proyecto('HONOR_X8_FRP', 'Honor X8, quitar la cuenta de Google con la key')
    moto = proyecto('MOTOROLA_FRP_2026', 'Motorola, cuenta de Google con USB Redirector')
    mi = proyecto('XIAOMI_MI_ACCOUNT', 'Eliminar cuenta Mi de un Redmi Note 13 con el unlock code')
    bandas = proyecto('IPHONE_13_BANDAS', 'Liberación de bandas de un iPhone 13 con el IMEI y el número de serie')
    google_mi = proyecto('XIAOMI_REDMI_FRP', 'Quitar la cuenta de Google (FRP) de un Redmi')
    noticia = proyecto('MOVISTAR_TIGO', 'Noticia: Movistar ahora es Tigo')

    # 1. el encargo del guion: gancho de 30 a 40 s, PC sencilla al principio, avisos dentro del paso, porqué solo en lo delicado
    txt = ia.encargo(honor, 'guion', 'Honor X8, quitar la cuenta de Google', [])
    ini = txt[txt.find('INICIO (primer minuto)'):]
    ok('de 30 a 40 s' in ini and 'nunca más de 40' in ini, 'el gancho debería pedirse de 30 a 40 s')
    ok('unos 45 s' not in txt and 'de 30 a 60' not in txt, 'ya no debería pedir un gancho de unos 45 s (30 a 60)')
    for trozo in ('PC avanzada', 'PC sencilla', 'café internet', 'prestada a un amigo o familiar', 'nunca digas «sin PC»'):
        ok(trozo in ini, f'en Honor el gancho debería decir «{trozo}»')
    ok('LO QUE NO HAY QUE HACER' in txt and 'DENTRO del paso donde aplica' in txt,
       'el encargo debería pedir lo que NO hay que hacer dentro del paso donde aplica')
    ok('lo que NO hay que hacer, los pasos numerados, el cierre) va después' not in ini,
       'el inicio ya no debería mandar «lo que NO hay que hacer» a un bloque antes de los pasos')
    ok('EL PORQUÉ, SOLO EN LOS PASOS DELICADOS' in txt, 'el encargo debería pedir el porqué solo en los pasos delicados')
    ok('el porqué,\n  solo en los pasos delicados' in txt or 'el porqué, solo en los pasos delicados' in txt.replace('\n  ', ' '),
       'el largo del guion ya no debería pedir explicar el porqué de cada paso')
    ok('un paso delicado que conviene explicar más' in txt, 'las mejoras deberían preguntar por los pasos delicados')
    ok('TESTIMONIOS' not in txt, 'sin testimonios reales en el proyecto no debería pedir testimonios')

    for d, nombre in ((moto, 'Motorola'), (google_mi, 'Xiaomi cuenta Google')):
        r = ia.regla_inicio(d)
        ok('PC sencilla' in r and 'café internet' in r and 'nunca digas «sin PC»' in r, f'{nombre} usa PC: va la PC sencilla')
    for d, nombre, basta in ((mi, 'Xiaomi cuenta Mi', 'el unlock code o el IMEI'), (bandas, 'iPhone bandas', 'el IMEI y el número de serie')):
        r = ia.regla_inicio(d)
        ok('NO necesita PC' in r and basta in r, f'{nombre} va sin PC (basta {basta}): {r[:900]}')
        ok('pedirla prestada' not in r and 'nunca digas «sin PC»' not in r, f'{nombre} no lleva lo de la PC sencilla')
        ok(ia.proceso_pc(d) == (False, basta), f'{nombre}: proceso sin PC: {ia.proceso_pc(d)}')
    r = ia.regla_inicio(noticia)
    ok('PC sencilla' not in r and 'NO necesita PC' not in r, 'una noticia (sin marca) no lleva la regla de la PC')
    ok(ia.proceso_pc(honor) == (True, '') and ia.proceso_pc(noticia)[0] is None, 'Honor usa PC; una noticia no es un proceso')

    # 2. testimonios reales: dentro del cierre, en 1 o 2 frases, nunca inventados
    os.makedirs(os.path.join(honor, 'testimonios'))
    json.dump({'TESTIMONIOS': [{'archivo': 'cliente.mp4', 'momento': 'auto'}]},
              open(os.path.join(honor, 'testimonios', 'testimonios.json'), 'w', encoding='utf-8'))
    txt = ia.encargo(honor, 'guion', 'Honor X8, quitar la cuenta de Google', [])
    te = txt[txt.find('TESTIMONIOS:'):][:900]
    ok('DENTRO DEL CIERRE' in te and '1 o 2 frases' in te, f'los testimonios deberían ir dentro del cierre, en 1-2 frases: {te}')
    ok('bloque propio' not in te, 'los testimonios ya no deberían ir en un bloque propio')
    ok('Nunca inventes un testimonio' in te, 'debería prohibir testimonios inventados')
    ok('«clientes» y «confianza»' in te, 'la frase sigue diciendo «clientes» y «confianza» (ahí entra el video del testimonio)')

    # 3. la revisión: PC sencilla al principio en los procesos con PC; nada de eso en los sin PC; nunca «sin PC»
    con = [bloque('L01', PC_SI, gancho=True)] + PASOS
    ok(ia.falta_pc_sencilla(honor, con) == [], f'con la PC sencilla al principio no debería avisar: {ia.falta_pc_sencilla(honor, con)}')
    sin = [bloque('L01', 'Así queda tu Honor, libre y sin la cuenta.', gancho=True)] + PASOS
    ok(any(x.startswith('al principio') and 'PC sencilla' in x for x in ia.falta_pc_sencilla(honor, sin)),
       'sin la frase de la PC sencilla debería avisar en Honor')
    ok(any(x.startswith('al principio') for x in ia.falta_pc_sencilla(moto, sin)), 'y también en Motorola (usa PC)')
    tarde = [bloque('L01', 'Así queda tu Honor, libre y sin la cuenta.', gancho=True)] + PASOS + [bloque('L09', PC_SI)]
    ok(any(x.startswith('al principio') for x in ia.falta_pc_sencilla(honor, tarde)),
       'la frase de la PC sencilla recién al final (pasados ~90 s) no cuenta como «al principio»')
    dice = con + [bloque('L08', 'Y todo esto lo hicimos sin PC, desde el teléfono.')]
    ok(any(x.startswith('L08') and '«sin PC»' in x for x in ia.falta_pc_sencilla(honor, dice)),
       f'un bloque que dice «sin PC» en Honor debería avisar: {ia.falta_pc_sencilla(honor, dice)}')
    avanzada = con + [bloque('L08', 'Lo hicimos sin una PC avanzada, con la laptop vieja de la casa.')]
    ok(not any('«sin PC»' in x for x in ia.falta_pc_sencilla(honor, avanzada)), '«sin una PC avanzada» sí se puede decir')
    ok(any('va sin PC' in x and 'unlock code' in x for x in ia.falta_pc_sencilla(mi, con)),
       'en la cuenta Mi (sin PC) debería avisar que sobra lo de la PC sencilla')
    ok(ia.falta_pc_sencilla(mi, sin) == [] and ia.falta_pc_sencilla(bandas, sin) == [], 'sin PC y sin la frase: sin avisos')
    ok(ia.falta_pc_sencilla(noticia, sin) == [], 'una noticia no lleva avisos de la PC')
    ok(any('al principio' in x for x in ia.verificar_orden(honor, sin)), 'la revisión del guion debería incluir el aviso de la PC')

    # 4. el gancho avisa desde los 40 s (antes recién a los 60)
    medio = [bloque(f'L0{k}', ' '.join(['palabra'] * 37) + '.', gancho=True) for k in (1, 2, 3)] + PASOS  # ~46 s
    ok(any('pasa de 30-40 s' in x and 'unos 35 s' in x for x in ia.revisar_gancho(honor, medio)),
       f'un gancho de ~46 s debería avisar que pasa de 30-40 s: {ia.revisar_gancho(honor, medio)}')
    justo = [bloque(f'L0{k}', ' '.join(['palabra'] * 27) + '.', gancho=True) for k in (1, 2, 3)] + PASOS  # ~34 s
    ok(not any('dura unos' in x for x in ia.revisar_gancho(honor, justo)), 'un gancho de ~34 s no debería avisar')
    os.chdir(tmp)  # avisos_inicio.json se escribe en la carpeta actual
    bl = [{'id': 'L01', 'gancho': True, 'inicio_min': 0.0, 'fin_max': 20.0,
           'montaje': {'modo': 'lento', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0}},
          {'id': 'L02', 'gancho': True, 'inicio_min': 20.0, 'fin_max': 45.0,
           'montaje': {'modo': 'lento', 'src_inicio': 1.0, 'src_fin': 2.0, 'velocidad': 1.0}}]
    rotar.planear(bl, os.path.join(tmp, 'no_hay_mapa.json'), os.path.join(tmp, 'voz'), 60.0, 30)
    av = json.load(open(rotar.AVISOS, encoding='utf-8')) if os.path.exists(rotar.AVISOS) else []
    ok(any('pasa de 30-40 s' in x['aviso'] for x in av), f'en el montaje, un gancho de 45 s debería avisar: {av}')
    bl[1]['fin_max'] = 38.0
    rotar.planear(bl, os.path.join(tmp, 'no_hay_mapa.json'), os.path.join(tmp, 'voz'), 60.0, 30)
    av = json.load(open(rotar.AVISOS, encoding='utf-8')) if os.path.exists(rotar.AVISOS) else []
    ok(not any('pasa de' in x['aviso'] for x in av), f'un gancho de 38 s no debería avisar: {av}')

    # 5. avatar ahorro: el gancho sin cara queda en 30-40 s
    ok(ahorro.AJUSTES['gancho_s'] == 35, f'el gancho del modo ahorro debería ser de ~35 s: {ahorro.AJUSTES["gancho_s"]}')
    for largo in (8.0, 11.0, 13.0):  # frases de distinto largo
        fr = [{'s': k * largo, 'e': k * largo + largo - 0.5, 'texto': f'Frase número {k} del video.', 'bloque': f'L{k // 3:02d}'}
              for k in range(int(900 // largo))]
        t = ahorro.elegir(fr)
        ok(t[0]['tipo'] == 'voz' and t[0]['e'] <= 40, f'con frases de {largo} s el gancho sin avatar no debería pasar de 40 s: {t[0]}')
    fr = [{'s': k * 8.0, 'e': k * 8.0 + 7.5, 'texto': f'Frase {k}.', 'bloque': 'L01'} for k in range(112)]
    ok(ahorro.elegir(fr, 'ahorro', {'gancho_s': 55})[0]['e'] >= 50, 'si fabian pone 55 s en «Ritmo», se respeta')

    # 6. «faltan palabras» ya no pide explicar el porqué de cada paso
    corto = [bloque('L01', 'Pocas palabras.')] + [dict(bloque('L02', 'Otra.'), montaje={'modo': 'lento', 'src_inicio': 0.0,
                                                                                        'src_fin': 300.0, 'velocidad': 1.0})]
    falta = [x for x in ia.problemas(corto, 300.0) if x.startswith('faltan palabras')]
    ok(falta and 'pasos delicados' in falta[0] and 'explica mejor cada paso' not in falta[0],
       f'«faltan palabras» debería pedir el porqué solo en los pasos delicados: {falta}')
finally:
    os.chdir(viejo_cwd)
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: guion 03/11 (gancho de 30-40 s, PC sencilla al principio, avisos dentro del paso, porqué en lo '
      'delicado, testimonios dentro del cierre)')
sys.exit(1 if fallos else 0)
