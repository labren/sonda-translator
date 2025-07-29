import pandas as pd
import pathlib
from testeTemporal import testeTemporal

def prequalificarDado(df, tipo_dado, logger, estacao, output_dir, tipo_completo):

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

    if tipo_dado == 'MD':
        expct_freq = pd.Timedelta(minutes=10)
    elif tipo_dado == 'SD':
        expct_freq = pd.Timedelta(minutes=1)
    elif tipo_dado == 'WD':
        expct_freq = pd.Timedelta(minutes=10)
    else:
        logger.error(f"Error 7 - Error no prequalificaDado: \
            Tipo de dado inválido: {tipo_dado}.")
        return None, None
        
    # Listas para armazenar as datas consideradas boas ou problemáticas
    code_data = []
    good_data = []
    bad_data = []
    problemas = []

    # Remove valores duplicados no dataframe inteiro
    df = df.drop_duplicates(keep='first').reset_index(drop=True)

    # Encontra todas as linhas que que contem a string "00:00:00" no timestamp
    zero_hour_rows = df['timestamp'].astype(str).str.contains("00:00:00")
    # Retorna apenas os indices verdadeiros
    zero_hour_rows = zero_hour_rows[zero_hour_rows].index.tolist()

    # Baseado nos indices de horas 00:00:00, separa os dados por data
    # Faça um loop que vai pegar os indices + e -1
    for i in range(1, len(zero_hour_rows)):
        # Pega os valores entre os indices i e i -1
        group = df.iloc[zero_hour_rows[i - 1]:zero_hour_rows[i]]
        # Testes temporais
        code, problema, data_df = testeTemporal(group)
        # Se não houver problemas, adiciona a data na lista de dados bons
        if code == 0:
            good_data.append(data_df)
            continue
        # Se houver problemas, adiciona a data na lista de dados problemáticos
        code_data.append(code)
        bad_data.append(data_df)
        problemas.append(problema)

    return code_data, good_data, bad_data, problemas
