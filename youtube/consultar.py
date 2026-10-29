"""Preguntas rápidas a las estadísticas del canal, para que Claude (o cualquiera) las conteste desde la PC.

Usa el mismo permiso de YouTube que la app (app/ajustes.json). Solo lee: no publica, no borra ni cambia nada.

    python youtube/consultar.py canal                 últimos 28 días contra los 28 anteriores
    python youtube/consultar.py recientes [N]         los N videos más nuevos: vistas, % visto, suscriptores
    python youtube/consultar.py video LINK_O_ID       un video: totales, retención por tramo y de dónde vino la gente
    python youtube/consultar.py busquedas [DIAS]      lo que escriben en el buscador de YouTube para llegar a tus videos
    python youtube/consultar.py fuentes [DIAS]        de dónde llegan las vistas (búsqueda, sugeridos, externos…)
    python youtube/consultar.py paises [DIAS]         de qué países te ven
"""
import json, os, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import youtube  # noqa: E402

FUENTES = {'YT_SEARCH': 'Búsqueda de YouTube', 'RELATED_VIDEO': 'Videos sugeridos', 'SUBSCRIBER': 'Suscriptores (inicio y feed)',
           'EXT_URL': 'Webs y apps externas', 'BROWSE': 'Inicio / explorar', 'YT_CHANNEL': 'Tu canal', 'PLAYLIST': 'Listas',
           'NOTIFICATION': 'Notificaciones', 'SHORTS': 'Feed de Shorts', 'NO_LINK_OTHER': 'Directo o desconocido',
           'YT_OTHER_PAGE': 'Otras páginas de YouTube', 'END_SCREEN': 'Pantallas finales', 'HASHTAGS': 'Hashtags'}


def cfg():
    aj = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8'))
    c = youtube.config(aj)
    if not (c.get('token') or {}).get('refresh'):
        raise SystemExit('YouTube no está conectado: en la app, «▶️ YouTube» → «🔑 Conectar YouTube».')
    return c


def informe(c, desde, hasta, **p):
    return youtube.pedir(c, 'GET', youtube.ANALYTICS, dict({'ids': 'channel==MINE', 'startDate': desde, 'endDate': hasta}, **p))


def dia(n):
    return time.strftime('%Y-%m-%d', time.localtime(time.time() - n * 86400))


def canal(c):
    m = 'views,estimatedMinutesWatched,averageViewPercentage,subscribersGained,subscribersLost'
    a = (informe(c, dia(28), dia(1), metrics=m).get('rows') or [[0] * 5])[0]
    b = (informe(c, dia(56), dia(29), metrics=m).get('rows') or [[0] * 5])[0]
    nombres = ['Vistas', 'Minutos vistos', '% visto promedio', 'Suscriptores ganados', 'Suscriptores perdidos']
    print(f'Últimos 28 días ({dia(28)} a {dia(1)}) contra los 28 anteriores:')
    for n, x, y in zip(nombres, a, b):
        cambio = f'{(x - y) / y * 100:+.0f} %' if y else ''
        fmt = (lambda z: f'{z:.1f} %') if '%' in n else (lambda z: f'{z:,.0f}'.replace(',', '.'))
        print(f'  {n}: {fmt(x)}  (antes {fmt(y)}) {cambio}')


def recientes(c, n=10):
    vs = youtube.mis_videos(c, maximo=n)[:n]
    ids = ','.join(v['id'] for v in vs)
    r = informe(c, '2015-01-01', dia(0), dimensions='video', filters=f'video=={ids}',
                metrics='views,averageViewPercentage,averageViewDuration,subscribersGained')
    datos = {f[0]: f[1:] for f in r.get('rows') or []}
    for v in vs:
        x = datos.get(v['id'])
        if not x:
            print(f"- {v['publicado']} · {v['titulo'][:80]}\n    {v['vistas']} vistas · YouTube todavía no tiene las estadísticas (tarda 2 o 3 días) · https://youtu.be/{v['id']}")
            continue
        print(f"- {v['publicado']} · {v['titulo'][:80]}\n    {v['vistas']} vistas · se mira el {x[1]:.0f} % ({x[2] // 60:.0f}:{x[2] % 60:02.0f}) · +{x[3]:.0f} suscriptores · https://youtu.be/{v['id']}")


def video(c, cual):
    vid = youtube.id_de(cual)
    v = youtube.video(c, vid)
    desde = v['publicado'][:10] or '2015-01-01'
    t = (informe(c, desde, dia(0), filters=f'video=={vid}',
                 metrics='views,averageViewPercentage,averageViewDuration,subscribersGained,likes,comments,shares').get('rows') or [[0] * 7])[0]
    print(f"{v['titulo']}\n  publicado {desde} · {v['segundos'] // 60}:{v['segundos'] % 60:02d} · {t[0]:.0f} vistas · se mira el {t[1]:.0f} % "
          f"({t[2] // 60:.0f}:{t[2] % 60:02.0f}) · +{t[3]:.0f} suscriptores · {t[4]:.0f} likes · {t[5]:.0f} comentarios · {t[6]:.0f} compartidos")
    curva = youtube.retencion(c, vid, desde=desde)
    if curva:
        print('  Retención (qué parte sigue mirando):')
        for p in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 0.95):
            x = min(curva, key=lambda f: abs(f['t'] - p))
            s = p * v['segundos']
            print(f"    {int(s) // 60}:{int(s) % 60:02d} ({p * 100:.0f} %): {x['mira'] * 100:.0f} %  · frente a videos parecidos: {x['relativa']:.2f}")
    else:
        print('  Retención: YouTube todavía no la tiene (tarda unos días).')
    r = informe(c, desde, dia(0), dimensions='insightTrafficSourceType', filters=f'video=={vid}', metrics='views', sort='-views')
    print('  De dónde vino la gente: ' + ', '.join(f"{FUENTES.get(f[0], f[0])} {f[1]:.0f}" for f in (r.get('rows') or [])[:6]))


def busquedas(c, dias=90):
    r = informe(c, dia(dias), dia(1), dimensions='insightTrafficSourceDetail', filters='insightTrafficSourceType==YT_SEARCH',
                metrics='views', sort='-views', maxResults=25)  # YouTube no da más de 25 aquí
    print(f'Lo que buscaron en YouTube para llegar a tus videos (últimos {dias} días):')
    for f in r.get('rows') or []:
        print(f'  {f[1]:>6.0f}  {f[0]}')


def fuentes(c, dias=28):
    r = informe(c, dia(dias), dia(1), dimensions='insightTrafficSourceType', metrics='views,estimatedMinutesWatched', sort='-views')
    print(f'De dónde llegan las vistas (últimos {dias} días):')
    for f in r.get('rows') or []:
        print(f'  {FUENTES.get(f[0], f[0])}: {f[1]:,.0f} vistas · {f[2]:,.0f} minutos'.replace(',', '.'))


def paises(c, dias=90):
    r = informe(c, dia(dias), dia(1), dimensions='country', metrics='views,averageViewPercentage', sort='-views', maxResults=15)
    print(f'Países (últimos {dias} días):')
    for f in r.get('rows') or []:
        print(f'  {f[0]}: {f[1]:,.0f} vistas · se mira el {f[2]:.0f} %'.replace(',', '.'))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('canal', 'recientes', 'video', 'busquedas', 'fuentes', 'paises'):
        raise SystemExit(__doc__)
    c = cfg()
    q, args = sys.argv[1], sys.argv[2:]
    try:
        if q == 'video':
            video(c, args[0])
        elif q == 'recientes':
            recientes(c, int(args[0]) if args else 10)
        elif q == 'canal':
            canal(c)
        else:
            globals()[q](c, int(args[0]) if args else (90 if q != 'fuentes' else 28))
    except youtube.ErrorYT as e:
        raise SystemExit(f'YouTube: {e}')


if __name__ == '__main__':
    main()
