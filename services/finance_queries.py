
"""
Consultas financeiras padronizadas.

Este módulo centraliza:
- normalização de datas
- filtro de exclusão (soft-delete)
- definição de data de referência
- consultas de despesas/receitas por período

✅ Evita bugs de despesas "sumindo"
✅ Garante consistência entre Dashboard, Lançamentos e Gráficos
"""

from datetime import date
import pandas as pd


# ---------------------------------------------------------
# Normalização base (DEVE ser chamada uma única vez)
# ---------------------------------------------------------
def preparar_transacoes_df(transacoes: list[dict]) -> pd.DataFrame:
    """
    Constrói um DataFrame seguro e consistente a partir das transações.

    Regras:
    - remove registros excluídos
    - converte campos de data corretamente
    - cria coluna `data_ref` (efetiva > prevista)
    """
    if not transacoes:
        return pd.DataFrame()

    df = pd.DataFrame(transacoes)

    # Campos obrigatórios defensivos
    for col in ("valor", "excluido"):
        if col not in df:
            df[col] = 0 if col == "valor" else False

    # Tipos
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["excluido"] = df["excluido"].fillna(False)

    # Datas
    df["data_prevista"] = pd.to_datetime(df.get("data_prevista"), errors="coerce").dt.date
    df["data_efetiva"] = pd.to_datetime(df.get("data_efetiva"), errors="coerce").dt.date

    # Remove soft-deletes
    df = df[df["excluido"] == False]

    # Data de referência única
    df["data_ref"] = df["data_efetiva"].combine_first(df["data_prevista"])

    return df.reset_index(drop=True)


# ---------------------------------------------------------
# KPIs do mês
# ---------------------------------------------------------
def kpis_mes(df: pd.DataFrame, inicio: date, fim: date) -> dict:
    """
    Calcula KPIs financeiros do período.

    Retorna:
    {
        rec_real,
        des_real,
        rec_prev,
        des_prev,
        saldo_real,
        saldo_prev
    }
    """
    if df.empty:
        return {
            "rec_real": 0.0,
            "des_real": 0.0,
            "rec_prev": 0.0,
            "des_prev": 0.0,
            "saldo_real": 0.0,
            "saldo_prev": 0.0,
        }

    periodo = df[df["data_ref"].between(inicio, fim)]

    realizadas = periodo[periodo["data_efetiva"].notna()]
    previstas = periodo[periodo["data_efetiva"].isna()]

    rec_real = realizadas.query("tipo == 'receita'")["valor"].sum()
    des_real = realizadas.query("tipo == 'despesa'")["valor"].sum()

    rec_prev = previstas.query("tipo == 'receita'")["valor"].sum()
    des_prev = previstas.query("tipo == 'despesa'")["valor"].sum()

    return {
        "rec_real": rec_real,
        "des_real": des_real,
        "rec_prev": rec_prev,
        "des_prev": des_prev,
        "saldo_real": rec_real - des_real,
        "saldo_prev": rec_prev - des_prev,
    }


# ---------------------------------------------------------
# Despesas por categoria
# ---------------------------------------------------------
def despesas_por_categoria(
    df: pd.DataFrame,
    inicio: date,
    fim: date,
    cat_map: dict[str, str],
) -> pd.Series:
    """
    Agrupa despesas do período por categoria.

    Retorna uma Series:
        Categoria -> soma dos valores
    """
    if df.empty:
        return pd.Series(dtype=float)

    despesas = df[
        (df["tipo"] == "despesa")
        & (df["data_ref"].between(inicio, fim))
    ].copy()

    if despesas.empty:
        return pd.Series(dtype=float)

    despesas["Categoria"] = (
        despesas["categoria_id"]
        .map(cat_map)
        .fillna("Sem categoria")
    )

    return (
        despesas
        .groupby("Categoria")["valor"]
        .sum()
        .sort_values(ascending=False)
    )


# ---------------------------------------------------------
# Série de saldo acumulado
# ---------------------------------------------------------
def serie_saldo_acumulado(
    df: pd.DataFrame,
    inicio: date,
    fim: date,
    incluir_previstas: bool = False,
) -> pd.Series:
    """
    Gera série temporal de saldo acumulado.
    """
    if df.empty:
        return pd.Series(dtype=float)

    base = df.copy()

    if not incluir_previstas:
        base = base[base["data_efetiva"].notna()]

    base = base[base["data_ref"].between(inicio, fim)]

    if base.empty:
        return pd.Series(dtype=float)

    base["signed"] = base.apply(
        lambda r: r["valor"] if r["tipo"] == "receita" else -r["valor"],
        axis=1,
    )

    return (
        base
        .groupby("data_ref")["signed"]
        .sum()
        .sort_index()
        .cumsum()
    )

