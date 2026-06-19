"""Diagnóstico do gerar_base — rode na máquina onde o erro ocorre:
    python diag_base.py
Imprime versões, colunas canônicas (que criam a tabela), colunas lidas da tabela
e colunas do CSV, mostrando exatamente onde o casamento falha.
"""
import sys, glob
sys.path.insert(0, 'sdt')
import pandas as pd
import duckdb
from carregaCabecalhos import carregaCabecalhos

print("VERSOES:", "pandas", pd.__version__, "| duckdb", duckdb.__version__)

headers, _ = carregaCabecalhos()
variaveis = list(headers['MD'].keys())
print("\n[1] headers['MD'].keys() (usado para CRIAR a tabela):")
print("   ", variaveis)

# Recria a tabela canônica exatamente como criar_base faz
con = duckdb.connect(':memory:')
colunas_int = ["year", "day", "min"]
columns_def = ', '.join(
    f"{col} VARCHAR" if col == "acronym" else
    f"{col} TIMESTAMP" if col == "timestamp" else
    f"{col} INT" if col in colunas_int else
    f"{col} FLOAT"
    for col in variaveis)
con.execute(f"CREATE TABLE METEOROLOGICA ({columns_def})")

print("\n[2] colunas lidas DA TABELA:")
desc = con.execute("DESCRIBE METEOROLOGICA").fetchall()
print("    via DESCRIBE fetchall (linha 0):", desc[0] if desc else None)
print("    via DESCRIBE col[0]:", [r[0] for r in desc])
descr = con.execute("SELECT * FROM METEOROLOGICA LIMIT 0").description
print("    via .description d[0]:", [d[0] for d in descr])
print("    tipos de d[0]:", [type(d[0]).__name__ for d in descr][:3])

# Lê um CSV MD real
arquivos = glob.glob('output/sonda-formatados/**/*MD*.csv', recursive=True)
print(f"\n[3] CSVs MD encontrados: {len(arquivos)}")
if arquivos:
    f = arquivos[0]
    nd = pd.read_csv(f, skiprows=[1])
    nd.columns = [str(c).strip().lstrip('﻿') for c in nd.columns]
    print("    arquivo:", f)
    print("    colunas do CSV:", list(nd.columns))

    table_columns = [d[0].lower() for d in
                     con.execute("SELECT * FROM METEOROLOGICA LIMIT 0").description]
    cins = [c for c in nd.columns if c.lower() in table_columns]
    print("\n[4] RESULTADO DO CASAMENTO:")
    print("    table_columns:", table_columns)
    print("    columns_to_insert:", cins, "-> n =", len(cins))
