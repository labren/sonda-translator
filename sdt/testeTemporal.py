import pandas as pd

def testeTemporal(df, expected_rows, expct_freq, expected_last_time):
    """
    Novo teste temporal para verificar a consistência dos dados temporais.
    Args:
        df (pd.DataFrame): DataFrame contendo os dados com uma coluna 'timestamp'.
        expected_rows (int): Número esperado de linhas por dia.
        expct_freq (pd.Timedelta): Intervalo esperado entre os registros.
        expected_last_time (datetime.time): Último horário esperado no dia.
    Returns:
        str: Mensagem de erro se houver problemas, ou string vazia se tudo estiver correto.
    """

    # Salva o DataFrame original para referência
    df_orig = df.copy()

    # Tratamento 1: Verifica se existem características inválidas na coluna 'timestamp'
    df['timestamp'] = df['timestamp'].astype(str).str.replace(r'[^0-9:/\-\s]', '', regex=True)
    # Tratamento 2: Converte a coluna 'timestamp' para datetime, ignorando erros
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    # Critério 1. As DATAS dentro de cada intervalo devem ser iguais (mesmo dia)
    # Ou seja, pega o dia do primeiro timestamp e verifica se todos os outros timestamps
    # pertencem ao mesmo dia.
    dia_dado = df['timestamp'].dt.date.iloc[0]
    if not (df['timestamp'].dt.date == dia_dado).all():
        # Pegue os indices onde o dia é diferente do primeiro dia
        idxs_diferentes = df[df['timestamp'].dt.date != dia_dado].index.tolist()
        timestamps = df_orig.loc[idxs_diferentes, 'timestamp']
        # Remove os caracters invalidos dos timestamps
        timestamps = timestamps.astype(str).str.replace(r'[^0-9:/\-\s]', '', regex=True)
        # Pega só a parte inicial do timestamp
        timestamps = [ts.split(' ')[0] for ts in timestamps.tolist()]
        # Apenas valores unicos
        timestamps = list(set(timestamps))
        return (
            f"datas diferentes encontradas, esperado: {dia_dado}, "
            f"encontrados: {timestamps}, "
        , df_orig)
    ## Critério 2. A progressão de cada dia deve ser monotônica e crescente
    elif not df['timestamp'].is_monotonic_increasing:
        # Encontre os indices onde a progressão não é monotônica
        idxs_nao_monotonicos = df[~df['timestamp'].is_monotonic_increasing].index.tolist()
        return (
            f"progressão de timestamps não é monotônica crescente, "
            f"índices problemáticos: {idxs_nao_monotonicos}"
        )
    # Critério 3. Verifica se o numero total de registros dentro de cada intervalo é superior a 12 horas
    elif df['timestamp'].max() - df['timestamp'].min() < pd.Timedelta(hours=12):
        return (
            f"intervalo total de timestamps é menor que 12 horas, "
            f"encontrado: {df['timestamp'].max() - df['timestamp'].min()}"
        , df)

    # Tratamento para dados bons
    # Reamostra o DataFrame para Completar o intervalo esperado
    start = df['timestamp'].min().normalize()
    end = start + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    novo_indice = pd.date_range(start=start, end=end, freq=expct_freq)
    df = df.set_index('timestamp')
    df = df.reindex(novo_indice)
    df = df.rename_axis('timestamp').reset_index()

    # Preenche os valores NaN da coluna 'acronym' com o valor da primeira linha
    df['acronym'] = df['acronym'].fillna(method='ffill')

    return ("", df)