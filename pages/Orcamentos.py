
# pages/Orcamentos.py
import streamlit as st
import pandas as pd

from services.app_context import init_context, get_context
from services.data_loader import load_all, listar_categorias
from services.permissions import require_admin
from services.utils import fmt_brl, key_for   # CHANGE
from services.finance_core import novo_id

st.set_page_config(
    page_title="Orçamentos",
    page_icon="📊",
    layout="wide",
)
st.title("📊 Orçamentos por Categoria")

# --------------------------------------------------
# Contexto / Permissões
# --------------------------------------------------
init_context()
ctx = get_context()

if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

require_admin(ctx)

gh = ctx.get("gh")
usuario = ctx.get("usuario_id", "u1")

# --------------------------------------------------
# Carregamento
# --------------------------------------------------
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

orc_map = data.get("data/orcamentos.json", {"content": [], "sha": None})
orcamentos = [o for o in orc_map.get("content", []) if isinstance(o, dict)]
sha = orc_map.get("sha")

cats, _ = listar_categorias(gh)
cat_map = {c["id"]: c["nome"] for c in cats}
inv_cat = {v: k for k, v in cat_map.items()}
cat_names = list(inv_cat.keys())

# --------------------------------------------------
# Sanitização defensiva (sem commit se não mudou)
# --------------------------------------------------
changed = False
clean = []

for o in orcamentos:
    oid = o.get("id") or novo_id("o")
    try:
        limite = float(o.get("limite_mensal", 0))
    except Exception:
        limite = 0.0

    item = {
        "id": oid,
        "categoria_id": o.get("categoria_id"),
        "limite_mensal": limite,
        "ativo": bool(o.get("ativo", True)),
    }

    if o.get("id") is None:
        changed = True

    clean.append(item)

if changed:
    sha = gh.put_json(
        "data/orcamentos.json",
        clean,
        f"[{usuario}] Sanitiza orcamentos.json",
        sha=sha,
    )
    st.cache_data.clear()
    orcamentos = clean

# --------------------------------------------------
# Novo orçamento
# --------------------------------------------------
st.subheader("➕ Cadastrar orçamento")

with st.form("novo_orc"):
    col1, col2 = st.columns([3, 2])

    categoria = col1.selectbox(
        "Categoria",
        options=cat_names if cat_names else ["—"],
    )

    limite = col2.number_input(
        "Limite mensal (R$)",
        min_value=0.01,
        step=0.01,
    )

    salvar = st.form_submit_button("Salvar")

    if salvar:
        if categoria not in inv_cat:
            st.error("Categoria inválida.")
        else:
            orcamentos.append({
                "id": novo_id("o"),
                "categoria_id": inv_cat[categoria],
                "limite_mensal": float(limite),
                "ativo": True,
            })
            gh.put_json(
                "data/orcamentos.json",
                orcamentos,
                f"[{usuario}] Novo orçamento: {categoria}",
                sha=sha,
            )
            st.cache_data.clear()
            st.success("Orçamento cadastrado.")
            st.rerun()

st.divider()

# --------------------------------------------------
# Filtros
# --------------------------------------------------
st.subheader("🔍 Filtros")

f1, f2 = st.columns([3, 2])
filtro_texto = f1.text_input("Buscar por categoria")
filtro_status = f2.selectbox("Status", ["todos", "ativos", "inativos"])

# --------------------------------------------------
# Listagem
# --------------------------------------------------
st.subheader("📚 Orçamentos cadastrados")

def ativo(o): 
    return bool(o.get("ativo", True))

filtered = []
for o in orcamentos:
    nome = cat_map.get(o.get("categoria_id"), "Sem categoria")
    if filtro_texto and filtro_texto.lower() not in nome.lower():
        continue
    if filtro_status == "ativos" and not ativo(o):
        continue
    if filtro_status == "inativos" and ativo(o):
        continue
    filtered.append(o)

if not filtered:
    st.info("Nenhum orçamento encontrado.")
else:
    rows = [{
        "ID": o["id"],
        "Categoria": cat_map.get(o["categoria_id"], "Sem categoria"),
        "Limite Mensal": fmt_brl(o["limite_mensal"]),
        "Ativo": ativo(o),
    } for o in filtered]

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📤 Exportar CSV",
        data=csv,
        file_name="orcamentos.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("✏️ Editar / Excluir")

    for o in filtered:
        oid = o["id"]
        nome_cat = cat_map.get(o["categoria_id"], "—")
        idx = cat_names.index(nome_cat) if nome_cat in cat_names else 0

        c1, c2, c3, c4 = st.columns([4, 2, 2, 2])

        with c1:
            novo_cat = st.selectbox(
                "Categoria",
                options=cat_names,
                index=idx,
                key=key_for("cat", oid),
            )

        with c2:
            novo_lim = st.number_input(
                "Limite (R$)",
                min_value=0.01,
                step=0.01,
                value=float(o["limite_mensal"]),
                key=key_for("lim", oid),
            )

        with c3:
            novo_ativo = st.checkbox(
                "Ativo",
                value=ativo(o),
                key=key_for("ativo", oid),
            )

        with c4:
            if st.button("Salvar", key=key_for("save", oid)):
                o["categoria_id"] = inv_cat.get(novo_cat)
                o["limite_mensal"] = float(novo_lim)
                o["ativo"] = bool(novo_ativo)
                gh.put_json(
                    "data/orcamentos.json",
                    orcamentos,
                    f"[{usuario}] Atualiza orçamento {oid}",
                    sha=sha,
                )
                st.cache_data.clear()
                st.success("Orçamento atualizado.")
                st.rerun()

            if st.button("Excluir", key=key_for("del", oid)):
                orcamentos = [x for x in orcamentos if x.get("id") != oid]
                gh.put_json(
                    "data/orcamentos.json",
                    orcamentos,
                    f"[{usuario}] Remove orçamento {oid}",
                    sha=sha,
                )
                st.cache_data.clear()
                st.success("Orçamento removido.")
                st.rerun()
