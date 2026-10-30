"""Títulos para la miniatura: los sugiere la IA de la app (⚙ Ajustes IA) o traduce el tuyo al inglés y al portugués.

Uso: python titulos.py --proyecto mis_proyectos/NOMBRE              → sugiere 8 títulos (titulos_miniatura_ia.json)
     python titulos.py --proyecto ... --traducir "HONOR|SIN CUENTA GOOGLE"  → solo la traducción de ese título
Imprime una línea JSON. Gasta un pedido corto de texto a la IA (sin imágenes). Pedido de fabian, 30/10/2026.
"""
import argparse, json, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
ARCHIVO = 'titulos_miniatura_ia.json'
REGLAS = ('Cada título tiene DOS partes cortas en MAYÚSCULAS que van en una sola fila al pie de la miniatura: la primera en '
          'blanco (la marca o el modelo, por ejemplo «HONOR» o «HONOR 400 LITE») y la segunda en amarillo, la palabra clave o '
          'la promesa (por ejemplo «SIN CUENTA GOOGLE», «ELIM. PATRÓN», «QUITAR GOOGLE»). Entre las dos, máximo 26 letras. '
          'Nada de signos raros ni emojis. Lo de inglés y portugués es la traducción natural, corta, como lo buscaría la gente '
          'en YouTube (los nombres de marcas, modelos y sistemas quedan igual).')


def leer(f, defecto=''):
    try:
        return open(f, encoding='utf-8').read()
    except OSError:
        return defecto


def contexto(d):
    """Lo que la IA necesita saber del video y del canal."""
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
        guion = ' '.join(str(b.get('texto') or '') for b in g.get('bloques', []))[:3500]
    except (OSError, ValueError):
        guion = ''
    try:
        import conocimiento
        marca = conocimiento.marca_de_proyecto(d) or ''
    except Exception:
        marca = ''
    try:
        pc = json.load(open(os.path.join(RAIZ, 'mis_conocimientos', 'procesos_pc.json'), encoding='utf-8'))
    except (OSError, ValueError):
        pc = {}
    sin_pc = pc.get(marca.lower()) is False
    estad = leer(os.path.join(RAIZ, 'mis_conocimientos', 'ESTADISTICAS_CANAL.md'))
    estad = estad[:3000]
    return (f'Proyecto: {os.path.basename(d)}. Marca: {marca or "(no se sabe)"}.\n'
            f'Lo que dijo el autor del video (idea.txt): {leer(os.path.join(d, "idea.txt")).strip()[:800] or "(nada)"}\n'
            f'Lo que dice la voz del video: {guion or "(todavía no hay guion)"}\n'
            + ('' if sin_pc else 'OJO: este proceso NECESITA PC: nunca pongas «SIN PC» ni lo prometas.\n')
            + (f'Lo que funciona en el canal (estadísticas reales):\n{estad}\n' if estad else ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--traducir', help='«LÍNEA 1|LÍNEA 2»: solo traduce ese título')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    import ia  # la misma IA y las mismas llamadas que usa la app para el guion
    ajustes = dict(json.load(open(a.ajustes, encoding='utf-8')), imagenes=False)
    if a.traducir:
        partes = [x.strip() for x in a.traducir.split('|')[:2] if x.strip()]
        prompt = ('Traduce al inglés (en) y al portugués de Brasil (pt) este título de miniatura de YouTube de un canal de '
                  f'desbloqueo de celulares: {json.dumps(partes, ensure_ascii=False)}. ' + REGLAS +
                  ' Responde SOLO con JSON: {"en": ["…", "…"], "pt": ["…", "…"]}, con las mismas partes y en el mismo orden.')
        r = ia.extraer_json(ia.llamar(ajustes, prompt, []))
        out = {'es': partes}
        for idioma in ('en', 'pt'):
            v = r.get(idioma) if isinstance(r, dict) else None
            out[idioma] = [str(x).strip().upper() for x in v][:len(partes)] if isinstance(v, list) and len(v) >= len(partes) else partes
        print(json.dumps({'ok': True, 'titulo': out}, ensure_ascii=False))
        return
    prompt = ('Eres el que hace las miniaturas del canal de YouTube Xiaomiunlock (fabian, técnico que desbloquea celulares: '
              'cuentas Google/FRP, iCloud, patrones, MDM). Propón 8 títulos distintos para la miniatura de ESTE video, que '
              'den ganas de hacer clic sin mentir: solo promete lo que el video muestra. ' + REGLAS + '\n\n' + contexto(d) +
              '\nResponde SOLO con JSON: {"titulos": [{"es": ["PARTE 1", "PARTE 2"], "en": ["…", "…"], "pt": ["…", "…"], '
              '"por_que": "una frase corta"}, …]}')
    r = ia.extraer_json(ia.llamar(ajustes, prompt, []))
    titulos = []
    for x in (r.get('titulos') if isinstance(r, dict) else None) or []:
        es = [str(p).strip().upper() for p in (x.get('es') or []) if str(p).strip()][:2]
        if not es or re.search(r'\bSIN PC\b', ' '.join(es)) and 'NUNCA PONGAS' in prompt.upper():
            continue
        t = {'es': es, 'por_que': str(x.get('por_que') or '')[:200]}
        for idioma in ('en', 'pt'):
            v = [str(p).strip().upper() for p in (x.get(idioma) or []) if str(p).strip()][:2]
            t[idioma] = v if len(v) == len(es) else es
        titulos.append(t)
    json.dump({'titulos': titulos}, open(os.path.join(d, ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({'ok': True, 'titulos': titulos}, ensure_ascii=False))


if __name__ == '__main__':
    main()
