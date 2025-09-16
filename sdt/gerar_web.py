import os
import duckdb
import pandas as pd
import pathlib
import logging

def gerar_web(output_path='output/sonda-banco-dados', tipo='SD'):
    # Replace any sonda-formatados para sonda-banco-dados em output_path
    output_path = output_path.replace('sonda-formatados', 'sonda-banco-dados')
    output_path = output_path.replace('sonda-quarentena', 'sonda-banco-dados')
    output_web = output_path.replace('sonda-banco-dados', 'sonda-web')
    # Verifica se arquivo já existe
    if tipo == 'SD':
        output_file = os.path.join(output_path, f'Solarimetrica.parquet')
        columns_of_interest = ['timestamp', 'acronym', 'year', 'day', 'min', 'glo_avg', 'dir_avg', 'dif_avg', 'lw_avg', 'par_avg', 'lux_avg']
    elif tipo == 'MD':
        output_file = os.path.join(output_path, f'Meteorologica.parquet')
    elif tipo == 'WD':
        output_file = os.path.join(output_path, f'Anemometrica.parquet')
    else:
        print(f"Tipo de dado '{tipo}' não reconhecido.")
        exit()

    # Verifica se arquivo já existe
    if not os.path.exists(output_file):
        print(f"Arquivo '{output_file}' não encontrado.")
        exit()

    # Configuração mais avançada para log em arquivo e console
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('gerar_web.log'),
            logging.StreamHandler()  # Para exibir no console também
        ]
    )

    # Create database in file mode
    con = duckdb.connect()

    # Create a table with only the columns of interest
    con.execute(f"""CREATE TABLE IF NOT EXISTS solarimetrica AS 
                SELECT {', '.join(columns_of_interest)} FROM read_parquet('{output_file}', union_by_name=true)
                """)

    # Obter lista de estações únicas
    estacoes_query = "SELECT DISTINCT acronym FROM solarimetrica ORDER BY acronym"
    estacoes = con.execute(estacoes_query).fetchall()
    estacoes = [row for row in estacoes if row[0] is not None]

    print(f"Encontradas {len(estacoes)} estações:")

    # Ler arquivo Tabela-estados.csv
    estacoes_df = pd.read_csv('sdt/utils/Tabela-estacao.csv')

    # Loop por cada estação
    for estacao_row in estacoes:
        acronym = estacao_row[0]
        print(f"Processando estação: {acronym}")
        # Pega o nome da estação de estacoes_df
        estacao_info = estacoes_df[estacoes_df['Sigla'] == acronym]
        if estacao_info.empty:
            nome_estacao = 'Desconhecida'
            lat_estacao = 'Desconhecida'
            lon_estacao = 'Desconhecida'
            alt_estacao = 'Desconhecida'
            logging.error(f"Informações da estação {acronym}, {estacao_row} não encontradas no arquivo sdt/utils/Tabela-estacao.csv.")
        else:
            nome_estacao = estacao_info['Estação'].values[0]
            lat_estacao = estacao_info['Latitude'].values[0]
            lon_estacao = estacao_info['Longitude'].values[0]
            alt_estacao = estacao_info['Alt.(m)'].values[0]

        # Criar MultiIndex com os nomes das colunas e unidades
        multi_columns = pd.MultiIndex.from_arrays([
        [acronym,nome_estacao,'lat:'+str(lat_estacao),'lon:'+str(lon_estacao),'alt:'+str(alt_estacao),'SONDA Network','http://sonda.ccst.inpe.br','sonda@inpe.br', '','',''],
        columns_of_interest,
        ['','','','','','W/m2','W/m2','W/m2','W/m2','µmols/m2.s','klux']
        ])

        # Query para obter os dados da estação
        query = f"""
        SELECT {', '.join(columns_of_interest)}
        FROM solarimetrica 
        WHERE acronym = '{acronym}'
        ORDER BY timestamp
        """
        df = con.execute(query).df()
        
        # Debug: comparar as duas abordagens
        years_from_column = set(df['year'].dropna().unique())

        # Set timestamp as index
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        # Get years from timestamp
        years_from_timestamp = set(df['timestamp'].dt.year.dropna().unique())
        # Verifica se os anos são diferentes
        if years_from_column != years_from_timestamp:
            logging.warning(f"Estação {acronym}: Anos diferentes entre coluna year ({years_from_column}) e timestamp ({years_from_timestamp})")
        # Agrupar por ano baseado no timestamp
        df_year_group = df.groupby(df['timestamp'].dt.year)
        for year, group in df_year_group:
            if pd.isna(year):
                continue

            # Check if acronym is "CGR" and year < 2021 and replace "CGU" by "CGR"
            if acronym == "CGR" and int(year) < 2021:
                multi_columns = check_CGU(multi_columns)
                group['acronym'] = "CGU"
                acronym = "CGU"

            # Set name of file
            output_file = pathlib.Path(output_web) / f"anual/Solarimetrico/{acronym}/{int(year)}/{acronym}_{int(year)}_SD"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            # Fill values
            group = fill_values(group, acronym)
            # Add multicolumns
            group.columns = multi_columns
            # Save to csv
            print(group)
            exit()
            group.to_csv(output_file.with_suffix('.dat'), index=False)
            os.system(f"zip -j {output_file}.zip {output_file.with_suffix('.dat')}")
            os.remove(output_file.with_suffix('.dat'))

        # Agrupa por ano e mês (usando a mesma base de dados)
        df_year_month = df.groupby([df['timestamp'].dt.year, df['timestamp'].dt.month])
        for (year, month), group in df_year_month:
            if pd.isna(year) or pd.isna(month):
                continue

            # Check if acronym is "CGR" and year < 2021 and replace "CGU" by "CGR"
            if acronym == "CGR" and int(year) < 2021:
                multi_columns = check_CGU(multi_columns)
                group['acronym'] = "CGU"
                acronym = "CGU"

            # Set name of file
            output_file = pathlib.Path(output_web) / f"mensal/Solarimetrico/{acronym}/{int(year)}/{acronym}_{int(year)}_{str(int(month)).zfill(2)}_SD"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            # Fill values
            group = fill_values(group, acronym)
            # Add multicolumns
            group.columns = multi_columns
            # Save csv
            group.to_csv(output_file.with_suffix('.dat'), index=False)
            os.system(f"zip -j {output_file}.zip {output_file.with_suffix('.dat')}")
            os.remove(output_file.with_suffix('.dat'))
    print("Processamento concluído.")
    con.close()


def fill_values(df, acronym):
    # Remove any duplicated values based on timestamp
    df = df[~df['timestamp'].duplicated(keep='first')]

    # Fill gaps with interpolation
    min_timestamp = df['timestamp'].min()
    max_timestamp = df['timestamp'].max()
    min_year = min_timestamp.year
    max_year = max_timestamp.year
    min_month = min_timestamp.month
    max_month = max_timestamp.month
    full_time_index = pd.date_range(start=f'{min_year}-{str(min_month).zfill(2)}-01 00:00:00', 
                                    end=f'{max_year}-{str(max_month).zfill(2)}-{pd.Period(f"{max_year}-{str(max_month).zfill(2)}").days_in_month} 23:59:00', 
                                    freq='1 min')
    df = df.set_index('timestamp').reindex(full_time_index).reset_index().rename(columns={'index': 'timestamp'})

    # Fill NaN value and fill year, day, min and acronym columns
    df['year'] = df['timestamp'].dt.year.fillna(method='ffill')
    df['day'] = df['timestamp'].dt.dayofyear.fillna(method='ffill')
    df['min'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute
    df['min'] = df['min'].astype(int)
    df['acronym'] = df['acronym'].fillna(acronym)
    return df

def check_CGU(multi_columns, name='Campo Grande Uniderp', acronym='CGU', latitude=-20.438, longitude=-54.538, altitude=677):
    level_0 = list(multi_columns.get_level_values(0))
    level_1 = list(multi_columns.get_level_values(1))
    level_2 = list(multi_columns.get_level_values(2))
    level_0 = [acronym if x == 'CGR' else x for x in level_0]
    level_0 = [name if 'Campo Grande' in str(x) else x for x in level_0]
    level_0 = [f'lat:{latitude}' if 'lat:' in str(x) else x for x in level_0]
    level_0 = [f'lon:{longitude}' if 'lon:' in str(x) else x for x in level_0]
    level_0 = [f'alt:{altitude}' if 'alt:' in str(x) else x for x in level_0]
    # Ensure all arrays have the same length
    min_len = min(len(level_0), len(level_1), len(level_2))
    level_0 = level_0[:min_len]
    level_1 = level_1[:min_len]
    level_2 = level_2[:min_len]
    new_multi_columns = pd.MultiIndex.from_arrays([level_0, level_1, level_2])
    return new_multi_columns