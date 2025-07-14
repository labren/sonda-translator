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
    good_data = []
    bad_data = []
    problemas = []

    # # Número esperado de linhas por dia: 24 horas * 60 minutos = 1440
    expected_rows = int(pd.Timedelta("1 day") / expct_freq)
    expected_last_time = (pd.Timestamp("00:00:00") + (expected_rows - 1) * expct_freq).time()

    # Remove valores duplicados no dataframe inteiro
    df = df.drop_duplicates(keep='first').reset_index(drop=True)

    # Encontra todas as linhas que que contem a string "00:00:00" no timestamp
    zero_hour_rows = df['timestamp'].astype(str).str.contains("00:00:00")
    # Retorna apenas os indices verdadeiros
    zero_hour_rows = zero_hour_rows[zero_hour_rows].index.tolist()

    # Baseado nos indices de horas 00:00:00, separa os dados por data
    # Faça um loop que vai pegar os indices + expected_rows
    for i in zero_hour_rows:
        # Separa a linha atual + expected_rows
        group = df.iloc[i:i + expected_rows].copy()
        # Testes temporais
        problema, data_df = testeTemporal(group, expected_rows, expct_freq, expected_last_time)
        # Se não houver problemas, adiciona a data na lista de dados bons
        if len(problema) == 0:
            good_data.append(data_df)
            continue
        # Se houver problemas, adiciona a data na lista de dados problemáticos
        bad_data.append(data_df)
        problemas.append(problema)

    return good_data, bad_data, problemas
