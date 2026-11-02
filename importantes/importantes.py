"""«⭐ Cortes importantes»: los tramos de tu grabación que se muestran ENTEROS y a velocidad normal.

Son los momentos delicados que el espectador tiene que ver bien: poner el teléfono en Recovery o en DFU, los botones
que se aprietan, escribir una key… Los marcas tú en la app (o en mis_proyectos/NOMBRE/cortes_importantes.json):
    [{"inicio": 339.0, "fin": 382.0, "nota": "entrar a Recovery"}]

Los respetan todos los pasos que pueden acelerar o recortar la imagen:
  - la IA que escribe el guion (se le dicen, con su nota)
  - la revisión del guion y el ajuste de largo (los bloques que los tocan van a ×1 y no se recortan)
  - la voz (no acelera esos bloques para que entren)
  - Acortar (no corta ni acelera nada dentro de ellos)
"""
import json, os

ARCHIVO = 'cortes_importantes.json'


def leer(d):
    """[{inicio, fin, nota}] ordenados; vacío si no marcaste ninguno."""
    try:
        lista = json.load(open(os.path.join(d, ARCHIVO), encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return []
    out = []
    for x in lista if isinstance(lista, list) else []:
        try:
            a, b = float(x['inicio']), float(x['fin'])
        except (KeyError, TypeError, ValueError):
            continue
        if b > a:
            out.append({'inicio': round(a, 2), 'fin': round(b, 2), 'nota': str(x.get('nota') or '').strip()})
    return sorted(out, key=lambda x: x['inicio'])


def guardar(d, lista):
    tmp = os.path.join(d, ARCHIVO + '.tmp')
    json.dump([x for x in lista if x['fin'] > x['inicio']], open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(d, ARCHIVO))


def _tramo(mo):
    a = float(mo.get('src_inicio') or 0)
    b = float(mo.get('src_fin') or a) if str(mo.get('modo', 'lento')).startswith('lento') else a
    return a, max(a, b)


def toca(mo, lista):
    """El corte importante que pisa el tramo de este bloque (o None)."""
    a, b = _tramo(mo)
    return next((x for x in lista if a < x['fin'] and b > x['inicio'] or a == b and x['inicio'] <= a <= x['fin']), None)


def marcar(bloques, lista):
    """Marca «importante» los bloques que tocan un corte importante y los deja a velocidad normal (×1 como máximo).
    Devuelve los id de los bloques que cambiaron de velocidad."""
    frenados = []
    for b in bloques:
        mo = b.get('montaje') or {}
        if toca(mo, lista):
            mo['importante'] = mo['critico'] = True
            if float(mo.get('velocidad') or 1) > 1:
                mo['velocidad'] = 1.0
                frenados.append(b.get('id', '?'))
        else:
            mo.pop('importante', None)
    return frenados


def sin_mostrar(bloques, lista):
    """Los cortes importantes (o sus partes) que ningún bloque muestra: la IA los saltó."""
    faltan = []
    for x in lista:
        trozos = [(x['inicio'], x['fin'])]
        for b in bloques:
            a, c = _tramo(b.get('montaje') or {})
            trozos = [y for i, f in trozos for y in ((i, min(f, a)), (max(i, c), f)) if y[1] - y[0] > 0.5]
        faltan += [dict(x, inicio=i, fin=f) for i, f in trozos]
    return faltan


def retiempos(bloques):
    """Vuelve a calcular dónde empieza y termina cada bloque en el video final (después de cambiar velocidades)."""
    t = 0.0
    for b in bloques:
        mo = b.get('montaje') or {}
        largo = ((mo['src_fin'] - mo['src_inicio']) / (mo.get('velocidad') or 1) if str(mo.get('modo', '')).startswith('lento') else 0) \
            + (mo.get('congelar_s') or 0)
        b['inicio_min'], b['fin_max'] = round(t, 2), round(t + largo, 2)
        t += largo
    return t


def recortar(tramos, lista, minimo=2):
    """Saca de los tramos de Acortar (cortes y aceleraciones) todo lo que cae dentro de un corte importante."""
    out = []
    for c in tramos:
        trozos = [(c['inicio'], c['fin'])]
        for x in lista:
            trozos = [y for a, b in trozos for y in ((a, min(b, x['inicio'])), (max(a, x['fin']), b)) if y[1] - y[0] > 0]
        out += [dict(c, inicio=a, fin=b) for a, b in trozos if b - a >= minimo]
    return out


def mmss(s):
    return f'{int(s // 60)}:{int(s % 60):02d}'


def texto_para_ia(lista):
    if not lista:
        return ''
    return ('CORTES IMPORTANTES QUE MARCÓ EL AUTOR (los momentos más delicados del video). Cada uno se muestra ENTERO, '
            'a velocidad 1 (nunca acelerado, nunca recortado ni saltado), en bloques "tipo": "critico" que lo expliquen '
            'paso a paso con calma:\n' + '\n'.join(f"- {mmss(x['inicio'])}–{mmss(x['fin'])} ({x['inicio']:g}–{x['fin']:g} s)"
                                                    + (f": {x['nota']}" if x['nota'] else '') for x in lista))
