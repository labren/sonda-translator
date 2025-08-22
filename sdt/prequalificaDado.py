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
    df['dia_unico'] = df['timestamp'].dt.date
    # Loop por cada bloco de dias únicos
    for _, dados in df.groupby('dia_unico'):
        # Pega os dados do bloco
        dados = dados.reset_index(drop=True)
        # Remove as colunas dia_original e bloco
        dados = dados.drop(columns=['dia_unico'])
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

    return code_data, good_data, bad_data, problemas
