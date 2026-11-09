"""«📦 Carpeta de entrega» (pedido de fabian, 09/11/2026: «todo en orden, para no estar saliendo a otras carpetas»).

Deja en <proyecto>/ENTREGA/ una carpeta por video con todo junto: el video final (y sus calidades exportadas),
sus miniaturas, DESCRIPCION.txt y TITULO.txt (de lo que guardaste en «▶️ YouTube»). Las versiones en otro idioma
(FINAL_EN.mp4, FINAL_PT.mp4) y el Short (SHORT.mp4) van en su propia carpeta. Solo COPIA: nunca mueve ni borra nada
del proyecto, y lo que ya está copiado igual no se vuelve a copiar.

Uso: python entrega.py --proyecto CARPETA_DEL_PROYECTO
"""
import argparse, glob, json, os, re, shutil, sys


def copiar(src, dst_dir, nombre=None):
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, nombre or os.path.basename(src))
    if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst  # ya está igual
    shutil.copy2(src, dst)
    return dst


def escribir(f, texto):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, 'w', encoding='utf-8-sig') as o:
        o.write(texto.rstrip() + '\n')


def miniaturas(d):
    fs = glob.glob(os.path.join(d, 'miniatura*.jpg')) + glob.glob(os.path.join(d, 'miniatura*.png'))
    fs = [f for f in fs if '_escena' not in os.path.basename(f) and not (f.endswith('.png') and '_titulo_' in os.path.basename(f))]
    return sorted(fs, key=os.path.getmtime, reverse=True)


def elegida(d, fs):
    try:
        a = json.load(open(os.path.join(d, 'youtube', 'miniatura.json'), encoding='utf-8-sig')).get('archivo')
        if a and os.path.join(d, a) in fs:
            return os.path.join(d, a)
    except (OSError, ValueError, AttributeError):
        pass
    return fs[0] if fs else None


def metadatos(d, sufijo=''):
    f = os.path.join(d, 'youtube', f'metadatos{sufijo}.json')
    try:
        return json.load(open(f, encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}


def textos(meta, carpeta):
    hechos = []
    if meta.get('titulo'):
        escribir(os.path.join(carpeta, 'TITULO.txt'), meta['titulo'])
        hechos.append('TITULO.txt')
    partes = [meta.get('descripcion') or '']
    if meta.get('capitulos_texto') and meta['capitulos_texto'] not in partes[0]:
        partes.append(meta['capitulos_texto'])
    if meta.get('etiquetas'):
        et = meta['etiquetas'] if isinstance(meta['etiquetas'], str) else ', '.join(meta['etiquetas'])
        partes.append('Etiquetas: ' + et)
        escribir(os.path.join(carpeta, 'ETIQUETAS.txt'), et)
        hechos.append('ETIQUETAS.txt')
    if any(p.strip() for p in partes):
        escribir(os.path.join(carpeta, 'DESCRIPCION.txt'), '\n\n'.join(p.strip() for p in partes if p.strip()))
        hechos.append('DESCRIPCION.txt')
    return hechos


def main():
    try:  # la consola de Windows no siempre acepta emojis ni tildes
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    d = os.path.abspath(ap.parse_args().proyecto)
    nombre = re.sub(r'[<>:"/\\|?*]+', '_', os.path.basename(d)).strip() or 'video'
    raiz = os.path.join(d, 'ENTREGA')
    hechos = []

    # el video principal: FINAL.mp4, sus calidades exportadas (FINAL_720p.mp4…) y el audio solo (FINAL.mp3)
    principal = [f for f in glob.glob(os.path.join(d, 'FINAL*.mp4')) if re.fullmatch(r'FINAL(_\d+p)?\.mp4', os.path.basename(f))]
    principal += [f for f in [os.path.join(d, 'FINAL.mp3')] if os.path.exists(f)]
    carpeta = os.path.join(raiz, nombre)
    if principal:
        for f in principal:
            copiar(f, carpeta)
        mins = miniaturas(d)
        for f in mins:
            copiar(f, os.path.join(carpeta, 'miniaturas'))
        e = elegida(d, mins)
        if e:
            copiar(e, carpeta, 'MINIATURA_ELEGIDA' + os.path.splitext(e)[1])
        t = textos(metadatos(d), carpeta)
        hechos.append(f'{carpeta}: {len(principal)} video(s), {len(mins)} miniatura(s)' + (', ' + ', '.join(t) if t else ', sin título ni descripción todavía (hazlos en «▶️ YouTube»)'))

    # otros idiomas: FINAL_EN.mp4, FINAL_PT.mp4… (con sus metadatos_EN.json si existen)
    for f in sorted(glob.glob(os.path.join(d, 'FINAL_*.mp4'))):
        m = re.fullmatch(r'FINAL_([A-Za-z]{2})\.mp4', os.path.basename(f))
        if not m:
            continue
        lang = m.group(1).upper()
        c = os.path.join(raiz, f'{nombre}_{lang}')
        copiar(f, c)
        for x in miniaturas(d):
            if re.search(rf'_{lang}\b|_{lang.lower()}\b', os.path.basename(x)):
                copiar(x, os.path.join(c, 'miniaturas'))
        t = textos(metadatos(d, '_' + lang) or metadatos(d, '_' + lang.lower()), c)
        hechos.append(f'{c}: video en {lang}' + (', ' + ', '.join(t) if t else ''))

    # el Short vertical
    if os.path.exists(os.path.join(d, 'SHORT.mp4')):
        c = os.path.join(raiz, f'{nombre}_SHORT')
        copiar(os.path.join(d, 'SHORT.mp4'), c)
        for x in glob.glob(os.path.join(d, 'portada*.jpg')) + glob.glob(os.path.join(d, 'portada*.png')):
            copiar(x, os.path.join(c, 'portadas'))
        t = textos(metadatos(d, '_short'), c)
        hechos.append(f'{c}: Short' + (', ' + ', '.join(t) if t else ''))

    if not hechos:
        print('Todavía no hay video final para entregar (pulsa «▶ Hacer todo» o «⬇ Preparar las marcadas»).')
        return
    print('📦 Carpeta de entrega lista (solo copias, nada se movió):')
    for h in hechos:
        print('  ' + h)


if __name__ == '__main__':
    main()
