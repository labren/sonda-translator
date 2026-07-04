#!/usr/bin/env python3
"""
Merge de dois arquivos Parquet SEM sobrescrever dados existentes — v2.

Diferença para a v1: em vez de FULL OUTER JOIN (que MULTIPLICA linhas quando
a chave se repete e estoura a memória), esta versão empilha os dois arquivos
(UNION ALL BY NAME) e agrega por chave:

    arg_min(coluna, prioridade) FILTER (WHERE coluna IS NOT NULL)

Ou seja, para cada chave e cada coluna, fica o primeiro valor NÃO NULO
seguindo a prioridade (novo antes do antigo, ou o inverso). Valores
existentes nunca são substituídos por valores do outro arquivo — o outro
arquivo só preenche lacunas (NULLs e linhas que faltam).

IMPORTANTE sobre chaves duplicadas: linhas que tiverem EXATAMENTE a mesma
chave são colapsadas em uma só (mantendo os valores não nulos preferidos).
Se as repetições de timestamp forem na verdade registros de estações ou
sensores diferentes, inclua essa coluna em KEY_COLS, por exemplo:
    KEY_COLS = ["id_estacao", "timestamp"]
Rode primeiro com SOMENTE_DIAGNOSTICO = True para ver amostras das
duplicatas e decidir.

Uso:
  pip install duckdb
  python merge_solarimetrica.py
"""

import os
import sys

import duckdb

# ========================= CONFIGURAÇÃO =========================
ARQUIVO_NOVO   = "Solarimetrica_new.parquet"
ARQUIVO_ANTIGO = "Solarimetrica_old.parquet"
ARQUIVO_SAIDA  = "/media/helvecioneto/Barracuda/Solarimetrica_merged.parquet"

# Coluna(s) que identificam unicamente cada linha. Pode ser composta,
# ex.: ["id_estacao", "timestamp"]. Deixe vazio ( [] ) para só listar
# as colunas dos arquivos e sair.
KEY_COLS = ["acronym", "timestamp"]

# Quem "vence" quando ambos os arquivos têm valor preenchido na mesma célula:
#   "new" -> mantém o valor do novo; o antigo só preenche NULLs
#   "old" -> mantém o valor do antigo; o novo só preenche NULLs
PRIORIDADE = "new"

# True -> não gera nada: só mostra colunas, conta duplicatas e imprime
# amostras de linhas com chave repetida, para você conferir a chave certa.
SOMENTE_DIAGNOSTICO = False

ORDENAR_POR_CHAVE = True          # ordena a saída pela(s) chave(s).
                                  # É a operação que MAIS usa disco temporário.
                                  # Se faltar espaço, mude para False.
LIMITE_MEMORIA    = "4GB"         # ~50-70% da RAM LIVRE da máquina
THREADS           = 2             # menos threads = menos pico de memória
DIR_TEMP          = "/media/helvecioneto/Barracuda/duckdb_tmp"  # disco com espaço
COMPRESSAO        = "ZSTD"        # ZSTD comprime melhor; SNAPPY é mais rápido
# ================================================================


def qi(ident: str) -> str:
    """Quota um identificador SQL (suporta espaço/acento no nome da coluna)."""
    return '"' + ident.replace('"', '""') + '"'


def qp(path: str) -> str:
    """Escapa um caminho de arquivo para uso dentro de string SQL."""
    return path.replace("'", "''")


def main() -> None:
    for f in (ARQUIVO_NOVO, ARQUIVO_ANTIGO):
        if not os.path.exists(f):
            sys.exit(f"ERRO: arquivo não encontrado: {f}")

    if not SOMENTE_DIAGNOSTICO and os.path.exists(ARQUIVO_SAIDA):
        sys.exit(f"ERRO: '{ARQUIVO_SAIDA}' já existe. "
                 "Renomeie ou apague antes de rodar (nada é sobrescrito).")

    if PRIORIDADE not in ("new", "old"):
        sys.exit("ERRO: PRIORIDADE deve ser 'new' ou 'old'.")

    os.makedirs(DIR_TEMP, exist_ok=True)

    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{LIMITE_MEMORIA}'")
    con.execute(f"SET temp_directory = '{qp(DIR_TEMP)}'")
    con.execute("SET preserve_insertion_order = false")
    con.execute(f"SET threads = {int(THREADS)}")

    cols_new = [r[0] for r in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{qp(ARQUIVO_NOVO)}')").fetchall()]
    cols_old = [r[0] for r in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{qp(ARQUIVO_ANTIGO)}')").fetchall()]

    print(f"Colunas do novo:   {cols_new}")
    print(f"Colunas do antigo: {cols_old}\n")

    if not KEY_COLS:
        sys.exit("Defina KEY_COLS no topo do script com base nas colunas acima.")

    faltando = [k for k in KEY_COLS if k not in cols_new or k not in cols_old]
    if faltando:
        sys.exit(f"ERRO: coluna(s)-chave não encontrada(s) nos dois arquivos: {faltando}")

    keys_sql = ", ".join(qi(k) for k in KEY_COLS)

    # ---- Diagnóstico de duplicatas -----------------------------------
    for nome, arq in (("novo", ARQUIVO_NOVO), ("antigo", ARQUIVO_ANTIGO)):
        dup = con.execute(
            f"SELECT count(*) FROM (SELECT 1 FROM read_parquet('{qp(arq)}') "
            f"GROUP BY {keys_sql} HAVING count(*) > 1)").fetchone()[0]
        if dup:
            print(f"Arquivo {nome}: {dup:,} chave(s) repetida(s) -> essas linhas "
                  "serão colapsadas em uma por chave, mantendo os valores não nulos.")
            if SOMENTE_DIAGNOSTICO:
                print(f"Amostra de linhas com chave repetida no arquivo {nome}:")
                con.sql(f"""
                    WITH dups AS (
                        SELECT {keys_sql}
                        FROM read_parquet('{qp(arq)}')
                        GROUP BY {keys_sql} HAVING count(*) > 1
                        LIMIT 3
                    )
                    SELECT t.*
                    FROM read_parquet('{qp(arq)}') AS t
                    JOIN dups USING ({keys_sql})
                    ORDER BY {keys_sql}
                """).show(max_rows=40)

    if SOMENTE_DIAGNOSTICO:
        print("Diagnóstico concluído. Se as duplicatas forem estações/sensores "
              "diferentes, acrescente essa coluna em KEY_COLS. Para gerar o "
              "arquivo, rode novamente com SOMENTE_DIAGNOSTICO = False.")
        return

    # ---- Montagem do SELECT ------------------------------------------
    # Ordem final das colunas: as do arquivo novo primeiro + extras do antigo
    todas = cols_new + [c for c in cols_old if c not in cols_new]

    prio_col = "__prio_fonte__"
    while prio_col in todas:
        prio_col += "_"

    prio_new, prio_old = (1, 2) if PRIORIDADE == "new" else (2, 1)

    exprs = []
    for c in todas:
        col = qi(c)
        if c in KEY_COLS:
            exprs.append(col)
        else:
            exprs.append(
                f"arg_min({col}, {qi(prio_col)}) "
                f"FILTER (WHERE {col} IS NOT NULL) AS {col}")

    order_by = f"ORDER BY {keys_sql}" if ORDENAR_POR_CHAVE else ""

    sql = f"""
    COPY (
        SELECT {", ".join(exprs)}
        FROM (
            SELECT *, {prio_new} AS {qi(prio_col)}
            FROM read_parquet('{qp(ARQUIVO_NOVO)}')
            UNION ALL BY NAME
            SELECT *, {prio_old} AS {qi(prio_col)}
            FROM read_parquet('{qp(ARQUIVO_ANTIGO)}')
        )
        GROUP BY {keys_sql}
        {order_by}
    ) TO '{qp(ARQUIVO_SAIDA)}' (FORMAT PARQUET, COMPRESSION {COMPRESSAO});
    """

    print(f"\nExecutando merge (prioridade: arquivo {PRIORIDADE}, "
          f"RAM: {LIMITE_MEMORIA}, threads: {THREADS})...")
    con.execute(sql)

    n_new = con.execute(f"SELECT count(*) FROM read_parquet('{qp(ARQUIVO_NOVO)}')").fetchone()[0]
    n_old = con.execute(f"SELECT count(*) FROM read_parquet('{qp(ARQUIVO_ANTIGO)}')").fetchone()[0]
    n_out = con.execute(f"SELECT count(*) FROM read_parquet('{qp(ARQUIVO_SAIDA)}')").fetchone()[0]

    print("Concluído.")
    print(f"  Linhas no novo:            {n_new:,}")
    print(f"  Linhas no antigo:          {n_old:,}")
    print(f"  Linhas no merged (chaves): {n_out:,}")
    print(f"  Linhas colapsadas:         {n_new + n_old - n_out:,}")
    print(f"  Arquivo gerado:            {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()