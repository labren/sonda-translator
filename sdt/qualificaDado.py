import pandas as pd
import pathlib

def prequalificarDado(df, tipo_dado, logger, estacao, output_dir):
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
        expected_interval = pd.Timedelta(minutes=10)
    elif tipo_dado == 'SD':
        expected_interval = pd.Timedelta(minutes=1)
    elif tipo_dado == 'WD':
        expected_interval = pd.Timedelta(minutes=10)
    else:
        logger.error(f"Error 7 - Error no prequalificaDado: \
            Tipo de dado inválido: {tipo_dado}.")
        return None
    
    # Cria coluna auxiliar 'data' para agrupar por dia
    df['data'] = df['timestamp'].dt.date
    
    # Listas para armazenar as datas consideradas boas ou problemáticas
    good_dates = []
    problematic_dates = []
    # Dicionário para armazenar os problemas encontrados por data
    problems_by_date = {}
    
    # Número esperado de linhas por dia: 24 horas * 60 minutos = 1440
    expected_rows = int(pd.Timedelta("1 day") / expected_interval)
    
    # Itera sobre cada dia
    for date, group in df.groupby('data'):
        group = group.sort_values('timestamp').reset_index(drop=True)
        problemas = []
        
        # Teste 1: Verifica se o primeiro registro é exatamente 00:00:00
        if group.iloc[0]['timestamp'].time() != pd.Timestamp("00:00:00").time():
            problemas.append("início não é 00:00:00")
        
        # Teste 2: Verifica se a quantidade de registros é a esperada
        if len(group) != expected_rows:
            problemas.append("número de linhas incorreto")
        
        # Teste 3: Verifica se os intervalos entre os registros são consistentes
        deltas = group['timestamp'].diff().dropna()
        if not (deltas == expected_interval).all():
            problemas.append("intervalos inconsistentes")
        
        # Se não houver problemas, adiciona a data na lista de dados bons
        if not problemas:
            good_dates.append(date)
        else:
            problematic_dates.append(date)
            # Armazena os tipos de problema encontrados para essa data
            problems_by_date[date] = "; ".join(problemas)
    
    # Separa os dados bons e os problemáticos
    good_data = df[df['data'].isin(good_dates)].copy()
    problem_data = df[df['data'].isin(problematic_dates)].copy()
    
    # Adiciona a coluna 'problem_type' nos dados com problemas
    problem_data['problem_type'] = problem_data['data'].apply(lambda d: problems_by_date.get(d))
    
    # Remove a coluna auxiliar 'data'
    good_data.drop(columns=['data'], inplace=True)
    problem_data.drop(columns=['data'], inplace=True)

    # move a coluna 'problem_type' para o inicio do DataFrame
    # cols = problem_data.columns.tolist()
    # cols.insert(0, cols.pop(cols.index('problem_type')))
    # problem_data = problem_data[cols]
    if not problem_data.empty:
        # Volta um diretorio do output_dir e cria o diretorio sonda_quarentena
        output_dir = pathlib.Path(output_dir).parent / 'sonda_quarentena'
        # Cria o nome do arquivo output_dir/estacao/ano/mes/dia/estacao_ano_mes_dia_problemas.csv
        estacao = estacao.upper()
        output_dir = output_dir / estacao
        # Cria o nome do arquivo
        problem_file = output_dir / f"{estacao}_{tipo_dado}_problemas.csv"
        # Cria o diretório se não existir
        output_dir.mkdir(parents=True, exist_ok=True)
        # Remove o arquivo existente, se houver cria um novo acrescentando _n
        if problem_file.exists():
            i = 1
            while problem_file.exists():
                problem_file = output_dir / f"{estacao}_problemas_{i}.csv"
                i += 1        
        # Salva os dados problemáticos em um arquivo CSV
        problem_data.to_csv(problem_file, index=False)

    return good_data

    

    