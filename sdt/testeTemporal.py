import pandas as pd

def testeTemporal(df, estacao, logger):
    """
    Novo teste temporal para verificar a consistência dos dados temporais.
    Args:
        df (pd.DataFrame): DataFrame contendo os dados temporais.
    Returns:
        str: Mensagem de erro se houver problemas, ou string vazia se tudo estiver correto.
    """

    # Salva o DataFrame original para referência
    df_orig = df.copy()
    
    # Critério 1: Se todos os valores de 'timestamp' forem nulos, não é possível realizar o teste
    if df['timestamp'].isnull().all():
        return (1, "todos os valores de 'timestamp' são nulos, "
            "não é possível realizar o teste temporal."
        , df_orig)
    # Critério 2: se mais de 50% dos valores de 'timestamp' forem nulos, não é possível realizar o teste
    elif (df['timestamp'].isnull().sum() / len(df)) > 0.5:
        # Retorna uma mensagem de erro e o DataFrame original
        return (2, "mais de 50% dos valores de 'timestamp' são nulos, "
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
        return (3,
            f"datas diferentes encontradas, esperado: {df['timestamp'].dt.date.iloc[0]}, "
            f"encontrados: {timestamps}, "
        , df_orig)
    ## Critério 4. A progressão de cada dia deve ser monotônica e crescente
    elif not df['timestamp'].is_monotonic_increasing:
        # Método simples: compara cada timestamp com o próximo
        problemas = []
        for i in range(len(df) - 1):
            if pd.notna(df['timestamp'].iloc[i]) and pd.notna(df['timestamp'].iloc[i + 1]):
                if df['timestamp'].iloc[i] >= df['timestamp'].iloc[i + 1]:
                    problemas.append(df['timestamp'].iloc[i + 1])
        return (4,
            f"progressão de timestamps não é monotônica crescente, "
            f"índices problemáticos: {problemas[:10]}"  # mostra apenas os primeiros 10
        , df_orig
        )
    # Critério 5. Verifica se o numero total de registros dentro de cada intervalo é superior a 12 horas
    elif df['timestamp'].max() - df['timestamp'].min() < pd.Timedelta(hours=8):
        return (5,
            f"intervalo total de timestamps é menor que 8 horas, "
            f"encontrado: {df['timestamp'].max() - df['timestamp'].min()}"
        , df)
    # Critério 6. Verifica se o numero total de registros dentro de cada intervalo é superior a 24 horas
    elif df['timestamp'].max() - df['timestamp'].min() > pd.Timedelta(hours=24):
        return (6,
            f"intervalo total de timestamps é maior que 24 horas, "
            f"encontrado: {df['timestamp'].max() - df['timestamp'].min()}"
        , df)
    # Tratamento. Verificar dia ano, diajuliano, e minuto contem informações vazias em alguma dessas colunas
    elif df[['year', 'day', 'min']].isnull().any(axis=None):
        intervalo = df['timestamp'].max() - df['timestamp'].min()
        # Este error não inválida o teste, mas é importante registrar
        # que os dados não estão completos, e devem ser preenchidos
        # com os valores corretos
        logger.error("WARNING! - Estacao %s: Dados com intervalo de %s, "
                     "mas colunas 'year', 'day' ou 'min' contem valores nulos, "
                     "verifique os dados.",
                     estacao, intervalo)
    return (0, "", df)