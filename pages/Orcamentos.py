
# pages/Orcamentos.py
import streamlit as st
import pandas as pd

from services.app_context import init_context, get_context
from services.data_loader import load_all, listar_categorias
from services.permissions import require_admin
from services.utils import fmt_brl
from services.finance_core import novo_id

st.set_page_config(page_title="Orçamentos", page_icon="📊", layout="wide")
st.title("📊 Orçamentos por Categoria")

init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)

gh = ctx.get("gh")
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

orc_map = data.get("data/orcamentos.json", {"content": [], "sha": None})
orcamentos_raw = orc_map.get("content", [])
sha = orc_map.get("sha")

cats, _ = listar_categorias(gh)
cat_map = {c["id"]: c["nome"] for c in cats}
cat_names = list(cat_map.values())
inv_cat = {v: k for k, v in cat_map.items()}

# Sanitização defensiva: garante 'id' e campos
orcamentos: list[dict] = []
changed = False
for o in orcamentos_raw:
    if not isinstance(o, dict):
        changed = True
        continue
    oid = o.get("id") or novo_id("o")
    categoria_id = o.get("categoria_id")
    try:
        limite_mensal = float(o.get("limite_mensal", 0.0))
    except Exception:
        limite_mensal = 0.0
    ativo = bool(o.get("ativo", True))
    orcamentos.append({
        "id": oid,
        "categoria_id": categoria_id,
        "limite_mensal": limite_mensal,
        "ativo": ativo,
    })
    if o.get("id") is None:
        changed = True

if changed:
    new_sha = gh.put_json("data/orcamentos.json", orcamentos, "Sanitiza orcamentos.json (garante 'id' e campos)", sha=sha)
    sha = new_sha
    st.cache_data.clear()

# Nova categoria de orçamento
st.subheader("➕ Cadastrar orçamento")
with st.form("novo_orc"):
    col1, col2 = st.columns([3, 2])
    if not cat_names:
        st.info("Nenhuma categoria encontrada. Cadastre categorias na página **Categorias**.")
    categoria_nome = col1.selectbox("Categoria", options=cat_names if cat_names else ["—"])
    limite = col2.number_input("Limite mensal (R$)", min_value=0.01, step=0.01)
    salvar_btn = st.form_submit_button("Salvar")

    if salvar_btn:
        if categoria_nome not in inv_cat:
            st.error("Categoria inválida. Verifique a lista de categorias.")
        else:
            orcamentos.append({
                "id": novo_id("o"),
                "categoria_id": inv_cat.get(categoria_nome),
                "limite_mensal": float(limite),
                "ativo": True,
            })
            gh.put_json("data/orcamentos.json", orcamentos, "Novo orçamento", sha=sha)
            st.cache_data.clear()
            st.success("Orçamento cadastrado.")
            st.rerun()

st.divider()

# Filtros
st.subheader("🔍 Filtros")
f1, f2 = st.columns([3, 2])
filtro_texto = f1.text_input("Buscar por categoria")
filtro_ativo = f2.selectbox("Status", ["todos", "ativos", "inativos"], index=0)

# Listagem
st.subheader("📚 Orçamentos cadastrados")
if not orcamentos:
    st.info("Nenhum orçamento cadastrado.")
else:
    filtered = []
    for o in orcamentos:
        nome_cat = cat_map.get(o.get("categoria_id"), o.get("categoria_id") or "Sem categoria")
        if filtro_texto:
            s = filtro_texto.strip().lower()
            if s not in str(nome_cat).lower():
                continue
        if filtro_ativo == "ativos" and not bool(o.get("ativo", True)):
            continue
        if filtro_ativo == "inativos" and bool(o.get("ativo", True)):
            continue
        filtered.append(o)

    if not filtered:
        st.info("Nenhum orçamento encontrado com os filtros atuais.")
    else:
        rows = []
        for o in filtered:
            rows.append({
                "ID": o.get("id", "—"),
                "Categoria": cat_map.get(o.get("categoria_id"), o.get("categoria_id") or "Sem categoria"),
                "Limite Mensal": fmt_brl(o.get("limite_mensal", 0.0)),
                "Ativo": bool(o.get("ativo", True)),
            })
        df_view = pd.DataFrame(rows)
        st.dataframe(df_view, use_container_width=True)

        csv_bytes = df_view.to_csv(index=False).encode("utf-8")
        st.download_button("📤 Exportar CSV", data=csv_bytes, file_name="orcamentos.csv", mime="text/csv")

        st.divider()
        st.subheader("✏️ Editar / Excluir")

        for o in filtered:
            oid = o.get("id", novo_id("o"))
            cid = o.get("categoria_id")
            cat_atual = cat_map.get(cid, "—")

            if cat_names and cat_atual in cat_names:
                idx = cat_names.index(cat_atual)
            else:
                idx = 0

            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
            with c1:
                novo_cat = st.selectbox("Categoria", options=cat_names if cat_names else ["—"], index=idx, key=f"orc-cat-{oid}")
            with c2:
                novo_lim = st.number_input("Limite (R$)", min_value=0.01, step=0.01, value=float(o.get("limite_mensal", 0.0)), key=f"orc-lim-{oid}")
            with c3:
                novo_ativo = st.checkbox("Ativo", value=bool(o.get("ativo", True)), key=f"orc-ativo-{oid}")
            with c4:
                if st.button("Salvar", key=f"orc-save-{oid}"):
                    if novo_cat not in inv_cat:
                        st.error("Categoria inválida. Verifique a lista de categorias.")
                    else:
                        o["categoria_id"] = inv_cat.get(novo_cat, cid)
                        o["limite_mensal"] = float(novo_lim)
                        o["ativo"] = bool(novo_ativo)
                        gh.put_json("data/orcamentos.json", orcamentos, f"Atualiza orçamento {oid}", sha=sha)
                        st.cache_data.clear()
                        st.success("Orçamento atualizado.")
                        st.rerun()

                if st.button("Excluir", key=f"orc-del-{oid}"):
                    orcamentos = [x for x in orcamentos if x.get("id") != oid]
                    gh.put_json("data/orcamentos.json", orcamentos, f"Remove orçamento {oid}", sha=sha)
                    st.cache_data.clear()
                    st.success("Orçamento removido.")
                    st.rerun()
