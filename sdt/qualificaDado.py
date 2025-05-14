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
        elif len(group) != expected_rows:
            # Procure por registros com timestamp fora do intervalo esperado
            # e adicione os índices problemáticos
            problematic_indices = group[(group['timestamp'] < group.iloc[0]['timestamp']) | 
                                        (group['timestamp'] > group.iloc[-1]['timestamp'])].index
            if not problematic_indices.empty:
                problemas.append(f"registros fora do intervalo esperado, \
                    índices: {problematic_indices.tolist()}")
            # Adicione o problema de número de linhas
            if len(group) < expected_rows:
                problemas.append(f"número de linhas menor que o esperado, \
                    esperado: {expected_rows}, encontrado: {len(group)}")
            else:
                problemas.append(f"número de linhas maior que o esperado, \
                    esperado: {expected_rows}, encontrado: {len(group)}")
        
        # Teste 3: Verifica se os intervalos entre os registros são consistentes
        elif not (group['timestamp'].diff().dropna() == expected_interval).all():
            deltas = group['timestamp'].diff().dropna()
            # Encontre os índices onde o intervalo não é o esperado
            inconsistent_intervals = deltas[deltas != expected_interval].index
            problemas.append(f"intervalos inconsistentes entre os registros, \
                índices: {inconsistent_intervals.tolist()}")
        
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

    if not problem_data.empty:
        # Volta um diretorio do output_dir e cria o diretorio sonda_quarentena
        quarentena_dir = pathlib.Path(output_dir).parent / 'sonda_quarentena'
        # Converte estação para maiúsculo
        estacao = estacao.upper()
        # Cria o diretório base da estação
        estacao_dir = quarentena_dir / estacao
        estacao_dir.mkdir(parents=True, exist_ok=True)
        
        # Agrupa os dados problemáticos por dia e salva cada dia em um arquivo separado
        for date in problematic_dates:
            # Filtra dados apenas deste dia
            day_data = df[df['data'] == date].copy()
            # Remove a coluna auxiliar 'data'
            day_data.drop(columns=['data'], inplace=True)
            # Adiciona a coluna de tipo de problema
            # day_data['problem_type'] = problems_by_date.get(date)
            
            # Cria nome do arquivo com data (YYYY-MM-DD)
            date_str = date.strftime('%Y-%m-%d')
            problem_file = estacao_dir / f"{estacao}_{tipo_dado}_{date_str}_problemas.csv"
            
            # Cria diretório por ano/mês (opcional)
            year_month_dir = estacao_dir / f"{date.year}/{date.month:02d}"
            year_month_dir.mkdir(parents=True, exist_ok=True)
            problem_file = year_month_dir / f"{estacao}_{tipo_dado}_{date_str}_problemas.csv"
            
            # Salva os dados problemáticos deste dia no arquivo CSV
            day_data.to_csv(problem_file, index=False)
            
            # Log para acompanhamento
            logger.info(f"Dados problemáticos do dia {date_str} salvos em: {problem_file}")

        # Opcional: salvar também um sumário com todos os dias problemáticos
        summary_file = estacao_dir / f"{estacao}_{tipo_dado}_sumario_problemas.csv"
        # Abre o arquivo de sumário, se já existir, para adicionar os novos dados
        if summary_file.exists():
            summary_df = pd.read_csv(summary_file)
        else:
            summary_df = pd.DataFrame()
        # Pega o maior qid do sumário
        if not summary_df.empty:
            max_qid = summary_df['qid'].max()
        else:
            max_qid = 0
        # Adiciona os dados problemáticos ao sumário
        problem_summary = pd.DataFrame({
            'qid': range(max_qid + 1, max_qid + len(problematic_dates) + 1),
            'estacao': estacao,
            'tipo_dado': tipo_dado,
            'data': problematic_dates,
            'problema': [problems_by_date.get(d) for d in problematic_dates],
            'path': [estacao_dir / f"{estacao}_{tipo_dado}_{d.strftime('%Y-%m-%d')}_problemas.csv" for d in 
            problematic_dates],
            'status': 'quarentena'
        })
        # Trata espaços em branco de problemas, substitui por um unico espaço
        problem_summary['problema'] = problem_summary['problema'].str.replace(r'\s+', ' ', regex=True)

        # Antes de concatenar, verifica se o DataFrame o dado já foi tratado, ou seja, se o status é diferente de 'quarentena', isso deve ser feito com uma comparação entre summary_df e problem_summary
        if not summary_df.empty:
            # Verifica se o dado já foi tratado
            treated_data = summary_df[summary_df['status'] != 'quarentena']
            # Adiciona os dados tratados ao sumário
            summary_df = pd.concat([summary_df, treated_data], ignore_index=True)
        # Concatena os dados problemáticos com o sumário
        summary_df = pd.concat([summary_df, problem_summary], ignore_index=True)
        # Remove duplicatas, mantendo o último para todas as colunas
        summary_df.drop_duplicates(subset=['path'], keep='last', inplace=True)        
        # Ordena pelo qid
        summary_df.sort_values(by='qid', ascending=True, inplace=True)
        # Salva o sumário atualizado
        summary_file = estacao_dir / f"{estacao}_{tipo_dado}_sumario_problemas.csv"
        summary_df.to_csv(summary_file, index=False)

    return good_data



