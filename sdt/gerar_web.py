import os
import duckdb
import pandas as pd
import pathlib
import logging

# Colunas de metadados (sempre as 5 primeiras, sem unidade e sem _dqc).
META_COLS = ['acronym', 'timestamp', 'year', 'day', 'min']

# Configuração por tipo de dado. Cada variável é (coluna_no_parquet, nome_web, unidade).
# No arquivo web cada variável é seguida da coluna <nome_web>_dqc (controle de qualidade),
# que atualmente sai VAZIA — não há flag de qualidade computado no pipeline.
TIPO_CONFIG = {
    'SD': {
        'parquet': 'Solarimetrica.parquet',
        'tabela': 'solarimetrica',
        'subdir': 'Solarimetrico',
        'titulo': 'Arquivos públicos para distribuição na web',
        'freq': '1min',
        'variaveis': [
            ('glo_avg', 'glo_avg', 'W/m2'),
            ('dir_avg', 'dir_avg', 'W/m2'),
            ('dif_avg', 'dif_avg', 'W/m2'),
            ('lw_calc_avg', 'lw_avg', 'W/m2'),  # parquet não tem 'lw_avg'; usa o longwave calculado
            ('par_avg', 'par_avg', 'µmols/m2.s'),
            ('lux_avg', 'lux_avg', 'klux'),
        ],
    },
    'MD': {
        'parquet': 'Meteorologica.parquet',
        'tabela': 'meteorologica',
        'subdir': 'Meteorologico',
        'titulo': 'Arquivos para distribuição na web',
        'freq': '10min',
        'variaveis': [
            ('tp_sfc', 'tp_sfc', '°C'),
            ('humid_sfc', 'humid_sfc', '%'),
            ('press', 'press', 'mb'),
            ('rain', 'rain', 'mm'),
            ('ws10_avg', 'ws10_avg', 'm/s'),
            ('ws10_std', 'ws10_std', 'm/s'),
            ('wd10_avg', 'wd10_avg', 'deg'),
            ('wd10_std', 'wd10_std', 'deg'),
        ],
    },
    'WD': {
        'parquet': 'Anemometrica.parquet',
        'tabela': 'anemometrica',
        'subdir': 'Anemometrico',
        'titulo': 'Arquivos para distribuição na web',
        'freq': '1min',
        'variaveis': [
            ('ws10_avg', 'ws10_avg', 'm/s'),
            ('ws10_std', 'ws10_std', 'm/s'),
            ('ws10_max', 'ws10_max', 'm/s'),
            ('wd10_avg', 'wd10_avg', 'deg'),
            ('ws25_avg', 'ws25_avg', 'm/s'),
            ('ws25_std', 'ws25_std', 'm/s'),
            ('ws25_max', 'ws25_max', 'm/s'),
            ('wd25_avg', 'wd25_avg', 'deg'),
            ('tp_25', 'tp_25', '°C'),
            ('ws50_avg', 'ws50_avg', 'm/s'),
            ('ws50_std', 'ws50_std', 'm/s'),
            ('ws50_max', 'ws50_max', 'm/s'),
            ('wd50_avg', 'wd50_avg', 'deg'),
            ('tp_50', 'tp_50', '°C'),
        ],
    },
}

# Metadados fixos da rede
SONDA_META = ['SONDA Network', 'http://sonda.ccst.inpe.br', 'sonda@inpe.br']

# Regra histórica: CGR antes de 2021 deve ser publicado como CGU (Campo Grande UNIDERP).
CGU = {'acronym': 'CGU', 'nome': 'Campo Grande UNIDERP',
       'lat': -20.438, 'lon': -54.538, 'alt': 677}

SEP = '\t'


def gerar_web(output_path='output/sonda-banco-dados', tipo='SD'):
    output_path = output_path.replace('sonda-formatados', 'sonda-banco-dados')
    output_path = output_path.replace('sonda-quarentena', 'sonda-banco-dados')
    output_web = output_path.replace('sonda-banco-dados', 'sonda-web')

    if tipo not in TIPO_CONFIG:
        print(f"Tipo de dado '{tipo}' não reconhecido. Use SD, MD ou WD.")
        return
    cfg = TIPO_CONFIG[tipo]

    parquet_path = os.path.join(output_path, cfg['parquet'])
    if not os.path.exists(parquet_path):
        print(f"Arquivo '{parquet_path}' não encontrado. Gere a base com -gerar_base -tipo {tipo}.")
        return

    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler('gerar_web.log'), logging.StreamHandler()]
    )

    # Cabeçalhos derivados da config (iguais para todas as estações)
    web_columns = list(META_COLS)
    units = [''] * len(META_COLS)
    for _, web, unidade in cfg['variaveis']:
        web_columns += [web, f'{web}_dqc']
        units += [unidade, 'dqc']
    ncols = len(web_columns)

    # SELECT do parquet já renomeando as colunas-fonte para o nome web (ex.: lw_calc_avg AS lw_avg)
    select_exprs = list(META_COLS) + [
        f'{src} AS {web}' if src != web else web for src, web, _ in cfg['variaveis']
    ]

    con = duckdb.connect()
    con.execute(f"""
        CREATE OR REPLACE TABLE {cfg['tabela']} AS
        SELECT {', '.join(select_exprs)}
        FROM read_parquet('{parquet_path}', union_by_name=true)
    """)

    estacoes = con.execute(
        f"SELECT DISTINCT acronym FROM {cfg['tabela']} WHERE acronym IS NOT NULL ORDER BY acronym"
    ).fetchall()
    estacoes = [row[0] for row in estacoes]
    print(f"Encontradas {len(estacoes)} estações para o tipo {tipo}.")

    estacoes_df = pd.read_csv('sdt/utils/Tabela-estacao.csv')
    var_web = [web for _, web, _ in cfg['variaveis']]

    for acronym in estacoes:
        print(f"Processando estação: {acronym}")
        info = estacoes_df[estacoes_df['Sigla'] == acronym]
        if info.empty:
            nome = lat = lon = alt = 'Desconhecida'
            logging.error(f"Informações da estação {acronym} não encontradas em sdt/utils/Tabela-estacao.csv.")
        else:
            nome = info['Estação'].values[0]
            lat = info['Latitude'].values[0]
            lon = info['Longitude'].values[0]
            alt = info['Alt.(m)'].values[0]

        df = con.execute(
            f"SELECT * FROM {cfg['tabela']} WHERE acronym = '{acronym}' ORDER BY timestamp"
        ).df()
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Consistência: ano da coluna vs ano do timestamp
        anos_col = set(df['year'].dropna().unique())
        anos_ts = set(df['timestamp'].dt.year.dropna().unique())
        if anos_col != anos_ts:
            logging.warning(f"Estação {acronym}: anos divergentes entre coluna year ({anos_col}) e timestamp ({anos_ts})")

        # Geração anual e mensal
        _salvar_periodos(df, 'anual', df.groupby(df['timestamp'].dt.year),
                         acronym, nome, lat, lon, alt, cfg, tipo, var_web,
                         web_columns, units, ncols, output_web)
        _salvar_periodos(df, 'mensal', df.groupby([df['timestamp'].dt.year, df['timestamp'].dt.month]),
                         acronym, nome, lat, lon, alt, cfg, tipo, var_web,
                         web_columns, units, ncols, output_web)

    con.close()
    print("Processamento concluído.")


def _salvar_periodos(df_full, escopo, grupos, acronym, nome, lat, lon, alt,
                     cfg, tipo, var_web, web_columns, units, ncols, output_web):
    """Itera sobre os grupos (ano, ou ano+mês) e grava um .dat zipado por período."""
    for chave, group in grupos:
        if escopo == 'anual':
            year, month = chave, None
            if pd.isna(year):
                continue
        else:
            year, month = chave
            if pd.isna(year) or pd.isna(month):
                continue

        # Regra CGR -> CGU antes de 2021
        if acronym == 'CGR' and int(year) < 2021:
            cur_acr = CGU['acronym']
            meta_vals = _montar_metadados(CGU['acronym'], CGU['nome'], CGU['lat'], CGU['lon'], CGU['alt'], ncols)
        else:
            cur_acr = acronym
            meta_vals = _montar_metadados(acronym, nome, lat, lon, alt, ncols)

        group = group.copy()
        group['acronym'] = cur_acr
        group = fill_values(group, cur_acr, var_web, cfg['freq'])

        # Monta o DataFrame de saída com as colunas _dqc (vazias) intercaladas
        df_out = pd.DataFrame()
        for col in META_COLS:
            df_out[col] = group[col]
        for web in var_web:
            df_out[web] = group[web]
            df_out[f'{web}_dqc'] = ''

        if escopo == 'anual':
            base = (pathlib.Path(output_web) / f"anual/{cfg['subdir']}/{cur_acr}/{int(year)}"
                    / f"{cur_acr}_{int(year)}_{tipo}")
        else:
            base = (pathlib.Path(output_web) / f"mensal/{cfg['subdir']}/{cur_acr}/{int(year)}"
                    / f"{cur_acr}_{int(year)}_{str(int(month)).zfill(2)}_{tipo}")
        base.parent.mkdir(parents=True, exist_ok=True)

        dat_path = base.with_suffix('.dat')
        _escrever_dat(df_out, web_columns, meta_vals, units, cfg['titulo'], dat_path)
        os.system(f"zip -j {base}.zip {dat_path}")
        os.remove(dat_path)


def _montar_metadados(acronym, nome, lat, lon, alt, ncols):
    vals = [str(acronym), str(nome), f'lat: {lat}', f'lon: {lon}', f'alt: {alt}'] + SONDA_META
    vals += [''] * (ncols - len(vals))
    return vals[:ncols]


def _escrever_dat(df, web_columns, meta_vals, units, titulo, caminho):
    """Grava o .dat no formato SONDA: título + linhas rotuladas + dados (tab-separado)."""
    linhas = [
        titulo,
        'Metadados da estação >' + SEP + SEP.join(meta_vals),
        'Identificação da coluna >' + SEP + SEP.join(web_columns),
        'Unidade >' + SEP + SEP.join(units),
    ]
    corpo = df.to_csv(sep=SEP, index=False, header=False)
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas) + '\n' + corpo)


def fill_values(df, acronym, var_web, freq='1min'):
    """Remove duplicatas de timestamp e preenche o grid temporal completo na frequência
    do tipo de dado (MD=10min, SD/WD=1min)."""
    df = df[~df['timestamp'].duplicated(keep='first')]

    min_ts = df['timestamp'].min()
    max_ts = df['timestamp'].max()
    dias_no_mes = pd.Period(f"{max_ts.year}-{str(max_ts.month).zfill(2)}").days_in_month
    full_index = pd.date_range(
        start=f'{min_ts.year}-{str(min_ts.month).zfill(2)}-01 00:00:00',
        end=f'{max_ts.year}-{str(max_ts.month).zfill(2)}-{dias_no_mes} 23:59:00',
        freq=freq)
    df = df.set_index('timestamp').reindex(full_index).reset_index().rename(columns={'index': 'timestamp'})

    # Reconstrói colunas de metadados a partir do timestamp (grid completo, sem NaN)
    df['year'] = df['timestamp'].dt.year.astype(int)
    df['day'] = df['timestamp'].dt.dayofyear.astype(int)
    df['min'] = (df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute).astype(int)
    df['acronym'] = df['acronym'].fillna(acronym)
    return df
