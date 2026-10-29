"""El trabajo sin estar sentado al lado del PC: aviso al celular, cola de noche y lo gastado en el mes.

- Aviso al celular (ntfy, gratis): cuando termina o falla un paso, llega una notificación al teléfono. Se instala la app
  «ntfy» (Play Store) y se suscribe al tema que muestra «📲 Celular». Ajustes en «avisos» de ajustes.json.
- Cola de noche: varios proyectos en fila, cada uno con «▶ Hacer todo», uno detrás del otro. Vive en
  mis_proyectos/.cola.json (al actualizar la app no se toca).
- Gastos del mes: los caracteres de ElevenLabs (su API lo dice exacto) y los tokens de cada IA, sumados de los
  diagnósticos de todos los proyectos, con un precio aproximado por modelo que se puede corregir en ajustes.json.
"""
import glob, json, os, secrets, threading, time, urllib.parse, urllib.request

# dólares por millón de tokens (entrada, salida), aproximados a octubre de 2026; «precios_ia» en ajustes.json los corrige
PRECIOS = {
    'claude-opus': (5, 25), 'claude-sonnet': (3, 15), 'claude-haiku': (1, 5),
    'gpt-5-mini': (0.25, 2), 'gpt-5': (1.25, 10), 'gpt-4.1-mini': (0.4, 1.6), 'gpt-4.1': (2, 8), 'gpt-4o': (2.5, 10),
    'gemini-2.5-pro': (1.25, 10), 'gemini-2.5-flash': (0.3, 2.5), 'deepseek': (0.28, 0.42), 'qwen': (0.4, 1.2),
}
_CANDADO = threading.Lock()


# ---------- aviso al celular ----------

def avisos(aj):
    a = aj.get('avisos')
    return a if isinstance(a, dict) else {}


def tema_nuevo():
    return 'estudio-' + secrets.token_hex(6)  # difícil de adivinar: quien sepa el tema lee los avisos


def avisar(aj, titulo, texto, url='', fallo=False):
    """Manda el aviso sin frenar nada: si no hay internet o está apagado, no pasa nada."""
    a = avisos(aj)
    if not (a.get('activo') and a.get('tema')):
        return False
    cuerpo = {'topic': a['tema'], 'title': titulo, 'message': texto[:1000],
              'tags': ['warning'] if fallo else ['clapper'], 'priority': 4 if fallo else 3}
    if url:
        cuerpo['click'] = url
    try:
        pedido = urllib.request.Request((a.get('servidor') or 'https://ntfy.sh').rstrip('/'), method='POST',
                                        data=json.dumps(cuerpo).encode(), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(pedido, timeout=10).close()
        return True
    except Exception:
        return False


def avisar_resultado(aj, proyecto, r, url=''):
    if not r:
        return
    minutos = max(1, round((r.get('segundos') or 0) / 60))
    if r.get('ok'):
        pausa = ' Espera que revises el guion.' if r.get('pausa') == 'guion' else ''
        avisar(aj, f'✅ {proyecto}: listo', f"Terminó en {minutos} min ({r.get('total', 0)} pasos).{pausa}", url)
    elif r.get('msg') != 'detenido por ti':
        avisar(aj, f'❌ {proyecto}: falló en «{r.get("paso") or "un paso"}»', r.get('msg') or 'Mira el diagnóstico en la app.',
               url, fallo=True)


# ---------- cola de noche ----------

def _archivo(proyectos):
    return os.path.join(proyectos, '.cola.json')


def leer_cola(proyectos):
    try:
        c = json.load(open(_archivo(proyectos), encoding='utf-8'))
        return c if isinstance(c, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_cola(proyectos, c):
    os.makedirs(proyectos, exist_ok=True)
    tmp = _archivo(proyectos) + '.tmp'
    json.dump(c, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, _archivo(proyectos))


def cambiar_cola(proyectos, fn):
    with _CANDADO:
        c = leer_cola(proyectos)
        c.setdefault('items', [])
        fn(c)
        guardar_cola(proyectos, c)
        return c


def siguiente(proyectos, puerto, ocupado):
    """Si la cola está andando y el PC está libre, arranca el próximo proyecto con el mismo «▶ Hacer todo» de la página."""
    if ocupado():
        return
    with _CANDADO:
        c = leer_cola(proyectos)
        if not c.get('andando'):
            return
        item = next((x for x in c.get('items', []) if x.get('estado') == 'espera'), None)
        if not item:
            c['andando'] = False
            guardar_cola(proyectos, c)
            return 'vacia'
        item.update(estado='corriendo', desde=time.time())
        guardar_cola(proyectos, c)
    try:
        q = urllib.parse.urlencode({'p': item['p'], 'paso': 'todo'})
        pedido = urllib.request.Request(f'http://127.0.0.1:{puerto}/api/ejecutar?{q}', method='POST',
                                        data=json.dumps({'calidad': item.get('calidad') or 'alta'}).encode())
        urllib.request.urlopen(pedido, timeout=30).close()
    except Exception as e:  # p. ej. «primero sube tu video»: se anota y se sigue con el próximo
        msg = e.read().decode(errors='replace') if hasattr(e, 'read') else str(e)
        try:
            msg = json.loads(msg).get('error', msg)
        except ValueError:
            pass
        def fallo(c):
            for x in c['items']:
                if x.get('id') == item['id']:
                    x.update(estado='fallo', msg=msg[:300])
        cambiar_cola(proyectos, fallo)
        return siguiente(proyectos, puerto, ocupado)
    return item['p']


def termino(proyectos, proyecto, r):
    """Al terminar un trabajo: si era el de la cola, queda marcado como hecho o fallado."""
    def marcar(c):
        for x in c['items']:
            if x.get('estado') == 'corriendo' and x.get('p') == proyecto:
                x.update(estado='hecho' if r and r.get('ok') else 'fallo', msg=(r or {}).get('msg', '')[:300], hasta=time.time())
    if any(x.get('estado') == 'corriendo' for x in leer_cola(proyectos).get('items', [])):
        cambiar_cola(proyectos, marcar)


# ---------- gastos del mes ----------

def _precio(modelo, propios):
    m = (modelo or '').lower()
    for tabla in (propios or {}, PRECIOS):
        for k in sorted(tabla, key=len, reverse=True):  # «gpt-5-mini» antes que «gpt-5»
            if k in m:
                return tabla[k]
    return None


def gastos_mes(proyectos, aj, clave_eleven=''):
    mes = time.strftime('%Y-%m')
    por_modelo = {}
    for f in glob.glob(os.path.join(proyectos, '*', 'diagnosticos', 'llamadas_*.jsonl')):
        if time.strftime('%Y-%m', time.localtime(os.path.getmtime(f))) < mes:
            continue
        try:
            lineas = open(f, encoding='utf-8').read().splitlines()
        except OSError:
            continue
        for l in lineas:
            try:
                ev = json.loads(l)
            except ValueError:
                continue
            if not str(ev.get('fecha', '')).startswith(mes) or ev.get('reutilizada'):
                continue
            uso = ev.get('uso') or {}
            ent = uso.get('input_tokens') or uso.get('prompt_tokens') or 0
            sal = uso.get('output_tokens') or uso.get('completion_tokens') or 0
            modelo = ev.get('modelo_respondio') or ev.get('modelo') or ev.get('modelo_pedido') or '?'
            x = por_modelo.setdefault(modelo, {'modelo': modelo, 'pedidos': 0, 'entrada': 0, 'salida': 0})
            x['pedidos'] += 1
            x['entrada'] += int(ent or 0)
            x['salida'] += int(sal or 0)
    total = 0.0
    for x in por_modelo.values():
        p = _precio(x['modelo'], aj.get('precios_ia'))
        x['dolares'] = round(x['entrada'] / 1e6 * p[0] + x['salida'] / 1e6 * p[1], 2) if p else None
        total += x['dolares'] or 0
    eleven = None
    if clave_eleven:
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(
                'https://api.elevenlabs.io/v1/user/subscription', headers={'xi-api-key': clave_eleven}), timeout=10))
            eleven = {'usados': r.get('character_count'), 'limite': r.get('character_limit'), 'plan': r.get('tier'),
                      'renueva': time.strftime('%d/%m/%Y', time.localtime(r['next_character_count_reset_unix']))
                      if r.get('next_character_count_reset_unix') else ''}
        except Exception as e:
            eleven = {'error': f'no pude consultar ElevenLabs ({type(e).__name__})'}
    return {'mes': mes, 'ias': sorted(por_modelo.values(), key=lambda x: -(x['dolares'] or 0)),
            'total_ias': round(total, 2), 'eleven': eleven}

