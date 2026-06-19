import os
import glob
import duckdb
import pandas as pd
import pathlib


def gerarBase(output_dir, tipo, cabecalhos, overwrite=False):
    # Altera sonda-formatados/ para sonda-banco-dados/
    output_base = output_dir.replace('sonda-formatados/', 'sonda-banco-dados/')
    tipo_completo = tipo
    # Verifica se o tipo é Meteorologico, Solarimetrico ou Anemometrico
    tipo_map = {'MD': 'Meteorologica.parquet', 
                'SD': 'Solarimetrica.parquet',
                 'WD': 'Anemometrica.parquet'}
    if tipo not in tipo_map:
        raise ValueError(f"Tipo inválido: {tipo}. Deve ser MD, SD ou WD.")
    tipo_completo = tipo_map[tipo]
    output_base = os.path.join(output_base)
    pathlib.Path(output_base).mkdir(parents=True, exist_ok=True)

    # Conectar ao banco de dados DuckDB
    pasta_dbs = os.path.join(output_base, 'dbs/')
    pathlib.Path(os.path.dirname(pasta_dbs)).mkdir(parents=True, exist_ok=True)
    arquivo_db = os.path.join(pasta_dbs, tipo_completo.replace('.parquet', '.db'))
    global con
    con = duckdb.connect(database=arquivo_db)

    # Configurações de memória para evitar OutOfMemoryException
    # Limita o uso de RAM e permite que o DuckDB use disco quando necessário
    pasta_temp = os.path.join(pasta_dbs, 'tmp')
    pathlib.Path(pasta_temp).mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{pasta_temp}'")
    con.execute("SET memory_limit = '8GB'")
    con.execute("SET threads = 4")

    print(f"Criando base de dados em {output_base}...")
    variaveis = cabecalhos[tipo].keys()
    nome_base = tipo_completo.split('.')[0].upper()

    # Procurar por arquivos CSV no diretório de saída que contenham o tipo
    arquivos = glob.glob(os.path.join(output_dir, '**', f'*{tipo}*.csv'), recursive=True)
    if len(arquivos) == 0:
        raise ValueError(f"Nenhum arquivo encontrado para o tipo {tipo} no diretório {output_dir}.")
    # Pega primeiro arquivo pra servir de base
    arquivo = arquivos[0]
    # Criar base
    criar_base(arquivo, nome_base, variaveis)
    print(50 * '-')
    print('')

    # Popular a base com os dados
    processar_arquivos(arquivos, nome_base, sobreescrever=overwrite)

    # Verificar se as tabelas têm dados antes de salvar
    counter = con.execute(f"SELECT COUNT(*) FROM {nome_base}").fetchone()[0]

    # Salvar a base de dados meteorológicos em um arquivo parquet
    if counter > 0:
        # Obter nomes e tipos das colunas
        schema = con.execute(f"DESCRIBE SELECT * FROM {nome_base}").fetchdf()
        colunas = schema['column_name'].tolist()

        # Valores a substituir por NULL
        valores_a_nular = [3333.0, -5555.0]
        valores_str = ', '.join(str(v) for v in valores_a_nular)
        # Expressões: manter as 4 primeiras colunas como estão, aplicar lógica nas restantes
        exprs = []
        for i, col in enumerate(colunas):
            if i < 4:
                # Primeiras 4 colunas: mantém sem alteração
                exprs.append(col)
            else:
                # A partir da 5ª coluna: cast para DOUBLE + nulos para valores indesejados
                # exprs.append(f"""
                # CASE 
                #     WHEN try_cast({col} AS DOUBLE) IN ({valores_str}) THEN NULL
                #     ELSE try_cast({col} AS DOUBLE)
                # END AS {col}
                # """)
                exprs.append(f"""
                             try_cast({col} AS DOUBLE) AS {col}
                """)
        
        # Executa a query
        con.execute(f"""
            CREATE OR REPLACE TABLE {nome_base} AS
            SELECT {', '.join(exprs)}
            FROM {nome_base}
        """)

        # Salvar a tabela em um arquivo parquet sem duplicatas
        print(f"Salvando tabela em arquivo parquet: {output_base + tipo_completo}")
        con.execute(f"""
            COPY (
                SELECT DISTINCT *
                FROM {nome_base}
                WHERE acronym IS NOT NULL
                ORDER BY timestamp, acronym
            )
            TO '{output_base + tipo_completo}' (FORMAT 'parquet');
        """)

        
    else:
        print(f"A tabela {nome_base} está vazia. Nenhum arquivo parquet foi criado.")
    
    con.close()
    print(f"Base de dados criada e salva em {output_base}")
    # Remover arquivos temporários
    os.system('rm -rf .tmp')


# Função para criar a tabela no banco de dados e inicializa todas as variáveis vazias
def criar_base(arquivo, nome_base, variaveis):
    # O schema é sempre derivado dos nomes canônicos do cabecalhos.json (variaveis),
    # nunca inferido via read_csv_auto do CSV-semente. CSVs com cabeçalho irregular
    # (ex.: linha de unidades/sensores multilinha) faziam o read_csv_auto produzir
    # nomes de coluna inesperados, quebrando o restante do pipeline (binder/duplicados).
    # Tabela vazia + inserir_dados (que usa pd.read_csv skiprows=[1]) popula tudo de
    # forma consistente para MD, SD e WD.
    colunas_int = ["year", "day", "min"]
    columns_def = ', '.join(
        f"{col} VARCHAR" if col == "acronym" else
        f"{col} TIMESTAMP" if col == "timestamp" else
        f"{col} INT" if col in colunas_int else
        f"{col} FLOAT"
        for col in variaveis)

    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {nome_base} ({columns_def})
    """)
    print(f"Tabela {nome_base} criada a partir dos cabeçalhos canônicos "
          f"({len(list(variaveis))} colunas).")
    

# Função para processar os arquivos em paralelo
def processar_arquivos(arquivos, base, sobreescrever):
    
    # Cria uma lista de argumentos para cada arquivo
    args = [(arquivo, base, sobreescrever) for arquivo in arquivos]
    
    # Processa os arquivos em serie
    for arg in args:
        inserir_dados(arg)
        print('' * 50)
    
    # Verificar quantos registros foram inseridos
    count = con.execute(f"SELECT COUNT(*) FROM {base}").fetchone()[0]
    print(f"\nTotal de registros na base {base} após processamento: {count}")

# Função para popular a tabela com os dados, nessa função será possível fazer o append dos dados, atualizar os dados variavel a variavel
def inserir_dados(args):
    """
    Função para popular a base de dados com os dados de um arquivo CSV.
    
    Parâmetros:
    - args: tupla contendo (arquivo, base, sobreescrever)
      - arquivo: caminho para o arquivo CSV
      - base: nome da tabela no banco de dados
      - sobreescrever: se True, sobrescreve os dados existentes
    """
    arquivo, base, sobreescrever = args
    
    print(f"Processando arquivo {arquivo} para a base {base}...")
    
    # Limpar tabelas temporárias
    try:
        con.execute("DROP TABLE IF EXISTS temp_new_data")
        con.execute("DROP VIEW IF EXISTS new_data_view")
    except Exception:
        pass
    
    try:
        # 1. Leitura dos dados
        try:
            new_data = pd.read_csv(arquivo, skiprows=[1])
            # Normaliza nomes de coluna (remove BOM/espaços) para casar com a tabela
            # de forma robusta entre versões de pandas.
            new_data.columns = [str(c).strip().lstrip('﻿') for c in new_data.columns]
            if new_data.empty:
                print(f" - Arquivo {arquivo} não contém dados.")
                return
        except Exception as e:
            print(f" - Erro ao ler o arquivo {arquivo}: {str(e)}")
            return
            
        # 2. Preparação das colunas
        colunas_meta = ['acronym', 'timestamp', 'year', 'day', 'min']
        variaveis = [col for col in new_data.columns if col not in colunas_meta]
        
        if 'acronym' not in new_data.columns or new_data['acronym'].isna().all():
            print(f" - Erro: Arquivo {arquivo} não possui informação de estação (acronym)")
            return
            
        # 3. Limpeza e preparação dos dados
        # Substituir vírgulas por pontos e tratar valores inválidos
        for var in variaveis:
            if var in new_data.columns:
                new_data[var] = (new_data[var].astype(str)
                                 .str.replace(',', '.', regex=False)
                                 .str.replace(r'\d+-', '0', regex=True))
        
        # Converter para numérico e timestamp
        try:
            for var in variaveis:
                if var in new_data.columns:
                    new_data[var] = pd.to_numeric(new_data[var], errors='coerce')
                    
            new_data['timestamp'] = pd.to_datetime(new_data['timestamp'], errors='coerce')
            new_data = new_data.dropna(subset=['timestamp'])
            
            if new_data.empty:
                print(f" - Erro: Todos os timestamps são inválidos no arquivo {arquivo}")
                return
        except Exception as e:
            print(f" - Erro ao converter dados: {str(e)}")
            return
        
        # 4. Informações básicas
        estacao = new_data['acronym'].iloc[0]
        total_registros = len(new_data)
        tempo_min = new_data['timestamp'].min()
        tempo_max = new_data['timestamp'].max()
        
        # 5. Verificar colunas da tabela
        try:
            # Nomes das colunas da tabela via description do cursor (DB-API) — estável
            # entre versões do DuckDB. O formato de saída do DESCRIBE muda entre versões,
            # então col[0] nem sempre é o nome da coluna (podia ser o tipo), o que zerava
            # columns_to_insert e disparava o erro "Need a DataFrame with at least one column".
            table_columns = [d[0].lower() for d in
                             con.execute(f"SELECT * FROM {base} LIMIT 0").description]
            columns_to_insert = [col for col in new_data.columns if col.lower() in table_columns]
            if not columns_to_insert:
                print(f" - Erro: nenhuma coluna de {arquivo} casa com a tabela {base} "
                      f"(colunas do arquivo: {list(new_data.columns)}). Pulando.")
                return
            new_data = new_data[columns_to_insert].reset_index(drop=True)
            columns_str = ', '.join(columns_to_insert)
        except Exception as e:
            print(f" - Erro ao verificar colunas da tabela: {str(e)}")
            return
        
        # 6. Registrar DataFrame para operações SQL.
        # Preferimos converter para Arrow (formato nativo do DuckDB) — isso evita o erro
        # "Need a DataFrame with at least one column" que ocorre quando a versão do DuckDB
        # não consegue introspectar os dtypes do pandas (ex.: string dtype do pandas >=3.0).
        try:
            import pyarrow as pa
            con.register('temp_df', pa.Table.from_pandas(new_data, preserve_index=False))
        except Exception:
            con.register('temp_df', new_data)
        con.execute("CREATE OR REPLACE VIEW new_data_view AS SELECT * FROM temp_df")
        
        # 7. Verificar registros duplicados
        duplicates = con.execute(f"""
            SELECT COUNT(*) FROM {base} b
            WHERE EXISTS (
                SELECT 1 FROM new_data_view n
                WHERE b.acronym = n.acronym AND b.timestamp = n.timestamp
            )
        """).fetchone()[0]
        
        # 8. Processar conforme a flag sobreescrever
        if duplicates > 0:
            if sobreescrever:
                # Remover registros existentes
                deleted = con.execute(f"""
                    DELETE FROM {base} 
                    WHERE acronym = '{estacao}' 
                    AND timestamp BETWEEN '{tempo_min}' AND '{tempo_max}'
                """).fetchone()[0]
                
                # Inserir novos dados
                con.execute(f"""
                    INSERT INTO {base} ({columns_str})
                    SELECT {columns_str} FROM new_data_view
                """)
                
                print(f" - Sobreescritos {deleted} registros existentes para estação {estacao}")
            else:
                # Verificar se todos já existem
                if duplicates == total_registros:
                    print(f" - Todos os {total_registros} registros já existem para estação {estacao}. Use a opção de sobreescrever (--overwrite) para atualizar.")
                    return
                
                # Inserir apenas os que não existem
                inserted = con.execute(f"""
                    INSERT INTO {base} ({columns_str})
                    SELECT n.* FROM new_data_view n
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {base} b
                        WHERE b.acronym = n.acronym AND b.timestamp = n.timestamp
                    )
                """).fetchone()[0]
                
                print(f" - {duplicates} registros já existem e foram ignorados")
                print(f" - Inseridos {inserted} novos registros para estação {estacao}")
        else:
            # Nenhum registro duplicado, inserir todos
            inserted = con.execute(f"""
                INSERT INTO {base} ({columns_str})
                SELECT {columns_str} FROM new_data_view
            """).fetchone()[0]
            
            print(f" - Inseridos {inserted} novos registros para estação {estacao}")
        
        # Limpar recursos temporários
        con.execute("DROP TABLE IF EXISTS temp_new_data")
        con.execute("DROP VIEW IF EXISTS new_data_view")
        
    except Exception as e:
        print(f" - Erro ao processar arquivo {arquivo}: {str(e)}")
        # Garantir limpeza
        try:
            con.execute("DROP TABLE IF EXISTS temp_new_data")
            con.execute("DROP VIEW IF EXISTS new_data_view")
        except:
            pass
