import json, os, base64, urllib.request
VOICE = "94zOad0g7T7K4oa7zhDq"  # Mauricio - Narrator and Conversational Voice (mismo del video anterior)
OUT = "/mnt/project-files/guion-pico/voz_v4"
os.makedirs(OUT, exist_ok=True)
d = json.load(open('/mnt/project-files/guion-pico/guion_pico_largo.json'))
for b in d['bloques']:
    mp3 = f"{OUT}/{b['id']}.mp3"
    if os.path.exists(mp3): continue
    body = json.dumps({"text": b['texto'], "model_id": "eleven_v4", "language_code": "es",
                       "voice_settings": {"stability": 0.5}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_128",
                                 data=body, headers={"Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        print(b['id'], e.code, e.read()[:300]); raise SystemExit(1)
    open(mp3, "wb").write(base64.b64decode(r["audio_base64"]))
    json.dump(r.get("alignment"), open(f"{OUT}/{b['id']}.align.json", "w"))
    print(b['id'], "ok")
