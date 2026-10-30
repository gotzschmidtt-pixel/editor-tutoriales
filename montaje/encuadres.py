"""Nunca más de 15 s con la misma toma (pedido de fabian, 30/10/2026, el inicio del HONOR 8 LITE).

Si la misma escena sigue en pantalla más de LARGO segundos del video (un tramo largo, una pausa larga o varios bloques
seguidos de la misma toma), el montaje cambia el encuadre cada CADA segundos: general → cerca → general → detalle…,
como si hubiera varias cámaras. El acercamiento apunta a lo que más detalle tiene (la pantalla del teléfono).
En los bloques con un corte importante (critico) solo se acerca un poco, para no dejar nada afuera.
"encuadre": "fijo" en el montaje de un bloque lo deja sin cambios.
"""
import os, subprocess

import numpy as np

LARGO = 15.0      # segundos de la misma escena a partir de los cuales se cambia el encuadre
CADA = 7.0        # cada cuánto cambia
MINIMO = 2.0      # un pedazo más corto se queda con el encuadre del anterior
DIFERENCIA = 22.0  # diferencia media (0-255) entre miniaturas a partir de la cual es otra escena
CICLO = (1.0, 1.35, 1.0, 1.7)            # zoom de cada encuadre: general, cerca, general, detalle
CICLO_CRITICO = (1.0, 1.2, 1.0, 1.25)    # con un corte importante: sin acercarse tanto
MW, MH = 64, 36


def miniaturas(original, cache):
    """Una miniatura gris por segundo de la grabación (en caché junto al original)."""
    try:
        z = np.load(cache)
        if z['m'].shape[1:] == (MH, MW):
            return z['m']
    except (OSError, ValueError, KeyError):
        pass
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', original, '-vf', f'fps=1,scale={MW}:{MH},format=gray',
                        '-f', 'rawvideo', '-'], capture_output=True, check=True)
    m = np.frombuffer(r.stdout, np.uint8).reshape(-1, MH, MW)
    try:
        np.savez_compressed(cache, m=m)
    except OSError:
        pass
    return m


def centro_de_interes(img):
    """(cx, cy) en fracciones: donde más bordes hay (texto de una pantalla, botones), sin irse a las orillas."""
    f = img.astype(np.float32)
    g = np.abs(np.diff(f, axis=1))[:-1, :] + np.abs(np.diff(f, axis=0))[:, :-1]
    if g.max() <= 0:
        return 0.5, 0.5
    w = np.where(g >= np.percentile(g, 85), g, 0)
    ys, xs = np.mgrid[0:w.shape[0], 0:w.shape[1]]
    cx = float((w * xs).sum() / w.sum() / w.shape[1])
    cy = float((w * ys).sum() / w.sum() / w.shape[0])
    return min(max(cx, 0.3), 0.7), min(max(cy, 0.3), 0.7)


def piezas_del_guion(bloques):
    """Los pedazos del montaje en orden, con su lugar en el video y de dónde salen de la grabación."""
    out, t = [], 0.0
    for b in bloques:
        m = b['montaje']
        if m['modo'].startswith('lento'):
            v = m.get('velocidad') or 1
            dur = (m['src_fin'] - m['src_inicio']) / v
            out.append({'id': b['id'], 'parte': 'a', 't0': t, 'dur': dur, 'src': lambda s, m=m, v=v: m['src_inicio'] + s * v, 'm': m})
            t += dur
        if m['modo'].endswith('congelar') and (m.get('congelar_s') or 0) > 0:
            s = m['src_fin'] - 1 if m['modo'] == 'lento+congelar' else m['src_inicio'] + 1
            out.append({'id': b['id'], 'parte': 'b', 't0': t, 'dur': m['congelar_s'], 'src': lambda _, s=s: s, 'm': m})
            t += m['congelar_s']
        if m['modo'] == 'imagen':
            out.append({'id': b['id'], 'parte': 'img', 't0': t, 'dur': m.get('congelar_s') or 0, 'src': None, 'm': m})
            t += m.get('congelar_s') or 0
    return out


def planear(bloques, original, cache):
    """{(id, parte): [(desde, hasta, zoom, cx, cy), ...]} en segundos de ese pedazo; solo los que cambian de encuadre."""
    mini = miniaturas(original, cache)
    if not len(mini):
        return {}
    piezas = piezas_del_guion(bloques)
    # cada segundo del video: qué escena es (se corta cuando la miniatura cambia mucho o viene una imagen)
    pasos = []  # (pieza, s dentro de la pieza, escena)
    escena, ref = -1, None
    for p in piezas:
        s = 0.0
        while s < p['dur'] - 1e-6:
            if p['src'] is None:
                escena, ref = escena + 1, None
            else:
                k = min(len(mini) - 1, max(0, int(round(p['src'](s)))))
                if ref is None or np.abs(mini[k].astype(np.int16) - ref.astype(np.int16)).mean() > DIFERENCIA:
                    escena, ref = escena + 1, mini[k]
            pasos.append((p, s, escena, ref))
            s += 1.0
    # el largo de cada escena y dónde empieza
    inicio, largo = {}, {}
    for p, s, e, _ in pasos:
        t = p['t0'] + s
        inicio.setdefault(e, t)
        largo[e] = t + 1 - inicio[e]
    plan = {}
    for p, s, e, ref in pasos:
        m = p['m']
        if largo[e] <= LARGO or ref is None or m.get('encuadre') == 'fijo' or p['parte'] == 'img':
            z, cx, cy = 1.0, 0.5, 0.5
        else:
            ciclo = CICLO_CRITICO if m.get('critico') else CICLO
            z = ciclo[int((p['t0'] + s - inicio[e]) // CADA) % len(ciclo)]
            cx, cy = centro_de_interes(ref)
        lst = plan.setdefault((p['id'], p['parte']), [])
        hasta = min(s + 1.0, p['dur'])
        if lst and lst[-1][2:] == (z, cx, cy):
            lst[-1] = (lst[-1][0], hasta, z, cx, cy)
        else:
            lst.append((s, hasta, z, cx, cy))
    # los pedazos muy cortos se pegan al anterior; los que quedan todos en general no hacen falta
    final = {}
    for k, lst in plan.items():
        junt = []
        for x in lst:
            if junt and (x[1] - x[0] < MINIMO or junt[-1][1] - junt[-1][0] < MINIMO):
                junt[-1] = (junt[-1][0], x[1]) + junt[-1][2:]
            else:
                junt.append(x)
        if any(x[2] != 1.0 for x in junt):
            final[k] = [tuple(round(v, 3) for v in x) for x in junt]
    return final


def filtro(z, cx, cy):
    """Recorte de ffmpeg para un encuadre (antes del scale del montaje); vacío en el general."""
    if z == 1.0:
        return ''
    return (f"crop=trunc(iw/{z}/2)*2:trunc(ih/{z}/2)*2:"
            f"min(max(iw*{cx}-iw/{z}/2\\,0)\\,iw-iw/{z}):min(max(ih*{cy}-ih/{z}/2\\,0)\\,ih-ih/{z}),")
