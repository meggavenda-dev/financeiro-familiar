# services/data_loader.py
import streamlit as st
from services.app_context import get_context
from services.finance_core import novo_id

# Defaults para todos os arquivos usados pelo app.
# Inclui arquivos "legados" para permitir migração automática.
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
    # Opcional (se você usar orçamento por categoria)
    "data/orcamentos.json": [],
}


def _migrar_legado(gh, data_dict: dict) -> None:
    """
    Migra seus arquivos antigos (despesas/receitas/contas_pagar/contas_receber)
    para o modelo unificado em data/transacoes.json. Executa uma vez
    somente se transacoes.json estiver vazio.
    """
    transacoes = data_dict["data/transacoes.json"]["content"]
    trans_sha = data_dict["data/transacoes.json"]["sha"]

    # Se já há transações, não migrar
    if isinstance(transacoes, list) and len(transacoes) > 0:
        return

    # Coleta conteúdo legado
    despesas = data_dict.get("data/despesas.json", {"content": []})["content"]
    receitas = data_dict.get("data/receitas.json", {"content": []})["content"]
    pagar = data_dict.get("data/contas_pagar.json", {"content": []})["content"]
    receber = data_dict.get("data/contas_receber.json", {"content": []})["content"]

    txs = []

    # Despesas antigas -> transações tipo "despesa"
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

    # Receitas antigas -> transações tipo "receita"
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

    # Contas a pagar -> transações tipo "despesa" futuras
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

    # Contas a receber -> transações tipo "receita" futuras
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

    # Se geramos transações, comitar
    if txs:
        new_sha = gh.put_json(
            "data/transacoes.json",
            txs,
            "Migração automática: unificação (despesas/receitas/pagar/receber -> transacoes.json)",
            sha=trans_sha
        )
        data_dict["data/transacoes.json"] = {"content": txs, "sha": new_sha}
        # Limpa cache para refletir estado novo
        st.cache_data.clear()


def _sanitizar_lista_de_dicts(gh, path: str, obj, sha: str, commit_msg: str) -> tuple[list, str]:
    """
    Sanitiza um conteúdo de arquivo JSON que deve ser uma lista de dicts.
    - Se 'obj' não for lista, transforma em lista vazia.
    - Remove qualquer item que não seja dict.
    - Se houve alteração, comita e retorna (lista_sanitizada, novo_sha).
    - Caso contrário, retorna (obj_original, sha_original).
    """
    if not isinstance(obj, list):
        obj = []

    clean = [x for x in obj if isinstance(x, dict)]
    if len(clean) != len(obj):
        new_sha = gh.put_json(path, clean, commit_msg, sha=sha)
        return clean, new_sha
    return obj, sha


@st.cache_data(ttl=60, show_spinner=False)
def load_all(cache_key: tuple):
    """
    Lê todos os arquivos via GitHubService presente no contexto.
    Usa (repo_full_name, branch_name) como chave do cache, evitando erro de hash.
    - Executa migração automática do legado para transações unificadas.
    - Sanitiza transacoes.json e metas.json (remove itens inválidos que não sejam dict).
    """
    ctx = get_context()

    # ctx é um dict (st.session_state). Use .get ou indexação por chave.
    if not ctx.get("connected"):
        raise RuntimeError("Não conectado ao GitHub. Informe repositório e token na barra lateral.")

    gh = ctx.get("gh")
    if gh is None:
        raise RuntimeError("GitHubService não está inicializado.")

    # Carrega todos os arquivos assegurando existência (create-if-missing)
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}

    # MIGRA LEGADO -> transacoes.json (se estiver vazio)
    _migrar_legado(gh, data)

    # RECARREGA transacoes.json (após migração) e sanitiza
    obj, sha = gh.ensure_file("data/transacoes.json", [])
    obj, sha = _sanitizar_lista_de_dicts(
        gh, "data/transacoes.json", obj, sha,
        commit_msg="Sanitiza transacoes.json (remove itens inválidos)"
    )
    data["data/transacoes.json"] = {"content": obj, "sha": sha}

    # Sanitiza metas.json também (evita AttributeError em páginas)
    obj_m, sha_m = gh.ensure_file("data/metas.json", [])
    obj_m, sha_m = _sanitizar_lista_de_dicts(
        gh, "data/metas.json", obj_m, sha_m,
        commit_msg="Sanitiza metas.json (remove itens inválidos)"
    )
    data["data/metas.json"] = {"content": obj_m, "sha": sha_m}

    return data


# ---------- Funções utilitárias de categorias ----------

def listar_categorias(gh) -> tuple[list, str | None]:
    """
    Retorna (categorias, sha) garantindo existência do arquivo.
    """
    cats, sha = gh.ensure_file("data/categorias.json", DEFAULTS["data/categorias.json"])
    # Sanitiza: apenas dicts
    cats = [c for c in cats if isinstance(c, dict)]
    return cats, sha


def adicionar_categoria(gh, nome: str, tipo: str = "despesa") -> dict:
    """
    Adiciona uma nova categoria ao data/categorias.json.
    """
    categorias, sha = listar_categorias(gh)
    nova = {"id": novo_id("cat"), "nome": (nome or "").strip(), "tipo": tipo}
    categorias.append(nova)
    new_sha = gh.put_json("data/categorias.json", categorias, f"Nova categoria: {nova['nome']}", sha=sha)
    st.cache_data.clear()
    return nova


def atualizar_categoria(gh, categoria_id: str, nome: str | None = None, tipo: str | None = None) -> bool:
    """
    Atualiza campos de uma categoria existente.
    """
    categorias, sha = listar_categorias(gh)
    ok = False
    for c in categorias:
        if c.get("id") == categoria_id:
            if nome is not None:
                c["nome"] = (nome or "").strip()
            if tipo is not None:
                c["tipo"] = tipo
            ok = True
            break
    if ok:
        gh.put_json("data/categorias.json", categorias, f"Atualiza categoria: {categoria_id}", sha=sha)
        st.cache_data.clear()
    return ok


def excluir_categoria(gh, categoria_id: str) -> bool:
    """
    Remove categoria por ID. (Hard delete; se preferir, marque como 'excluido')
    """
    categorias, sha = listar_categorias(gh)
    novo = [c for c in categorias if c.get("id") != categoria_id]
    if len(novo) == len(categorias):
        return False
    gh.put_json("data/categorias.json", novo, f"Remove categoria: {categoria_id}", sha=sha)
    st.cache_data.clear()
    return True
