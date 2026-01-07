
# pages/2_Contas.py
import streamlit as st
from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin

st.set_page_config(page_title="Contas", page_icon="📅", layout="wide")
st.title("📅 Contas a Pagar / Receber")

ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)
gh = ctx.gh

data = load_all((ctx.repo_full_name, ctx.branch_name))

pagar_map = data["data/contas_pagar.json"]
receber_map = data["data/contas_receber.json"]

contas_pagar = pagar_map["content"]
contas_receber = receber_map["content"]

# Guardamos os SHAs atuais dos arquivos para atualizar corretamente
sha_map = {
    "data/contas_pagar.json": pagar_map["sha"],
    "data/contas_receber.json": receber_map["sha"],
}

for label, lista, path in [
    ("A Pagar", contas_pagar, "data/contas_pagar.json"),
    ("A Receber", contas_receber, "data/contas_receber.json"),
]:
    st.subheader(label)
    if not lista:
        st.info(f"Nenhuma conta {label.lower()}.")
        continue

    for c in lista:
        col1, col2, col3 = st.columns([4, 2, 3])
        col1.write(f"**{c.get('descricao', '—')}**")
        col2.write(f"R$ {float(c.get('valor', 0.0)):.2f}")
        novo = col3.selectbox(
            "Status",
            ["em_aberto", "paga", "atrasada"],
            index=["em_aberto", "paga", "atrasada"].index(c.get("status", "em_aberto")),
            key=c["id"],
        )
        if novo != c.get("status", "em_aberto"):
            c["status"] = novo
            # 👉 PASSAMOS O SHA correspondente ao arquivo
            new_sha = gh.put_json(path, lista, f"Update status: {c['descricao']} -> {novo}", sha=sha_map[path])
            # Opcional: atualiza o sha no runtime (se houver múltiplas alterações sem rerun)
            sha_map[path] = new_sha

            st.success(f"Status atualizado: {c['descricao']} → {novo}")
            st.cache_data.clear()
            st.rerun()
