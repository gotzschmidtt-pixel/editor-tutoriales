"""«🎧 Pista de audio en inglés» (fabian, 03/11/2026: «¿Pistas de audio en inglés? SÍ, PERO CON MI CONFIRMACIÓN»), sin
gastar nada (voces de prueba hechas con ffmpeg):
- si a la versión NOMBRE_EN le falta la voz de un bloque, se para, dice cuáles y cuántos créditos costarían y NO la genera;
- nunca llama a ElevenLabs, a voz.py ni a YouTube;
- con las voces hechas, deja PISTA_AUDIO_EN.mp3 del largo exacto de FINAL.mp4, cada voz en el segundo de su bloque, la que
  no cabe un poco más rápida (y cortada si ni así cabe), con la música debajo, y avisa que se sube a mano en Studio.
Uso: python tests/test_pista_idioma.py"""
import json, os, shutil, subprocess, sys, tempfile, urllib.request
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
import pista_idioma as pi  # noqa: E402

LLAMADAS = []
correr = subprocess.run


def vigilar(cmd, *a, **k):  # ni voz.py ni ElevenLabs ni YouTube: solo ffmpeg/ffprobe
    texto = ' '.join(map(str, cmd))
    assert 'voz.py' not in texto and 'elevenlabs' not in texto.lower() and 'googleapis' not in texto, texto
    LLAMADAS.append(cmd[0])
    return correr(cmd, *a, **k)


def sin_internet(*a, **k):
    raise AssertionError('la pista no debe llamar a internet')


pi.subprocess.run = vigilar
urllib.request.urlopen = sin_internet

t = tempfile.mkdtemp()
try:
    d, ver = os.path.join(t, 'HONOR'), os.path.join(t, 'HONOR_EN')
    os.makedirs(d)
    os.makedirs(os.path.join(ver, 'voz'))
    textos = {'L01': 'Your Honor asks for the Google account.', 'L02': 'Connect the cable and press the button.', 'L03': 'Done!'}
    json.dump({'bloques': [{'id': k, 'texto': v} for k, v in textos.items()] + [{'id': 'L04', 'texto': ''}]},
              open(os.path.join(ver, 'guion.json'), 'w', encoding='utf-8'))
    tono = lambda f, hz, s: correr(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={hz}:duration={s}',
                                     '-c:a', 'libmp3lame', f], check=True)
    tono(os.path.join(ver, 'voz', 'L01.mp3'), 440, 1.0)
    tono(os.path.join(ver, 'voz', 'L02.mp3'), 660, 3.0)  # no cabe en su lugar (2 s): más rápida y cortada
    inicios, total = {'L01': 1.0, 'L02': 3.0, 'L03': 5.0}, 8.0

    # 1) falta la voz de L03: se para, dice cuántos créditos y no deja nada (no la genera)
    try:
        pi.armar(d, 'en', inicios, total)
        raise AssertionError('armó la pista sin la voz de L03')
    except pi.FaltaVoz as e:
        assert e.bloques == ['L03'] and e.caracteres == len(textos['L03']) and 'SI' in str(e) and 'no la genera' in str(e), str(e)
    assert not os.path.exists(os.path.join(d, 'PISTA_AUDIO_EN.mp3'))
    m = str(pi.FaltaVoz(['L01', 'L02'], 1234, 'HONOR_EN'))
    assert '(L01, L02)' in m and 'unos 1.234 créditos' in m and '«HONOR_EN»' in m, m

    # 2) con todas las voces: el largo exacto, cada voz en su segundo, con música y el aviso de Studio
    tono(os.path.join(ver, 'voz', 'L03.mp3'), 550, 1.0)
    musica = os.path.join(t, 'musica.mp3')
    tono(musica, 220, 3.0)  # se repite hasta cubrir la pista
    r = pi.armar(d, 'en', inicios, total, musica)
    f = os.path.join(d, 'PISTA_AUDIO_EN.mp3')
    assert r['archivo'] == 'PISTA_AUDIO_EN.mp3' and os.path.isfile(f) and abs(pi.duracion(f) - total) < 0.1, r
    assert r['bloques'] == 3 and r['acelerados'] == ['L02'] and r['cortados'] == ['L02'], r
    assert any('YouTube Studio' in a and 'NO la sube' in a for a in r['avisos']), r['avisos']

    def volumen(f, desde, dur):
        x = correr(['ffmpeg', '-v', 'info', '-ss', str(desde), '-t', str(dur), '-i', f, '-af', 'volumedetect', '-f', 'null', '-'],
                   capture_output=True, text=True).stderr
        return float(x.split('mean_volume:')[1].split('dB')[0])

    sin = pi.armar(d, 'en', inicios, total, None, salida=os.path.join(t, 'sin_musica.mp3'))  # sin música: solo la voz
    assert any('Sin música' in a for a in sin['avisos'])
    s = os.path.join(t, 'sin_musica.mp3')
    assert volumen(s, 0.1, 0.7) < -60 and volumen(s, 1.2, 0.6) > -40, (volumen(s, 0.1, 0.7), volumen(s, 1.2, 0.6))  # L01 en 1 s
    assert volumen(s, 2.3, 0.5) < -60 and volumen(s, 3.2, 1.2) > -40  # L02 entra en 3 s
    assert volumen(s, 4.95 - 0.05, 0.04) < -50  # cortada antes de L03: nunca dos voces a la vez
    assert volumen(s, 5.2, 0.6) > -40 and volumen(s, 6.6, 1.2) < -60  # L03 en 5 s y después silencio hasta el final
    assert volumen(f, 0.1, 0.7) > -60  # con música: debajo, desde el principio
    assert set(LLAMADAS) <= {'ffmpeg', 'ffprobe'}, LLAMADAS
    print('ok: la pista de audio en inglés se arma gratis con la voz ya hecha, del largo del video, y no se sube sola')
finally:
    shutil.rmtree(t, ignore_errors=True)
