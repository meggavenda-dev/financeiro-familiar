
# services/data_loader.py
import streamlit as st
from services.app_context import get_context
from services.finance_core import novo_id

# Defaults para todos os arquivos usados pelo app.
DEFAULTS = {
    "data/usuarios.json": [
        {"id": "u1", "nome": "Administrador", "perfil": "admin", "ativo": True}
    ],
    "data/contas.json": [
        {
            "id": "c1",
            "nome": "Conta Corrente",
            "tipo": "banco",
            "moeda": "BRL",
            "saldo_inicial": 0.0,
            "ativa": True
        }
    ],
    "data/categorias.json": [
        {"id": "cat1", "nome": "Moradia", "tipo": "despesa"},
        {"id": "cat2", "nome": "Alimentação", "tipo": "despesa"},
        {"id": "cat3", "nome": "Transporte", "tipo": "despesa"},
        {"id": "cat4", "nome": "Educação", "tipo": "despesa"},
        {"id": "cat5", "nome": "Lazer", "tipo": "despesa"},
        {"id": "cat6", "nome": "Salário", "tipo": "receita"},
        {"id": "cat7", "nome": "Freelancer", "tipo": "receita"},
        {"id": "cat8", "nome": "Aluguel Recebido", "tipo": "receita"},
    ],
    # Base única e moderna (CORE)
    "data/transacoes.json": [],
    "data/metas.json": [],
    "data/eventos.json": [],
    # Legado (para migração automática)
    "data/despesas.json": [],
    "data/receitas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    # Opcional (orçamentos por categoria)
    "data/orcamentos.json": [],
}

def _migrar_legado(gh, data_dict: dict) -> None:
    """
    Migra arquivos antigos (despesas/receitas/contas_pagar/contas_receber)
    para o modelo unificado em data/transacoes.json. Executa uma vez
    somente se transacoes.json estiver vazio.
    """
    transacoes = data_dict["data/transacoes.json"]["content"]
    trans_sha = data_dict["data/transacoes.json"]["sha"]

    if isinstance(transacoes, list) and len(transacoes) > 0:
        return

    despesas = data_dict.get("data/despesas.json", {"content": []})["content"]
    receitas = data_dict.get("data/receitas.json", {"content": []})["content"]
    pagar    = data_dict.get("data/contas_pagar.json", {"content": []})["content"]
    receber  = data_dict.get("data/contas_receber.json", {"content": []})["content"]

    txs = []

    # Despesas -> transações "despesa"
    if isinstance(despesas, list):
        for d in despesas:
            if not isinstance(d, dict):
                continue
            txs.append({
                "id": d.get("id") or novo_id("tx"),
                "tipo": "despesa",
                "descricao": d.get("descricao", "Despesa"),
                "valor": float(d.get("valor", 0.0)),
                "data_prevista": d.get("data"),
                "data_efetiva": d.get("paga_em"),
                "conta_id": d.get("conta_id", "c1"),
                "categoria_id": d.get("categoria_id"),
                "excluido": bool(d.get("excluido", False)),
                "parcelamento": d.get("parcelamento"),
                "recorrente": bool(d.get("recorrente", False)),
            })

    # Receitas -> transações "receita"
    if isinstance(receitas, list):
        for r in receitas:
            if not isinstance(r, dict):
                continue
            txs.append({
                "id": r.get("id") or novo_id("tx"),
                "tipo": "receita",
                "descricao": r.get("descricao", "Receita"),
                "valor": float(r.get("valor", 0.0)),
                "data_prevista": r.get("data"),
                "data_efetiva": r.get("recebido_em"),
                "conta_id": r.get("conta_id", "c1"),
                "categoria_id": r.get("categoria_id"),
                "excluido": bool(r.get("excluido", False)),
            })

    # Contas a pagar -> transações "despesa"
    if isinstance(pagar, list):
        for c in pagar:
            if not isinstance(c, dict):
                continue
            txs.append({
                "id": c.get("id") or novo_id("tx"),
                "tipo": "despesa",
                "descricao": c.get("descricao", "Conta a pagar"),
                "valor": float(c.get("valor", 0.0)),
                "data_prevista": c.get("vencimento"),
                "data_efetiva": c.get("paga_em"),
                "conta_id": c.get("conta_id", "c1"),
                "categoria_id": c.get("categoria_id"),
                "excluido": False,
            })

    # Contas a receber -> transações "receita"
    if isinstance(receber, list):
        for c in receber:
            if not isinstance(c, dict):
                continue
            txs.append({
                "id": c.get("id") or novo_id("tx"),
                "tipo": "receita",
                "descricao": c.get("descricao", "Conta a receber"),
                "valor": float(c.get("valor", 0.0)),
                "data_prevista": c.get("previsto"),
                "data_efetiva": c.get("recebido_em"),
                "conta_id": c.get("conta_id", "c1"),
                "categoria_id": c.get("categoria_id"),
                "excluido": False,
            })

    if txs:
        new_sha = gh.put_json(
            "data/transacoes.json",
            txs,
            "Migração automática: unificação (despesas/receitas/pagar/receber -> transacoes.json)",
            sha=trans_sha
        )
        data_dict["data/transacoes.json"] = {"content": txs, "sha": new_sha}
        st.cache_data.clear()

def _sanitizar_lista_de_dicts(gh, path: str, obj, sha: str, commit_msg: str) -> tuple[list, str]:
    """
    Sanitiza conteúdo que deve ser lista de dicts.
    - Se 'obj' não for lista, transforma em lista vazia.
    - Remove itens não-dict.
    - Se houve alteração, comita e retorna (lista_sanitizada, novo_sha).
    """
    if not isinstance(obj, list):
        obj = []

    clean = [x for x in obj if isinstance(x, dict)]
    if len(clean) != len(obj):
        new_sha = gh.put_json(path, clean, commit_msg, sha=sha)
        return clean, new_sha
    return obj, sha

def _garantir_codigos_categorias(gh, categorias: list[dict], sha: str) -> tuple[list[dict], str]:
    """
    Garante que TODAS as categorias tenham 'codigo' numérico (int) e único.
    Se faltar, atribui próximo incremental e persiste.
    """
    changed = False
    existing_codes = [c.get("codigo") for c in categorias if isinstance(c.get("codigo"), int)]
    next_code = (max(existing_codes) + 1) if existing_codes else 1
    seen = set(existing_codes)

    for c in categorias:
        cod = c.get("codigo")
        if not isinstance(cod, int):
            while next_code in seen:
                next_code += 1
            c["codigo"] = next_code
            seen.add(next_code)
            next_code += 1
            changed = True

    if changed:
        new_sha = gh.put_json("data/categorias.json", categorias, "Normaliza categorias: adiciona 'codigo' numérico", sha=sha)
        st.cache_data.clear()
        return categorias, new_sha
    return categorias, sha

def _garantir_codigos_transacoes(gh, transacoes: list[dict], sha: str) -> tuple[list[dict], str]:
    """
    Garante que TODAS as transações tenham 'codigo' numérico (int) e único.
    Se faltar, atribui próximo incremental e persiste.
    """
    changed = False
    existing = [t.get("codigo") for t in transacoes if isinstance(t.get("codigo"), int)]
    next_code = (max(existing) + 1) if existing else 1
    seen = set(existing)

    for t in transacoes:
        cod = t.get("codigo")
        if not isinstance(cod, int):
            while next_code in seen:
                next_code += 1
            t["codigo"] = next_code
            seen.add(next_code)
            next_code += 1
            changed = True

    if changed:
        new_sha = gh.put_json("data/transacoes.json", transacoes, "Normaliza transacoes: adiciona 'codigo' numérico", sha=sha)
        st.cache_data.clear()
        return transacoes, new_sha
    return transacoes, sha

@st.cache_data(ttl=60, show_spinner=False)
def load_all(cache_key: tuple):
    """
    Lê todos os arquivos via GitHubService (no contexto).
    - Migra legado -> transacoes.json (se vazio).
    - Sanitiza transacoes.json e metas.json (remove itens inválidos).
    - Garante 'codigo' numérico em categorias e transações.
    """
    ctx = get_context()
    if not ctx.get("connected"):
        raise RuntimeError("Não conectado ao GitHub. Informe repositório e token na barra lateral.")

    gh = ctx.get("gh")
    if gh is None:
        raise RuntimeError("GitHubService não está inicializado.")

    # Carrega todos os arquivos (create-if-missing)
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}

    # MIGRA LEGADO -> transacoes.json (se estiver vazio)
    _migrar_legado(gh, data)

    # Sanitiza e garante códigos em transacoes.json
    obj, sha = gh.ensure_file("data/transacoes.json", [])
    obj, sha = _sanitizar_lista_de_dicts(
        gh, "data/transacoes.json", obj, sha,
        commit_msg="Sanitiza transacoes.json (remove itens inválidos)"
    )
    obj, sha = _garantir_codigos_transacoes(gh, obj, sha)
    data["data/transacoes.json"] = {"content": obj, "sha": sha}

    # Sanitiza metas.json
    obj_m, sha_m = gh.ensure_file("data/metas.json", [])
    obj_m, sha_m = _sanitizar_lista_de_dicts(
        gh, "data/metas.json", obj_m, sha_m,
        commit_msg="Sanitiza metas.json (remove itens inválidos)"
    )
    data["data/metas.json"] = {"content": obj_m, "sha": sha_m}

    # Garante códigos em categorias
    cats, cats_sha = gh.ensure_file("data/categorias.json", DEFAULTS["data/categorias.json"])
    cats = [c for c in cats if isinstance(c, dict)]
    cats, cats_sha = _garantir_codigos_categorias(gh, cats, cats_sha)
    data["data/categorias.json"] = {"content": cats, "sha": cats_sha}

    return data

# ---------- Funções utilitárias de categorias ----------
def listar_categorias(gh) -> tuple[list, str | None]:
    """Retorna (categorias, sha) garantindo existência do arquivo."""
    cats, sha = gh.ensure_file("data/categorias.json", DEFAULTS["data/categorias.json"])
    cats = [c for c in cats if isinstance(c, dict)]
    return cats, sha

def _proximo_codigo(categorias: list[dict]) -> int:
    """Retorna o próximo 'codigo' disponível (int) com base nas categorias existentes."""
    cods = [c.get("codigo") for c in categorias if isinstance(c.get("codigo"), int)]
    return (max(cods) + 1) if cods else 1

def adicionar_categoria(gh, nome: str, tipo: str = "despesa", codigo: int | None = None) -> dict:
    """Adiciona nova categoria (com 'codigo' numérico) ao data/categorias.json."""
    categorias, sha = listar_categorias(gh)
    if codigo is None:
        codigo = _proximo_codigo(categorias)
    else:
        codigo = int(codigo)
        if any(c.get("codigo") == codigo for c in categorias):
            raise ValueError(f"Código {codigo} já existe.")

    nova = {"id": novo_id("cat"), "codigo": int(codigo), "nome": (nome or "").strip(), "tipo": tipo}
    categorias.append(nova)
    gh.put_json("data/categorias.json", categorias, f"Nova categoria: {nova['nome']} (cod {nova['codigo']})", sha=sha)
    st.cache_data.clear()
    return nova

def atualizar_categoria(gh, categoria_id: str, nome: str | None = None, tipo: str | None = None, codigo: int | None = None) -> bool:
    """Atualiza campos de uma categoria existente (inclui 'codigo' numérico)."""
    categorias, sha = listar_categorias(gh)
    if codigo is not None:
        codigo = int(codigo)
        if any(c.get("id") != categoria_id and c.get("codigo") == codigo for c in categorias):
            return False  # conflito de código

    ok = False
    for c in categorias:
        if c.get("id") == categoria_id:
            if nome is not None:
                c["nome"] = (nome or "").strip()
            if tipo is not None:
                c["tipo"] = tipo
            if codigo is not None:
                c["codigo"] = int(codigo)
            ok = True
            break

    if ok:
        gh.put_json("data/categorias.json", categorias, f"Atualiza categoria: {categoria_id}", sha=sha)
        st.cache_data.clear()
    return ok

def excluir_categoria(gh, categoria_id: str) -> bool:
    """Remove categoria por ID."""
    categorias, sha = listar_categorias(gh)
    novo = [c for c in categorias if c.get("id") != categoria_id]
    if len(novo) == len(categorias):
        return False
    gh.put_json("data/categorias.json", novo, f"Remove categoria: {categoria_id}", sha=sha)
    st.cache_data.clear()
    return True
