"""«📱 Usar desde el celular»: la app del PC se controla desde el teléfono (APK o Chrome), en casa o con datos móviles.

El PC sigue haciendo todo el trabajo; el celular solo abre la misma página. Está apagado por defecto: mientras no lo
actives, la app escucha solo en tu PC (127.0.0.1) como siempre. Activado:
- escucha también en tu red, pero solo contesta a direcciones privadas: el Wi‑Fi de casa (192.168.x, 10.x, 172.16–31.x)
  y Tailscale (100.64–127.x), que es lo que deja entrar con datos móviles sin abrir puertos del router;
- cada celular entra una vez con el PIN y queda recordado (una cookie firmada, que deja de valer si cambias el PIN);
- tras 5 PIN equivocados, esa dirección espera 5 minutos;
- desde el celular no se cambian estos ajustes ni se ven las claves.
Los ajustes van en «celular» de ajustes.json: {"activo": true, "pin_hash": ..., "sal": ...}. El PIN no se guarda.
"""
import hashlib, hmac, html, ipaddress, secrets, socket, threading, time

COOKIE = 'estudio_celular'
INTENTOS, ESPERA = 5, 300
_FALLOS = {}  # ip -> [cuántos, desde cuándo]
_CANDADO = threading.Lock()
# lo que se abre sin PIN: la pantalla para ponerlo, y el icono para la pantalla de inicio
LIBRES = {'/celular', '/api/celular/entrar', '/manifest.webmanifest', '/icono.png'}
# lo que el celular nunca toca, aunque haya puesto el PIN
SOLO_PC = {'/api/celular', '/api/youtube/conectar', '/api/youtube/cliente', '/api/youtube/desconectar'}
_REDES = [ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '100.64.0.0/10',
                                             'fd7a:115c:a1e0::/48', 'fe80::/10')]


def _ip(x):
    try:
        ip = ipaddress.ip_address((x or '').strip('[]'))
        return ip.ipv4_mapped or ip if ip.version == 6 else ip
    except ValueError:
        return None


def es_local(ip):
    i = _ip(ip)
    return bool(i and i.is_loopback)


def red_permitida(ip):
    """Wi‑Fi de casa o Tailscale. Una dirección de internet nunca entra, aunque alguien abra un puerto del router."""
    i = _ip(ip)
    return bool(i and any(i in r for r in _REDES if r.version == i.version))


def host_valido(host):
    """El nombre con que el celular llama al PC: su IP de la red, o el nombre de Tailscale (…ts.net). Así otra página
    no puede hacerse pasar por la app (DNS rebinding)."""
    h = (host or '').lower()
    if h.startswith('['):
        h = h[1:h.find(']')]
    elif h.count(':') == 1:
        h = h.split(':')[0]
    return red_permitida(h) or h.endswith('.ts.net') or ('.' not in h and h.replace('-', '').isalnum() and not h.isdigit())  # «mi-pc» de MagicDNS


def config(aj):
    c = aj.get('celular')
    return c if isinstance(c, dict) else {}


def activo(aj):
    c = config(aj)
    return bool(c.get('activo') and c.get('pin_hash'))


def _hash(pin, sal):
    return hashlib.pbkdf2_hmac('sha256', pin.encode(), bytes.fromhex(sal), 200_000).hex()


def nuevo_pin(c, pin):
    pin = (pin or '').strip()
    if len(pin) < 6 or not pin.isdigit():
        raise ValueError('El PIN tiene que tener al menos 6 números.')
    c['sal'] = secrets.token_hex(16)
    c['pin_hash'] = _hash(pin, c['sal'])


def _ficha(c):
    return hmac.new(bytes.fromhex(c['sal']), ('celular:' + c['pin_hash']).encode(), 'sha256').hexdigest()


def autorizado(aj, cookies):
    c = config(aj)
    if not activo(aj):
        return False
    for parte in (cookies or '').split(';'):
        k, _, v = parte.strip().partition('=')
        if k == COOKIE and hmac.compare_digest(v, _ficha(c)):
            return True
    return False


def entrar(aj, ip, pin):
    """Devuelve (cookie, '') si el PIN es correcto, o ('', motivo)."""
    c = config(aj)
    if not activo(aj):
        return '', 'El acceso desde el celular está apagado en la app del PC.'
    with _CANDADO:
        n, desde = _FALLOS.get(ip, (0, 0))
        if n >= INTENTOS and time.time() - desde < ESPERA:
            return '', f'Demasiados PIN equivocados. Espera {int(ESPERA - (time.time() - desde)) // 60 + 1} min.'
    if hmac.compare_digest(_hash((pin or '').strip(), c['sal']), c['pin_hash']):
        with _CANDADO:
            _FALLOS.pop(ip, None)
        return (f'{COOKIE}={_ficha(c)}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict'), ''
    with _CANDADO:
        n, desde = _FALLOS.get(ip, (0, 0))
        _FALLOS[ip] = [n + 1 if time.time() - desde < ESPERA else 1, time.time()]
    return '', 'PIN equivocado.'


def direcciones(puerto):
    """Las direcciones con que el celular encuentra este PC: Wi‑Fi de casa y Tailscale."""
    ips = set()
    try:
        for x in socket.getaddrinfo(socket.gethostname(), None):
            ips.add(x[4][0])
    except OSError:
        pass
    try:  # la IP con que el PC sale a internet (la del Wi‑Fi o el cable), sin mandar nada
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    salida = []
    for ip in sorted(ips):
        i = _ip(ip)
        if not i or i.version != 4 or not red_permitida(ip):
            continue
        tipo = 'Tailscale (datos móviles)' if i in _REDES[3] else 'Wi‑Fi de casa'
        salida.append({'tipo': tipo, 'url': f'http://{ip}:{puerto}'})
    return sorted(salida, key=lambda x: x['tipo'] != 'Wi‑Fi de casa')


def pagina_pin(volver='/', aviso=''):
    volver = volver if volver.startswith('/') and not volver.startswith('//') else '/'
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Estudio · PIN</title>
<link rel="manifest" href="/manifest.webmanifest"><meta name="theme-color" content="#06070c">
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#06070c;color:#fff;font:18px system-ui,sans-serif}}
form{{width:min(320px,90vw);text-align:center}}input,button{{width:100%;font-size:24px;padding:12px;margin-top:12px;border-radius:10px;
border:1px solid #343c5e;background:#0f121c;color:#fff;text-align:center;letter-spacing:.2em}}button{{background:#ff2bd6;border:0;letter-spacing:0}}
.aviso{{color:#ff4d6d;min-height:1.4em}}</style></head><body>
<form method="post" action="/api/celular/entrar"><h2>📱 Estudio de tutoriales</h2>
<p>Pon el PIN que elegiste en la app del PC.</p>
<input name="pin" type="password" inputmode="numeric" autocomplete="current-password" autofocus required>
<input type="hidden" name="volver" value="{html.escape(volver)}">
<button>Entrar</button><p class="aviso">{html.escape(aviso)}</p></form></body></html>'''


MANIFIESTO = {
    'name': 'Estudio de tutoriales', 'short_name': 'Estudio', 'start_url': '/', 'scope': '/',
    'display': 'standalone', 'background_color': '#06070c', 'theme_color': '#06070c',
    'icons': [{'src': '/icono.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}],
}
