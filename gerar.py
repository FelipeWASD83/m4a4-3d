"""Gera o modelo 3D de uma M4A4 (a carabina M4 com trilhos, como a M4A4 do CS2), com as animações de tiro e de recarga.

Roda dentro do Blender (o mesmo caminho do deagle-3d e do revolver-3d):

    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup --python gerar.py -- --leve

Opções depois de `--`: `--sem-render` pula as imagens; `--rapido` faz as imagens em meia resolução e poucas
amostras; `--leve` é o rápido com só 4 vistas, 4 núcleos e prioridade mínima do Windows (dá para rodar com o PC
ocupado); `--vistas a,b` escolhe as imagens do modo leve.

Tudo em milímetros, 1 unidade do Blender = 1 mm. Eixos: X para a frente (a boca do cano aponta para +X), Y
largura (o lado direito de quem atira é -Y, onde ficam a janela de ejeção, o assistente do ferrolho e o botão do
pente), Z para cima. O eixo do cano é Z = 0 e X = 0 é a frente do receptor superior (onde entra a porca do cano).

As proporções saíram de uma foto de lado de uma M4 com trilhos (Wikimedia Commons, `PEO M4 Carbine RAS noBG.png`,
4,415 px por mm, conferida pelo comprimento de 838 mm e pelo quebra-chamas de 21,6 mm) e da imagem de inventário
da M4A4 do CS2. O CLAUDE.md tem a tabela das medidas.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "modelo"
RENDER = PASTA / "render"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

X_BOCA = 411.0                     # a ponta do quebra-chamas (cano de 14,5")
TOPO_TRILHO = 34.5                 # topo do trilho Picatinny, em cima do receptor e do guarda-mão
MEIA_SUPERIOR = 14.5               # meia largura do receptor superior
MEIA_INFERIOR = 13.5               # meia largura do receptor inferior (o poço do pente é mais largo)
CURSO = 60.0                       # quanto o transportador do ferrolho recua
CURSO_ALAVANCA = 65.0              # quanto a alavanca em T é puxada na recarga
AVISOS = []

# ---------------------------------------------------------------- perfis 2D (x, z)

# ---------------------------------------------------------------- perfis 2D (x, z)

def _area(pts):
    n = len(pts)
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))


def _sem_repetidos(pts):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-4:
            out.append((p[0], p[1]))
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-4:
        out.pop()
    return out


def arredondar(pts, raio_padrao, raio_min=0.0, passo_ang=math.radians(10)):
    """Arredonda cada canto do polígono fechado. Ponto pode ser (x, z) ou (x, z, raio)."""
    P = [(p[0], p[1], max(p[2] if len(p) > 2 else raio_padrao, raio_min)) for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        x, z, r = P[i]
        ax, az = P[i - 1][:2]
        bx, bz = P[(i + 1) % n][:2]
        ux, uz = ax - x, az - z
        vx, vz = bx - x, bz - z
        la, lb = math.hypot(ux, uz), math.hypot(vx, vz)
        if la < 1e-6 or lb < 1e-6:
            continue
        ux, uz, vx, vz = ux / la, uz / la, vx / lb, vz / lb
        ang = math.acos(max(-1.0, min(1.0, ux * vx + uz * vz)))
        if r <= 0 or ang > math.radians(165):
            out.append((x, z))
            continue
        t = min(r / math.tan(ang / 2), 0.48 * la, 0.48 * lb)
        re = t * math.tan(ang / 2)
        bxv, bzv = ux + vx, uz + vz
        lbv = math.hypot(bxv, bzv)
        bxv, bzv = bxv / lbv, bzv / lbv
        d = re / math.sin(ang / 2)
        cx, cz = x + bxv * d, z + bzv * d
        sx, sz, ex, ez = x + ux * t, z + uz * t, x + vx * t, z + vz * t
        a0 = math.atan2(sz - cz, sx - cx)
        a1 = math.atan2(ez - cz, ex - cx)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        m = max(2, math.ceil(abs(da) / passo_ang))
        for k in range(m + 1):
            a = a0 + da * k / m
            out.append((cx + re * math.cos(a), cz + re * math.sin(a)))
    return _sem_repetidos(out)


def recuar(pts, o):
    """Desloca o polígono para dentro em `o` (miter limitado)."""
    if o <= 0:
        return list(pts)
    n = len(pts)
    s = 1.0 if _area(pts) > 0 else -1.0
    out = []
    for i in range(n):
        px, pz = pts[i - 1]
        x, z = pts[i]
        qx, qz = pts[(i + 1) % n]
        d1x, d1z, d2x, d2z = x - px, z - pz, qx - x, qz - z
        l1, l2 = math.hypot(d1x, d1z), math.hypot(d2x, d2z)
        n1 = (-d1z * s / l1, d1x * s / l1)
        n2 = (-d2z * s / l2, d2x * s / l2)
        mx, mz = n1[0] + n2[0], n1[1] + n2[1]
        lm = math.hypot(mx, mz)
        if lm < 1e-9:
            mx, mz = n1
        else:
            mx, mz = mx / lm, mz / lm
        c = max(mx * n1[0] + mz * n1[1], 0.35)
        out.append((x + mx * o / c, z + mz * o / c))
    return out


def _cruza(pts):
    """True se o polígono fechado se cruza (O(n²), só para conferência)."""
    n = len(pts)

    def lado(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if lado(a, b, c) * lado(a, b, d) < 0 and lado(c, d, a) * lado(c, d, b) < 0:
                return True
    return False


def bez3(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def _suave(a, b, t):
    t = max(0.0, min(1.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def chaikin(pts, vezes=2):
    """Suaviza um caminho aberto mantendo as pontas."""
    for _ in range(vezes):
        novo = [pts[0]]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            novo += [(0.75 * ax + 0.25 * bx, 0.75 * az + 0.25 * bz), (0.25 * ax + 0.75 * bx, 0.25 * az + 0.75 * bz)]
        novo.append(pts[-1])
        pts = novo
    return pts


def _normais(caminho, lado):
    ns = []
    n = len(caminho)
    for i in range(n):
        ax, az = caminho[max(i - 1, 0)]
        bx, bz = caminho[min(i + 1, n - 1)]
        dx, dz = bx - ax, bz - az
        c = math.hypot(dx, dz)
        ns.append((lado * dz / c, -lado * dx / c))
    return ns


def _solido_de_aneis(nome, aneis, mat):
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in anel] for anel in aneis]
    m = len(aneis[0])
    bm.faces.new(vs[0])
    bm.faces.new(vs[-1])
    for a, b in zip(vs, vs[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            bm.faces.new([a[k], a[k2], b[k2], b[k]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def varrer(nome, caminho, lado, meia_y, meia_n, mat, desloc=0.0, expoente=2.6, m=28):
    """Haste de seção oval arredondada correndo ao longo de um caminho (x, z).
    meia_y / meia_n: meia largura (em Y) e meia espessura (na normal), número ou função de t (0 a 1)."""
    fy = meia_y if callable(meia_y) else (lambda t: meia_y)
    fn = meia_n if callable(meia_n) else (lambda t: meia_n)
    ns = _normais(caminho, lado)
    aneis = []
    for i, ((x, z), (nx, nz)) in enumerate(zip(caminho, ns)):
        t = i / (len(caminho) - 1)
        wy, wn = fy(t), fn(t)
        cx, cz = x + nx * desloc, z + nz * desloc
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            dy = wy * _sgnpow(math.cos(a), 2 / expoente)
            dn = wn * _sgnpow(math.sin(a), 2 / expoente)
            anel.append((cx + nx * dn, dy, cz + nz * dn))
        aneis.append(anel)
    return _solido_de_aneis(nome, aneis, mat)


def _tampa_redonda(anel, f, b, centro_vizinho, w, raio, n):
    """Fatias extras que encolhem e se afastam da peça, arredondando uma ponta do cabo."""
    meio = (f + b) / 2
    eixo = (b - f).normalized()
    fora = Vector((eixo.y, -eixo.x))
    if fora.dot(meio - centro_vizinho) < 0:
        fora = -fora
    meio_l = (b - f).length / 2
    extras = []
    for k in range(1, n + 1):
        th = (math.pi / 2) * k / n
        enc, anda = raio * (1 - math.cos(th)), raio * math.sin(th)
        su, sy = max(1 - enc / meio_l, 0.05), max(1 - enc / w, 0.05)
        novo = []
        for (x, y, z) in anel:
            du = (Vector((x, z)) - meio).dot(eixo)
            pt = meio + eixo * du * su + fora * anda
            novo.append((pt.x, y * sy, pt.y))
        extras.append(novo)
    return extras


def cabo_solido(nome, frente, costas, largura, mat, m=64, expoente=2.0, raio_fundo=5.0, raio_topo=3.0,
                aneis_tampa=6, sulcos=None, alcance=0.42):
    """Cabo de madeira como sólido de fatias: cada fatia vai da linha da frente (lisa) à de trás e tem
    seção oval, com o volume puxado para trás (onde a palma encosta). `sulcos` (um valor por fatia,
    negativo = para dentro) afunda só a parte da frente da fatia, até `alcance` dela, para os sulcos
    dos dedos não ondularem os lados nem as costas. As duas pontas são arredondadas."""
    aneis = []
    for i, (f, b) in enumerate(zip(frente, costas)):
        t = i / (len(frente) - 1)
        w = largura(t)
        eixo = Vector((b[0] - f[0], b[1] - f[1])).normalized()
        sulco = sulcos[i] if sulcos else 0.0
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            u = 0.5 - 0.5 * _sgnpow(math.cos(a), 2 / expoente)
            u = u ** 0.86
            y = w * _sgnpow(math.sin(a), 2 / expoente)
            x, z = f[0] + (b[0] - f[0]) * u, f[1] + (b[1] - f[1]) * u
            if sulco and u < alcance:
                peso = (1 - u / alcance) ** 2
                x, z = x - eixo.x * sulco * peso, z - eixo.y * sulco * peso
            anel.append((x, y, z))
        aneis.append(anel)
    c = lambda i: (Vector(frente[i]) + Vector(costas[i])) / 2
    fundo = _tampa_redonda(aneis[-1], Vector(frente[-1]), Vector(costas[-1]), c(-2), largura(1.0),
                           raio_fundo, aneis_tampa)
    topo = _tampa_redonda(aneis[0], Vector(frente[0]), Vector(costas[0]), c(1), largura(0.0),
                          raio_topo, aneis_tampa)
    return _solido_de_aneis(nome, topo[::-1] + aneis + fundo, mat)


# ---------------------------------------------------------------- malhas

def objeto(nome, bm, mat=None):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def almofada(nome, pts, meia, r, mat, raio_canto=None, aneis=6):
    """Perfil (x, z) extrudado de -meia a +meia em Y com a borda arredondada de raio r."""
    base = arredondar(pts, raio_canto if raio_canto is not None else r * 1.3, raio_min=r * 1.15)
    niveis = []
    for k in range(aneis, -1, -1):
        th = (math.pi / 2) * k / aneis
        niveis.append((-(meia - r + r * math.sin(th)), r * (1 - math.cos(th))))
    for k in range(aneis + 1):
        th = (math.pi / 2) * k / aneis
        niveis.append((meia - r + r * math.sin(th), r * (1 - math.cos(th))))
    if _cruza(recuar(base, r)):
        AVISOS.append(f"{nome}: o contorno se cruza depois de recuar {r} mm (raio da borda grande demais)")
    bm = bmesh.new()
    aneis_v = []
    for y, o in niveis:
        aneis_v.append([bm.verts.new((x, y, z)) for x, z in recuar(base, o)])
    n = len(base)
    bm.faces.new(aneis_v[0])
    bm.faces.new(aneis_v[-1])
    for a, b in zip(aneis_v, aneis_v[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def tornear(nome, pts, mat, pos=(0, 0, 0), eixo='x', seg=64, fechado=False):
    """Sólido de revolução: pts = [(posição no eixo, raio)]; raio 0 vira ponta.
    `fechado` liga o último anel ao primeiro (tubos ocos)."""
    bm = bmesh.new()
    aneis = []
    for t, r in pts:
        if r < 1e-9:
            aneis.append([bm.verts.new((t, 0, 0))])
        else:
            aneis.append([bm.verts.new((t, r * math.cos(2 * math.pi * k / seg),
                                        r * math.sin(2 * math.pi * k / seg))) for k in range(seg)])
    pares = list(zip(aneis, aneis[1:]))
    if fechado:
        pares.append((aneis[-1], aneis[0]))
    for a, b in pares:
        for k in range(seg):
            k2 = (k + 1) % seg
            vs = []
            for v in (a[k % len(a)], a[k2 % len(a)], b[k2 % len(b)], b[k % len(b)]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if eixo == 'y':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
    elif eixo == 'z':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=pos)
    return objeto(nome, bm, mat)


def caixa(nome, x0, x1, y0, y1, z0, z1, mat=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = ((x1 if v.co.x > 0 else x0), (y1 if v.co.y > 0 else y0), (z1 if v.co.z > 0 else z0))
    return objeto(nome, bm, mat)


def aplicar(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    novo = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    velho = ob.data
    nome = velho.name
    ob.modifiers.clear()
    ob.data = novo
    bpy.data.meshes.remove(velho)
    novo.name = nome


def booleano(base, ferramentas, op='DIFFERENCE'):
    if not ferramentas:
        return base
    col = bpy.data.collections.new("_ferramentas")
    bpy.context.scene.collection.children.link(col)
    for f in ferramentas:
        for c in list(f.users_collection):
            c.objects.unlink(f)
        col.objects.link(f)
    mod = base.modifiers.new("bool", 'BOOLEAN')
    mod.operation = op
    mod.solver = 'MANIFOLD'
    mod.operand_type = 'COLLECTION'
    mod.collection = col
    aplicar(base)
    for f in list(col.objects):
        malha = f.data
        bpy.data.objects.remove(f)
        bpy.data.meshes.remove(malha)
    bpy.data.collections.remove(col)
    return base


def acabar(ob, bisel=0.0, segmentos=3, angulo=36):
    """Chanfro opcional nas quinas vivas e sombreamento liso só onde a curva é suave."""
    if bisel > 0:
        m = ob.modifiers.new("bisel", 'BEVEL')
        m.width = bisel
        m.segments = segmentos
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(50)
        aplicar(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(angulo)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    m = ob.modifiers.new("normais", 'WEIGHTED_NORMAL')
    m.mode = 'FACE_AREA'
    m.keep_sharp = True
    aplicar(ob)
    return ob


def girar(ob, rot, loc):
    ob.rotation_euler = rot
    ob.location = loc
    return ob



# ---------------------------------------------------------------- materiais e texturas

def material(nome, cor, metal=0.0, rug=0.5, imagem=None, verniz=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rug
    if verniz:
        b.inputs["Coat Weight"].default_value = verniz
        b.inputs["Coat Roughness"].default_value = 0.12
    if imagem:
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = imagem
        m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


def ruido(linhas, colunas, celulas_y, celulas_x, rng):
    g = rng.random((celulas_y + 2, celulas_x + 2))
    ty = np.linspace(0, celulas_y, linhas, endpoint=False)
    tx = np.linspace(0, celulas_x, colunas, endpoint=False)
    iy, ix = ty.astype(int), tx.astype(int)
    fy, fx = ty - iy, tx - ix
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    iy, fy, ix, fx = iy[:, None], fy[:, None], ix[None, :], fx[None, :]
    v00, v10 = g[iy, ix], g[iy, ix + 1]
    v01, v11 = g[iy + 1, ix], g[iy + 1, ix + 1]
    return (v00 * (1 - fx) + v10 * fx) * (1 - fy) + (v01 * (1 - fx) + v11 * fx) * fy


def _normalizar(t):
    return (t - t.min()) / (t.max() - t.min())


def _salvar_imagem(nome, rgb):
    n = rgb.shape[0]
    px = np.concatenate([rgb, np.ones((n, n, 1))], axis=2).astype(np.float32)
    img = bpy.data.images.new(nome, n, n)
    img.pixels.foreach_set(px.ravel())
    SAIDA.mkdir(exist_ok=True)
    img.filepath_raw = str(SAIDA / f"{nome}.png")
    img.file_format = 'PNG'
    img.save()
    return img


def uv_caixa(ob, escala=1 / 200.0):
    """Projeção de caixa (cada face pelo eixo dominante da normal), para a têmpera."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        eixo = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            u, v = ((c.y, c.z), (c.x, c.z), (c.x, c.y))[eixo]
            l[uv].uv = (u * escala + 0.5, v * escala + 0.5)
    bm.to_mesh(ob.data)
    bm.free()


def _juntar(base, extra, mat):
    """Põe a malha de `extra` dentro de `base`, com o material dado, e apaga `extra`. O índice é procurado pelo
    material: o booleano deixa espaços vazios na lista de materiais da peça."""
    nomes = [m.name if m else None for m in base.data.materials]
    if mat.name not in nomes:
        base.data.materials.append(mat)
        nomes.append(mat.name)
    indice_material = nomes.index(mat.name)
    bm = bmesh.new()
    bm.from_mesh(extra.data)
    for f in bm.faces:
        f.material_index = indice_material
    tmp = bpy.data.meshes.new("_tmp")
    bm.to_mesh(tmp)
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(base.data)
    bm.from_mesh(tmp)
    bm.to_mesh(base.data)
    bm.free()
    malha = extra.data
    bpy.data.objects.remove(extra)
    bpy.data.meshes.remove(malha)
    bpy.data.meshes.remove(tmp)


def _pivo(ob, ponto):
    """Muda a origem da peça para o ponto em que ela gira, sem mexer na forma (peça sem transformação)."""
    p = Vector(ponto)
    ob.data.transform(Matrix.Translation(-p))
    ob.location = p


def _prender(filho, pai):
    mw = filho.matrix_world.copy()
    filho.parent = pai
    filho.matrix_world = mw


class Faixa:
    """Uma animação com nome (vira uma faixa de NLA e uma animação no GLB). As chaves de cada peça vão
    de 1 a `fim`, para todas começarem e acabarem juntas."""

    def __init__(self, nome, inicio, fim, extrapolacao='NOTHING'):
        self.nome, self.inicio, self.fim, self.extrapolacao = nome, inicio, fim, extrapolacao
        self.chaves = {}

    def k(self, ob, prop, quadro, valor, interp='BEZIER'):
        self.chaves.setdefault(ob, []).append((quadro, prop, tuple(valor), interp))

    def gravar(self, repouso):
        from bpy_extras import anim_utils
        for ob, lista in self.chaves.items():
            por_prop = {}
            for c in lista:
                por_prop.setdefault(c[1], []).append(c)
            ob.animation_data_create()
            ob.animation_data.action = None
            interps = {}
            for prop, cs in por_prop.items():
                cs.sort(key=lambda c: c[0])
                if cs[0][0] > 1:
                    cs.insert(0, (1, prop, cs[0][2], 'CONSTANT'))
                if cs[-1][0] < self.fim:
                    cs.append((self.fim, prop, cs[-1][2], 'CONSTANT'))
                for quadro, _, valor, interp in cs:
                    setattr(ob, prop, valor)
                    ob.keyframe_insert(prop, frame=quadro)
                    interps[(prop, quadro)] = interp
            acao = ob.animation_data.action
            # o keyframe_insert ignora a interpolação pedida: grava chave por chave na curva
            canais = anim_utils.action_get_channelbag_for_slot(acao, ob.animation_data.action_slot)
            for fc in canais.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = interps.get((fc.data_path, round(kp.co.x)), 'BEZIER')
            acao.name = f"{self.nome}|{ob.name}"
            trilha = ob.animation_data.nla_tracks.new()
            trilha.name = self.nome
            faixa = trilha.strips.new(self.nome, self.inicio, acao)
            faixa.extrapolation = self.extrapolacao
            ob.animation_data.action = None
            for prop, valor in repouso[ob].items():
                setattr(ob, prop, valor)


def luz_de_estudio(nome, pos, alvo, tam, forca):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co = (v.co.x * tam[0] * 2, v.co.y * tam[1] * 2, 0)
    ob = objeto(nome, bm)
    d = Vector(alvo) - Vector(pos)
    ob.rotation_euler = d.to_track_quat('Z', 'Y' if abs(d.normalized().z) < 0.9 else 'X').to_euler()
    ob.location = pos
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = forca
    saida = nodes.new("ShaderNodeOutputMaterial")
    m.node_tree.links.new(em.outputs["Emission"], saida.inputs["Surface"])
    ob.data.materials.append(m)
    ob.visible_camera = False
    ob.visible_shadow = False
    return ob

def prisma_x(nome, pts_yz, x0, x1, r, mat):
    """Seção vista de frente (y, z), cantos arredondados, extrudada em X de x0 a x1 com a borda de raio r."""
    ob = almofada(nome, pts_yz, (x1 - x0) / 2, r, mat)
    ob.data.transform(Matrix.Translation(((x0 + x1) / 2, 0, 0)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    return ob

def deslocar(ob, v):
    ob.data.transform(Matrix.Translation(v))
    return ob


def pino(nome, x, z, raio, meia, mat):
    perfil = [(-meia, 0), (-meia, raio * 0.8), (-meia + 0.5, raio), (meia - 0.5, raio), (meia, raio * 0.8), (meia, 0)]
    return acabar(tornear(nome, perfil, mat, pos=(x, 0, z), eixo='y', seg=32))



# ---------------------------------------------------------------- a M4A4


def textura_polimero():
    """Polímero do cabo, da coronha e das capas do trilho: grão fino e manchas suaves, cinza escuro com cor."""
    n = 1024
    rng = np.random.default_rng(2026)
    pontos = ruido(n, n, 260, 260, rng)
    grao = rng.random((n, n))
    manchas = ruido(n, n, 5, 5, rng)
    t = _normalizar(0.45 * pontos + 0.25 * grao + 0.30 * manchas)
    # valores em sRGB (o PNG é lido assim pelo Blender e pelo mod): 0,34 a 0,42 dá ~0,10 a 0,15 linear
    v = 0.34 + 0.08 * t
    return _salvar_imagem("polimero", v[..., None] * np.array([1.0, 1.02, 0.94]))


def plano_t(nome, pts_xy, z0, z1, r, mat):
    """Peça deitada: o contorno visto de cima (x, y), extrudado em Z de z0 a z1 com a borda de raio r."""
    ob = almofada(nome, pts_xy, (z1 - z0) / 2, r, mat)
    # almofada extruda em Y: girar +90° em X leva a extrusão para Z e o segundo número do contorno para -Y
    # (o contorno tem que ser simétrico em y: o giro o espelha)
    ob.data.transform(Matrix.Translation((0, 0, (z0 + z1) / 2)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    return ob


def trilho(nome, x0, x1, mat, embaixo=False):
    """Trilho Picatinny: seção em rabo de andorinha de 21,2 mm e ranhuras a cada 10 mm."""
    topo, base = TOPO_TRILHO, TOPO_TRILHO - 8.5
    secao = [(-10.6, topo, 0.6), (10.6, topo, 0.6), (10.6, topo - 2.5, 0.4), (8.0, topo - 4.5, 0.4),
             (8.0, base, 0.3), (-8.0, base, 0.3), (-8.0, topo - 4.5, 0.4), (-10.6, topo - 2.5, 0.4)]
    ob = prisma_x(nome, secao, x0, x1, 0.4, mat)
    n = int((x1 - x0 - 6) // 10)
    meio = (x0 + x1) / 2
    booleano(ob, [caixa(f"_ranhura{k}", meio + (k - (n - 1) / 2) * 10 - 2.65, meio + (k - (n - 1) / 2) * 10 + 2.65,
                        -12, 12, topo - 3.0, topo + 1) for k in range(n)])
    if embaixo:     # meia volta em X: a seção é simétrica, então só desce
        ob.data.transform(Matrix.Rotation(math.pi, 4, 'X'))
    return acabar(ob, 0.2, 2)


def construir():
    """Proporções de uma M4 com trilhos (a M4A4 do CS2), medidas numa foto de lado: receptor superior plano com
    trilho, a alça de mira destacável atrás e a alavanca em T embaixo dela; janela de ejeção com a tampa aberta,
    assistente do ferrolho e defletor à direita; guarda-mão de trilhos até a massa de mira triangular; cano fino
    com o degrau do lança-granadas e o quebra-chamas de gaiola; receptor inferior com poço do pente, guarda-mato
    fino e o cabo de polímero; tubo do amortecedor e a coronha retrátil."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # metálico baixo de propósito: com metálico alto o estúdio claro se reflete e a arma sai quase branca
    anod = material("aluminio_anodizado", (0.17, 0.175, 0.185), metal=0.3, rug=0.5)
    aco = material("aco_fosfatizado", (0.21, 0.21, 0.22), metal=0.55, rug=0.45)
    polimero = material("polimero", (1, 1, 1), rug=0.68, imagem=textura_polimero())
    borracha = material("borracha", (0.12, 0.12, 0.118), rug=0.9)
    aco_pente = material("aluminio_pente", (0.19, 0.185, 0.17), metal=0.3, rug=0.5)
    P = {}

    # ---- receptor superior: corpo plano em cima, cavidade do transportador, janela de ejeção à direita, canal da
    # alavanca em T sob o trilho e o trilho Picatinny por cima
    sup = almofada("superior", [(-190, -12, 1.5), (-190, 22, 3), (-185, 27, 3), (0, 27, 1.5), (0, -12, 1.5)],
                   MEIA_SUPERIOR, 1.8, anod)
    booleano(sup, [trilho("_trilho_sup", -181, 0, anod)], 'UNION')
    cortes = [tornear("_cavidade", [(-195, 0), (-195, 13.0), (0.6, 13.0), (0.6, 0)], None, seg=48),
              deslocar(almofada("_janela", [(-91, -1), (-11, -1), (-11, 15), (-91, 15)], 6, 1.0, None), (0, -14, 0)),
              caixa("_canal_alavanca", -196, -50, -5, 5, 22.3, 30.2)]
    booleano(sup, cortes)
    P["superior"] = acabar(sup, 0.3, 2)

    # defletor de estojo atrás da janela e o assistente do ferrolho (botão redondo inclinado)
    P["defletor"] = acabar(deslocar(almofada("defletor", [(-101, -2), (-92, -2), (-92, 19), (-97, 23), (-101, 23)], 2.4,
                                             0.7, anod), (0, -15.5, 0)), angulo=40)
    assist = tornear("assistente", [(-126, 0), (-126, 7.2), (-100, 7.2), (-97, 5.5), (-97, 0)], anod, seg=40)
    _juntar(assist, tornear("_botao_assist", [(-138, 0), (-138, 5.0), (-137, 6.0), (-126, 6.0), (-126, 0)], None,
                            seg=40), aco)
    assist.data.transform(Matrix.Translation((-112, -16.5, 17)) @ Matrix.Rotation(math.radians(-6), 4, 'Y')
                          @ Matrix.Translation((112, 0, 0)))
    P["assistente"] = acabar(assist)

    # tampa da janela de ejeção: aberta (pendurada para baixo) como depois do primeiro tiro. A origem fica na
    # dobradiça; girar 180° em X fecha.
    tampa = deslocar(almofada("tampa_janela", [(-90, -1), (-12, -1), (-12, -19, 2), (-90, -19, 2)], 0.75, 0.3, anod),
                     (0, -16.2, 0))
    _juntar(tampa, tornear("_dobradica", [(-92, 0), (-92, 1.6), (-10, 1.6), (-10, 0)], None, pos=(0, -15.6, -1),
                           seg=20), aco)
    P["tampa_janela"] = acabar(tampa)

    # alça de mira destacável no trilho, atrás: base que abraça o trilho, torre com as duas orelhas e a abertura
    alca = almofada("alca_mira", [(-170, TOPO_TRILHO - 7), (-130, TOPO_TRILHO - 7), (-130, 41.5), (-170, 41.5)], 12.5,
                    1.2, anod)
    torre = almofada("_torre", [(-161, 40), (-139, 40), (-141, 52), (-144, 64), (-156, 64), (-159, 52)], 9.5, 1.4,
                     None)
    booleano(torre, [caixa("_vao_orelhas", -170, -130, -4.0, 4.0, 58.5, 70),
                     tornear("_abertura", [(-175, 0), (-175, 1.4), (-125, 1.4), (-125, 0)], None, pos=(0, 0, 55),
                             seg=24)])
    booleano(alca, [torre], 'UNION')
    booleano(alca, [caixa("_vao_trilho", -175, -125, -10.8, 10.8, TOPO_TRILHO - 8.6, TOPO_TRILHO + 0.05)])
    acabar(alca, 0.25, 2)
    _juntar(alca, tornear("_regulagem", [(-21, 0), (-21, 4.6), (-20, 5.2), (-12, 5.2), (-12, 0)], None,
                          pos=(-150, 0, 47), eixo='y', seg=28), aco)
    _juntar(alca, tornear("_aperto", [(-19, 0), (-19, 5.5), (-13, 5.5), (-13, 0)], None,
                          pos=(-150, 0, 37.5), eixo='y', seg=28), aco)
    P["alca_mira"] = alca

    # ---- receptor inferior: torre do amortecedor atrás, corpo sob o superior, poço do pente com a boca aberta
    perfil = [(-206, 18, 3), (-190, 18, 1), (-190, -12, 1), (0, -12, 1), (0, -58, 2), (-3, -64, 2), (-76, -66, 2),
              (-78, -57, 2), (-81, -48, 2), (-138, -46, 3), (-182, -44, 4), (-198, -37, 6), (-206, -22, 4)]
    inf = almofada("inferior", perfil, MEIA_INFERIOR, 1.8, anod)
    # o poço do pente é mais largo que o resto
    booleano(inf, [almofada("_poco_fora", [(-78, -14), (0, -14), (0, -58, 2), (-3, -64, 2), (-76, -66, 2)],
                            15.5, 1.8, None)], 'UNION')
    booleano(inf, [caixa("_poco", -69, -7, -13.0, 13.0, -80, -11),
                   tornear("_canal_transportador", [(-218, 0), (-218, 13.2), (0.6, 13.2), (0.6, 0)], None, seg=48),
                   caixa("_fenda_gatilho", -124, -102, -3.6, 3.6, -52, -30),
                   caixa("_vao_cao", -150, -95, -9, 9, -40, -12.5)])
    P["inferior"] = acabar(inf, 0.35, 2)

    # guarda-mato fino de alumínio, da traseira do poço ao cabo
    linha = chaikin([(-80, -56), (-80, -76), (-86, -81.5), (-132, -81.5), (-139, -75), (-140, -48)], 2)
    P["guarda_mato"] = acabar(varrer("guarda_mato", linha, -1, 6.2, 2.1, anod, expoente=3.2), angulo=40)

    # pinos de desmontagem, seletor (esquerda) e retém do ferrolho (esquerda, atrás do poço)
    P["pino_frente"] = pino("pino_frente", -3.5, -17, 2.6, MEIA_INFERIOR + 2.7, aco)
    P["pino_tras"] = pino("pino_tras", -196, -16, 2.6, MEIA_INFERIOR + 0.6, aco)
    seletor = pino("seletor", -150, -26, 4.2, MEIA_INFERIOR + 0.8, aco)
    _juntar(seletor, deslocar(almofada("_alavanca_seletor", [(-151, -22), (-129, -24.5), (-128, -28.5), (-151, -30)],
                                       1.1, 0.4, None), (0, MEIA_INFERIOR + 1.6, 0)), aco)
    P["seletor"] = seletor
    P["retem_ferrolho"] = acabar(deslocar(almofada("retem_ferrolho", [(-88, -6), (-74, -6), (-73, -16), (-79, -30),
                                                                       (-86, -30), (-88, -18)], 1.4, 0.5, aco),
                                          (0, MEIA_INFERIOR + 1.1, 0)), angulo=40)

    # ---- cabo de polímero, inclinado para trás, com o ressalto do dedo médio
    cabo = almofada("punho", [(-139, -43, 3), (-142, -74, 6), (-150, -95, 4), (-146, -104, 3), (-159, -128, 8),
                              (-170, -149, 4), (-232, -134, 5), (-181, -43, 6)], 13.0, 5.0, polimero)
    acabar(cabo, angulo=40)
    uv_caixa(cabo, 1 / 70)
    P["punho"] = cabo

    # ---- tubo do amortecedor (oco, o transportador entra nele no tiro) e a porca castelo
    P["tubo"] = acabar(tornear("tubo", [(-206, 12.8), (-206, 14.5), (-404, 14.5), (-404, 12.8)], aco, seg=56,
                               fechado=True))
    castelo = tornear("castelo", [(-216, 12.9), (-216, 17.2), (-215, 17.8), (-207.5, 17.8), (-207, 17.2),
                                  (-207, 12.9)], aco, seg=56, fechado=True)
    booleano(castelo, [girar(caixa(f"_dente{k}", -217, -212, -2.2, 2.2, 15, 20), (math.radians(90 * k + 45), 0, 0),
                             (0, 0, 0)) for k in range(4)])
    P["castelo"] = acabar(castelo)

    # ---- coronha retrátil de polímero: corpo em volta do tubo, braço inferior inclinado com a janela vazada,
    # trava embaixo e a soleira de borracha
    # três volumes: o corpo arredondado em volta do tubo, a placa larga da soleira e o braço mais fino embaixo
    coronha = prisma_x("coronha", [(-17, 21, 9), (17, 21, 9), (17, -25, 7), (-17, -25, 7)], -412, -228, 2.5,
                       polimero)
    placa = almofada("_placa_coronha", [(-421, 21, 4), (-400, 21, 4), (-400, -104, 4), (-421, -104, 3)], 18.0, 3.0,
                     None)
    braco = almofada("_braco_coronha", [(-404, -10, 3), (-404, -104, 4), (-386, -106, 5), (-338, -52, 6),
                                        (-296, -43, 4), (-236, -40, 3), (-232, -18, 3)], 11.0, 2.5, None)
    booleano(coronha, [placa, braco], 'UNION')
    booleano(coronha, [almofada("_janela_coronha", [(-388, -32, 4), (-388, -84, 4), (-350, -36, 4)], 25, 0.1, None),
                       caixa("_vao_dedo", -330, -250, -20, 20, -38.5, -30),
                       tornear("_canal_tubo", [(-405, 0), (-405, 14.7), (-200, 14.7), (-200, 0)], None, seg=48)])
    acabar(coronha, angulo=40)
    _juntar(coronha, acabar(almofada("_trava_coronha", [(-330, -46), (-288, -42), (-290, -52, 3), (-326, -58, 3)],
                                     5.0, 1.5, None)), polimero)
    uv_caixa(coronha, 1 / 70)
    P["coronha"] = coronha
    soleira = almofada("soleira", [(-430, 23, 3), (-420, 23, 1), (-420, -108, 1), (-430, -108, 3)], 19.0, 3.0,
                       borracha)
    booleano(soleira, [caixa(f"_sulco{k}", -433, -428.6, -25, 25, -100 + 9 * k, -97.5 + 9 * k) for k in range(13)])
    P["soleira"] = acabar(soleira, angulo=40)

    # ---- porca do cano com o anel delta, guarda-mão de trilhos com capas nos lados
    P["anel"] = acabar(tornear("anel", [(0, 0), (0, 20), (1, 27.5), (9, 27.5), (10, 23), (12, 21.5), (14, 22.5),
                                        (16, 21.5), (18, 22.5), (20, 21.5), (22, 22.5), (26.5, 22.5), (26.5, 0)],
                               aco, seg=64))
    nucleo = prisma_x("guarda_mao", [(-21, 27.5, 3), (21, 27.5, 3), (24.5, 24, 3), (24.5, -18, 3), (21, -21.5, 3),
                                     (-21, -21.5, 3), (-24.5, -18, 3), (-24.5, 24, 3)], 26, 192, 1.4, anod)
    booleano(nucleo, [trilho("_trilho_cima", 26, 191, anod), deslocar(trilho("_trilho_baixo", 26, 191, anod,
                                                                            embaixo=True), (0, 0, 6))], 'UNION')
    cortes = [tornear(f"_furo_gm{k}", [(-30, 0), (-30, 4.6), (30, 4.6), (30, 0)], None,
                      pos=(45 + 19.5 * k, 0, -13.0), eixo='y', seg=24) for k in range(8)]
    cortes.append(tornear("_miolo_gm", [(20, 0), (20, 17), (198, 17), (198, 0)], None, seg=48))
    booleano(nucleo, cortes)
    P["guarda_mao"] = acabar(nucleo, 0.3, 2)
    for lado, nome in ((-1, "capa_direita"), (1, "capa_esquerda")):
        capa = almofada(nome, [(32, -8, 3), (186, -8, 3), (186, 20, 3), (32, 20, 3)], 2.6, 1.2, polimero)
        booleano(capa, [caixa(f"_friso{k}{lado}", 36, 182, -6, 6, -2.5 + 7 * k, -1.3 + 7 * k) for k in range(3)])
        deslocar(capa, (0, lado * 26.4, 0))
        acabar(capa, angulo=40)
        uv_caixa(capa, 1 / 70)
        P[nome] = capa

    # ---- cano com o degrau do lança-granadas, quebra-chamas de gaiola (fechado embaixo) e a alma
    cano = tornear("cano", [(0.5, 0), (0.5, 10), (292, 10), (294, 7.7), (316, 7.7), (318, 9.1), (364, 9.1), (364, 0)],
                   aco, seg=48)
    booleano(cano, [tornear("_alma", [(290, 0), (290, 2.85), (370, 2.85), (370, 0)], None, seg=24)])
    P["cano"] = acabar(cano)
    qc = tornear("quebra_chamas", [(362, 0), (362, 8.4), (364, 10.8), (408, 10.8), (411, 9.6), (411, 0)], aco, seg=48)
    cortes = [tornear("_alma_qc", [(360, 0), (360, 2.9), (378, 2.9), (379, 5.4), (414, 5.4), (414, 0)], None, seg=32)]
    for k, ang in enumerate((0, 60, -60, 120, -120)):
        cortes.append(girar(caixa(f"_fenda_qc{k}", 383, 404, -1.35, 1.35, 3.5, 13), (math.radians(ang), 0, 0),
                            (0, 0, 0)))
    for k in range(3):
        cortes.append(tornear(f"_sulco_qc{k}", [(366 + 3 * k, 10.0), (366 + 3 * k, 12), (367.4 + 3 * k, 12),
                                                (367.4 + 3 * k, 10.0)], None, seg=48, fechado=True))
    booleano(qc, cortes)
    P["quebra_chamas"] = acabar(qc)

    # ---- massa de mira: bloco do gás em volta do cano, o triângulo vazado com as duas orelhas, a massa no meio e o
    # ressalto da baioneta embaixo
    massa = almofada("massa_mira", [(192, -19, 2), (249, -19, 2), (249, 13, 2), (192, 13, 2)], 12.0, 1.6, aco)
    tri = almofada("_triangulo", [(197, 11, 3), (246, 11, 3), (236.5, 66, 2.5), (224.5, 66, 2.5)], 8.0, 1.6, None)
    booleano(tri, [almofada("_vazado", [(210, 19.5, 2), (236.5, 19.5, 2), (231, 47, 2), (225.5, 47, 2)], 12, 0.1, None),
                   caixa("_vao_massa", 218, 243, -3.2, 3.2, 47.5, 70)])
    booleano(massa, [tri, caixa("_baioneta", 238, 252, -3.6, 3.6, -27, -17)], 'UNION')
    booleano(massa, [tornear("_furo_massa", [(180, 0), (180, 9.9), (260, 9.9), (260, 0)], None, seg=48)])
    acabar(massa, 0.25, 2)
    _juntar(massa, tornear("_poste", [(44, 0), (44, 1.9), (59.5, 1.9), (61, 1.2), (61, 0)], None, pos=(230.5, 0, 0),
                           eixo='z', seg=16), aco)
    _juntar(massa, tornear("_rebite", [(-9, 2.8), (-9, 4.2), (9, 4.2), (9, 2.8)], None, pos=(214, 0, -26),
                           eixo='y', seg=24, fechado=True), aco)
    P["massa_mira"] = massa

    # ---- peças que mexem: transportador do ferrolho, alavanca em T, gatilho e botão do pente
    fer = tornear("ferrolho", [(-186, 0), (-186, 11.6), (-185, 12.3), (-19, 12.3), (-17, 11), (-15, 0)], aco, seg=48)
    _juntar(fer, tornear("_cabeca", [(-17, 0), (-17, 7.4), (-1.5, 7.4), (-0.5, 6.6), (-0.5, 0)], None, seg=32), aco)
    booleano(fer, [caixa("_alivio", -150, -60, -20, -11.2, -4, 4),
                   caixa("_rebaixo_fer", -170, -35, -20, -10.0, 6.5, 9.5)])
    P["ferrolho"] = acabar(fer)

    alavanca = plano_t("alavanca", [(-55, -4), (-55, 4), (-192, 4), (-193, 17), (-199, 24), (-207.5, 21),
                                    (-207.5, -21), (-199, -24), (-193, -17), (-192, -4)], 23.2, 29.4, 1.2, anod)
    P["alavanca"] = acabar(alavanca, angulo=40)
    P["gatilho"] = acabar(almofada("gatilho", [(-106, -34), (-118, -34), (-119.5, -48), (-117.5, -61), (-112, -72.5),
                                               (-107.5, -73.5, 1.5), (-108.5, -65), (-111, -57), (-111.5, -46)],
                                   3.0, 0.9, aco))
    P["botao_pente"] = acabar(tornear("botao_pente", [(-17.0, 0), (-17.0, 3.3), (-16.2, 4.4), (-11, 4.4), (-11, 0)],
                                      aco, pos=(-82, 0, -27), eixo='y', seg=32))

    pente_e_municao(P, aco_pente, aco)
    clarao(P)
    return P


def pente_e_municao(P, mat, mat_base):
    """Pente reto de 30 de 5,56 (curvo só embaixo, como o de verdade): seções de canto arredondado com as nervuras
    dos lados, base mais larga e o cartucho de cima deitado no topo. A origem fica no centro do fundo."""
    # reto até sair do poço (a boca fica em Z = -66) e só então curvo para a frente
    caminho = [(-38.0, -17.0 - 53.0 * k / 8) for k in range(8)] + bez3((-38, -70), (-38, -112), (-27, -152),
                                                                        (-15, -184), n=22)
    D, W, e = 30.0, 11.4, 6.0
    m = 64

    def anel(c, t, d, w, nervura):
        nf = Vector((-t.y, t.x))
        pts = []
        for k in range(m):
            a = 2 * math.pi * k / m
            n = d * _sgnpow(math.cos(a), 2 / e)
            s = _sgnpow(math.sin(a), 2 / e)
            extra = nervura * (math.exp(-((n + 11) / 3.2) ** 2) + math.exp(-((n - 10) / 3.2) ** 2))
            y = s * (w + extra * abs(s))
            pts.append((c.x + n * nf.x, y, c.y + n * nf.y))
        return pts

    aneis = []
    for i, (x, z) in enumerate(caminho):
        a, b = Vector(caminho[max(i - 1, 0)]), Vector(caminho[min(i + 1, len(caminho) - 1)])
        t = (b - a).normalized()
        aneis.append(anel(Vector((x, z)), t, D, W, 0.9 * _suave(66, 84, -z)))
    t_fim = (Vector(caminho[-1]) - Vector(caminho[-2])).normalized()
    fim = Vector(caminho[-1])
    corpo = _solido_de_aneis("pente", aneis, mat)
    acabar(corpo, angulo=40)
    # base (chapa do fundo) mais larga, perpendicular ao fim da curva
    base = [anel(fim + t_fim * s, t_fim, D + dd, W + dw, 0.0) for s, dd, dw in
            ((-1.0, 2.6, 1.8), (5.0, 2.6, 1.8), (6.0, 1.6, 1.0))]
    _juntar(corpo, acabar(_solido_de_aneis("_base_pente", base, None), angulo=40), mat_base)
    fundo = fim + t_fim * 6.0
    _pivo(corpo, (fundo.x, 0, fundo.y))
    P["pente"] = corpo

    # cartucho 5,56 x 45: estojo de latão com gola, ponta de cobre
    latao = material("latao", (0.80, 0.6, 0.34), metal=1.0, rug=0.3)
    espoleta = material("espoleta", (0.62, 0.6, 0.56), metal=1.0, rug=0.35)
    cobre = material("cobre", (0.72, 0.42, 0.26), metal=1.0, rug=0.32)
    estojo = tornear("estojo_ejetado", [(0, 0), (0, 4.35), (0.3, 4.75), (1.1, 4.75), (1.3, 3.9), (2.6, 3.9),
                                        (3.1, 4.75), (36.0, 4.5), (39.5, 3.1), (44.7, 3.1), (44.7, 0)], latao, seg=32)
    _juntar(estojo, tornear("_espoleta", [(-0.1, 0), (-0.1, 2.2), (0.2, 2.2), (0.2, 0)], None, seg=20), espoleta)
    acabar(estojo)
    bala = acabar(tornear("bala_topo", [(43.5, 0), (43.5, 2.85), (47.5, 2.85), (51, 2.4), (54.5, 1.3), (57.2, 0.35),
                                        (57.4, 0)], cobre, seg=32))
    topo = bpy.data.objects.new("estojo_topo", estojo.data)
    bpy.context.scene.collection.objects.link(topo)
    deitado = Matrix.Translation((-65, 4.0, -18.2))
    topo.matrix_world = deitado
    bala.matrix_world = deitado
    estojo.location = (0.5, 0, 0)          # na câmara, escondido (escala 0) em repouso
    P["estojo_ejetado"], P["estojo_topo"], P["bala_topo"] = estojo, topo, bala


def clarao(P):
    """O clarão da boca: um cone de fogo e uma estrela de cinco pontas (as fendas do quebra-chamas), com a origem na
    boca."""
    mat = material("clarao", (1.0, 0.78, 0.4))
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.22, 1)
    b.inputs["Emission Strength"].default_value = 40.0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=7.0, radius2=0.0, depth=46)
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(23.0, 0, 0))
    pontas = []
    for i in range(10):
        r = 19.0 if i % 2 == 0 else 4.5
        a = 2 * math.pi * i / 10 + math.pi / 2
        pontas.append((r * math.cos(a), r * math.sin(a)))
    frente = [bm.verts.new((2.2, y, z)) for y, z in pontas]
    tras = [bm.verts.new((1.0, y, z)) for y, z in pontas]
    bm.faces.new(frente)
    bm.faces.new(tras)
    for i in range(10):
        j = (i + 1) % 10
        bm.faces.new([frente[i], frente[j], tras[j], tras[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    ob = objeto("clarao", bm, mat)
    ob.location = (X_BOCA + 0.4, 0, 0)
    P["clarao"] = ob


# ---------------------------------------------------------------- animações

# onde cada faixa começa na linha do tempo do .blend (30 qps) e quantos quadros ela tem
REPOUSO_INICIO, REPOUSO_FIM = 1, 2
TIRO_INICIO, TIRO_FIM = 10, 4
REC_INICIO, REC_FIM = 20, 70
EVENTOS = {"tiro": {"disparo": 2},
           "recarregar": {"pente_sai": 14, "troca": 27, "pente_entra": 44, "alavanca": 55}}
RECUO = (-172.0, 0.0, -88.0)           # onde a mão segura (no cabo): o coice gira a arma em volta daqui
PIVO_GATILHO = (-112.0, 0.0, -40.0)
GATILHO_PUXADO = math.radians(12)
INCLINADA = (math.radians(24), math.radians(-7), 0.0)   # a arma deitada para trocar o pente
VISTAS_ANIMACAO = {}


def animar(P):
    """Pivôs, hierarquia e as faixas: repouso (segura tudo), tiro (4 quadros, o mod repete na rajada) e
    recarregar (troca de pente e puxa a alavanca em T)."""
    cena = bpy.context.scene
    cena.render.fps = 30
    _pivo(P["gatilho"], PIVO_GATILHO)
    _pivo(P["tampa_janela"], (-51, -15.6, -1))
    raiz = bpy.data.objects.new("m4a4", None)
    raiz.empty_display_size = 60
    cena.collection.objects.link(raiz)
    raiz.location = RECUO
    bpy.context.view_layer.update()
    for nome, ob in P.items():
        if nome not in ("estojo_topo", "bala_topo"):
            _prender(ob, raiz)
    bpy.context.view_layer.update()
    for nome in ("estojo_topo", "bala_topo"):
        _prender(P[nome], P["pente"])
    bpy.context.view_layer.update()
    P["clarao"].scale = (0, 0, 0)
    P["estojo_ejetado"].scale = (0, 0, 0)

    fer, alav, gat, botao, pente, flash, ejet = (P[n] for n in (
        "ferrolho", "alavanca", "gatilho", "botao_pente", "pente", "clarao", "estojo_ejetado"))
    animados = [raiz, fer, alav, gat, botao, pente, flash, ejet]
    repouso = {ob: {"location": tuple(ob.location), "rotation_euler": tuple(ob.rotation_euler),
                    "scale": tuple(ob.scale)} for ob in animados}
    loc0 = {ob: Vector(repouso[ob]["location"]) for ob in animados}
    atras = loc0[fer] + Vector((-CURSO, 0, 0))
    R = math.radians

    base = Faixa("repouso", REPOUSO_INICIO, REPOUSO_FIM, 'HOLD')
    for ob in animados:
        for prop, valor in repouso[ob].items():
            base.k(ob, prop, 1, valor)
            base.k(ob, prop, REPOUSO_FIM, valor)
    base.gravar(repouso)

    # ---- tiro: 4 quadros, o primeiro e o último em repouso, para o mod repetir a faixa na rajada sem pulo
    t = Faixa("tiro", TIRO_INICIO, TIRO_FIM)
    for q, a in [(1, 0), (2, GATILHO_PUXADO), (3, GATILHO_PUXADO), (4, 0)]:
        t.k(gat, "rotation_euler", q, (0, a, 0), 'LINEAR')
    for q, pos in [(1, loc0[fer]), (2, atras), (3, loc0[fer] + Vector((-CURSO * 0.45, 0, 0))), (4, loc0[fer])]:
        t.k(fer, "location", q, pos, 'LINEAR')
    for q, esc, giro in [(1, 0, 0), (2, 1.0, 0.0), (3, 0.4, 0.6), (4, 0, 0)]:
        t.k(flash, "scale", q, (esc * 1.15, esc, esc), 'CONSTANT')
        t.k(flash, "rotation_euler", q, (giro, 0, 0), 'CONSTANT')
    c = loc0[ejet]
    for q, esc in [(1, 0), (2, 1), (3, 1), (4, 0)]:
        t.k(ejet, "scale", q, (esc, esc, esc), 'CONSTANT')
    na_arma = lambda v: Vector(v) - Vector(RECUO)          # posição na arma -> posição filha da raiz
    for q, pos, rot in [(1, c, (0, 0, 0)), (2, na_arma((-60, -15, 7)), (0, 0, R(-20))),
                        (3, na_arma((-80, -85, 32)), (R(70), R(25), R(-150))), (4, c, (0, 0, 0))]:
        t.k(ejet, "location", q, pos, 'CONSTANT')
        t.k(ejet, "rotation_euler", q, rot, 'CONSTANT')
    for q, giro, desl in [(1, 0, (0, 0, 0)), (2, -2.2, (-4, 0, 0.8)), (3, -1.0, (-2, 0, 0.4)), (4, 0, (0, 0, 0))]:
        t.k(raiz, "rotation_euler", q, (0, R(giro), 0), 'LINEAR')
        t.k(raiz, "location", q, loc0[raiz] + Vector(desl), 'LINEAR')
    t.gravar(repouso)
    VISTAS_ANIMACAO["anim-tiro"] = TIRO_INICIO + 1

    # ---- recarregar: deita a arma, aperta o botão, o pente velho cai reto (o poço é reto), o novo sobe e entra com
    # um tranco, e a mão puxa e solta a alavanca em T (o transportador vai junto e volta batendo)
    r = Faixa("recarregar", REC_INICIO, REC_FIM)
    deitada = loc0[raiz] + Vector((0, 0, 15))
    for q, rot, loc in [(1, (0, 0, 0), loc0[raiz]), (10, INCLINADA, deitada), (43, INCLINADA, deitada),
                        (45, (INCLINADA[0], INCLINADA[1] - R(2.5), 0), deitada + Vector((0, 0, 5))),
                        (48, INCLINADA, deitada), (50, (R(10), R(-12), R(4)), deitada + Vector((-4, 0, 6))),
                        (56, (R(10), R(-12), R(4)), deitada + Vector((-4, 0, 6))),
                        (57, (R(10), R(-13.5), R(4)), deitada + Vector((-6, 0, 7))),
                        (68, (0, 0, 0), loc0[raiz]), (REC_FIM, (0, 0, 0), loc0[raiz])]:
        r.k(raiz, "rotation_euler", q, rot)
        r.k(raiz, "location", q, loc)
    for q, d in [(1, 0), (12, 0), (14, 2.2), (20, 2.2), (23, 0)]:
        r.k(botao, "location", q, loc0[botao] + Vector((0, d, 0)))
    p0 = loc0[pente]
    abaixo = Vector((0, 0, -1))
    for q, pos, interp in [(1, p0, 'CONSTANT'), (14, p0, 'LINEAR'), (17, p0 + abaixo * 35, 'LINEAR'),
                           (24, p0 + abaixo * 240 + Vector((6, 0, 0)), 'CONSTANT'),
                           (29, p0 + abaixo * 170 + Vector((-18, 0, 0)), 'BEZIER'),
                           (38, p0 + abaixo * 58, 'BEZIER'), (42, p0 + abaixo * 14, 'LINEAR'),
                           (44, p0, 'BEZIER'), (REC_FIM, p0, 'CONSTANT')]:
        r.k(pente, "location", q, pos, interp)
    # o pente velho só tomba depois de sair inteiro do poço (no quadro 19 o topo já passou da boca)
    for q, rot, interp in [(1, (0, 0, 0), 'CONSTANT'), (19, (0, 0, 0), 'LINEAR'), (24, (0.25, 0.35, 0.1), 'CONSTANT'),
                           (29, (0, R(-14), 0), 'BEZIER'), (37, (0, 0, 0), 'CONSTANT'), (REC_FIM, (0, 0, 0), 'CONSTANT')]:
        r.k(pente, "rotation_euler", q, rot, interp)
    for q, esc in [(1, 1), (24, 1), (25, 0), (28, 0), (29, 1), (REC_FIM, 1)]:
        r.k(pente, "scale", q, (esc, esc, esc), 'CONSTANT')
    a0 = loc0[alav]
    for q, d, interp in [(1, 0, 'CONSTANT'), (48, 0, 'BEZIER'), (52, -CURSO_ALAVANCA, 'LINEAR'),
                         (55, -CURSO_ALAVANCA, 'LINEAR'), (57, 0, 'CONSTANT'), (REC_FIM, 0, 'CONSTANT')]:
        r.k(alav, "location", q, a0 + Vector((d, 0, 0)), interp)
    for q, pos, interp in [(1, loc0[fer], 'CONSTANT'), (48, loc0[fer], 'BEZIER'), (52, atras, 'LINEAR'),
                           (55, atras, 'LINEAR'), (57, loc0[fer], 'CONSTANT'), (REC_FIM, loc0[fer], 'CONSTANT')]:
        r.k(fer, "location", q, pos, interp)
    r.gravar(repouso)
    VISTAS_ANIMACAO["anim-recarga-pente"] = REC_INICIO + 19

    cena.frame_start, cena.frame_end = 1, REC_INICIO + REC_FIM + 4
    for nome, quadro in [("tiro", TIRO_INICIO), ("recarregar", REC_INICIO)]:
        cena.timeline_markers.new(nome, frame=quadro)
    cena.frame_set(0)
    return raiz


def gravar_animacoes_json(P):
    """O contrato com o mod: onde cada faixa começa na cena, quantos quadros tem e em que quadro (contado do começo
    da faixa, 1 = primeiro) acontece cada evento."""
    dados = {
        "raiz": "m4a4",
        "fps": 30,
        "faixas": {
            "repouso": {"inicio": REPOUSO_INICIO, "quadros": REPOUSO_FIM, "eventos": {}},
            "tiro": {"inicio": TIRO_INICIO, "quadros": TIRO_FIM, "eventos": EVENTOS["tiro"]},
            "recarregar": {"inicio": REC_INICIO, "quadros": REC_FIM, "eventos": EVENTOS["recarregar"]},
        },
        "pecas": ["ferrolho", "alavanca", "gatilho", "pente", "estojo_topo", "bala_topo", "botao_pente", "clarao",
                  "estojo_ejetado"],
    }
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "animacoes.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def conferir_movimento(P):
    """Mede, em momentos das animações, quantos triângulos de cada par de peças se cruzam, comparado com o
    repouso: número que cresce muito é peça atravessando outra."""
    from mathutils.bvhtree import BVHTree
    cena = bpy.context.scene
    pares = [("ferrolho", "superior"), ("ferrolho", "inferior"), ("ferrolho", "tubo"), ("ferrolho", "castelo"),
             ("ferrolho", "coronha"), ("ferrolho", "alavanca"), ("ferrolho", "estojo_topo"),
             ("alavanca", "superior"), ("alavanca", "coronha"), ("alavanca", "alca_mira"), ("alavanca", "castelo"),
             ("alavanca", "inferior"), ("gatilho", "inferior"), ("gatilho", "guarda_mato"), ("pente", "inferior"),
             ("pente", "guarda_mato"), ("pente", "botao_pente"), ("botao_pente", "inferior"),
             ("estojo_ejetado", "superior"), ("estojo_ejetado", "tampa_janela")]
    momentos = [("tiro, ferrolho atrás", TIRO_INICIO + 1), ("tiro, ferrolho voltando", TIRO_INICIO + 2),
                ("recarga, pente saindo", REC_INICIO + 16), ("recarga, pente caindo", REC_INICIO + 19),
                ("recarga, pente entrando", REC_INICIO + 40), ("recarga, pente no lugar", REC_INICIO + 45),
                ("recarga, alavanca atrás", REC_INICIO + 52), ("recarga, alavanca voltando", REC_INICIO + 55)]

    def arvore(ob):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        t = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
        return t

    def contar():
        return {(a, b): len(arvore(P[a]).overlap(arvore(P[b]))) for a, b in pares}

    cena.frame_set(0)
    base = contar()
    linhas = ["", "Animações (30 qps): " + ", ".join(f"{n} {i} a {i + q - 1}" for n, i, q in [
        ("tiro", TIRO_INICIO, TIRO_FIM), ("recarregar", REC_INICIO, REC_FIM)]),
              "Eventos (quadro contado do começo da faixa): " + "; ".join(
                  f"{f}: " + ", ".join(f"{e} {q}" for e, q in ev.items()) for f, ev in EVENTOS.items()),
              "Cruzamentos entre peças (triângulos que se tocam; repouso -> no momento):"]
    for nome, quadro in momentos:
        cena.frame_set(quadro)
        agora = contar()
        mudou = [f"{a} x {b}: {base[(a, b)]} -> {agora[(a, b)]}" for a, b in pares
                 if agora[(a, b)] > base[(a, b)] + 10]
        linhas.append(f"  {nome} (quadro {quadro}): " + ("; ".join(mudou) if mudou else "nada novo"))
    cena.frame_set(0)
    linhas.append("No repouso: " + ("; ".join(f"{a} x {b}: {n}" for (a, b), n in base.items() if n) or "nada"))
    return linhas


def relatorio(P, extra=()):
    linhas = ["M4A4 3D: relatório", ""]
    todos_x, todos_y, todos_z = [], [], []
    tris_total = 0
    abertas = []
    for nome, ob in P.items():
        if ob.matrix_world.to_scale().length < 1e-6:
            continue
        cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        x0, x1 = min(c.x for c in cs), max(c.x for c in cs)
        y0, y1 = min(c.y for c in cs), max(c.y for c in cs)
        z0, z1 = min(c.z for c in cs), max(c.z for c in cs)
        todos_x += [x0, x1]
        todos_y += [y0, y1]
        todos_z += [z0, z1]
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        abertas_ob = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        bm.free()
        tris_total += tris
        if abertas_ob:
            abertas.append(nome)
        linhas.append(f"{nome:<22} {x1 - x0:7.1f} x {y1 - y0:5.1f} x {z1 - z0:6.1f} mm  {tris:6d} triângulos"
                      f"  {'MALHA ABERTA: ' + str(abertas_ob) + ' arestas' if abertas_ob else 'fechada'}")
    linhas += ["", f"Total: {len(P)} peças, {tris_total} triângulos (sem contar as escondidas)",
               f"Comprimento {max(todos_x) - min(todos_x):.0f} mm, altura {max(todos_z) - min(todos_z):.0f} mm, "
               f"largura {max(todos_y) - min(todos_y):.0f} mm",
               "Textura: polimero.png (cabo, coronha e capas do trilho), gerada por código; o resto é cor lisa.",
               "As peças se sobrepõem de propósito nas junções: cada uma é um sólido fechado, não uma malha única."]
    linhas += list(extra)
    if abertas:
        linhas.append("ATENÇÃO, malha aberta em: " + ", ".join(abertas))
    for aviso in AVISOS:
        linhas.append("ATENÇÃO, " + aviso)
    texto = "\n".join(linhas)
    (SAIDA / "relatorio.txt").write_text(texto, encoding="utf-8")
    print(texto)


# ---------------------------------------------------------------- imagens

def renderizar():
    leve = "--leve" in ARGS
    vistas_leves = ("lateral-direita", "tres-quartos", "anim-tiro", "anim-recarga-pente")
    if "--vistas" in ARGS:
        vistas_leves = tuple(ARGS[ARGS.index("--vistas") + 1].split(","))
    rapido = "--rapido" in ARGS or leve
    cena = bpy.context.scene
    if leve:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x40)   # IDLE_PRIORITY_CLASS
        except Exception:
            pass
        cena.render.threads_mode = 'FIXED'
        cena.render.threads = 4
    cena.unit_settings.system = 'METRIC'
    cena.unit_settings.scale_length = 0.001
    cena.render.engine = 'CYCLES'
    cena.cycles.device = 'CPU'
    cena.cycles.samples = 16 if leve else (24 if rapido else 256)
    cena.cycles.use_denoising = True
    cena.cycles.denoiser = 'OPENIMAGEDENOISE'
    cena.render.resolution_x, cena.render.resolution_y = 1920, 1200
    cena.render.resolution_percentage = 50 if rapido else 100
    cena.view_settings.view_transform = 'AgX'
    cena.view_settings.look = 'None'
    # o estúdio do deagle-3d, ampliado para uma arma de 84 cm, estourava a M4 cinza-escura em quase branco
    cena.view_settings.exposure = -1.6

    mundo = bpy.data.worlds.new("mundo")
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.12, 0.125, 1)
    cena.world = mundo

    chao = -560.0
    perfil = [(chao, 0), (chao, 3200)]
    for i in range(1, 13):
        a = math.radians(90 * i / 12)
        perfil.append((chao + 1500 - 1500 * math.cos(a), 3200 + 1500 * math.sin(a)))
    perfil += [(9000, 4700), (9000, 0)]
    fundo = tornear("fundo", perfil, material("fundo", (0.36, 0.355, 0.35), rug=0.8), eixo='z', seg=128)
    acabar(fundo, angulo=60)

    alvo = (-20, 0, -60)
    luz_de_estudio("luz_topo", (0, 0, 1400), alvo, (1000, 700), 5.0)
    luz_de_estudio("luz_principal", (-650, -1500, 760), alvo, (700, 500), 13)
    luz_de_estudio("luz_faixa", (200, -750, 1150), (30, 0, -10), (1300, 100), 30)
    luz_de_estudio("luz_contra", (900, 1080, 300), alvo, (460, 760), 15)
    luz_de_estudio("luz_recorte", (-1260, 870, 140), alvo, (390, 690), 11)
    luz_de_estudio("luz_baixa", (500, -1150, -330), alvo, (600, 200), 4)

    cam_ob = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam_ob.data.clip_start, cam_ob.data.clip_end = 5, 30000
    cena.collection.objects.link(cam_ob)
    cena.camera = cam_ob
    mira = bpy.data.objects.new("mira_camera", None)
    cena.collection.objects.link(mira)
    trava = cam_ob.constraints.new('TRACK_TO')
    trava.target = mira
    trava.track_axis = 'TRACK_NEGATIVE_Z'
    trava.up_axis = 'UP_Y'

    RENDER.mkdir(exist_ok=True)
    for velho in RENDER.glob("*.png"):
        velho.unlink()

    def foto(nome, local, ponto, lente, f=None, foco=None, quadro=0):
        if leve and nome not in vistas_leves:
            return
        cena.frame_set(quadro)
        cam_ob.location = local
        mira.location = ponto
        cam_ob.data.lens = lente
        cam_ob.data.dof.use_dof = f is not None
        if f is not None:
            cam_ob.data.dof.aperture_fstop = f
            cam_ob.data.dof.focus_distance = (Vector(local) - Vector(foco or ponto)).length
        cena.render.filepath = str(RENDER / f"{nome}.png")
        bpy.ops.render.render(write_still=True)

    foto("lateral-direita", (-10, -2350, -50), (-10, 0, -60), 70)
    foto("lateral-esquerda", (-10, 2350, -50), (-10, 0, -60), 70)
    foto("tres-quartos", (720, -1250, 460), (-30, 0, -60), 45, f=11, foco=(0, -15, -30))
    foto("traseira-esquerda", (-900, 950, 420), (-60, 0, -55), 45, f=11, foco=(-120, 10, -30))
    foto("receptor", (-60, -620, 160), (-100, 0, -10), 60, f=5.6, foco=(-60, -15, 5))
    foto("anim-tiro", (-10, -2350, -50), (-10, 0, -60), 70, quadro=VISTAS_ANIMACAO["anim-tiro"])
    foto("anim-recarga-pente", (250, -1500, -80), (-60, 0, -135), 45, quadro=VISTAS_ANIMACAO["anim-recarga-pente"])
    cena.frame_set(0)
    cena.unit_settings.scale_length = 1.0


# ---------------------------------------------------------------- exportação

def exportar(raiz):
    SAIDA.mkdir(exist_ok=True)
    cena = bpy.context.scene
    cena.frame_set(0)
    bpy.context.preferences.filepaths.save_version = 0
    for ob in bpy.data.objects:
        ob.select_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(SAIDA / "m4a4.blend"))
    # OBJ em milímetros, parado e carregado, sem o clarão nem o estojo que voa (escondidos)
    for velho in SAIDA.glob("m4a4.obj*"):
        velho.unlink()
    for ob in bpy.data.objects:
        ob.select_set(ob.type == 'MESH' and ob.name not in ("clarao", "estojo_ejetado"))
    bpy.ops.wm.obj_export(filepath=str(SAIDA / "m4a4.obj"), export_materials=True, path_mode='COPY',
                          forward_axis='NEGATIVE_Z', up_axis='Y', apply_modifiers=True,
                          export_selected_objects=True)
    # GLB em metros, com uma animação por faixa, todas começando no zero
    for ob in bpy.data.objects:
        if ob.animation_data:
            for trilha_nla in ob.animation_data.nla_tracks:
                for faixa in trilha_nla.strips:
                    faixa.frame_start_ui = 1
    escala = bpy.data.objects.new("escala_metros", None)
    cena.collection.objects.link(escala)
    escala.scale = (0.001, 0.001, 0.001)
    raiz.parent = escala
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=str(SAIDA / "m4a4.glb"), export_format='GLB', use_selection=False,
                              export_apply=True, export_animations=True, export_animation_mode='NLA_TRACKS')


def principal():
    P = construir()
    raiz = animar(P)
    gravar_animacoes_json(P)
    relatorio(P, conferir_movimento(P))
    if "--sem-render" not in ARGS:
        renderizar()
        for o in list(bpy.data.objects):
            if o.name.startswith(("luz_", "fundo", "camera", "mira_camera")):
                bpy.data.objects.remove(o)
    exportar(raiz)
    print("pronto")


principal()
