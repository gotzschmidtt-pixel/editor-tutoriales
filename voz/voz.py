"""Genera la voz de cada bloque del guion con ElevenLabs y guarda los tiempos por carácter.

Uso: python3 voz.py --guion guion.json --salida carpeta_voz [--voz 94zOad0g7T7K4oa7zhDq] [--modelo eleven_v4]
Escribe <bloque>.mp3 y <bloque>.align.json. Un bloque se vuelve a generar solo si cambió su texto (o la voz, el
modelo o la estabilidad); si no, se reutiliza y no gasta créditos dos veces.

Después mide cuánto dura de verdad cada voz y, si no cabe en su bloque, alarga el bloque en guion.json con una pausa
congelada al final y corre los bloques siguientes. Así la voz nunca se monta encima de la del bloque siguiente.
"""
import argparse, base64, json, os, shutil, subprocess, urllib.error, urllib.request

# En tu PC: define la variable ELEVENLABS_API_KEY. En el entorno de Claude la clave la pone el proxy.
def _clave():
    """La clave de ElevenLabs: la variable ELEVENLABS_API_KEY o la guardada con el botón 🔑 de la app."""
    k = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if k:
        return k, 'variable ELEVENLABS_API_KEY'
    aj = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'ajustes.json')
    try:
        k = json.load(open(aj, encoding='utf-8')).get('elevenlabs', '').strip()
    except (OSError, ValueError):
        k = ''
    return k, aj


_K, FUENTE_CLAVE = _clave()
CLAVE = {'xi-api-key': _K} if _K else {}


DESFASE = 0.3  # la voz entra 0,3 s después del inicio del bloque (mezclar_voz.py)
MARGEN = 0.4   # aire al final, antes del bloque siguiente


def firma(b, a):
    return {'texto': b['texto'], 'voz': a.voz, 'modelo': a.modelo, 'estabilidad': a.estabilidad}


def vigente(carpeta, b, a):
    """¿El mp3 que hay corresponde al texto actual del bloque?"""
    mp3 = os.path.join(carpeta, f"{b['id']}.mp3")
    if not os.path.exists(mp3):
        return False
    meta = os.path.join(carpeta, f"{b['id']}.voz.json")
    if os.path.exists(meta):
        try:
            return json.load(open(meta, encoding='utf-8')) == firma(b, a)
        except ValueError:
            return False
    try:  # voces de antes de este cambio: el texto dicho está en la alineación de ElevenLabs
        al = json.load(open(os.path.join(carpeta, f"{b['id']}.align.json"), encoding='utf-8'))
        return ''.join(al['characters']).strip() == b['texto'].strip()
    except (OSError, ValueError, KeyError, TypeError):
        return False


def duracion_voz(carpeta, bid):
    try:
        al = json.load(open(os.path.join(carpeta, f'{bid}.align.json'), encoding='utf-8'))
        return float(al['character_end_times_seconds'][-1])
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                            os.path.join(carpeta, f'{bid}.mp3')], capture_output=True, text=True)
        return float(r.stdout or 0)


def largo_bloque(mo):
    lento = (mo['src_fin'] - mo['src_inicio']) / (mo.get('velocidad') or 1) if mo['modo'].startswith('lento') else 0
    return lento + (mo.get('congelar_s') or 0)


def ajustar_guion(guion, carpeta):
    """Pone en cada bloque la duración real de su voz y lo alarga si no cabe. Devuelve los avisos."""
    g = json.load(open(guion, encoding='utf-8'))
    antes = json.dumps(g, sort_keys=True)
    avisos, t = [], 0.0
    for b in g['bloques']:
        mo = b['montaje']
        real = round(duracion_voz(carpeta, b['id']), 2)
        b['voz_real_s'] = real
        falta = round(real + DESFASE + MARGEN - largo_bloque(mo), 2)
        if falta > 0:
            if mo['modo'] == 'lento':
                mo['modo'] = 'lento+congelar'
            mo['congelar_s'] = round((mo.get('congelar_s') or 0) + falta, 2)
            avisos.append(f"{b['id']}: la voz dura {real:.1f} s y no cabía; alargué el bloque {falta:.1f} s con una pausa")
        largo = largo_bloque(mo)
        b['inicio_min'], b['fin_max'] = round(t, 2), round(t + largo, 2)
        t += largo
    g['duracion_s'] = round(t, 1)
    if json.dumps(g, sort_keys=True) == antes:
        return avisos  # nada cambió: no se toca el archivo (así el montaje no queda como «viejo»)
    if avisos:  # el guion como estaba, por si quieres comparar
        shutil.copyfile(guion, guion + '.antes_voz')
    json.dump(g, open(guion, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guion', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--voz', default='94zOad0g7T7K4oa7zhDq', help='id de voz de ElevenLabs (por defecto Mauricio)')
    ap.add_argument('--modelo', default='eleven_v4')
    ap.add_argument('--estabilidad', type=float, default=0.5)
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    for b in json.load(open(a.guion, encoding='utf-8'))['bloques']:
        mp3 = os.path.join(a.salida, f"{b['id']}.mp3")
        if vigente(a.salida, b, a):
            continue
        if os.path.exists(mp3):
            print(b['id'], 'cambió el texto: genero la voz de nuevo', flush=True)
        body = json.dumps({'text': b['texto'], 'model_id': a.modelo, 'language_code': 'es',
                           'voice_settings': {'stability': a.estabilidad}}).encode()
        req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{a.voz}/with-timestamps?output_format=mp3_44100_128',
                                     data=body, headers={'Content-Type': 'application/json', **CLAVE})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=180))
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{b['id']}: error {e.code} {e.read()[:300]}")
        open(mp3, 'wb').write(base64.b64decode(r['audio_base64']))
        json.dump(r.get('alignment'), open(os.path.join(a.salida, f"{b['id']}.align.json"), 'w'))
        json.dump(firma(b, a), open(os.path.join(a.salida, f"{b['id']}.voz.json"), 'w', encoding='utf-8'), ensure_ascii=False)
        print(b['id'], 'ok', flush=True)
    for x in ajustar_guion(a.guion, a.salida):
        print('·', x, flush=True)
    print('Duraciones reales de la voz guardadas en el guion.', flush=True)


if __name__ == '__main__':
    main()
