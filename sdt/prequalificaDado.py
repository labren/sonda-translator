import pandas as pd
import pathlib
from testeTemporal import testeTemporal

def prequalificarDado(df, estacao, logger):

    """
    Função para qualificar os dados de um DataFrame.

    Args:
        df (pd.DataFrame): DataFrame de dado formatado.
        tipo_dado (str): Tipo do dado.
        logger (logging.Logger): Logger para registrar erros.
    Returns:
        pd.DataFrame: DataFrame qualificado.
    """
    #### Configurações de qualificação ####

    # - intervalo: Intervalo esperado entre registros (default: 1 minuto)
    #   - tolerancia: Tolerância percentual para a comparação do intervalo esperado (default: 10%)
    #   - mad_factor: Fator multiplicativo para o limiar baseado no MAD (default: 3)

    # Listas para armazenar as datas consideradas boas ou problemáticas
    code_data = []
    good_data = []
    bad_data = []
    problemas = []

    ###### TRATAMENTO INICIAL #####
    # Tratamento 1: Elimina linhas duplicadas, mantem a última
    df = df.drop_duplicates(keep='first').reset_index(drop=True)
    # Tratamento 2: Verifica se existem características inválidas na coluna 'timestamp'
    df['timestamp'] = df['timestamp'].astype(str).str.replace(r'[^0-9:/\-\s]', '', regex=True)
    # Tratamento 3: Converte a coluna 'timestamp' para datetime, ignorando erros
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    # Tratamento 4: Elimina valores com NaN
    df = df.dropna(subset=['timestamp'])

    ###### PARSING TEMPORAL POR blocos de dia unico #####
    # Encontra dias unicos presentes nos dados
    df['dia_original'] = df['timestamp'].dt.date
    # Cria uma coluna auxiliar para identificar blocos de dias únicos com des
    #df['bloco'] = (df['dia_original'] != df['dia_original'].shift()).cumsum()
    # Loop por cada bloco de dias únicos
    for _, dados in df.groupby('dia_original'):
        # Pega os dados do bloco
        dados = dados.reset_index(drop=True)
        # Remove as colunas dia_original e bloco
        dados = dados.drop(columns=['dia_original'])
        # Testes temporais
        code, problema, data_df = testeTemporal(dados, estacao, logger)
        # Se não houver problemas, adiciona a data na lista de dados bons
        if code == 0:
            good_data.append(data_df)
            continue
        # Se houver problemas, adiciona a data na lista de dados problemáticos
        code_data.append(code)
        bad_data.append(data_df)
        problemas.append(problema)

    # ###### PARSING TEMPORAL POR HORÁRIO 00:00:00 #####
    # zero_hour_rows = df['timestamp'].astype(str).str.contains("00:00:00")
    # # Retorna apenas os indices verdadeiros
    # zero_hour_rows = zero_hour_rows[zero_hour_rows].index.tolist()

    # # Baseado nos indices de horas 00:00:00, separa os dados por data
    # # Faça um loop que vai pegar os indices + e -1
    # for i in range(1, len(zero_hour_rows)):
    #     # Pega os valores entre os indices i e i -1
    #     group = df.iloc[zero_hour_rows[i - 1]:zero_hour_rows[i]]
    #     # Testes temporais
    #     code, problema, data_df = testeTemporal(group, estacao, logger)
    #     # Se não houver problemas, adiciona a data na lista de dados bons
    #     if code == 0:
    #         good_data.append(data_df)
    #         continue
    #     # Se houver problemas, adiciona a data na lista de dados problemáticos
    #     code_data.append(code)
    #     bad_data.append(data_df)
    #     problemas.append(problema)

    return code_data, good_data, bad_data, problemas
