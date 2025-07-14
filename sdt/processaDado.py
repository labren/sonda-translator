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
        print(file_path)
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
            ignore_errors=true, strict_mode=false)
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

    ############################################################################
    ### Parte 2 - Ler o arquivo novamente com o cabeçalho e a linha de dados ###
    ############################################################################
    # Abre o arquivo novamente, agora com o cabeçalho e a linha de dados encontrados
    try:
        data = duckdb.query(f"""
            SELECT * 
            FROM read_csv_auto('{file_path}',
            ignore_errors=true,
            skip={data_row})
            LIMIT 10000
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
    # Agora, baseado no tipo iremos procurar o verdadeiro nome das colunas
    main_header = headers[file_type]
    try:
        main_header = headers[file_type]
    except KeyError:
        # Registra o erro usando o logger
        logger.error(f"Error 4 - Não foi possível encontrar o cabeçalho para o tipo {file_type} no arquivo {file_path}.")
        return pd.DataFrame()
    # Cria um dicionário para mapear os cabeçalhos encontrados para os cabeçalhos principais
    # O dicionário será criado com os valores do cabeçalho principal como chaves
    normalized_headers = {}
    for key, values in main_header.items():
        for value in values:
            normalized_headers[value.strip().upper()] = key
    renamed_columns = {}
    for col in data.columns:
        if str(col).strip().upper() in normalized_headers:
            renamed_columns[col] = normalized_headers[str(col).strip().upper()]
    
    # Renomeia as colunas do DataFrame com os nomes encontrados
    if renamed_columns:
        data = data.rename(columns=renamed_columns)
    
    # Verifica se o cabeçalho principal tem o mesmo número de colunas que o arquivo
    # Isso irá deixar os dados já organizados para o formato correto
    result = pd.DataFrame()
    for key in main_header.keys():
        result[key] = data.get(key, pd.NA)

    # Pega colunas que não foram renomeadas e separa em um novo DataFrame
    outros_dados = data.drop(columns=main_header.keys(), errors='ignore')
    # Verifica se tem outros dados e cria um log
    if not outros_dados.empty:
        # Registra o erro usando o logger
        logger.error(f"WARNING - O arquivo {file_path} contém colunas que não foram processadas: {outros_dados.columns.tolist()}")

    # Converte acronym para maiúsculas
    # result['acronym'] = estacao.upper()
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

    ############################################################################
    ### Parte 3 - Pré-Qualificar os dados e salvar o arquivo formatado ###############
    ############################################################################

    # Cria um DataFrame vazio para o sumário com as colunas necessárias
    summary_df = pd.DataFrame(columns=['qid', 'estacao', 'tipo', 'tipo_completo' ,
                                       'data_tratamento', 'status', 'problema', 'data_detecao' , 'path'])

    # Prequalifica os dados, separando os bons e ruins, e retorna o resumo
    good_data, bad_data, summary = prequalificarDado(result, file_type, logger, estacao, output_dir, tipo_completo)

    # Cria um DataFrame para os dados bons
    if len(good_data) > 0:
        for gdata in good_data:
            # Inicio do mês
            start = gdata['timestamp'].min().replace(day=1).normalize()
            # Fim do mês (último dia às 23:59:59)
            end = (start + pd.offsets.MonthEnd(1)).replace(hour=23, minute=59, second=59)
            # Preenche o arquivo com o índice mensal
            novo_indice = pd.date_range(start=start, end=end, freq=expct_freq)
            gdata = gdata.set_index('timestamp')
            gdata = gdata.reindex(novo_indice)
            gdata = gdata.rename_axis('timestamp')
            # Preenche a coluna 'acronym' com o nome da estação
            gdata['acronym'] = estacao.upper()
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
                    print(f'Arquivo {file_path} já existe e a flag de sobrescrever está desativada. Pulando...')
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
                    gdata.to_csv(file_path, index=False)
            else:
                # Reseta o índice e salva o arquivo
                gdata = gdata.reset_index()
                gdata.to_csv(file_path, index=False)



            # print(f"Processando dados bons de {estacao.upper()} do tipo {file_type} de {start} até {end}")


        # Concatena os dados bons
        # good_data = pd.concat(good_data, ignore_index=True)


        # Dados bons devem ser reagrupados por mês e separados em arquivos
        # monthly_good_data = good_data.groupby(good_data['timestamp'].dt.to_period('M'))
        # # Loop para escrever os dados bons em arquivos separados
        # for period, group in monthly_good_data:
        #     # Remove duplicatas no timestamp
        #     group = group.drop_duplicates(subset='timestamp')
        #     # 1. Início do mês
        #     start = group['timestamp'].min().replace(day=1).normalize()
        #     # 2. Fim do mês (último dia às 23:59:59)
        #     end = (start + pd.offsets.MonthBegin(1)).replace(day=1) + pd.offsets.MonthEnd(0)
        #     end = end + pd.Timedelta(hours=23, minutes=59, seconds=59)
        #     # 3. Criar novo índice mensal com a frequência desejada
        #     novo_indice = pd.date_range(start=start, end=end, freq=expct_freq)
        #     # 4. Reindexar e preencher
        #     group = group.set_index('timestamp')
        #     group = group.reindex(novo_indice)
        #     group = group.rename_axis('timestamp').reset_index()
        #     group['acronym'] = estacao.upper()
            
            # print(group)
            # Verifica se arquivo já existe


    return summary_df

    
# Adiciona subcabeçalho ao DataFrame
        # try:
        #     sub_header = header_sensor[estacao][file_type]
        # except KeyError:
        #     # Registra o erro usando o logger
        #     logger.error(f"Error 6 - Não foi possível encontrar o cabeçalho para a estação {estacao} e tipo {file_type} no arquivo {file_path}, um subcabeçalho vazio será adicionado.")
        #     sub_header = [''] * len(good_df.columns)
        # # Adiciona o subcabeçalho ao DataFrame
        # sub_header = ['', '', '', '', ''] + sub_header
        # good_df.columns = pd.MultiIndex.from_tuples(list(zip(good_df.columns,sub_header)))


    # try:
    #     # Agrupa por mês e cria um loop para criar os arquivos
    #     result_groups = result.groupby(result['timestamp'].dt.to_period('M'))
    #     for period, group in result_groups:
    #         # Cria o nome do arquivo, o padrão é: SMS_YYYY_MM_SD_formatado.csv
    #         file_name = f"{estacao.upper()}_{period.year}_{period.month:02d}_{file_type}_formatado.csv"
    #         # O output_path será sempre output_dir + estacao + tipo_completo + ano
    #         output_path = os.path.join(output_dir, estacao.upper(), tipo_completo, str(period.year))
    #         # Verifica se o arquivo já existe, caso exista verifica flag de overwrite, acaso não exista, cria o arquivo, caso exista e a flag overwrite for False, pula a criação do arquivo
    #         file_path = os.path.join(output_path, file_name)
    #         # Cria diretorio caso não exista
    #         pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    #         # Verifica se existem linhas duplicadas
    #         if group.duplicated().any():
    #             # Registra o erro usando o logger
    #             # logger.error(f"WARNING - O arquivo {file_path} contém linhas duplicadas.")
    #             # Remove as linhas duplicadas
    #             group = group.drop_duplicates()
    #         # Verifica se o arquivo já existe
    #         if os.path.exists(file_path):
    #             if not overwrite:
    #                 continue
    #             else:
    #                 group.to_csv(file_path, index=False)
    #         else:
    #             # Cria diretorio caso não exista
    #             pathlib.Path(output_path).mkdir(parents=True, exist_ok=True)
    #             # Cria o arquivo
    #             group.to_csv(file_path, index=False)
    # except:
    #     # Registra o erro usando o logger
    #     logger.error(f"Não foi possível criar o arquivo {file_path} durante o processo de salvar os dados.\nDetalhes do erro: {result}")
    #     return summary
        
    # Retorna o resumo dos dados
    # return summary
