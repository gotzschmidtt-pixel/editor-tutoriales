"""Prueba rápida de «frenar antes de congelar» (voz/voz.py frenar_tramo, ajustar_guion e ia/ia.py revisar). Sin red ni
gastos: las voces son tiempos falsos (no se llama a ElevenLabs) y el video es uno sintético de ffmpeg.
- un tramo a ×3 (100–130 s, 10 s en pantalla) con 13 s de voz va a ~×2,19 y sin pausa (antes: ×3 + 3,7 s de pausa);
- una pausa de relleno tras un tramo a ×1,16 se achica yendo a ×1 y el bloque dura lo mismo;
- no se tocan los bloques de «Alinear», del gancho, con cara, ⭐, «quieto», sin voz ni los ya ajustados con su voz;
- nunca sube una velocidad ni pasa los topes de fabian (pasos de configuración a ×2 como máximo);
- correrlo dos veces no cambia nada más;
- ia.revisar (voz estimada, antes de pagarla) deja el bloque igual que ajustar_guion con la voz real.
Uso: python tests/test_frenar_antes_de_congelar.py   (sale con 1 si algo falla)
"""
import copy, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
import voz  # noqa: E402
import ia  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def montaje(a, z, v, pausa=None, **extra):
    return {'modo': 'lento+congelar' if pausa else 'lento', 'src_inicio': a, 'src_fin': z, 'velocidad': v,
            'congelar_s': pausa, **extra}


def correr(d, bloques, voces):
    """Guarda el guion y voces falsas (solo sus tiempos) y corre voz.ajustar_guion. Devuelve ({id: bloque}, avisos)."""
    os.makedirs(os.path.join(d, 'voz'), exist_ok=True)
    g = os.path.join(d, 'guion.json')
    json.dump({'bloques': bloques}, open(g, 'w', encoding='utf-8'), ensure_ascii=False)
    for bid, s in voces.items():
        json.dump({'characters': list('hola'), 'character_start_times_seconds': [0] * 4,
                   'character_end_times_seconds': [s] * 4}, open(os.path.join(d, 'voz', f'{bid}.align.json'), 'w'))
    avisos = voz.ajustar_guion(g, os.path.join(d, 'voz'))
    return {b['id']: b for b in json.load(open(g, encoding='utf-8'))['bloques']}, avisos


TEXTO = 'Esperamos a que termine de borrar y se reinicie el teléfono solo.'
tmp = tempfile.mkdtemp(prefix='frenar_')
try:
    # 1. tramo a ×3 con 13 s de voz: va más despacio y sin pausa; el bloque dura lo que la voz pide (13 + 0,7 s)
    r, avisos = correr(os.path.join(tmp, 'a'), [{'id': 'L05', 'texto': TEXTO, 'montaje': montaje(100.0, 130.0, 3.0)}],
                       {'L05': 13.0})
    mo = r['L05']['montaje']
    ok(abs(mo['velocidad'] - 2.19) <= 0.011, f"×3 con 13 s de voz debería ir a ~×2,19, quedó ×{mo['velocidad']}")
    ok(mo['modo'] == 'lento' and not mo.get('congelar_s'), f'no debería quedar pausa: {mo}')
    largo = voz.largo_bloque(mo)
    ok(13.7 <= largo <= 13.8, f'el bloque debería durar lo que pide la voz (13,7 s), dura {largo:.2f} s')
    ok(any('más despacio' in x and 'L05' in x for x in avisos), f'debería avisar que frenó el tramo: {avisos}')
    r2, avisos2 = correr(os.path.join(tmp, 'a'), list(r.values()), {'L05': 13.0})  # otra vez: ya está, no cambia nada
    ok(r2['L05']['montaje'] == mo and not avisos2, f'la segunda vez no debería cambiar nada: {r2["L05"]["montaje"]} {avisos2}')

    # 2. pausa de relleno (como L18 de MOTOROLA_FRP): ×1,16 + 8,62 s → ×1 y queda solo la pausa que falta; mismo largo
    m18 = montaje(200.0, 228.0, 1.16, 8.62, relleno_s=9.6, paso=True)
    antes = voz.largo_bloque(m18)
    r, avisos = correr(os.path.join(tmp, 'b'), [{'id': 'L18', 'texto': TEXTO, 'montaje': copy.deepcopy(m18)}], {'L18': 20.96})
    mo = r['L18']['montaje']
    ok(mo['velocidad'] == 1.0, f"la pausa de relleno debería pasar a ir a ×1, quedó ×{mo['velocidad']}")
    ok(mo['modo'] == 'lento+congelar' and 4.7 <= (mo.get('congelar_s') or 0) <= 4.8,
       f"la pausa debería bajar de 8,6 s a ~4,8 s: {mo}")
    ok(abs(voz.largo_bloque(mo) - antes) <= 0.02, f'el bloque debería durar lo mismo ({antes:.2f} s): {voz.largo_bloque(mo):.2f} s')
    ok(any('L18' in x and 'más despacio' in x for x in avisos), f'debería avisar que cambió la pausa: {avisos}')

    # 3. no se tocan: corridos por «Alinear», gancho, cara, ⭐, «quieto» (pedido a mano): como antes, ×3 + 3,7 s de pausa
    casos = {'L01': ({}, {'alineado': True}), 'L02': ({'gancho': True}, {}), 'L03': ({}, {'cara': True}),
             'L04': ({}, {'importante': True, 'critico': True}), 'L06': ({}, {'quieto': True})}
    bl = [{'id': i, 'texto': TEXTO, **b_extra, 'montaje': montaje(100.0 + 40 * k, 130.0 + 40 * k, 3.0, **m_extra)}
          for k, (i, (b_extra, m_extra)) in enumerate(casos.items())]
    bl.append({'id': 'L07', 'texto': '', 'montaje': montaje(400.0, 430.0, 3.0, 2.0)})  # sin voz: tal cual
    bl.append({'id': 'L08', 'texto': TEXTO, 'montaje': montaje(450.0, 460.0, 1.0, 4.0)})  # ya a ×1: nada que frenar
    r, _ = correr(os.path.join(tmp, 'c'), bl, dict({i: 13.0 for i in casos}, L08=13.0))
    for i in casos:
        mo = r[i]['montaje']
        ok(mo['velocidad'] == 3.0 and mo['modo'] == 'lento+congelar' and mo['congelar_s'] == 3.7,
           f'{i} ({casos[i]}) no debería frenarse: {mo}')
    ok(r['L07']['montaje'] == montaje(400.0, 430.0, 3.0, 2.0), f"el tramo sin voz no debería cambiar: {r['L07']['montaje']}")
    ok(r['L08']['montaje']['velocidad'] == 1.0 and r['L08']['montaje']['congelar_s'] == 4.0,
       f"un tramo a ×1 con pausa no debería cambiar: {r['L08']['montaje']}")

    # 4. ya ajustado con su misma voz (los «fijos»: lo retocaste a mano): no se toca y el guion no se reescribe
    d = os.path.join(tmp, 'd')
    r, avisos = correr(d, [{'id': 'L09', 'texto': TEXTO, 'voz_real_s': 13.0, 'montaje': montaje(100.0, 130.0, 3.0, 3.7)}],
                       {'L09': 13.0})
    ok(r['L09']['montaje']['velocidad'] == 3.0 and r['L09']['montaje']['congelar_s'] == 3.7 and not avisos,
       f"un bloque ya ajustado con su voz no debería cambiar: {r['L09']['montaje']} {avisos}")
    ok(not os.path.exists(os.path.join(d, 'guion.json.antes_voz')), 'sin cambios no debería guardar copia del guion')

    # 5. nunca sube una velocidad ni pasa los topes: un paso de configuración a ×3 queda a ×2 como máximo
    r, _ = correr(os.path.join(tmp, 'e'), [{'id': 'L10', 'texto': TEXTO, 'montaje': montaje(100.0, 130.0, 3.0, paso=True)},
                                          {'id': 'L11', 'texto': TEXTO, 'montaje': montaje(200.0, 212.0, 1.5, 2.0)}],
                  {'L10': 13.0, 'L11': 6.0})
    ok(r['L10']['montaje']['velocidad'] <= 2.0, f"un paso de configuración no pasa de ×2: {r['L10']['montaje']}")
    ok(r['L11']['montaje']['velocidad'] <= 1.5, f"nunca debería subir una velocidad: {r['L11']['montaje']}")
    ok(voz.tope_velocidad({'cara': True}) == 1.0 and voz.tope_velocidad({'importante': True}) == 1.0
       and voz.tope_velocidad({'critico': True}) == 1.5 and voz.tope_velocidad({'paso': True}) == 2.0, 'topes de fabian')

    # 6. ia.revisar con la voz estimada deja el bloque igual que ajustar_guion con la voz real
    d = os.path.join(tmp, 'f')
    os.makedirs(d)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=64x36:r=1', '-t', '150',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
    ia.marcar_caras = lambda d, bloques: []  # sin el detector de caras (no baja nada)
    ia.meta_guion = lambda d, dur, idea=None: (dur, 0, 10 ** 6)  # sin el ajuste del largo total: se mira solo este bloque
    texto = ' '.join(['Ahora vemos cómo el teléfono vuelve a arrancar solo después de borrar todo lo que tenía guardado'] * 2
                     + ['y seguimos con el siguiente bloque'])  # 40 palabras: 16,4 s estimados (no caben en 10 s)
    datos, avisos = ia.revisar(d, 'guion', {'bloques': [{'id': 'L05', 'texto': texto, 'montaje': montaje(100.0, 130.0, 3.0)}]})
    mo_ia = datos['bloques'][0]['montaje']
    voz_est = datos['bloques'][0]['voz_estimada_s']
    ok(mo_ia['modo'] == 'lento' and mo_ia['velocidad'] < 3.0 and not mo_ia.get('congelar_s'),
       f'la revisión debería frenar el tramo en vez de poner una pausa: {mo_ia} {avisos}')
    ok(any('L05: la voz no cabía' in x and 'más despacio' in x for x in avisos), f'la revisión debería avisarlo: {avisos}')
    # misma duración de bloque que pide la revisión (voz + 0,5 s) = voz real + 0,7 s en voz.py
    r, _ = correr(os.path.join(tmp, 'g'), [{'id': 'L05', 'texto': texto, 'montaje': montaje(100.0, 130.0, 3.0)}],
                  {'L05': round(voz_est - 0.2, 2)})
    mo_v = r['L05']['montaje']
    ok((mo_v['modo'], mo_v['velocidad'], mo_v.get('congelar_s')) == (mo_ia['modo'], mo_ia['velocidad'], mo_ia.get('congelar_s')),
       f'revisar y ajustar_guion deberían dar lo mismo: {mo_ia} / {mo_v}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: frenar antes de congelar (×3 → ~×2,19 sin pausa, relleno, saltos, topes y revisar)')
sys.exit(1 if fallos else 0)
