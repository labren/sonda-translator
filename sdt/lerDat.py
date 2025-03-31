import os
import duckdb
import logging
import pandas as pd
import json
from datetime import datetime

# Configuração do logger
def setup_logger():
    logger = logging.getLogger('sonda_translator')
    logger.setLevel(logging.ERROR)
    
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt")
    file_handler = logging.FileHandler(log_file)
    
    formatter = logging.Formatter('----------------------------------------\nDATA DO PROCESSAMENTO: %(asctime)s\nError: %(message)s\n')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    return logger

# Inicializa o logger
logger = setup_logger()

# Carrega o arquivo JSON com os cabeçalhos
script_dir = os.path.dirname(os.path.abspath(__file__))
dat_file_path = os.path.join(script_dir, 'json', 'cabecalhos.json')

global headers
if os.path.exists(dat_file_path):
    with open(dat_file_path, 'r') as f:
        headers = json.load(f)


def lerArquivo(args):
    file_path, file_type = args

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
    header_type = headers[file_type]
    
    print(data)

