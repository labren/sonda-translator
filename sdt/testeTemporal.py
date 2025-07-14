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
    # Remove linhas onde 'timestamp' é NaT (Not a Time)
    df = df.dropna(subset=['timestamp'])
    # Critério 1: Se todos os valores de 'timestamp' forem nulos, não é possível realizar o teste
    if df['timestamp'].isnull().all():
        return (
            "todos os valores de 'timestamp' são nulos, "
            "não é possível realizar o teste temporal."
        , df_orig)
    # Critério 2: se mais de 50% dos valores de 'timestamp' forem nulos, não é possível realizar o teste
    elif (df['timestamp'].isnull().sum() / len(df)) > 0.5:
        # Retorna uma mensagem de erro e o DataFrame original
        return (
            "mais de 50% dos valores de 'timestamp' são nulos, "
            "não é possível realizar o teste temporal."
        , df_orig)
    # Critério 3. As DATAS dentro de cada intervalo devem ser iguais (mesmo dia)
    # Ou seja, pega o dia do primeiro timestamp e verifica se todos os outros timestamps
    # pertencem ao mesmo dia.
    elif not (df['timestamp'].dt.date == df['timestamp'].dt.date.iloc[0]).all():        
        # Pegue os indices onde o dia é diferente do primeiro dia
        idxs_diferentes = df[df['timestamp'].dt.date != df['timestamp'].dt.date.iloc[0]].index.tolist()
        timestamps = df_orig.loc[idxs_diferentes, 'timestamp']
        # Remove os caracters invalidos dos timestamps
        timestamps = timestamps.astype(str).str.replace(r'[^0-9:/\-\s]', '', regex=True)
        # Pega só a parte inicial do timestamp
        timestamps = [ts.split(' ')[0] for ts in timestamps.tolist()]
        # Apenas valores unicos
        timestamps = list(set(timestamps))
        return (
            f"datas diferentes encontradas, esperado: {df['timestamp'].dt.date.iloc[0]}, "
            f"encontrados: {timestamps}, "
        , df_orig)
    ## Critério 4. A progressão de cada dia deve ser monotônica e crescente
    elif not df['timestamp'].is_monotonic_increasing:
        # Encontre os indices onde a progressão não é monotônica
        try:
            idxs_nao_monotonicos = df[~df['timestamp'].is_monotonic_increasing].index.tolist()
        except Exception as e:
            idxs_nao_monotonicos = []
        return (
            f"progressão de timestamps não é monotônica crescente, "
            f"índices problemáticos: {idxs_nao_monotonicos}"
        , df_orig
        )
    # Critério 4. Verifica se o numero total de registros dentro de cada intervalo é superior a 12 horas
    elif df['timestamp'].max() - df['timestamp'].min() < pd.Timedelta(hours=12):
        return (
            f"intervalo total de timestamps é menor que 12 horas, "
            f"encontrado: {df['timestamp'].max() - df['timestamp'].min()}"
        , df)

    return ("", df)