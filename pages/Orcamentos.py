
# pages/Orcamentos.py
import streamlit as st
import pandas as pd

# --------------------------------------------------
# Imports internos
# --------------------------------------------------
from services.app_context import init_context, get_context
from services.data_loader import load_all, listar_categorias
from services.permissions import require_admin
from services.utils import fmt_brl, key_for
from services.finance_core import novo_id
from services.layout import responsive_columns, is_mobile
from services.ui import section, card

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Orçamentos",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
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
# Sanitização defensiva
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
section("➕ Novo orçamento")

with st.form("novo_orcamento"):
    cols = responsive_columns(desktop=3, mobile=1)

    categoria = cols[0].selectbox(
        "Categoria",
        options=cat_names if cat_names else ["—"],
    )

    limite = cols[1].number_input(
        "Limite mensal (R$)",
        min_value=0.01,
        step=0.01,
    )

    ativo = cols[2].checkbox("Ativo", value=True)

    salvar = st.form_submit_button("Salvar")

if salvar:
    if categoria not in inv_cat:
        st.error("Categoria inválida.")
    else:
        orcamentos.append({
            "id": novo_id("o"),
            "categoria_id": inv_cat[categoria],
            "limite_mensal": float(limite),
            "ativo": bool(ativo),
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
section("🔍 Filtros")

cols_f = responsive_columns(desktop=2, mobile=1)

filtro_texto = cols_f[0].text_input("Buscar por categoria")
filtro_status = cols_f[1].selectbox(
    "Status",
    ["todos", "ativos", "inativos"],
)

# --------------------------------------------------
# Listagem
# --------------------------------------------------
section("📚 Orçamentos cadastrados")

def ativo(o):
    return bool(o.get("ativo", True))

filtrados = []
for o in orcamentos:
    nome_cat = cat_map.get(o.get("categoria_id"), "Sem categoria")

    if filtro_texto and filtro_texto.lower() not in nome_cat.lower():
        continue

    if filtro_status == "ativos" and not ativo(o):
        continue

    if filtro_status == "inativos" and ativo(o):
        continue

    filtrados.append(o)

if not filtrados:
    st.info("Nenhum orçamento encontrado.")
else:
    # -------------------------------
    # MOBILE
    # -------------------------------
    if is_mobile():
        for o in filtrados:
            oid = o["id"]
            nome_cat = cat_map.get(o["categoria_id"], "Sem categoria")

            card(
                nome_cat,
                [
                    f"Limite: {fmt_brl(o['limite_mensal'])}",
                    f"Status: {'Ativo' if ativo(o) else 'Inativo'}",
                ],
            )

            cols = responsive_columns(desktop=3, mobile=1)

            novo_lim = cols[0].number_input(
                "Limite (R$)",
                min_value=0.01,
                step=0.01,
                value=float(o["limite_mensal"]),
                key=key_for("lim", oid),
            )

            novo_ativo = cols[1].checkbox(
                "Ativo",
                value=ativo(o),
                key=key_for("ativo", oid),
            )

            if cols[2].button("💾 Salvar", key=key_for("save", oid)):
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

            if st.button("🗑️ Excluir", key=key_for("del", oid)):
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

            st.divider()

    # -------------------------------
    # DESKTOP
    # -------------------------------
    else:
        rows = [{
            "ID": o["id"],
            "Categoria": cat_map.get(o["categoria_id"], "Sem categoria"),
            "Limite Mensal": fmt_brl(o["limite_mensal"]),
            "Ativo": ativo(o),
        } for o in filtrados]

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
        section("✏️ Editar / Excluir")

        for o in filtrados:
            oid = o["id"]
            nome_cat = cat_map.get(o["categoria_id"], "—")
            idx = cat_names.index(nome_cat) if nome_cat in cat_names else 0

            cols = responsive_columns(desktop=4)

            novo_cat = cols[0].selectbox(
                "Categoria",
                options=cat_names,
                index=idx,
                key=key_for("cat-d", oid),
            )

            novo_lim = cols[1].number_input(
                "Limite (R$)",
                min_value=0.01,
                step=0.01,
                value=float(o["limite_mensal"]),
                key=key_for("lim-d", oid),
            )

            novo_ativo = cols[2].checkbox(
                "Ativo",
                value=ativo(o),
                key=key_for("ativo-d", oid),
            )

            if cols[3].button("Salvar", key=key_for("save-d", oid)):
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

            if st.button("Excluir", key=key_for("del-d", oid)):
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
