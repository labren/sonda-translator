import os
import duckdb
import pandas as pd
import pathlib
import warnings
from prequalificaDado import prequalificarDado
from carregaCabecalhos import cabecalhoManual
warnings.filterwarnings("ignore")


def _ler_csv_tolerante(file_path, **opcoes):
    """
    Lê um arquivo CSV/.dat de forma tolerante a diferentes formatos, SEM alterar
    os valores lidos. Primeiro tenta a detecção automática de dialeto do DuckDB;
    se o sniffer não conseguir determinar o dialeto (ex.: linhas fora do padrão
    CSV, cabeçalhos heterogêneos), refaz a leitura com parâmetros explícitos e em
    modo não-estrito.

    Args:
        file_path: caminho do arquivo.
        **opcoes: parâmetros extras do read_csv (ex.: all_varchar=True, skip=N)
            que sobrescrevem os padrões.
    Returns:
        pd.DataFrame com o conteúdo lido.
    """
    base = {
        'header': False,         # cabeçalho é localizado manualmente
        'ignore_errors': True,   # ignora linhas malformadas isoladas
        'null_padding': True,    # completa linhas curtas (ex.: linha de ambiente)
        'sample_size': -1,       # varre o arquivo todo para fixar a largura
    }
    base.update(opcoes)

    def _montar(opts):
        partes = []
        for chave, valor in opts.items():
            if isinstance(valor, bool):
                partes.append(f"{chave}={'true' if valor else 'false'}")
            elif isinstance(valor, str):
                partes.append(f"{chave}='{valor}'")
            else:
                partes.append(f"{chave}={valor}")
        return ", ".join(partes)

    # Cadeia de tentativas, da mais automática para a mais permissiva. Nenhuma
    # delas altera os valores — só mudam a forma de interpretar o arquivo.
    # O fallback usa parallel=false: o leitor paralelo do DuckDB não suporta
    # null_padding junto com quebras de linha dentro de campos entre aspas
    # (quoted new lines). A 1ª tentativa mantém a leitura paralela (rápida) para
    # os arquivos normais; só os problemáticos caem para a leitura serial.
    permissivo = dict(base, delim=',', quote='"', escape='"', strict_mode=False,
                      parallel=False, max_line_size=10_000_000)
    tentativas = [
        base,                                      # 1) detecção automática de dialeto (paralelo)
        permissivo,                                # 2) dialeto SONDA (vírgula+aspas), serial, não-estrito
        dict(permissivo, encoding='latin-1'),      # 3) idem, tolerante a bytes não-UTF-8
    ]
    erro = None
    for opts in tentativas:
        try:
            return duckdb.query(
                f"SELECT * FROM read_csv_auto('{file_path}', {_montar(opts)})"
            ).df()
        except Exception as e:
            erro = e
    # Se todas falharem, propaga o último erro para o chamador tratar/logar.
    raise erro


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
    file_path, estacao, file_type, output_dir, overwrite, logger, headers, header_sensor, manual_header = args

    # Check if the file exists
    if not os.path.exists(file_path):
        return pd.DataFrame()
    ############################################################################
    ############ Parte 1 - Encontrar o cabeçalho e a linha de dados ############
    ############################################################################
    # ---- Leitura BRUTA, somente para detectar a ESTRUTURA do arquivo ----
    # Esta leitura NÃO é usada como dado final; serve apenas para localizar a
    # linha de cabeçalho, a linha de dados e extrair os nomes das colunas. Ler em
    # duas passagens com read_csv_auto independentes fazia o DuckDB inferir
    # larguras diferentes (ex.: 8 colunas na amostra x 40 nos dados), provocando o
    # "Length mismatch" ao atribuir o cabeçalho. Aqui forçamos uma largura única e
    # consistente, sem alterar nenhum valor:
    #   - header=false: nenhuma linha é tratada como cabeçalho (achamos manualmente)
    #   - all_varchar=true: tudo como texto, apenas para inspeção estrutural
    #   - null_padding=true: completa linhas curtas (ex.: linha de ambiente do TOA5)
    #   - sample_size=-1: varre o arquivo todo para detectar o nº máximo de colunas
    try:
        raw = _ler_csv_tolerante(file_path, all_varchar=True)
    except Exception as e:
        logger.error(f"Error 1 - Não foi possível ler o arquivo {file_path} \
            durante o processo de encontrar dados.\nDetalhes do erro: {str(e)}")
        print(f"Error 1 - Não foi possível ler o arquivo {file_path} \
            durante o processo de encontrar dados.\nDetalhes do erro: {str(e)}")
        return pd.DataFrame()

    # Se o arquivo está vazio ou não pôde ser interpretado, não há o que processar.
    if raw.empty:
        logger.error(f"Error 1 - Arquivo {file_path} está vazio ou não pôde ser lido.")
        print(f"Error 1 - Arquivo {file_path} está vazio ou não pôde ser lido.")
        return pd.DataFrame()

    # Encontra a linha de cabeçalho nas primeiras linhas do arquivo. A linha de
    # cabeçalho deve conter qualquer uma das palavras-chave abaixo.
    # TODO: Verificar em alguns casos pois as variáveis podem não ser exatamente desta forma.
    header_row = None
    for i in range(min(len(raw), 10)):
        if any(keyword in str(raw.iloc[i]) for keyword in ['TIMESTAMP', 'RECORD', 'Id', 'Year', 'Jday', 'Min']):
            header_row = i
            break

    # Define os nomes das colunas (header_names) a partir do manual_header, da
    # linha de cabeçalho detectada ou, em último caso, da primeira linha. Como
    # raw tem largura única (null_padding), header_names já vem completo.
    if manual_header:
        header_names = cabecalhoManual(manual_header, logger)
        file_type = manual_header[1].upper()
        if header_names is None:
            logger.error(f"Error 2 - Cabeçalho manual inválido para o arquivo {file_path}.")
            print(f"Error 2 - Cabeçalho manual inválido para o arquivo {file_path}.")
            return pd.DataFrame()
    else:
        try:
            origem = 0 if header_row is None else header_row
            header_names = raw.iloc[origem].tolist()
        except Exception:
            logger.error(f"Error 2 - Não foi possível encontrar o cabeçalho no arquivo {file_path}.")
            print(f"Error 2 - Não foi possível encontrar o cabeçalho no arquivo {file_path}.")
            return pd.DataFrame()

    # Encontra a primeira linha de dados: aquela em que a maioria dos valores é numérica.
    data_row = 0
    for i in range(len(raw)):
        numeric_row = pd.to_numeric(raw.iloc[i], errors='coerce')
        if numeric_row.notna().sum() > len(raw.columns) / 2:
            data_row = i
            break

    ############################################################################
    ### Parte 2 - Lê os dados a partir da linha de dados e aplica o cabeçalho ###
    ############################################################################
    # Lê novamente, mas agora pulando até a linha de dados (skip=data_row) e
    # deixando o read_csv_auto inferir os tipos NORMALMENTE — os valores NÃO são
    # manipulados, apenas lidos. header=false evita consumir uma linha de dados
    # como cabeçalho; null_padding mantém a largura estável.
    try:
        data = _ler_csv_tolerante(file_path, skip=data_row)
    except Exception as e:
        logger.error(f"Error 2 - Não foi possível ler o arquivo {file_path} \
            durante o processo de encontrar dados.\nDetalhes do erro: {str(e)}")
        print(f"Error 2 - Não foi possível ler o arquivo {file_path} \
            durante o processo de encontrar dados.\nDetalhes do erro: {str(e)}")
        return pd.DataFrame()

    # Ajusta o tamanho dos NOMES do cabeçalho ao número de colunas dos dados em vez
    # de falhar (apenas nomes de coluna são ajustados — nenhum dado é alterado):
    # completa nomes faltantes e descarta os excedentes.
    header_names = [str(col).strip('"').strip() for col in header_names]
    n_cols = data.shape[1]
    if len(header_names) < n_cols:
        logger.warning(f"WARNING - Cabeçalho do arquivo {file_path} tem {len(header_names)} nomes \
para {n_cols} colunas. Completando com nomes genéricos.")
        header_names += [f'coluna_{j}' for j in range(len(header_names), n_cols)]
    elif len(header_names) > n_cols:
        logger.warning(f"WARNING - Cabeçalho do arquivo {file_path} tem {len(header_names)} nomes \
para {n_cols} colunas. Descartando nomes excedentes.")
        header_names = header_names[:n_cols]
    data.columns = header_names
    # Pega o cabeçalho principal baseado no file_type
    try:
        main_header = headers[file_type]
    except KeyError:
        # Registra o erro usando o logger
        logger.error(f"Error 4 - Não foi possível encontrar o cabeçalho para o tipo {file_type} no arquivo {file_path}.")
        print(f"Error 4 - Não foi possível encontrar o cabeçalho para o tipo {file_type} no arquivo {file_path}.")
        return pd.DataFrame()

    # Remove aspas duplas dos nomes das colunas    
    data.columns = data.columns.str.strip('"')

    # Normaliza os aliases e cria um mapeamento reverso com todos em maiúsculas
    mapa_colunas = {}
    for key, aliases in main_header.items():
        for alias in aliases:
            mapa_colunas[alias.upper()] = key
    # Também normaliza os nomes de colunas do DataFrame
    try:
        data.columns = [col.upper().strip('"') for col in data.columns]
    except:
        logger.error(f"Error 5 - Não foi possível normalizar os nomes das colunas do arquivo {file_path}.")
        print(f"Error 5 - Não foi possível normalizar os nomes das colunas do arquivo {file_path}.")
        return pd.DataFrame()

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

    # Encontra o tipo completo baseado no file_type
    tipo_completo = ''
    if file_type == 'MD':
        tipo_completo = 'Meteorologicos'
    elif file_type == 'SD':
        tipo_completo = 'Solarimetricos'
    elif file_type == 'WD':
        tipo_completo = 'Anemometricos'

    ##########################################################################
    ### Parte 3 - Prequalificar os dados e separar os bons e ruins ###########
    ########## Gerencia os dados bons e ruins, e cria o sumário ##############
    ##########################################################################

    # Cria um DataFrame vazio para o sumário com as colunas necessárias
    summary_df = pd.DataFrame(columns=['qid',  'estacao', 'tipo', 'status', 'code',
                                       'data_detecao' , 'data_tratamento', 'problema',  'path'])

    # Prequalifica os dados, separando os bons e ruins, e retorna o resumo
    code_data, good_data, bad_data, problemas = prequalificarDado(data, estacao, 
                                                                  logger,  header_sensor, file_type, file_path)
    
    # Loop para salvar dados bons
    if len(good_data) > 0:
        for gdata in good_data:
            # Cria o caminho do arquivo de dados bons
            start = gdata['timestamp'].min()
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
                    # Reseta o índice e salva o arquivo)
                    gdata.to_csv(file_path, index=False)
            gdata.to_csv(file_path, index=False)

        # Loop para salvar dados ruins na quarentena
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