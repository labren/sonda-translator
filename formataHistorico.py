import argparse
import pathlib
import json
import tqdm
import multiprocessing as mp
import pandas as pd
import glob
import time
import os
from ftplib import FTP
from distutils.util import strtobool
import duckdb


def filtrar_tipo_dado(estacao, tipo, historico):
    # Lê arquivo json/arquivos_ftp.json
    with open('json/arquivos_ftp.json', 'r') as arq:
        # Abre arquivo json como um dicionário
        arquivos_ftp = json.load(arq)

    # Converte arquivos_ftp em um DataFrame
    df = pd.DataFrame(arquivos_ftp)
    # Filtra os arquivos pela estação
    tipo = df['tipo_dado'].unique() if tipo == 'ALL' else [tipo]
    
    # Verifica se há arquivos para a estação
    df_f = df.loc[df['estacao'] == estacao]
    if df_f.empty:
        print(f'Nenhum arquivo encontrado para a estação {estacao}')
        print(f'As estações disponíveis são: {df["estacao"].unique()}')
        exit()

    # Verifica se há arquivos para o tipo de dado
    df_f = df_f.loc[df_f['tipo_dado'].isin(tipo)]
    if df_f.empty:
        print(f'Estação: {estacao}')
        print(f'Nenhum arquivo encontrado para o tipo de dado {tipo}')
        print(f'Os tipos de dados disponíveis são: {df["tipo_dado"].unique()}')
        exit()

    # Verifica se há arquivos para o histórico
    df_f = df_f.loc[df_f['is_historico'] == historico]
    if df_f.empty:
        print(f'Estação: {estacao} Tipo: {tipo} Histórico: {historico}')
        print(f'Nenhum arquivo histórico encontrado para o valor {historico}')
        print(f'Os valores históricos disponíveis são: {df["is_historico"].unique()}')
        exit()
    return df_f

def baixarDados(estacao, tipo, historico):
    # Filtra os arquivos pela estação
    df_f = filtrar_tipo_dado(estacao, tipo, historico)
    if df_f is None:
        return    
    # Pega todos os caminhos dos arquivos
    arquivos = df_f['caminho'].tolist()
    # Lê arquivo json/conexaoFTP.json
    with open('json/conexaoFTP.json', 'r') as arq:
        # Abre arquivo json como um dicionário
        config = json.load(arq)
    max_retries = 3
    retry_delay = 5
    # Baixar arquivos
    for arq in arquivos:
        print(f'Baixando {arq}')
        # Caminho local do arquivo
        local_path = arq[1:]
        dir_path = pathlib.Path(local_path).parent
        dir_path.mkdir(parents=True, exist_ok=True)
        
        for attempt in range(max_retries + 1):
            ftp = None  # Garantir que ftp é reiniciado a cada tentativa
            try:
                # Conectar ao servidor FTP
                ftp = FTP(config['host'])
                ftp.login(config['user'], config['passwd'])
                tamanho = ftp.size(arq)
                
                with open(local_path, 'wb') as f, tqdm.tqdm(
                    total=tamanho, unit='B', unit_scale=True, desc=arq, ascii=True
                ) as pbar:
                    def callback(data):
                        f.write(data)
                        pbar.update(len(data))
                    ftp.retrbinary(f'RETR {arq}', callback)
                break  # Sucesso - sai do loop de tentativas
                
            except Exception as e:
                print(f"Erro na tentativa {attempt + 1}: {str(e)}")
                if attempt == max_retries:
                    raise
                time.sleep(retry_delay)
            finally:
                # Fechamento seguro da conexão
                if ftp is not None:
                    try:
                        ftp.quit()
                    except:
                        try:
                            ftp.close()
                        except:
                            pass
    return




def lerDado(arqv, search_limit=10, data_row=None, header_row=None, timestamp_col=None):

    # Lê as primeiras 10 linhas do arquivo para tentar identificar, o cabeçalho, onde começa os dados e o separador
    finder_df = duckdb.query(f"""
        SELECT * 
        FROM read_csv_auto('{arqv}',
        header=false,
        ignore_errors=true)
        LIMIT {search_limit}
    """).df()

    # Loop para encontrar a linha do cabeçalho
    if header_row is None and timestamp_col is None:
        for i, row in finder_df.iterrows():
            # Se a linha tiver 'TIMESTAMP' ou 'DATE', é o cabeçalho
            if header_row is None and ('TIMESTAMP' in row.values or 'DATE' in row.values):
                header_row = i
            # Se a linha tiver 'YYYY-MM-DD HH:MM:SS' ou 'YYYY/MM/DD HH:MM:SS', é onde começam os dados
            if data_row is None and any(row.astype(str).str.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')):
                data_row = i

    # Abre apenas a linha do cabeçalho
    header = duckdb.query(f"""
        SELECT *
        FROM read_csv_auto('{arqv}',
        header=false,
        skip={header_row},
        ignore_errors=true)
        LIMIT {header_row+1}
    """).df().iloc[0].tolist()

    # Abre o dado com o duckdb de acordo com a linha dos dados
    df = duckdb.query(f"""
        SELECT *
        FROM read_csv_auto('{arqv}',
        header=false,
        skip={data_row + 1},
        ignore_errors=true)
    """).df()
    # Setar o cabeçalho
    df.columns = header

    print(df)

    return

    



if __name__ == '__main__':

    tipos_dados=['RAW','AMB','MD','RAD','SD','TD','ANE','10','25','50','ALL']
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', type=lambda s: s.lower(), help='Nome da estação', default='')
    parser.add_argument('-b', type=lambda s: s.lower(), help='Baixar os dados da estação', default='')
    parser.add_argument('-hist', type=lambda x: bool(strtobool(x)), default=False, help='Baixar dados históricos')
    parser.add_argument('-t', type=str, default='ALL', help='Tipo de dado', choices=tipos_dados)
    parser.add_argument('-ext', type=str, default='.DAT', help='Extensão do arquivo')
    parser.add_argument('-data_row', type=int, default=4, help='Número da linha dos dados')    
    parser.add_argument('-header_row', type=int, default=None, help='Número da linha do cabeçalho')
    parser.add_argument('-time_name', type=str, default=None, help='Nome da coluna de timestamp')
    parser.add_argument('-search_limit', type=int, default=10, help='Número de linhas para procurar cabeçalho e dados')
    args = parser.parse_args()

    # Caso a flag -b seja passada, baixar os dados da estação caso contrario, não fazer nada
    if args.b:
        baixarDados(args.b, args.t, args.hist)
        args.e = args.b
    else:
        pass

    # Filtra os arquivos pela estação
    df_f = filtrar_tipo_dado(args.e, args.t, args.hist)
    if df_f is None:
        exit()

    # Pega todos os caminhos dos arquivos sem a primeira barra
    arquivos = df_f['caminho'].str[1:].tolist()
    
    # ler os arquivos em serie
    for arq in arquivos:
        lerDado(arq, args.search_limit, args.data_row, 
                args.header_row, args.time_name)
        # break
        