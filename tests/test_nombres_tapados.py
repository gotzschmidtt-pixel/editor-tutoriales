"""Prueba rápida: ninguna función de app/app.py usa como variable local el nombre de una función o módulo global que
también LLAMA en su cuerpo (p. ej. «m = …» en do_POST tapaba el ayudante m() y toda ruta que lo usaba daba
«UnboundLocalError», 31/10/2026). Uso: python tests/test_nombres_tapados.py   (sale con 1 si encuentra alguno)
"""
import ast, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def revisar(archivo):
    arbol = ast.parse(open(archivo, encoding='utf-8').read())
    globales = {n.name for n in arbol.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for n in arbol.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            globales |= {(a.asname or a.name).split('.')[0] for a in n.names}
    malos = []
    for f in ast.walk(arbol):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        propios = [x for x in ast.walk(f) if x is not f and not isinstance(x, (ast.FunctionDef, ast.Lambda))]
        asignados = {t.id for x in propios if isinstance(x, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For, ast.With, ast.NamedExpr))
                     for t in ast.walk(x) if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store)}
        declarados = {nm for x in propios if isinstance(x, (ast.Global, ast.Nonlocal)) for nm in x.names}
        llamados = {x.func.id for x in propios if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)}
        for nombre in sorted((asignados & globales & llamados) - declarados):
            malos.append(f'{os.path.relpath(archivo, RAIZ)}:{f.lineno} {f.name}(): «{nombre}» es local y tapa la global {nombre}()')
    return malos


if __name__ == '__main__':
    malos = revisar(os.path.join(RAIZ, 'app', 'app.py'))
    print('\n'.join(malos) or 'ok: ninguna variable local tapa una función global que se llama ahí')
    sys.exit(1 if malos else 0)
