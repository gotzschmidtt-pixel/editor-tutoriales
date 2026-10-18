"""Música de fondo automática: la genera con ElevenLabs Music, la repite hasta cubrir el video
y la baja sola cada vez que habla la voz (sidechain), subiéndola en las pausas.

Uso:
  python3 musica.py --video con_voz.mp4 --salida final.mp4 [--pista musica.mp3]
      [--prompt "lo-fi alegre..."] [--volumen 0.22]

Sin --pista genera una nueva (cuesta créditos de ElevenLabs; unos 2.950 por 3:35).
La clave la pone el proxy del entorno para api.elevenlabs.io.
"""
import argparse, json, os, subprocess, tempfile, urllib.request

PROMPT = ("Instrumental background music for a fun, upbeat tech repair tutorial on YouTube. Playful lo-fi "
          "electronic with funky bass, light hip-hop drums, warm electric piano and subtle synth plucks, around "
          "100 BPM, positive and slightly cheeky mood, steady energy with no big drops, no vocals, loopable, "
          "mixed to sit under a voiceover.")


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True, check=True).stdout)


def generar(prompt, ms, destino):
    body = json.dumps({'prompt': prompt, 'music_length_ms': ms, 'model_id': 'music_v1', 'force_instrumental': True}).encode()
    req = urllib.request.Request('https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128', data=body,
                                 headers={'Content-Type': 'application/json'})
    open(destino, 'wb').write(urllib.request.urlopen(req, timeout=600).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True, help='video que ya tiene la voz')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--pista', help='mp3 de música ya generado; si falta, se genera')
    ap.add_argument('--prompt', default=PROMPT)
    ap.add_argument('--volumen', type=float, default=0.22, help='volumen base de la música (0.22 ≈ 10 dB bajo la voz)')
    a = ap.parse_args()

    total = duracion(a.video)
    tmp = tempfile.mkdtemp(prefix='musica_')
    pista = a.pista
    if not pista:
        pista = os.path.join(tmp, 'pista.mp3')
        generar(a.prompt, int(min(total, 300) * 1000), pista)  # la API genera hasta 5 min
    larga = os.path.join(tmp, 'larga.wav')
    vueltas = int(total // duracion(pista)) + 1
    # repite la pista con fundido cruzado de 4 s hasta cubrir el video, con entrada y salida suaves
    ins = sum([['-i', pista] for _ in range(vueltas)], [])
    cadena, prev = [], '0:a'
    for k in range(1, vueltas):
        cadena.append(f'[{prev}][{k}:a]acrossfade=d=4:c1=tri:c2=tri[x{k}]'); prev = f'x{k}'
    cadena.append(f'[{prev}]atrim=0:{total},afade=t=in:d=2,afade=t=out:st={total - 6}:d=6[m]')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins + ['-filter_complex', ';'.join(cadena), '-map', '[m]', larga], check=True)
    # la voz del video controla el compresor de la música: cuando hay voz, la música baja
    mezcla = (f'[0:a]asplit=2[v][sc];[1:a]volume={a.volumen}[mu];'
              '[mu][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];'
              '[v][duck]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89[a]')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', a.video, '-i', larga, '-filter_complex', mezcla,
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', a.salida], check=True)


if __name__ == '__main__':
    main()
