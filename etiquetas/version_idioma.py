"""«🌐 Hacer versión en otro idioma»: copia el proyecto y traduce su guion, para armar el mismo video con voz en ese idioma.

Uso: python version_idioma.py --proyecto mis_proyectos/NOMBRE --idioma en [--ajustes app/ajustes.json]
Crea mis_proyectos/NOMBRE_EN con: la grabación (sin duplicar espacio si se puede), la transcripción, el mapa, los cortes
importantes, tus capturas y etiquetas, y el guion con cada bloque traducido por la IA de Ajustes (mismos tramos, mismo
montaje). Deja idioma_video.json para que la voz salga en ese idioma (inglés: Brian) y las etiquetas en ese idioma.
No genera voz ni gasta ElevenLabs: eso lo haces tú después con «▶ Hacer todo», cuando revisaste el guion traducido.
"""
import argparse, json, os, re, shutil, subprocess, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
import idiomas  # noqa: E402

# lo que NO se copia: lo armado con la voz en español (se vuelve a hacer) y lo de diagnóstico
NO_COPIAR = re.compile(r'^\.|^(voz|diagnosticos|ia_capturas|hojas_2s|acciones|prueba_ingles|referencias)$|'
                       r'\.(mp4|mp3|wav)$|^(registro\.txt|ia_respuesta.*|guion\.json.*|.*\.antes_.*|idioma_video\.json|'
                       r'\d_.*\.(srt|json)|guion_para_leer\.md)$')


def copiar(origen, destino):
    os.makedirs(destino, exist_ok=True)
    for n in os.listdir(origen):
        f, g = os.path.join(origen, n), os.path.join(destino, n)
        if n == 'original.mp4':
            try:
                os.link(f, g)  # el mismo archivo, sin ocupar el doble de espacio
            except OSError:
                shutil.copy2(f, g)
        elif NO_COPIAR.search(n):
            continue
        elif os.path.isdir(f):
            shutil.copytree(f, g, dirs_exist_ok=True)
        else:
            shutil.copy2(f, g)


def traducir_guion(guion, idioma, ajustes):
    import ia
    nombre = idiomas.NOMBRES.get(idioma, idioma)
    textos = {b['id']: b['texto'] for b in guion['bloques'] if str(b.get('texto') or '').strip()}
    prompt = (f'Traduce al {nombre} (código {idioma}) la narración de un video tutorial de YouTube de reparación de celulares. '
              'Cada bloque se lee con una voz de IA sobre el mismo tramo del video, así que: mantén el largo parecido, el tono '
              'cercano y directo del original, los chistes adaptados con naturalidad, y los nombres de botones, programas, '
              'modelos y webs tal cual (VOL +, POWER, fastboot, USB Redirector, xiaomiunlock.com…). Escribe los números y años '
              'como se dicen en ese idioma (fifteen, twenty twenty-six) para que la voz los lea bien.\n'
              'Responde SOLO con un objeto JSON {"L01": "traducción", …} con exactamente estas claves:\n'
              + json.dumps(textos, ensure_ascii=False, indent=1))
    r = ia.extraer_json(ia.llamar(dict(ajustes, imagenes=False), prompt, []))
    faltan = []
    for b in guion['bloques']:
        if b['id'] in textos:
            t = str((r or {}).get(b['id']) or '').strip()
            if t:
                b['texto_original'] = b['texto']
                b['texto'] = t
            else:
                faltan.append(b['id'])
        for k in ('voz_real_s', 'voz_estimada_s'):
            b.pop(k, None)
    return faltan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--idioma', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    a = ap.parse_args()
    origen, idioma = os.path.abspath(a.proyecto), a.idioma.strip().lower()
    destino = origen.rstrip('\\/') + '_' + idioma.upper()
    if os.path.exists(os.path.join(destino, 'guion.json')):
        raise SystemExit(f'Ya existe la versión {os.path.basename(destino)}: ábrela desde la lista de proyectos (o bórrala para rehacerla).')
    guion = json.load(open(os.path.join(origen, 'guion.json'), encoding='utf-8'))
    print(f'Copio el proyecto a {os.path.basename(destino)}…', flush=True)
    copiar(origen, destino)
    print(f'La IA traduce el guion ({len(guion["bloques"])} bloques)…', flush=True)
    faltan = traducir_guion(guion, idioma, json.load(open(a.ajustes, encoding='utf-8')))
    json.dump(guion, open(os.path.join(destino, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'idioma': idioma, 'origen': os.path.basename(origen)}, open(os.path.join(destino, 'idioma_video.json'), 'w', encoding='utf-8'))
    et = idiomas.leer(destino)
    et['idioma'] = idioma
    idiomas.guardar(destino, et)
    if [t for t in idiomas.textos(destino) if not (et['traducciones'].get(idioma) or {}).get(t)]:  # etiquetas sin traducir
        subprocess.run([sys.executable, os.path.join(AQUI, 'traducir.py'), '--proyecto', destino, '--idioma', idioma, '--ajustes', a.ajustes])
    chars = sum(len(b['texto']) for b in guion['bloques'] if str(b.get('texto') or '').strip())
    print(json.dumps({'ok': True, 'proyecto': os.path.basename(destino), 'caracteres': chars, 'sin_traducir': faltan}, ensure_ascii=False))


if __name__ == '__main__':
    main()
