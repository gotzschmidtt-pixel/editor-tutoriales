"""Traduce con la IA de la app (⚙ Ajustes IA) los textos de las etiquetas de un proyecto a otro idioma.

Uso: python traducir.py --proyecto mis_proyectos/NOMBRE --idioma en [--ajustes app/ajustes.json] [--todo]
Deja las traducciones en etiquetas_idiomas.json (ver idiomas.py). Solo traduce lo que falta; con --todo, todo de nuevo.
Gasta un pedido corto a la IA (solo texto, sin imágenes). No toca ElevenLabs.
"""
import argparse, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
import idiomas  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--idioma', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--todo', action='store_true', help='vuelve a traducir también lo que ya estaba')
    a = ap.parse_args()
    d, idioma = os.path.abspath(a.proyecto), a.idioma.strip().lower()
    datos = idiomas.leer(d)
    tabla = datos['traducciones'].setdefault(idioma, {})
    pedir = [t for t in idiomas.textos(d) if a.todo or not tabla.get(t)]
    if not pedir:
        print(json.dumps({'ok': True, 'traducidos': 0, 'msg': 'No había nada nuevo que traducir.'}, ensure_ascii=False))
        return
    import ia  # la misma IA y las mismas llamadas que usa la app para el guion
    ajustes = dict(json.load(open(a.ajustes, encoding='utf-8')), imagenes=False)
    nombre = idiomas.NOMBRES.get(idioma, idioma)
    prompt = (f'Traduce al idioma «{nombre}» (código {idioma}) estos textos de etiquetas animadas de un video tutorial de '
              'reparación de celulares. Son cortos y van en pantalla: mantén el largo parecido, el tono directo y los nombres '
              'de botones, programas, modelos, webs, números y códigos tal cual (VOL +, POWER, 3uTools, DFU, xiaomiunlock.com…). '
              'Responde SOLO con un objeto JSON {"texto original": "traducción", …} con exactamente estas claves:\n'
              + json.dumps(pedir, ensure_ascii=False, indent=1))
    r = ia.extraer_json(ia.llamar(ajustes, prompt, []))
    n = 0
    for orig, trad in (r.items() if isinstance(r, dict) else []):
        if orig in pedir and str(trad or '').strip():
            tabla[orig] = str(trad).strip()
            n += 1
    idiomas.guardar(d, datos)
    print(json.dumps({'ok': True, 'traducidos': n, 'msg': f'Traduje {n} de {len(pedir)} texto(s) al {nombre}.'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
