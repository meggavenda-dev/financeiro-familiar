
# services/metas_engine.py
from datetime import datetime

def aplicar_regra_receita_para_metas(transacao_receita_paga: dict, metas: list) -> int:
    """Distribui parte da receita paga para metas ativas conforme regra."""
    if transacao_receita_paga.get("tipo") != "receita":
        return 0
    if not transacao_receita_paga.get("data_efetiva"):
        return 0

    valor = float(transacao_receita_paga.get("valor", 0.0))
    atualizadas = 0
    for m in metas:
        if not m.get("ativa", True):
            continue
        regra = m.get("regra") or {}
        if regra.get("tipo") == "percentual_receita":
            pct = float(regra.get("percentual", 0.0))
            aporte = round(valor * pct, 2)
            m["valor_atual"] = round(float(m.get("valor_atual", 0.0)) + aporte, 2)
            m["atualizado_em"] = datetime.now().isoformat()
            atualizadas += 1
    return atualizadas
