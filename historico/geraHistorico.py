import argparse
import pathlib
import json
import tqdm
import multiprocessing as mp
import pandas as pd
from ftplib import FTP


def connectFTP(estacao, extensao='.dat'):
    with open('conexaoFTP.json', 'r') as f:
        config = json.load(f)
    # Conectar ao servidor FTP
    ftp = FTP(config['host'])
    ftp.login(config['user'], config['passwd'])
    ftp.cwd(f"/restricted/coleta/{estacao}/data/")
    arquivos = [arq for arq in ftp.nlst() if arq.endswith(extensao)]
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

def formataMD(dado):
    # Formatar o dado
    return dado

def formataSD(dado):
    # Formatar o dado
    return dado

def formataTD(dado):
    # Formatar o dado
    return dado

def formata50(dado):
    # Formatar o dado
    return dado

def formata25(dado):
    # Formatar o dado
    return dado

def formata10(dado):
    # Formatar o dado
    return dado


def lerDado(dado, sep, estacao, formato):
    # Ler dado com pandas
    # df = pd.read_csv(dado, sep=sep, header=None,skiprows=4, skipinitialspace=False, error_bad_lines=False)
    df = pd.read_table(dado, sep=sep, header=None, skiprows=4, skipinitialspace=False, error_bad_lines=False)
    print(df)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', type=pathlib.Path, required=True, help='Nome da estação')
    parser.add_argument('-b', action='store_true', help='Baixar os dados da estação')
    parser.add_argument('-t', type=str, default='ALL', help='Tipo de dado', choices=['MD', 'SD', 'TD', '50', '25', '10', 'ALL'])
    parser.add_argument('-ext', type=str, default='.DAT', help='Extensão do arquivo')
    parser.add_argument('-sep', type=str, default=',', help='Separador do arquivo')
    args = parser.parse_args()

    # Criar diretório para estação
    args.e.mkdir(parents=True, exist_ok=True)

    # Caso a flag -b seja passada, baixar os dados da estação caso contrario, não fazer nada
    if args.b:
        connectFTP(args.e, args.ext)
    else:
        pass

    # Recuperar a lista de arquivos
    arquivos = list(args.e.glob(f'*{args.ext}'))
    # Recuperar o tipo de dado
    tipo = args.t
    # Filtrar os arquivos de acordo com o tipo de dado
    if tipo != 'ALL':
        arquivos = [arq for arq in arquivos if tipo in arq.name]
    if not arquivos:
        print(f'Nenhum arquivo com o tipo de dado {tipo} encontrado para a estação {args.e}.')
        exit()
    
    # ler os arquivos em serie
    for arq in arquivos:
        lerDado(arq, args.sep, args.e, tipo)
        break

