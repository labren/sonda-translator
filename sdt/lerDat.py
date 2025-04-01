import os
import duckdb
import logging
import pandas as pd
import json
import re
import pathlib

pd.set_option('future.no_silent_downcasting', True)

# Configuração do logger
def setup_logger():
    logger = logging.getLogger('sonda_translator')
    logger.setLevel(logging.ERROR)

    # Pega o diretório do script atual
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Caso o diretorio tenja o final com nome de sdt, volte uma pasta
    if script_dir.endswith('sdt'):
        script_dir = os.path.dirname(script_dir)
    # Cria o arquivo no diretório do script
    # O arquivo será chamado de error_log.txt
    # e será criado na mesma pasta do script
    log_file = os.path.join(script_dir, 'error_log.txt')
    file_handler = logging.FileHandler(log_file)
    
    formatter = logging.Formatter('----------------------------------------\nDATA DO PROCESSAMENTO: %(asctime)s\nError: %(message)s\n')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    return logger

# Inicializa o logger
logger = setup_logger()

global headers, header_sensor
# Carrega o arquivo JSON com os cabeçalhos
script_dir = os.path.dirname(os.path.abspath(__file__))
dat_file_path = os.path.join(script_dir, 'json', 'cabecalhos.json')
# Carrega o arquivo JSON com os sensores
header_sensor_path = os.path.join(script_dir, 'json', 'cabecalho_sensor.json')
# Carrega o arquivo JSON com os cabeçalhos
if os.path.exists(dat_file_path):
    with open(dat_file_path, 'r') as f:
        headers = json.load(f)
# Carrega o arquivo JSON com os sensores
if os.path.exists(header_sensor_path):
    with open(header_sensor_path, 'r') as f:
        header_sensor = json.load(f)


def lerArquivo(args):
    file_path, estacao, file_type, output_dir, overwrite = args

    # Check if the file exists
    if not os.path.exists(file_path):
        return
    
    # Tenta ler as primeiras linhas do arquivo
    try:
        find_data = duckdb.query(f"""
            SELECT * 
            FROM read_csv_auto('{file_path}',
            ignore_errors=true)
            LIMIT 10
        """).df()
    except Exception as e:
        # Registra o erro usando o logger
        logger.error(f"Não foi possível ler o arquivo {file_path} durante o processo de encontrar características do dado.\nDetalhes do erro: {str(e)}")
        return
    
    # Encontra linha de cabeçalho passando per todas as linhas
    # A linha de cabeçalho deve conter qualquer uma das palavras-chave
    # 'TIMESTAMP', 'RECORD', 'Id', 'Year', 'Jday', 'Min'. Caso contrário,
    # a linha de cabeçalho será None.
    header_row = None
    for i, row in find_data.iterrows():
        if any(keyword in str(row) for keyword in ['TIMESTAMP', 'RECORD', 'Id', 'Year', 'Jday', 'Min']):
            header_row = i
            break
    # Se a linha de cabeçalho não for encontrada, pega os valores da primeira linha
    # e coloca como cabeçalho, caso contrário será um cabeçalho vazio com o mesmo numero de colunas
    # do arquivo.
    if header_row is None:
        header_row = [None] * len(find_data.columns)
    else:
        header_row = find_data.iloc[header_row].tolist()

    # Encontra a linha de dados. Nesta linha, a maioria dos valores deve ser numérico.
    # Caso contrário, continue procurando. E se não houver linha de dados, retorne None.
    data_row = 0
    # Faz um cast para float na maioria dos valores para tentar encontrar a linha de dados
    # Se não for possível, ignora o erro e continua
    for i, row in find_data.iterrows():
        numeric_row = pd.to_numeric(row, errors='coerce')
        if numeric_row.notna().sum() > len(row) / 2:
            data_row = i
            break

    # Abre o arquivo novamente, agora com o cabeçalho e a linha de dados encontrados
    try:
        data = duckdb.query(f"""
            SELECT * 
            FROM read_csv_auto('{file_path}',
            ignore_errors=true,
            skip={data_row})
        """).df()
    except Exception as e:
        # Registra o erro usando o logger
        logger.error(f"Não foi possível ler o arquivo {file_path} durante o processo de encontrar dados.\nDetalhes do erro: {str(e)}")
        return
    
    # Adiciona o cabeçalho encontrado ao DataFrame
    data.columns = header_row

    # Agora, baseado no tipo iremos procurar o verdadeiro nome das colunas
    try:
        main_header = headers[file_type]
    except KeyError:
        # Registra o erro usando o logger
        logger.error(f"Tipo de arquivo inválido: {file_type} no arquivo {file_path}.")
        return
    
    # Create a mapping dictionary for column name normalization
    normalized_headers = {}
    for key, values in main_header.items():
        for value in values:
            normalized_headers[value.strip().upper()] = key
    
    # Rename columns using the mapping dictionary
    renamed_columns = {}
    for col in data.columns:
        if str(col).strip().upper() in normalized_headers:
            renamed_columns[col] = normalized_headers[str(col).strip().upper()]

        # Caso tipo seja WD, reamostr para dados de 10 minutos, deixando apenas o primeiro
    if file_type == 'WD':
        # Encontra a coluna de timestamp
        timestamp_col = None
        for col in data.columns:
            if 'TIMESTAMP' in str(col).upper():
                timestamp_col = col
                break
        if timestamp_col is None:
            # Registra o erro usando o logger
            logger.error(f"Não foi possível encontrar a coluna de timestamp no arquivo {file_path}.")
            return
        # Converte a coluna de timestamp para datetime
        data[timestamp_col] = pd.to_datetime(data[timestamp_col], errors='coerce')
        # Encontra dados com intervalo de 1 minuto
        one_minute = data[data[timestamp_col].diff().dt.total_seconds() == 60]
        if not one_minute.empty:
            # Registra o erro usando o logger
            logger.error(f"Encontrados dados com intervalo de 1 minuto no arquivo {file_path}.")
    
    # Apply the rename operation only once
    if renamed_columns:
        data = data.rename(columns=renamed_columns)
    
    # Create result DataFrame with columns in the correct order, filling missing ones with NA
    result = pd.DataFrame()
    for key in main_header.keys():
        result[key] = data.get(key, pd.NA)

    # Adiciona o nome da estacao na coluna acronym para todos os nans de acronym
    # Se estacao for uma lista vazia, entao pegue o nome a partir do nome do arquivo
    if len(estacao) == 0:
        # Extract station name using regex
        estacao = re.findall(r'coleta[/\\]([A-Z]{3})', file_path)
        if not estacao:
            # Try to get from filename if not found in path
            filename = os.path.basename(file_path)
            estacao = re.findall(r'^([A-Z]{3})_', filename)
            if not estacao:
                # Use directory name as fallback
                dirname = os.path.basename(os.path.dirname(file_path))
                if dirname and len(dirname) >= 3:
                    estacao = [dirname[:3]]
                else:
                    # Log error and exit function if station name can't be determined
                    logger.error(f"Não foi possível determinar o nome da estação para o arquivo {file_path}.")
                    return
        # Se o tipo for uma lista, pega o primeiro elemento
        if len(estacao) > 0:
            estacao = estacao[0].upper()
    else:
        estacao = estacao[0].upper()
    
    # Adiciona o nome da estacao na coluna acronym para todos os nans de acronym
    result['acronym'] = estacao

    # Para a coluna 'day', você deve converter timestamp para datetime e extrair o dia juliano
    result['timestamp'] = pd.to_datetime(result['timestamp'], errors='coerce')
    result['day'] = result['timestamp'].dt.dayofyear

    # Para todos os outros valores nans, preenche com o valor -5555
    result.fillna(-5555.0, inplace=True)

    # Pega cabecalho_sensor e adiciona como subcabeçalho
    try:
        sub_header = header_sensor[estacao][file_type]
    except KeyError:
        # Registra o erro usando o logger
        logger.error(f"Não foi possível encontrar o subcabeçalho para a estação {estacao} e tipo {file_type}.")
        # Crie um subcabeçalho vazio
        sub_header = [''] * len(result.columns)
    # Adiciona o subcabeçalho ao DataFrame
    sub_header = ['', '', '', '', ''] + sub_header
    # Adiciona o subcabeçalho ao DataFrame
    result.columns = pd.MultiIndex.from_tuples(list(zip(result.columns,sub_header)))
    # Encontr atipo completo baseado no file_type
    # Caso MD, o tipo é Meteorologico
    # Caso SD, o tipo é Solarimetrico
    # Caso WD, o tipo é Anemometrico
    tipo_completo = ''
    if file_type == 'MD':
        tipo_completo = 'Meteorologico'
    elif file_type == 'SD':
        tipo_completo = 'Solarimetrico'
    elif file_type == 'WD':
        tipo_completo = 'Anemometrico'

    # Agrupa por mês e cria um loop para criar os arquivos
    result_groups = result.groupby(result['timestamp'].dt.to_period('M'))
    for period, group in result_groups:
        # Cria o nome do arquivo, o padrão é: SMS_YYYY_MM_SD_formatado.csv
        file_name = f"{estacao.upper()}_{period.year}_{period.month:02d}_{file_type}_formatado.csv"
        # O output_path será sempre output_dir + estacao + tipo_completo + ano
        output_path = os.path.join(output_dir, estacao.upper(), tipo_completo, str(period.year))
        # Verifica se o arquivo já existe, caso exista verifica flag de overwrite, acaso não exista, cria o arquivo, caso exista e a flag overwrite for False, pula a criação do arquivo
        file_path = os.path.join(output_path, file_name)
        # Cria diretorio caso não exista
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        if os.path.exists(file_path):
            if not overwrite:
                continue
            else:
                group.to_csv(file_path, index=False)
        else:
            # Cria diretorio caso não exista
            pathlib.Path(output_path).mkdir(parents=True, exist_ok=True)
            # Cria o arquivo
            group.to_csv(file_path, index=False)

    