"""Prueba rápida del «modo avatar ahorro» (avatar/ahorro.py): qué tramos van con avatar, el ahorro, que se respeten las
marcas del guion y que el montaje dure lo mismo que la voz (sin desfase). No gasta nada.
Uso: python tests/test_avatar_ahorro.py   (sale con 1 si algo falla)
"""
import os, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'avatar'))
import ahorro  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def frases(n=90, largo=8.0, fuertes=()):
    """n frases de `largo` s (un video de 12 min); las de `fuertes` llevan una alerta."""
    out = []
    for k in range(n):
        texto = '¡Ojo, NO le des el código a nadie!' if k in fuertes else f'Esta es la frase número {k} del video, sin nada especial.'
        out.append({'s': k * largo, 'e': k * largo + largo - 0.5, 'texto': texto, 'bloque': f'L{k // 3:02d}'})
    return out


# 1) modo ahorro: inicio, cierre y 3 momentos fuertes; el resto voz en off
fr = frases(fuertes=(30, 55, 70))
t = ahorro.elegir(fr)
r = ahorro.resumen(t)
av = [x for x in t if x['tipo'] == 'avatar']
ok(av[0]['s'] == 0 and 20 <= av[0]['e'] <= 30, f'el inicio debería ir con avatar 20-30 s: {av[0]}')
ok(av[-1]['e'] == fr[-1]['e'] and 10 <= av[-1]['e'] - av[-1]['s'] <= 17, f'el cierre debería ir con avatar 10-15 s: {av[-1]}')
ok(len(av) == 5, f'esperaba 5 tramos con avatar (inicio, 3 fuertes, cierre), hay {len(av)}')
for k in (30, 55, 70):
    ok(any(x['i0'] <= k <= x['i1'] for x in av), f'la frase fuerte {k} debería ir con avatar')
ok(75 <= r['ahorro_pct'] <= 92, f'el ahorro debería rondar el 80 %: {r}')
ok(all(x['e'] - x['s'] < 60 for x in av), 'cada audio para HeyGen debe durar menos de 1 min')
# los tramos cubren toda la voz, seguidos y sin huecos
ok(t[0]['s'] == 0 and t[-1]['e'] == fr[-1]['e'] and all(a['e'] == b['s'] for a, b in zip(t, t[1:])), 'hay huecos entre tramos')

# 2) modo todo: un solo tipo
t2 = ahorro.elegir(fr, 'todo')
ok(all(x['tipo'] == 'avatar' for x in t2) and ahorro.resumen(t2)['ahorro_pct'] == 0, 'con «todo» todo va con avatar')

# 3) las marcas del guion mandan
fr3 = frases()
for f in fr3:
    if f['bloque'] == 'L10':
        f['avatar'] = True
    if f['bloque'] == 'L00':
        f['avatar'] = False
t3 = ahorro.elegir(fr3)
ok(all(x['tipo'] == 'avatar' for x in t3 if fr3[x['i0']]['bloque'] == 'L10'), 'el bloque marcado con avatar debe ir con avatar')
ok(t3[0]['tipo'] == 'voz', 'el bloque marcado sin avatar debe ir con voz en off aunque sea el inicio')

# 4) montaje: dura lo mismo que la voz
with tempfile.TemporaryDirectory() as tmp:
    voz = os.path.join(tmp, 'voz.mp3')
    ahorro.ff('-f', 'lavfi', '-i', 'sine=frequency=440:duration=12', voz)
    cara = os.path.join(tmp, 'cara.mp4')
    ahorro.ff('-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=25:duration=3', '-pix_fmt', 'yuv420p', cara)
    img = os.path.join(tmp, 'img.png')
    ahorro.ff('-f', 'lavfi', '-i', 'color=c=red:size=640x360', '-frames:v', '1', img)
    tramos = [{'tipo': 'avatar', 's': 0, 'e': 4}, {'tipo': 'voz', 's': 4, 'e': 9}, {'tipo': 'avatar', 's': 9, 'e': 12}]
    sal = os.path.join(tmp, 'm.mp4')
    ahorro.montar(tramos, voz, [cara, cara], [img, cara], sal)
    dv = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of',
                               'csv=p=0', sal], capture_output=True, text=True).stdout.strip() or 0)
    ok(abs(dv - 12) < 0.2, f'el video debería durar 12 s como la voz, dura {dv}')

print('\n'.join(fallos) or 'ok: modo avatar ahorro')
sys.exit(1 if fallos else 0)
