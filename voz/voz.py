"""Genera la voz de cada bloque del guion con ElevenLabs y guarda los tiempos por carácter.

Uso: python3 voz.py --guion guion.json --salida carpeta_voz [--voz 94zOad0g7T7K4oa7zhDq] [--modelo eleven_v4]
Escribe <bloque>.mp3 y <bloque>.align.json. Los bloques que ya tienen mp3 se saltan (no gasta créditos dos veces);
borra el mp3 de un bloque para regenerarlo.
"""
import argparse, base64, json, os, urllib.error, urllib.request

# En tu PC: define la variable ELEVENLABS_API_KEY. En el entorno de Claude la clave la pone el proxy.
CLAVE = {'xi-api-key': os.environ['ELEVENLABS_API_KEY']} if os.environ.get('ELEVENLABS_API_KEY') else {}


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
        if os.path.exists(mp3):
            continue
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
        print(b['id'], 'ok', flush=True)


if __name__ == '__main__':
    main()
