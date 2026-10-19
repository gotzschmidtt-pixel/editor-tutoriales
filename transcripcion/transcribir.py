"""Transcribe la voz de un video a texto con tiempos por palabra (para guion y subtítulos).

Motores:
  scribe   ElevenLabs Scribe, en línea, el mejor con español latino y ruido de taller.
  whisper  faster-whisper en tu PC, gratis y sin internet (pip install faster-whisper).

Uso:
  python3 transcribir.py --video "Mi video.mp4" --salida mi_video [--motor scribe|whisper] [--modelo small]
Escribe mi_video.txt (texto), mi_video.srt (subtítulos) y mi_video.json (palabras con inicio y fin).
"""
import argparse, json, os, subprocess, tempfile, urllib.request, uuid

# En tu PC: define la variable ELEVENLABS_API_KEY. En el entorno de Claude la clave la pone el proxy.
CLAVE = {'xi-api-key': os.environ['ELEVENLABS_API_KEY']} if os.environ.get('ELEVENLABS_API_KEY') else {}


def audio(video):
    f = os.path.join(tempfile.mkdtemp(prefix='stt_'), 'audio.mp3')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', video, '-vn', '-ac', '1', '-ar', '16000', '-b:a', '64k', f], check=True)
    return f


def scribe(f, idioma):
    lim = uuid.uuid4().hex
    partes = [f'--{lim}\r\nContent-Disposition: form-data; name="model_id"\r\n\r\nscribe_v1\r\n'.encode(),
              f'--{lim}\r\nContent-Disposition: form-data; name="language_code"\r\n\r\n{idioma}\r\n'.encode(),
              f'--{lim}\r\nContent-Disposition: form-data; name="file"; filename="audio.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode(),
              open(f, 'rb').read(), f'\r\n--{lim}--\r\n'.encode()]
    req = urllib.request.Request('https://api.elevenlabs.io/v1/speech-to-text', data=b''.join(partes),
                                 headers={'Content-Type': f'multipart/form-data; boundary={lim}', **CLAVE})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return [{'texto': w['text'], 'inicio': w['start'], 'fin': w['end']} for w in r['words'] if w.get('type') == 'word']


def whisper(f, idioma, modelo):
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel(modelo, compute_type='int8').transcribe(f, language=idioma, word_timestamps=True)
    return [{'texto': w.word.strip(), 'inicio': w.start, 'fin': w.end} for s in segs for w in s.words]


def ts(x):
    return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round(x % 1 * 1000)) % 1000:03d}"


def frases(palabras, maximo=42):
    """Agrupa palabras en líneas de subtítulo: corta en puntuación, en pausas o al llegar a ~42 caracteres."""
    out, act = [], []
    for k, w in enumerate(palabras):
        act.append(w)
        txt = ' '.join(x['texto'] for x in act)
        pausa = k + 1 < len(palabras) and palabras[k + 1]['inicio'] - w['fin'] > 0.6
        if len(txt) >= maximo or txt[-1] in '.?!' or pausa or k + 1 == len(palabras):
            out.append((act[0]['inicio'], act[-1]['fin'], txt)); act = []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--motor', choices=['scribe', 'whisper'], default='scribe')
    ap.add_argument('--modelo', default='small', help='solo whisper: tiny, base, small, medium, large-v3')
    ap.add_argument('--idioma', default='es')
    a = ap.parse_args()
    f = audio(a.video)
    pal = scribe(f, a.idioma) if a.motor == 'scribe' else whisper(f, a.idioma, a.modelo)
    json.dump(pal, open(a.salida + '.json', 'w'), ensure_ascii=False, indent=0)
    fr = frases(pal)
    open(a.salida + '.txt', 'w').write('\n'.join(t for _, _, t in fr) + '\n')
    open(a.salida + '.srt', 'w').write('\n'.join(f'{k}\n{ts(i)} --> {ts(e)}\n{t}\n' for k, (i, e, t) in enumerate(fr, 1)))
    print(f'{len(pal)} palabras, {len(fr)} líneas -> {a.salida}.txt / .srt / .json')


if __name__ == '__main__':
    main()
