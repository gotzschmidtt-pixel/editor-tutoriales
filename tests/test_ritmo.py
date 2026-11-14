"""«🎵 Ritmo de la voz» (14/11/2026). Sin red ni gastos: voces falsas (un tono hecho con ffmpeg y sus tiempos por letra).
- «Humano» alarga la voz (pausas + ×0,97) y corre los tiempos de las letras igual;
- aplicarlo dos veces no suma pausas sobre pausas, y «Antes» devuelve la voz original exacta;
- el paso crítico (KEY) va más lento que los demás; respiros de 2-4 s distintos entre sí, sin número fijo (uno cada ~45 s de voz);
- voz.ajustar_guion suma la pausa de párrafo y el respiro al largo del bloque;
- musica.py arma un filtro de volumen válido para ffmpeg que sube en los respiros.
Uso: python tests/test_ritmo.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
sys.path.insert(0, os.path.join(RAIZ, 'musica'))
import ritmo  # noqa: E402
import voz  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


TEXTOS = {
    'L01': 'Hoy te enseño a quitar la cuenta de Google en tu Honor. Es muy fácil y lo haces desde casa.',
    'L02': 'Primero apaga el teléfono, conecta el cable a la PC y espera unos segundos. Vamos con el siguiente paso.',
    'L03': 'Ahora entramos en modo fastboot. Mantén los botones de volumen y verás la pantalla negra con letras.',
    'L04': 'Copia el serial que aparece en el programa, porque con ese serial pedimos la KEY en la web. Revisa bien cada número.',
    'L05': 'Ya tenemos la KEY aquí, la pegamos en el campo del programa. Un número mal y no funciona, así que con calma.',
    'L06': 'Ahora pulsamos Erase FRP By Code y el teléfono se reinicia solo. Esperamos que termine.',
    'L07': 'Configuramos el teléfono de nuevo, elegimos el idioma y la red wifi. Todo normal, como un teléfono nuevo.',
    'L08': 'Y listo, ya puedes omitir la cuenta de Google y entrar sin problema. Así de fácil, sin llevarlo a un técnico.',
    'L09': 'Si te sirvió, escríbenos por WhatsApp y comenta el modelo exacto de tu teléfono. Nos vemos en el próximo video.',
}


def voz_falsa(carpeta, bid, texto):
    """Un tono con la duración de la frase a ~158 palabras por minuto, y sus tiempos por letra."""
    paso = 60 / 158 / 6  # ~6 letras por palabra
    s = [round(k * paso, 3) for k in range(len(texto))]
    e = [round(x + paso, 3) for x in s]
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'sine=f=220:d={e[-1]:.3f}', '-b:a', '128k',
                    os.path.join(carpeta, bid + '.mp3')], check=True)
    json.dump({'characters': list(texto), 'character_start_times_seconds': s, 'character_end_times_seconds': e},
              open(os.path.join(carpeta, bid + '.align.json'), 'w', encoding='utf-8'), ensure_ascii=False)


def dur(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True).stdout)


def fin(carpeta, bid):
    return json.load(open(os.path.join(carpeta, bid + '.align.json'), encoding='utf-8'))['character_end_times_seconds'][-1]


d = tempfile.mkdtemp(prefix='ritmo_')
try:
    cv = os.path.join(d, 'voz')
    os.makedirs(cv)
    bloques = []
    for bid, t in TEXTOS.items():
        voz_falsa(cv, bid, t)
        bloques.append({'id': bid, 'texto': t, 'tipo': 'clave' if bid == 'L05' else 'libre',
                        'montaje': {'modo': 'lento', 'src_inicio': 0, 'src_fin': 8, 'velocidad': 1}})
    g = os.path.join(d, 'guion.json')
    json.dump({'bloques': bloques}, open(g, 'w', encoding='utf-8'), ensure_ascii=False)
    crudo = {b: fin(cv, b) for b in TEXTOS}
    crudo_mp3 = {b: open(os.path.join(cv, b + '.mp3'), 'rb').read() for b in TEXTOS}

    # «Antes» por defecto: no toca nada
    ritmo.aplicar(g, cv, d, log=lambda x: None)
    ok(all(abs(fin(cv, b) - crudo[b]) < 1e-6 for b in TEXTOS), 'con «Antes» la voz cambió')
    ok(not os.path.isdir(os.path.join(cv, ritmo.CRUDO)), '«Antes» sin ritmo previo no debería copiar nada')

    # «Humano»
    json.dump({'ritmo_voz': 'humano'}, open(os.path.join(d, 'edicion.json'), 'w'))
    est = ritmo.aplicar(g, cv, d, log=print)
    h1 = {b: fin(cv, b) for b in TEXTOS}
    ok(all(h1[b] > crudo[b] for b in TEXTOS), f'«Humano» no alargó todas las voces: {h1} vs {crudo}')
    ok(all(abs(dur(os.path.join(cv, b + '.mp3')) - h1[b]) < 0.35 for b in TEXTOS), 'el mp3 y los tiempos no coinciden')
    vel = {b: x['vel'] for b, x in est['bloques'].items()}
    ok(vel['L05'] == 0.93 and vel['L04'] == 0.93, f'el paso crítico no va a ×0,93: {vel}')
    ok(vel['L02'] == 1.0, f'el paso obvio (apaga/conecta/espera) no va a ×1: {vel}')
    ok(vel['L07'] == 0.97, f'un bloque normal no va a ×0,97: {vel}')
    resp = {b: x['respiro'] for b, x in est['bloques'].items() if x['respiro']}
    ok(1 <= len(resp) <= 3, f'respiros: {resp}')
    ok(all(2 <= v <= 4 for v in resp.values()) and len(set(resp.values())) == len(resp), f'respiros no distintos o fuera de 2-4 s: {resp}')
    ok('L01' not in resp and 'L09' not in resp, 'un respiro en el primer o el último bloque')
    ok('L03' in resp, f'sin respiro en el modo fastboot: {resp}')

    # dos veces: igual (no suma pausas)
    ritmo.aplicar(g, cv, d, log=lambda x: None)
    ok(all(abs(fin(cv, b) - h1[b]) < 1e-6 for b in TEXTOS), 'aplicar dos veces sumó pausas')

    # voz.ajustar_guion suma la cola (párrafo + respiro)
    voz.ajustar_guion(g, cv)
    gb = {b['id']: b for b in json.load(open(g, encoding='utf-8'))['bloques']}
    for b, x in gb.items():
        largo = x['fin_max'] - x['inicio_min']
        ok(largo + 0.02 >= x['voz_real_s'] + 0.7 + x.get('ritmo_cola_s', 0), f'{b}: el bloque no deja la pausa después de la voz')
    ok(gb['L03'].get('ritmo_cola_s', 0) >= resp.get('L03', 0) + 0.6, f"L03: la cola no trae el respiro: {gb['L03'].get('ritmo_cola_s')}")

    # musica: filtro de volumen válido
    import musica
    tramos, sube = ritmo.tramos_respiro(g, cv)
    ok(len(tramos) == len(resp) and sube == 0.32, f'tramos de respiro: {tramos} {sube}')

    class A:
        volumen, guion, voz = 0.22, g, cv
    filtro = musica.volumen_respiros(A)
    r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=60', '-af', filtro,
                        '-f', 'null', '-'], capture_output=True, text=True)
    ok(r.returncode == 0, 'el filtro de volumen no anda en ffmpeg: ' + r.stderr[-300:])

    # una voz nueva de ElevenLabs (texto cambiado) se toma como la nueva «sin ritmo»
    voz_falsa(cv, 'L07', TEXTOS['L07'])
    ritmo.aplicar(g, cv, d, log=lambda x: None)
    ok(abs(fin(cv, 'L07') - h1['L07']) < 1e-6, 'la voz nueva de L07 no quedó con el mismo ritmo')

    # «Antes» devuelve la voz original exacta
    json.dump({'ritmo_voz': 'antes'}, open(os.path.join(d, 'edicion.json'), 'w'))
    ritmo.aplicar(g, cv, d, log=lambda x: None)
    ok(all(abs(fin(cv, b) - crudo[b]) < 1e-6 for b in TEXTOS), 'volver a «Antes» no devolvió los tiempos originales')
    ok(all(open(os.path.join(cv, b + '.mp3'), 'rb').read() == crudo_mp3[b] for b in TEXTOS if b != 'L07'), 'volver a «Antes» no devolvió el mp3 original')

    # «Pausas v2»: más lenta que «Antes», sin respiros
    json.dump({'ritmo_voz': 'pausas_v2'}, open(os.path.join(d, 'edicion.json'), 'w'))
    est = ritmo.aplicar(g, cv, d, log=lambda x: None)
    ok(all(fin(cv, b) > crudo[b] for b in TEXTOS), '«Pausas v2» no alargó')
    ok(not any(x['respiro'] for x in est['bloques'].values()), '«Pausas v2» con respiros')

    # MULTIMARCA: los momentos de respiro y los pasos críticos de otras marcas
    for t, n in [('Ahora entramos en modo DFU con los dos botones.', 0), ('Ponemos el Samsung y ya estamos en modo descarga.', 0),
                 ('Ya llegó el código de desbloqueo de Motorola.', 1), ('Damos clic en Unlock y se reinicia.', 2),
                 ('Listo, el Xiaomi quedó desbloqueado.', 3)]:
        ok(ritmo.RESPIRO[n].search(t), f'momento de respiro no reconocido: {t}')
    ok(ritmo.es_critico({'texto': 'Copia el ECID que aparece en 3uTools.'}), 'ECID (iPhone) no es paso crítico')
    ok(ritmo.es_critico({'texto': 'Marca la cuenta Mi y pega el código.'}), 'cuenta Mi (Xiaomi) no es paso crítico')

    # Short: pausas más cortas y sin respiros
    json.dump({'ritmo_voz': 'humano'}, open(os.path.join(d, 'edicion.json'), 'w'))
    cs = os.path.join(d, 'voz_short')
    os.makedirs(cs)
    for bid in ('L03', 'L04', 'L05', 'L06'):
        voz_falsa(cs, bid, TEXTOS[bid])
    gs = os.path.join(d, '.short_voz_guion.json')
    json.dump({'bloques': [b for b in bloques if b['id'] in ('L03', 'L04', 'L05', 'L06')]}, open(gs, 'w', encoding='utf-8'))
    es = ritmo.aplicar(gs, cs, d, log=lambda x: None, corto=True)
    ok(not any(x['respiro'] or x['cola'] for x in es['bloques'].values()), f'el Short con respiros o cola: {es}')
    cuatro = ('L03', 'L04', 'L05', 'L06')
    ok(all(crudo[b] < fin(cs, b) for b in cuatro) and sum(fin(cs, b) for b in cuatro) < sum(h1[b] for b in cuatro),
       'el Short no quedó entre «Antes» y «Humano»')

    # tráiler (voz sin tiempos por letra): alarga los silencios sin pasarse del largo pedido
    tr = os.path.join(d, 'trailer.voz.mp3')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=300:d=1.5', '-f', 'lavfi', '-i', 'anullsrc=d=0.25:r=44100',
                    '-f', 'lavfi', '-i', 'sine=f=300:d=1.5', '-f', 'lavfi', '-i', 'anullsrc=d=0.25:r=44100', '-f', 'lavfi', '-i', 'sine=f=300:d=1.5',
                    '-filter_complex', '[0][1][2][3][4]concat=n=5:v=0:a=1', tr], check=True)
    sal = ritmo.pausar_sin_tiempos(tr, os.path.join(d, 'trailer.voz_ritmo.mp3'), d, max_s=8, log=lambda x: None)
    ok(sal != tr and dur(tr) + 0.2 < dur(sal) <= 8.1, f'tráiler: {dur(tr)} → {dur(sal)}')

    # estilos propios
    ok(set(ritmo.estilos()) >= {'antes', 'pausas_v2', 'humano'}, 'faltan estilos')
finally:
    shutil.rmtree(d, ignore_errors=True)

if fallos:
    print('FALLÓ:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: ritmo de la voz')
