import os
import duckdb
import pandas as pd
import pathlib
import warnings
from prequalificaDado import prequalificarDado
warnings.filterwarnings("ignore")


def processarArquivo(args):

    """
    Função para ler arquivos de dados e processá-los.
    Args:
        args: Uma tupla contendo os seguintes parâmetros:
            - file_path: Caminho do arquivo a ser lido.
            - estacao: Nome da estação.
            - file_type: Tipo do arquivo (MD, SD, WD).
            - output_dir: Diretório de saída para salvar os arquivos processados.
            - overwrite: Flag para sobrescrever arquivos existentes.
            - logger: Logger para registrar erros.
            - headers: Cabeçalhos dos arquivos.
            - header_sensor: Cabeçalhos dos sensores.
    Returns:
        None
    """
    # Desempacota os argumentos
    file_path, estacao, file_type, output_dir, overwrite, logger, headers, header_sensor = args

    # Check if the file exists
    if not os.path.exists(file_path):
        return pd.DataFrame()
    ############################################################################
    ############ Parte 1 - Encontrar o cabeçalho e a linha de dados ############
    ############################################################################
    # Tenta ler as 10 primeiras linhas do arquivo para encontrar o cabeçalho
    # e a linha de dados. Caso não consiga, retorna None.
    try:
        find_data = duckdb.query(f"""
            SELECT * 
            FROM read_csv_auto('{file_path}',
            ignore_errors=true)
            LIMIT 10
        """).df()
    except Exception as e:
        logger.error(f"Error 1 - Não foi possível ler o arquivo {file_path} \
            durante o processo de encontrar dados.\nDetalhes do erro: {str(e)}")
        return pd.DataFrame()
    
    # Encontra linha de cabeçalho passando por todas as linhas do arquivo
    # A linha de cabeçalho deve conter qualquer uma das palavras-chave
    # 'TIMESTAMP', 'RECORD', 'Id', 'Year', 'Jday', 'Min'. 
    # Caso contrário, a linha de cabeçalho será None.
    # TODO: Verificar em alguns casos pois as variáveis podem não ser exatamente desta forma.
    header_row = None
    for i, row in find_data.iterrows():
        if any(keyword in str(row) for keyword in ['TIMESTAMP', 'RECORD', 'Id', 'Year', 'Jday', 'Min']):
            header_row = i
            break
    # Se a linha de cabeçalho não for encontrada, pega os valores da primeira linha
    # e coloca como cabeçalho, caso contrário será um cabeçalho vazio com o mesmo numero de colunas
    # do arquivo.
    try:
        if header_row is None:
            header_row = find_data.iloc[0].tolist()
        else:
            header_row = find_data.iloc[header_row].tolist()
    except:
        logger.error(f"Error 2 - Não foi possível encontrar o cabeçalho no arquivo {file_path}.")
        return pd.DataFrame()

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

    ############################################################################
    ### Parte 2 - Ler o arquivo novamente com o cabeçalho e a linha de dados ###
    ############################################################################
    # Abre o arquivo novamente, agora com o cabeçalho e a linha de dados encontrados
    try:
        data = duckdb.query(f"""
            SELECT * 
            FROM read_csv_auto('{file_path}',
            ignore_errors=true,
            skip={data_row + 1})
        """).df()
    except Exception as e:
        logger.error(f"Error 2 - Não foi possível ler o arquivo {file_path} \
            durante o processo de encontrar dados.\nDetalhes do erro: {str(e)} \
            Os dados encontrados foram: {data}")
        return pd.DataFrame()
    
    # Adiciona o cabeçalho encontrado ao DataFrame
    try:
        data.columns = header_row
    except Exception as e:
        logger.error(f"Error 3 - Não foi possível adicionar o cabeçalho ao arquivo {file_path} \
            durante o processo de encontrar dados.\nDetalhes do erro: {str(e)}")
        return pd.DataFrame()
    
    # Pega o cabeçalho principal baseado no file_type
    try:
        main_header = headers[file_type]
    except KeyError:
        # Registra o erro usando o logger
        logger.error(f"Error 4 - Não foi possível encontrar o cabeçalho para o tipo {file_type} no arquivo {file_path}.")
        return pd.DataFrame()
    
    # Remove aspas duplas dos nomes das colunas    
    data.columns = data.columns.str.strip('"')

    # Normaliza os aliases e cria um mapeamento reverso com todos em maiúsculas
    mapa_colunas = {}
    for key, aliases in main_header.items():
        for alias in aliases:
            mapa_colunas[alias.upper()] = key

    # Também normaliza os nomes de colunas do DataFrame
    data.columns = [col.upper().strip('"') for col in data.columns]

    # Aplica o mapeamento apenas às colunas que estão no dicionário
    new_columns = {col: mapa_colunas[col] for col in data.columns if col in mapa_colunas}

    # Renomeia as colunas do DataFrame
    data.rename(columns=new_columns, inplace=True)

    # Mantém somente as colunas que são chaves do main_header
    data = data[[col for col in data.columns if col in main_header.keys()]]

    # Adiciona as colunas que não estão no main_header como NaN
    for col in main_header.keys():
        if col not in data.columns:
            data[col] = pd.NA

    # Reordena as colunas do DataFrame para que fiquem na mesma ordem do main_header
    data = data[main_header.keys()]
    
    # Pega colunas que não foram renomeadas e separa em um novo DataFrame
    outros_dados = data.drop(columns=main_header.keys(), errors='ignore')
    # Verifica se tem outros dados e cria um log
    if not outros_dados.empty:
        # Registra o erro usando o logger
        logger.error(f"WARNING - O arquivo {file_path} contém colunas que não foram processadas: {outros_dados.columns.tolist()}")

    # Encontr atipo completo baseado no file_type
    # Caso MD, o tipo é Meteorologico
    # Caso SD, o tipo é Solarimetrico
    # Caso WD, o tipo é Anemometrico
    tipo_completo = ''
    if file_type == 'MD':
        tipo_completo = 'Meteorologicos'
        expct_freq = pd.Timedelta(minutes=10)
    elif file_type == 'SD':
        tipo_completo = 'Solarimetricos'
        expct_freq = pd.Timedelta(minutes=1)
    elif file_type == 'WD':
        tipo_completo = 'Anemometricos'
        expct_freq = pd.Timedelta(minutes=10)

    ##########################################################################
    ### Parte 3 - Prequalificar os dados e separar os bons e ruins ###########
    ########## Gerencia os dados bons e ruins, e cria o sumário ##############
    ##########################################################################

    # Cria um DataFrame vazio para o sumário com as colunas necessárias
    summary_df = pd.DataFrame(columns=['qid',  'estacao', 'tipo', 'status', 'code',
                                       'data_detecao' , 'data_tratamento', 'problema',  'path'])

    # Prequalifica os dados, separando os bons e ruins, e retorna o resumo
    code_data, good_data, bad_data, problemas = prequalificarDado(data, estacao, logger)
    # Cria um DataFrame para os dados bons
    if len(good_data) > 0:
        for gdata in good_data:
            # Inicio do mês
            start = gdata['timestamp'].min().replace(day=1).normalize()
            # Fim do mês (último dia às 23:59:59)
            end = (start + pd.offsets.MonthEnd(1)).replace(hour=23, minute=59, second=59)
            # Preenche o arquivo com o índice mensal
            novo_indice = pd.date_range(start=start, end=end, freq=expct_freq)

            # Preenche a coluna 'acronym' com o nome da estação e adiciona colunas de ano, dia e minuto
            gdata['acronym'] = estacao.upper()
            gdata['year'] = gdata['timestamp'].dt.year.fillna(method='ffill')
            gdata['day'] = gdata['timestamp'].dt.dayofyear.fillna(method='ffill')
            gdata['min'] = gdata['timestamp'].dt.hour * 60 + gdata['timestamp'].dt.minute
            gdata['min'] = gdata['min'].astype(int)
            # Seta
            gdata = gdata.set_index('timestamp')
            
            # Verificar e tratar timestamps duplicados antes do reindex
            if gdata.index.duplicated().any():
                # Opção 1: Manter apenas a primeira ocorrência
                gdata = gdata[~gdata.index.duplicated(keep='first')]
            gdata = gdata.reindex(novo_indice)
            gdata = gdata.rename_axis('timestamp')

            # Adiciona cabeçalho ao DataFrame
            try:
                sub_header = header_sensor[estacao][file_type]
            except KeyError:
                # Registra o erro usando o logger
                logger.error(f"Error 5 - Não foi possível encontrar o cabeçalho para a estação {estacao} e tipo {file_type} no arquivo {file_path}, um subcabeçalho vazio será adicionado.")
                sub_header = [''] * len(gdata.columns)
                continue
            # Adiciona o subcabeçalho ao DataFrame
            sub_header = ['', '', '', '', ''] + sub_header
            gdata.columns = pd.MultiIndex.from_tuples(list(zip(gdata.columns, sub_header)))
            # Cria o caminho do arquivo de dados bons
            file_name = f"{estacao.upper()}_{start.year}_{start.month:02d}_{file_type}_formatado.csv"
            output_path = os.path.join(output_dir, estacao.upper(), tipo_completo, str(start.year))
            file_path = os.path.join(output_path, file_name)
            # Cria o diretório se não existir
            pathlib.Path(output_path).mkdir(parents=True, exist_ok=True)

            # Verifica se o arquivo já existe
            if os.path.exists(file_path):
                if not overwrite:
                    logger.warning(f"Arquivo {file_path} já existe e a flag de sobrescrever está desativada. Pulando...")
                    continue
                else:
                    # Abre o arquivo existente
                    edata = pd.read_csv(file_path)
                    # Comparada dados edata e gdata e substitui apenas o que for diferente
                    edata = edata.set_index('timestamp')
                    # Atualiza dados formatados
                    gdata.update(edata)
                    # Reseta o índice e salva o arquivo
                    gdata = gdata.reset_index()
                    gdata['acronym'] = estacao.upper()
                    gdata['year'] = gdata['timestamp'].dt.year.fillna(method='ffill')
                    gdata['day'] = gdata['timestamp'].dt.dayofyear.fillna(method='ffill')
                    gdata['min'] = gdata['timestamp'].dt.hour * 60 + gdata['timestamp'].dt.minute
                    gdata['min'] = gdata['min'].astype(int)
                    gdata.to_csv(file_path, index=False)
            else:
                # Reseta o índice e salva o arquivo
                gdata = gdata.reset_index()
                gdata['acronym'] = estacao.upper()
                gdata['year'] = gdata['timestamp'].dt.year.fillna(method='ffill')
                gdata['day'] = gdata['timestamp'].dt.dayofyear.fillna(method='ffill')
                gdata['min'] = gdata['timestamp'].dt.hour * 60 + gdata['timestamp'].dt.minute
                gdata['min'] = gdata['min'].astype(int)
                gdata.to_csv(file_path, index=False)

        # Dados ruins
        if len(bad_data) > 0:
            # loop para cada DataFrame de dados ruins
            for bdata in range(len(bad_data)):
                # Pega código do erro
                code = code_data[bdata]
                # Pega dados ruins
                bdata_df = bad_data[bdata]
                # Pega problemas
                problema = problemas[bdata]
                # adiciona acronym
                bdata_df['acronym'] = estacao.upper()
                # Acronimo deve ser a segunda coluna do dataframe
                bdata_df.insert(1, 'acronym', bdata_df.pop('acronym'))
                # Transforma coluna timestamp em string
                bdata_df['timestamp'] = bdata_df['timestamp'].astype(str)
                min_stamp = bdata_df['timestamp'].min()
                max_stamp = bdata_df['timestamp'].max()
                # Como min_stamp é uma string, remove - e : e / e transforma em YYYYMMDD
                min_stamp = min_stamp.replace('-', '').replace(':', '').replace('/', '').replace('"', '')
                max_stamp = max_stamp.replace('-', '').replace(':', '').replace('/', '').replace('"', '')
                # Pega só primeira parte do timestamp
                min_stamp = min_stamp.split(' ')[0]
                max_stamp = max_stamp.split(' ')[0]
                # Monta o caminho do arquivo de dados ruins
                file_name = f"{estacao.upper()}_{str(code)}_{min_stamp}_{max_stamp}_{file_type}_quarentena.csv"
                # O Diretorio de quarentena é o mesmo que output_dir porém em vez de sonda-formatados, é sonda-quarentena
                quarentena_dir = pathlib.Path(output_dir).parent / 'sonda-quarentena'
                output_path = os.path.join(quarentena_dir, estacao.upper(), tipo_completo)
                file_path = os.path.join(output_path, file_name)
                # Cria o diretório se não existir
                pathlib.Path(output_path).mkdir(parents=True, exist_ok=True)
                # Verifica se o arquivo já existe
                if os.path.exists(file_path):
                        continue
                # Salva o DataFrame de dados ruins
                bdata_df.to_csv(file_path, index=False)
                # Atualiza o sumário com os dados ruins
                summary_df = pd.concat([summary_df, pd.DataFrame([{
                    'estacao': estacao.upper(),
                    'tipo': file_type,
                    'status': 'Ruim',
                    'code': code,
                    'data_detecao': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'data_tratamento': None,
                    'problema': problema,
                    'path': file_path
                }])], ignore_index=True)
    # Retorna o DataFrame de sumário
    return summary_df