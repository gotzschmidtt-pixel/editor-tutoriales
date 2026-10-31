"""«🧠 Lo que aprendí»: la app aprende sola de cada corrección tuya y se lo pasa a la IA en el próximo guion.

Cada vez que guardas el guion, las etiquetas o los círculos en la app (editor del guion, diapositivas, pistas), compara lo
que había con lo que dejaste y anota la edición en mis_conocimientos/aprendizaje/ediciones.jsonl:
  - cambiaste unas palabras por otras («ahora» → «seguidamente»), quitaste o agregaste una frase;
  - quitaste un bloque, le quitaste el humor;
  - quitaste o cambiaste una etiqueta o un círculo.
De ahí saca reglas (reglas.json). Una regla llega a la IA cuando la repetiste 2 veces o más, o cuando la aprobaste en
«🧠 Lo que aprendí»; las que rechazas no vuelven nunca. También arma tu perfil de estilo con los guiones aprobados
(mis_conocimientos/guiones): largo de cada bloque, cómo empiezas las frases, tus frases de siempre y cuánto humor usas.

No guarda claves ni audio: solo los textos que editaste. Si una IA reescribe el guion entero (más de la mitad de los
bloques cambian a la vez), no se toma como corrección tuya.
"""
import collections, difflib, hashlib, json, os, re, time, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
import conocimiento  # noqa: E402

CARPETA = os.path.join(conocimiento.CARPETA, 'aprendizaje')
EDICIONES = os.path.join(CARPETA, 'ediciones.jsonl')
REGLAS = os.path.join(CARPETA, 'reglas.json')
MIRA = {'guion.json', 'etiquetas.json', 'senales.json'}
MIN_VECES = 2          # una regla automática llega a la IA cuando la repetiste estas veces
MAX_PALABRAS = 6       # cambios más largos son reescrituras, no una costumbre
REESCRITURA = 0.5      # si cambia más de esta parte de los bloques a la vez, fue una IA, no tú
VACIAS = set('''a al de del el la las lo los en es un una y o que se con por para su sus tu te me mi no si ya le les nos
este esta eso esto ese esa como mas muy pero vamos va ahi aqui hay'''.split())


def _normal(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def _clave(s):
    s = unicodedata.normalize('NFD', _normal(s).lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').strip(' .,;:¡!¿?«»"\'…')


def _id(*partes):
    return hashlib.sha1('|'.join(partes).encode()).hexdigest()[:10]


def _cargar(txt):
    try:
        return json.loads(txt) if isinstance(txt, str) else txt
    except (ValueError, TypeError):
        return None


# ---------- 1. anotar lo que editaste ----------

def _cambios_texto(antes, despues):
    """Los pedazos cortos que cambiaste en un texto: [(tipo, antes, después)]."""
    a, b = _normal(antes).split(), _normal(despues).split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [_clave(x) for x in a], [_clave(x) for x in b], autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        x, y = ' '.join(a[i1:i2]), ' '.join(b[j1:j2])
        if _clave(x) == _clave(y) or (not _clave(x) and not _clave(y)):
            continue  # solo puntuación o mayúsculas
        if op in ('delete', 'insert') and len(_clave(x or y).split()) >= 2 and (
                _clave(x) in _clave(despues) if op == 'delete' else _clave(y) in _clave(antes)):
            continue  # la frase solo cambió de lugar dentro del texto: no la quitaste ni la agregaste
        largo = max(i2 - i1, j2 - j1) > MAX_PALABRAS  # una frase entera: no sale una regla literal, pero la IA saca el patrón
        tipos = ({'replace': 'reescribio_frase', 'delete': 'quito_frase', 'insert': 'agrego_frase'} if largo else
                 {'replace': 'cambio', 'delete': 'quito', 'insert': 'agrego'})
        out.append((tipos[op], x, y))
    return out


def _bloques(g):
    return {str(b.get('id')): b for b in ((g or {}).get('bloques') or []) if isinstance(b, dict) and b.get('id')}


def _eventos_guion(viejo, nuevo):
    va, vb = _bloques(viejo), _bloques(nuevo)
    if not va or not vb:
        return []
    comunes = [k for k in va if k in vb]
    tocados = [k for k in comunes if _normal(va[k].get('texto')) != _normal(vb[k].get('texto'))]
    if len(tocados) > max(3, REESCRITURA * len(comunes)):
        return []  # reescritura entera (una IA), no una corrección tuya
    ev = []
    for k in tocados:
        sim = difflib.SequenceMatcher(None, _clave(va[k].get('texto')), _clave(vb[k].get('texto'))).ratio()
        if sim < 0.35:
            ev.append({'tipo': 'reescribio', 'bloque': k, 'antes': _normal(va[k].get('texto')), 'despues': _normal(vb[k].get('texto'))})
            continue
        for t, x, y in _cambios_texto(va[k].get('texto'), vb[k].get('texto')):
            ev.append({'tipo': t, 'bloque': k, 'antes': x, 'despues': y})
    for k in comunes:
        if va[k].get('humor') and not vb[k].get('humor'):
            ev.append({'tipo': 'quito_humor', 'bloque': k, 'antes': _normal(va[k].get('texto'))})
    quitados = [k for k in va if k not in vb]
    if len(quitados) <= max(3, len(va) // 4):  # muchos bloques menos a la vez = otro guion, no una corrección
        for k in quitados:
            ev.append({'tipo': 'quito_bloque', 'bloque': k, 'antes': _normal(va[k].get('texto')), 'ancla': _normal(va[k].get('ancla'))})
    return ev


def _lista(x):
    if isinstance(x, dict):
        x = x.get('etiquetas') or x.get('senales') or x.get('items') or []
    return [e for e in (x or []) if isinstance(e, dict)]


def _id_item(e):
    return _clave(f"{e.get('bloque', '')}|{e.get('frase') or e.get('t') or e.get('src_t') or ''}|{e.get('texto') or e.get('etiqueta') or ''}")


def _eventos_lista(viejo, nuevo, que):
    va, vb = {_id_item(e): e for e in _lista(viejo)}, {_id_item(e): e for e in _lista(nuevo)}
    if not va or len([k for k in va if k not in vb]) > max(4, len(va) // 2):
        return []
    ev = []
    for k, e in va.items():
        if k not in vb:
            ev.append({'tipo': f'quito_{que}', 'bloque': e.get('bloque', ''), 'clase': e.get('tipo') or e.get('forma') or '',
                       'antes': _normal(e.get('texto') or e.get('etiqueta') or e.get('frase')), 'titulo': _normal(e.get('titulo'))})
    return ev


def registrar(d, archivo, viejo_txt, nuevo_txt, origen='editor'):
    """Lo llama la app al guardar un archivo desde el editor. Devuelve cuántas ediciones anotó."""
    if archivo not in MIRA:
        return 0
    viejo, nuevo = _cargar(viejo_txt), _cargar(nuevo_txt)
    if viejo is None or nuevo is None:
        return 0
    ev = _eventos_guion(viejo, nuevo) if archivo == 'guion.json' else \
        _eventos_lista(viejo, nuevo, 'etiqueta' if archivo == 'etiquetas.json' else 'circulo')
    if not ev:
        return 0
    os.makedirs(CARPETA, exist_ok=True)
    proyecto, fecha = os.path.basename(os.path.abspath(d)), time.strftime('%Y-%m-%d %H:%M')
    with open(EDICIONES, 'a', encoding='utf-8') as f:
        for e in ev:
            f.write(json.dumps(dict(e, proyecto=proyecto, fecha=fecha, origen=origen), ensure_ascii=False) + '\n')
    recalcular()
    return len(ev)


def ediciones():
    out = []
    try:
        for x in open(EDICIONES, encoding='utf-8'):
            try:
                out.append(json.loads(x))
            except ValueError:
                pass
    except OSError:
        pass
    return out


# ---------- 2. sacar reglas ----------

def _leer_reglas():
    try:
        r = json.load(open(REGLAS, encoding='utf-8'))
        return r if isinstance(r, list) else []
    except (OSError, ValueError):
        return []


def _guardar_reglas(rs):
    os.makedirs(CARPETA, exist_ok=True)
    tmp = REGLAS + '.tmp'
    json.dump(rs, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, REGLAS)


def _dice_algo(x):
    """Un pedazo que enseña algo: al menos una palabra que no sea «que», «los», «de»…"""
    return any(w not in VACIAS and len(w) >= 3 for w in _clave(x).split())


def _contraria(e):
    """La edición que deshace a e (si cambiaste a→b y después b→a, no aprendiste nada)."""
    t, a, b = e.get('tipo'), _clave(e.get('antes')), _clave(e.get('despues'))
    return {'cambio': ('cambio', b, a), 'quito': ('agrego', '', a), 'agrego': ('quito', b, '')}.get(t)


def _regla_de(e):
    """(id, texto de la regla) de una edición, o None si no enseña nada general."""
    t, a, b = e.get('tipo'), e.get('antes', ''), e.get('despues', '')
    if t in ('cambio', 'quito', 'agrego') and not (_dice_algo(a) or _dice_algo(b)):
        return None
    if t == 'cambio' and _clave(a) and _clave(b):
        return _id('cambio', _clave(a), _clave(b)), f'Escribe «{b}» en vez de «{a}».'
    if t == 'quito' and _clave(a):
        return _id('quito', _clave(a)), f'No digas «{a}» (el autor lo quita).'
    if t == 'agrego' and _clave(b):
        return _id('agrego', _clave(b)), f'El autor suele agregar «{b}».'
    if t == 'quito_humor':
        return _id('quito_humor'), 'Menos chistes: el autor quita humor que la IA puso.'
    if t == 'quito_etiqueta':
        cosa = e.get('titulo') or e.get('antes')
        if cosa:
            return _id('quito_etiqueta', _clave(cosa)), f'No pongas la etiqueta «{cosa}» (el autor la quita).'
    if t == 'quito_circulo':
        cosa = e.get('antes')
        if cosa:
            return _id('quito_circulo', _clave(cosa)), f'No marques «{cosa}» con círculo o flecha (el autor lo quita).'
    return None


def recalcular():
    """Rehace las reglas automáticas con todas las ediciones; lo que aprobaste, rechazaste o escribiste tú se respeta."""
    viejas = {r['id']: r for r in _leer_reglas()}
    cuenta = collections.OrderedDict()
    todas = ediciones()
    firma = collections.Counter((e.get('proyecto'), e.get('tipo'), _clave(e.get('antes')), _clave(e.get('despues'))) for e in todas)
    for e in todas:
        c = _contraria(e)
        if c and firma[(e.get('proyecto'),) + c] > 0:  # lo hiciste y lo deshiciste: se anulan los dos
            firma[(e.get('proyecto'),) + c] -= 1
            firma[(e.get('proyecto'), e.get('tipo'), _clave(e.get('antes')), _clave(e.get('despues')))] -= 1
            e['_anulada'] = True
    for e in todas:
        if e.get('_anulada') or firma[(e.get('proyecto'), e.get('tipo'), _clave(e.get('antes')), _clave(e.get('despues')))] < 0:
            continue
        r = _regla_de(e)
        if not r:
            continue
        rid, texto = r
        c = cuenta.setdefault(rid, {'id': rid, 'texto': texto, 'tipo': e['tipo'], 'veces': 0, 'proyectos': [], 'ejemplos': [],
                                    'del_editor': 0})
        c['veces'] += 1
        c['del_editor'] += e.get('origen', 'editor') == 'editor'
        if e.get('proyecto') and e['proyecto'] not in c['proyectos']:
            c['proyectos'].append(e['proyecto'])
        if len(c['ejemplos']) < 3:
            c['ejemplos'].append({k: e.get(k) for k in ('proyecto', 'bloque', 'antes', 'despues', 'fecha') if e.get(k)})
    out = []
    for rid, c in cuenta.items():
        v = viejas.pop(rid, {})
        c['estado'] = v.get('estado', 'auto')
        if v.get('texto_mio'):
            c['texto_mio'] = v['texto_mio']
        out.append(c)
    out += [r for r in viejas.values() if r.get('estado') == 'mia' or r.get('tipo') == 'patron']  # las tuyas y las de la IA
    out.sort(key=lambda r: (r.get('estado') != 'mia', -r.get('veces', 0)))
    _guardar_reglas(out)
    escribir_md()
    return out


MD = os.path.join(conocimiento.CARPETA, 'LO_QUE_APRENDI.md')


def escribir_md():
    """Lo mismo que ve la IA de la app, en un archivo de texto para Claude (paquete de la nube), DeepSeek o cualquier IA."""
    t = texto_para_ia(8000)
    conocimiento.escribir(MD, '# Lo que la app aprendió de las correcciones del autor\n\n'
                          '> Reglas sacadas de sus ediciones en la app (las aprueba o rechaza en «🧠 Lo que aprendí»). Cúmplelas.\n\n'
                          + (t or '(todavía nada aprobado)') + '\n')


def activa(r):
    """Llega a la IA: la aprobaste o la escribiste tú, o la repetiste a mano en el editor (no solo en versiones viejas
    del historial, que pudo cambiar una IA) y no es un «agregó» (agregar un chiste una vez no es una costumbre)."""
    if r.get('estado') in ('aprobada', 'mia'):
        return True
    return r.get('estado') == 'auto' and r.get('del_editor', 0) >= MIN_VECES and r.get('tipo') != 'agrego'


def cambiar(accion, rid='', texto=''):
    """Desde «🧠 Lo que aprendí»: aprobar, rechazar, volver a automática, corregir el texto, agregar una tuya o borrarla."""
    rs = _leer_reglas()
    if accion == 'agregar':
        texto = _normal(texto)
        if not texto:
            raise ValueError('Escribe la regla.')
        rs.insert(0, {'id': _id('mia', texto, str(time.time())), 'texto': texto, 'tipo': 'mia', 'estado': 'mia', 'veces': 0,
                      'proyectos': [], 'ejemplos': [], 'fecha': time.strftime('%Y-%m-%d')})
    else:
        r = next((x for x in rs if x['id'] == rid), None)
        if not r:
            raise ValueError('No encontré esa regla (recarga la página).')
        if accion in ('aprobada', 'rechazada', 'auto'):
            r['estado'] = accion
        elif accion == 'editar':
            r['texto_mio'] = _normal(texto) or None
            if r.get('estado') == 'auto':
                r['estado'] = 'aprobada'
        elif accion == 'borrar' and r.get('estado') == 'mia':
            rs.remove(r)
        else:
            raise ValueError('Acción desconocida.')
    _guardar_reglas(rs)
    escribir_md()
    return rs


# ---------- 2b. el patrón de tus correcciones, con la IA (pedido de fabian, 30/10/2026) ----------

VISTOS = os.path.join(CARPETA, 'patrones_vistos.json')  # hasta qué edición ya leyó la IA
TIPOS_PATRON = {'reescribio', 'reescribio_frase', 'quito_frase', 'agrego_frase', 'quito_bloque', 'quito_humor', 'quito', 'cambio',
                'agrego', 'quito_etiqueta', 'quito_circulo'}


def patrones_ia(ajustes):
    """Lee tus correcciones nuevas y le pide a la IA de «⚙ Ajustes IA» las reglas generales que hay detrás (el patrón, no el
    caso). Quedan como «💡 sugeridas»: llegan a la IA del guion cuando les das ✓. Devuelve las reglas nuevas."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'ia'))
    import ia
    todas = ediciones()
    try:
        visto = int(json.load(open(VISTOS, encoding='utf-8')).get('n', 0))
    except (OSError, ValueError, TypeError):
        visto = 0
    nuevas = [e for e in todas[visto:] if e.get('tipo') in TIPOS_PATRON and e.get('origen', 'editor') == 'editor']
    if not nuevas:
        return []
    nuevas = nuevas[-40:]
    rs = _leer_reglas()
    ya = [r.get('texto_mio') or r['texto'] for r in rs if r.get('estado') != 'rechazada'][:60]
    no = [r.get('texto_mio') or r['texto'] for r in rs if r.get('estado') == 'rechazada'][:30]
    lista = '\n'.join(f"{i}. [{e.get('tipo')}] {e.get('proyecto', '')} {e.get('bloque', '')}: «{str(e.get('antes') or '')[:300]}» → "
                      f"«{str(e.get('despues') or '')[:300]}»" for i, e in enumerate(nuevas, 1))
    pedido = ('Eres el editor del canal de YouTube Xiaomiunlock (fabian, tutoriales de desbloqueo de celulares). Una IA escribió '
              'el guion de un video y fabian lo corrigió a mano. Estas son sus correcciones («antes» → «después»; vacío = lo '
              f'quitó o lo agregó):\n{lista}\n\nSaca de 1 a 5 REGLAS GENERALES y accionables para que la IA que escribe los '
              'próximos guiones no vuelva a hacer lo que fabian corrige: el patrón, no el caso puntual (por ejemplo «No hagas '
              'chistes sobre la suegra», «Nombra cada botón tal como aparece en pantalla», «No prometas que es gratis»). Si un '
              'cambio es solo un dato de ese video, no saques regla de él. Escribe cada regla en una frase corta, en español, '
              'dirigida a la IA del guion.\n'
              f'No repitas estas reglas que ya existen: {json.dumps(ya, ensure_ascii=False)}\n'
              f'No propongas lo que fabian ya rechazó: {json.dumps(no, ensure_ascii=False)}\n'
              'Responde SOLO con JSON: {"reglas": [{"regla": "…", "por_que": "qué corrigió fabian, en una frase", '
              '"ejemplos": [números de las correcciones]}]}')
    r = ia.extraer_json(ia.llamar(dict(ajustes, imagenes=False), pedido, []))
    hechas = []
    for x in ((r or {}).get('reglas') or [])[:5] if isinstance(r, dict) else []:
        texto = _normal((x or {}).get('regla'))
        if not texto:
            continue
        rid = _id('patron', _clave(texto))
        if any(z['id'] == rid for z in rs):
            continue
        ej = [nuevas[i - 1] for i in (x.get('ejemplos') or []) if isinstance(i, int) and 1 <= i <= len(nuevas)][:3]
        regla = {'id': rid, 'texto': texto, 'tipo': 'patron', 'estado': 'sugerida', 'veces': len(ej) or 1,
                 'proyectos': sorted({e.get('proyecto') for e in ej if e.get('proyecto')}), 'del_editor': len(ej),
                 'ejemplos': [{k: e.get(k) for k in ('proyecto', 'bloque', 'antes', 'despues', 'fecha') if e.get(k)} for e in ej],
                 'por_que': _normal(x.get('por_que')), 'fecha': time.strftime('%Y-%m-%d')}
        rs.insert(0, regla)
        hechas.append(regla)
    _guardar_reglas(rs)
    escribir_md()
    os.makedirs(CARPETA, exist_ok=True)
    json.dump({'n': len(todas)}, open(VISTOS, 'w', encoding='utf-8'))
    return hechas


# ---------- 3. perfil de estilo ----------

def _guiones():
    """{proyecto: [(id, texto, humor, critico)]} de los guiones aprobados (mis_conocimientos/guiones/*.md)."""
    out = {}
    g = conocimiento.GUIONES
    for f in sorted(os.listdir(g)) if os.path.isdir(g) else []:
        if not f.endswith('.md'):
            continue
        filas = []
        for x in conocimiento.leer(os.path.join(g, f)).split('\n'):
            m = re.match(r'- (L\w+)( \(humor\))?( \[paso crítico\])?: (.*)', x)
            if m:
                filas.append((m.group(1), m.group(4), bool(m.group(2)), bool(m.group(3))))
        if filas:
            out[f[:-3]] = filas
    return out


def perfil():
    gs = _guiones()
    if not gs:
        return {}
    bloques = [b for v in gs.values() for b in v]
    palabras = [len(b[1].split()) for b in bloques]
    inicios = collections.Counter(' '.join(_clave(b[1]).split()[:2]) for b in bloques if len(b[1].split()) > 3)
    # tus frases de siempre: 3 a 5 palabras seguidas que aparecen en 2 o más guiones (o 3 veces en uno, si hay uno solo)
    frases, en = collections.Counter(), collections.defaultdict(set)
    for p, v in gs.items():
        for _, texto, _, _ in v:
            w = _clave(texto).split()
            for n in (3, 4, 5):
                for i in range(len(w) - n + 1):
                    k = ' '.join(w[i:i + n])
                    frases[k] += 1
                    en[k].add(p)
    minimo = 2 if len(gs) > 1 else 3
    tuyas = [k for k, c in frases.most_common(400) if (len(en[k]) >= 2 if len(gs) > 1 else c >= minimo)
             and sum(x not in VACIAS for x in k.split()) >= 2]
    elegidas = []
    for k in tuyas:  # sin repetir pedazos de la misma frase
        if not any(k in e or e in k for e in elegidas):
            elegidas.append(k)
        if len(elegidas) >= 12:
            break
    return {'guiones': len(gs), 'bloques': len(bloques),
            'palabras_por_bloque': round(sum(palabras) / len(palabras)) if palabras else 0,
            'humor_cada': round(len(bloques) / max(1, sum(b[2] for b in bloques)), 1),
            'inicios_mas_usados': [{'inicio': k, 'veces': c} for k, c in inicios.most_common(8) if c >= 3],
            'frases_tuyas': elegidas,
            'primeras': [v[0][1][:160] for v in gs.values()][:3],
            'ultimas': [v[-1][1][:160] for v in gs.values()][:3]}


# ---------- 4. para la IA y para el panel ----------

def texto_para_ia(limite=3500):
    """Lo que se suma al pedido del guion: tus correcciones de siempre, lo que quitas y tu perfil."""
    if not conocimiento.usar():
        return ''
    rs = [r for r in _leer_reglas() if activa(r)]
    partes = []
    if rs:
        partes.append('CORRECCIONES QUE EL AUTOR HACE SIEMPRE (aprendidas de sus ediciones en la app; cúmplelas sin que te lo pida):\n'
                      + '\n'.join(f"- {r.get('texto_mio') or r['texto']}" for r in rs[:40]))
    quitados = [e for e in ediciones() if e.get('tipo') == 'quito_bloque' and e.get('origen', 'editor') == 'editor'][-6:]
    if quitados:
        partes.append('BLOQUES QUE EL AUTOR QUITÓ en otros videos (no escribas bloques así):\n'
                      + '\n'.join(f"- «{e['antes'][:140]}»" for e in quitados))
    p = perfil()
    if p:
        linea = (f"PERFIL DEL AUTOR (de {p['guiones']} guion(es) aprobados): unas {p['palabras_por_bloque']} palabras por bloque; "
                 f"humor más o menos cada {p['humor_cada']} bloques.")
        if p['inicios_mas_usados']:
            linea += ' Estos comienzos ya los usa mucho, VARÍALOS: ' + ', '.join(f"«{x['inicio']}…»" for x in p['inicios_mas_usados'][:5]) + '.'
        if p['frases_tuyas']:
            linea += ' Frases suyas que puedes usar (sin abusar): ' + '; '.join(f'«{x}»' for x in p['frases_tuyas'][:8]) + '.'
        partes.append(linea)
    t = '\n\n'.join(partes)
    return t if len(t) <= limite else t[:limite].rsplit('\n', 1)[0]


def resumen():
    rs = _leer_reglas()
    ev = ediciones()
    return {'reglas': [dict(r, activa=activa(r)) for r in rs], 'perfil': perfil(), 'ediciones': len(ev),
            'ultimas': ev[-15:][::-1], 'min_veces': MIN_VECES, 'carpeta': CARPETA,
            'para_ia': texto_para_ia()}


# ---------- ④ lo que ya contestaste ----------

def respuesta_conocida(pregunta, proyectos, aqui=''):
    """Si ya contestaste una pregunta casi igual en otro proyecto: (proyecto, respuesta); si no, None."""
    k = _clave(pregunta)
    if len(k) < 12 or not os.path.isdir(proyectos):
        return None
    mejor = (0.0, None)
    for n in os.listdir(proyectos):
        if n == aqui:
            continue
        for f in ('preguntas_guion.json', 'preguntas_trailer.json'):
            try:
                lista = json.load(open(os.path.join(proyectos, n, f), encoding='utf-8'))
            except (OSError, ValueError):
                continue
            for x in lista if isinstance(lista, list) else []:
                if isinstance(x, dict) and _normal(x.get('respuesta')):
                    s = difflib.SequenceMatcher(None, k, _clave(x.get('pregunta'))).ratio()
                    if s > mejor[0]:
                        mejor = (s, (n, _normal(x['respuesta'])))
    return mejor[1] if mejor[0] >= 0.82 else None


def sugerir_respuestas(d, lista):
    """A cada pregunta nueva de la IA le pone «sugerida» si ya la contestaste en otro video (tú decides si la usas)."""
    proyectos, aqui = os.path.dirname(os.path.abspath(d)), os.path.basename(os.path.abspath(d))
    n = 0
    for x in lista:
        if isinstance(x, dict) and not _normal(x.get('respuesta')) and not x.get('sugerida'):
            r = respuesta_conocida(x.get('pregunta'), proyectos, aqui)
            if r:
                x['sugerida'], x['sugerida_de'] = r[1], r[0]
                n += 1
    return n


def aprender_historial(proyectos):
    """Aprende de las versiones viejas del guion que ya tenías (historial_guion de cada proyecto), una sola vez por par."""
    marca = os.path.join(CARPETA, '.historial_hecho.json')
    try:
        hecho = set(json.load(open(marca, encoding='utf-8')))
    except (OSError, ValueError):
        hecho = set()
    n, vistos = 0, set()
    for p in sorted(os.listdir(proyectos)) if os.path.isdir(proyectos) else []:
        h = os.path.join(proyectos, p, 'historial_guion')
        if p.startswith(('_', '.')) or not os.path.isdir(h):
            continue
        versiones = [os.path.join(h, f) for f in sorted(os.listdir(h)) if f.endswith('.json')]
        versiones.append(os.path.join(proyectos, p, 'guion.json'))
        for a, b in zip(versiones, versiones[1:]):
            k = f'{p}/{os.path.basename(a)}>{os.path.basename(b)}'
            if k in hecho or not os.path.exists(b):
                continue
            hecho.add(k)
            try:
                firma = hashlib.sha1(open(a, 'rb').read() + b'|' + open(b, 'rb').read()).hexdigest()
                if firma in vistos:  # el mismo par en otra copia del proyecto (p. ej. la versión _EN): una sola vez
                    continue
                vistos.add(firma)
                n += registrar(os.path.join(proyectos, p), 'guion.json', open(a, encoding='utf-8').read(), open(b, encoding='utf-8').read(),
                               'historial')
            except OSError:
                pass
    os.makedirs(CARPETA, exist_ok=True)
    json.dump(sorted(hecho), open(marca, 'w', encoding='utf-8'))
    return n
