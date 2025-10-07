import pandas as pd
import pathlib
from testeTemporal import testeTemporal

def prequalificarDado(df, estacao, logger, header_sensor, file_type, file_path):

    """
    Função para qualificar os dados de um DataFrame.

    Args:
        df (pd.DataFrame): DataFrame de dado formatado.
        estacao (str): Nome da estação.
        logger (logging.Logger): Logger para registrar erros.
        header_sensor (dict): Cabeçalhos dos sensores.
        file_type (str): Tipo do arquivo (MD, SD, WD).
        file_path (str): Caminho do arquivo.
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
    # Tratamento 1: Verifica se todos os valores da coluna 'timestamp' são NaN
    if df['timestamp'].isna().all():
        # Insere os valores das colunas Year  Day   Min para criar a coluna timestamp, Day é o dia do ano
        year = df['year'].astype(int).astype(str).str.zfill(4)
        day = df['day'].astype(int).astype(str).str.zfill(3)
        hour = (df['min'] // 60).astype(int).astype(str).str.zfill(2)
        minute = (df['min'] % 60).astype(int).astype(str).str.zfill(2)
        df['timestamp'] = pd.to_datetime(year + day + hour + minute, format='%Y%j%H%M', errors='coerce')
        # Verifica se estacao for NAT, e acrescenta 3 horas
        if estacao.upper() == 'NAT':
            df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=3)
        # Ajusta a coluna min para refletir a hora e minuto corretos
        df['min'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute
    # Tratamento 2: Elimina linhas duplicadas, mantem a última
    df = df.drop_duplicates(keep='first').reset_index(drop=True)
    # Tratamento 3: Verifica se existem características inválidas na coluna 'timestamp'
    df['timestamp'] = df['timestamp'].astype(str).str.replace(r'[^0-9:/\-\s]', '', regex=True)
    # Tratamento 4: Converte a coluna 'timestamp' para datetime, ignorando erros
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    # Tratamento 5: Elimina valores com NaN
    df = df.dropna(subset=['timestamp'])
    # Tratamento 6: Adiciona coluna 'acronym' com o valor da estação em maiúsculas
    df['acronym'] = estacao.upper()

     # Adiciona cabeçalho ao DataFrame
    try:
        sub_header = header_sensor[estacao][file_type]
    except KeyError:
        # Registra o erro usando o logger
        logger.error(f"Error 5 - Não foi possível encontrar o cabeçalho para a estação {estacao} e tipo {file_type} no arquivo {file_path}, um subcabeçalho vazio será adicionado.")
        sub_header = [''] * len(df.columns)
        return (5, [], [df], [f"Não foi possível encontrar o cabeçalho para a estação {estacao} e tipo {file_type} no arquivo {file_path}."])
    # Adiciona o subcabeçalho ao DataFrame
    sub_header = ['', '', '', '', ''] + sub_header
    df.columns = pd.MultiIndex.from_tuples(list(zip(df.columns, sub_header)))

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

    # Se não houver dados bons, retorna listas vazias
    if len(good_data) == 0:
        return code_data, [], bad_data, problemas

    # Concatena os dados bons em um único DataFrame por ano e mês
    good_data = pd.concat(good_data, ignore_index=True) if good_data else pd.DataFrame()
    good_data_by_month = []
    month_good_data = good_data.groupby([good_data['timestamp'].dt.year, good_data['timestamp'].dt.month])
    for _, data in month_good_data:
        good_data_by_month.append(data)

    return code_data, good_data_by_month, bad_data, problemas
