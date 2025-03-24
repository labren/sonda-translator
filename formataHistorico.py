import argparse
import pathlib
import json
import tqdm
import multiprocessing as mp
import pandas as pd
import glob
from ftplib import FTP


def baixarDados(estacao, extensao='.dat'):
    with open('conexaoFTP.json', 'r') as f:
        config = json.load(f)
    # Conectar ao servidor FTP
    ftp = FTP(config['host'])
    ftp.login(config['user'], config['passwd'])
    ftp.cwd(f"/restricted/coleta/{estacao}/data/")
    arquivos = [arq for arq in ftp.nlst() if arq.endswith(extensao)]
    # Verificar se há arquivos com a extensão especificada
    if not arquivos:
        ftp.quit()
        print(f'Nenhum arquivo com a extensão {extensao} encontrado.')
        return
    # Seta destino
    estacao = pathlib.Path('coleta') / estacao
    # Cria a pasta para armazenar os arquivos
    pathlib.Path(estacao).mkdir(parents=True, exist_ok=True)
    # Se nao houver arquivos com a extensão especificada, encerrar a conexão e retornar
    if not arquivos:
        ftp.quit()
        print(f'Nenhum arquivo com a extensão {extensao} encontrado.')
        return
    # Baixar arquivos
    for arq in arquivos:
        tamanho = ftp.size(arq)  # Obtém o tamanho do arquivo (em bytes)
        with open(estacao / arq, 'wb') as f, tqdm.tqdm(
            total=tamanho, unit='B', unit_scale=True, desc=arq, ascii=True
        ) as pbar:
            def callback(data):
                f.write(data)
                pbar.update(len(data))  # Atualiza a barra de progresso
            ftp.retrbinary(f'RETR {arq}', callback)
    ftp.quit()



import duckdb

def lerDado(arqv, data_row=4):
    
    # Ler o arquivo com o duckdb de forma automática
    df = duckdb.query(f"""
        SELECT * 
        FROM read_csv_auto('{arqv}',
        header=false,
        skip={data_row},
        ignore_errors=true)
        LIMIT 10
    """)


    print(df)
    return

    
    # Ler o arquivo com o pandas
    df = pd.read_csv(arqv, skiprows=data_row,
                      header=None, names=cabecalho,
                      engine='c', low_memory=False,
                      sep=separator, decimal=',', thousands='.',
                      quotechar='"',  
                      ).reset_index()
    # Se não houver cabeçalho, ler a linha do cabeçalho
    if not cabecalho:
        try:
            # Ler o arquivo apenas na linha do cabeçalho
            header = pd.read_csv(arqv,
                            sep=separator,
                            quotechar='"',
                            header=header_row,
                            nrows=0,
                            engine="c")
            cabecalho = header.columns.tolist()
            # Seta as colunas
            df.columns = cabecalho
        except:
            print('Erro ao ler cabeçalho')
            pass
    print(df)
    return
    
    
    
    
    # Encontra a coluna de timestamp, ou seja,
    # a primeira linha deve haver um dado que
    #  contenha os padrões 'YYYY-MM-DD HH:MM:SS', 'YYYY/MM/DD HH:MM:SS'
    for col in df.columns:
        if any(df[col].str.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')):
            timestamp_col = col
            # Converte a coluna para datetime
            df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
            # Seta a coluna de timestamp como índice
            df.set_index(timestamp_col, inplace=True)
            break
    # Se não encontrar a coluna de timestamp, retorna
    if timestamp_col is None:
        return
    # Força valores numéricos
    df = df.apply(pd.to_numeric, errors='coerce')
    # Separa os dados por frequência
    df_freq = df.resample(freq)
    # Separa estacao e tipo
    est_tipo = arqv.stem.split("_")
    for freq, grupo in df_freq:
        # Pega dia do ano inicial
        dia_ini = grupo.index[0].strftime('%j')
        # Pega dia juliano final
        dia_fim = grupo.index[-1].strftime('%j')
        # Nome do arquivo
        arq_name = f'{freq:%Y/}{est_tipo[0]}_{dia_ini}_a_{dia_fim}_{est_tipo[1]}.dat'
        # Adiciona 'historico' + nome da estação
        arq_name = pathlib.Path('historico') / est_tipo[0].lower() / arq_name
        # Transforma arq_name em um path
        arq_name = pathlib.Path(arq_name)
        # Cria diretório do arq_name
        arq_name.parent.mkdir(parents=True, exist_ok=True)
        # Salva o arquivo
        grupo.to_csv(arq_name, sep=separator, date_format='%Y-%m-%d %H:%M:%S')

    return



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', type=pathlib.Path, help='Nome da estação', default='')
    parser.add_argument('-b', type=str, help='Baixar os dados da estação', default=False)
    parser.add_argument('-t', type=str, default='ALL', help='Tipo de dado', choices=['MD', 'SD', 'TD', '50', '25', '10', 'ALL'])
    parser.add_argument('-ext', type=str, default='.DAT', help='Extensão do arquivo')
    parser.add_argument('-data', type=int, default=4, help='Número da linha dos dados')    
    args = parser.parse_args()

    # Caso a flag -b seja passada, baixar os dados da estação caso contrario, não fazer nada
    if args.b:
        baixarDados(args.b, args.ext)
    else:
        pass

    # Pega o caminho para os arquivos da estação
    path_arqv = pathlib.Path('coleta') / args.e

    # Recuperar a lista de arquivos
    arquivos = list(path_arqv.glob(f'*{args.ext}'))

    # Filtrar os arquivos de acordo com o tipo de dado
    if args.t != 'ALL':
        arquivos = [arq for arq in arquivos if args.t in arq.name]
    
    # ler os arquivos em serie
    for arq in arquivos:
        lerDado(arq)
        # break
        