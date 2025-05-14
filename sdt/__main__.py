import argparse
import json
import os
import pandas as pd
import tqdm
from distutils.util import strtobool
from multiprocessing import Pool
from carregaCabecalhos import carregaCabecalhos
from logger import setup_logger
from processaDado import processarArquivo
from scan_ftp import main as scan_ftp_main
from tratar_quarentena import tratar_quarentena

# Copyright (c) Helvecio Neto - 2025 - helvecioblneto@gmail.com
# Todos os direitos reservados.

if __name__ == "__main__":
    # Descrição do que o programa faz
    
    parser = argparse.ArgumentParser(
        description="""
        SONDA Translator - Ferramenta para processar e formatar arquivos de dados da rede SONDA.
        
        Esta ferramenta permite filtrar, qualificar e converter arquivos de dados meteorológicos (.dat) 
        para formatos padronizados. O processamento pode ser feito de forma sequencial ou paralela, 
        com suporte a diversos tipos de dados e estações.
        
        Exemplos de uso:
        # Exemplo 1: Processa arquivos das estações 'brb' e 'cai' do tipo SD (Solar Data) do ano de 2020 em modo paralelo
        python -m sdt -e brb cai -tipo SD -ano 2020 -p

        # Exemplo 2: Exibe (sem processar) os arquivos históricos da estação 'pet'
        python -m sdt -e pet -hist True -exibir

        # Exemplo 3: Processa o arquivo com ID 42, salva em um diretório específico e sobrescreve se já existir
        python -m sdt -id 42 -out /caminho/para/saida/ -overwrite
        
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-estacao', nargs='+', type=lambda s: s.lower(), 
                        help='Nome da estação ou lista de estações (ex: brb cai pet)', default=[])
    parser.add_argument('-historico',
                        type=lambda x: bool(strtobool(x)), 
                        help='Se True, irá buscar os dados históricos (ex: True ou False)')
    parser.add_argument('-ano', type=str,
                        help='Ano do dado a ser buscado. Aceita: YYYY, YYYY-MM, YYYY-MM-DD (ex: 2020, 2020-06, 2020-06-15)',
                        default='')
    parser.add_argument('-tipo', '--tipo', type=str,
                help='Tipo de dado a ser buscado: SD (Solar Data), MD (Meteorological Data), WD (Wind Data)',
                choices=['SD', 'MD', 'WD', 'INDEFINIDO', 'TD'])
    parser.add_argument('-exibir', action='store_true',
                        help='Exibe os dados filtrados e não executa o processamento')
    parser.add_argument('-parallel', action='store_true',
                        help='Paraleliza o processamento dos arquivos (recomendado para grandes volumes)')
    parser.add_argument('-id', type=int,
                        help='ID específico do arquivo a ser processado')
    parser.add_argument('-output', type=str, default='/media/helvecioneto/Barracuda/sonda-formatados/',
                        help='Caminho para salvar os arquivos processados')
    parser.add_argument('-overwrite', action='store_true',
                        help='Sobrescreve os arquivos de saída caso já existam')
    parser.add_argument('-ftp_dir', type=str, default='/media/helvecioneto/Barracuda/',
                        help='Diretório base onde estão localizados os arquivos a serem processados')
    parser.add_argument('-scan_ftp', action='store_true',
                        help='Escaneia o diretório FTP para encontrar arquivos .dat')
    parser.add_argument('-quarentena', type=str,
                        help='Caminho para um diretório de quarentena ou arquivo específico em quarentena')
    
    args = parser.parse_args()
    
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dat_file_path = os.path.join(script_dir, 'json', 'arquivos_ftp.json')
    
    if os.path.exists(dat_file_path):
        with open(dat_file_path, 'r') as f:
            dat_files = json.load(f)
            dat_files_df = pd.DataFrame(dat_files)
            if args.ftp_dir:
                # Update the 'caminho' column with the FTP directory
                dat_files_df['caminho'] = dat_files_df['caminho'].apply(lambda x: os.path.join(args.ftp_dir, x))
    else:
        print(f"Error: File '{dat_file_path}' not found.")
        exit(1)

    # Apply filters based on parameters
    if args.estacao:
        dat_files_df = dat_files_df[dat_files_df['estacao'].str.lower().isin(args.estacao)]
    
    # Filter by historical data if specified
    if args.historico is not None:
        dat_files_df = dat_files_df[dat_files_df['is_historico'] == args.historico]
    
    # Filter by type if specified
    if args.tipo:
        dat_files_df = dat_files_df[dat_files_df['tipo'] == args.tipo]

    # Filter by year if specified
    if args.ano:
        dat_files_df = dat_files_df[dat_files_df['date'] == args.ano]

    # Filter by ID if specified
    if args.id:
        dat_files_df = dat_files_df[dat_files_df['id'] == args.id]

    # Exibe the filtered data
    if args.exibir:
        # Limita o número de caracteres da coluna 'caminho' para exibição
        df_to_show = dat_files_df[['id', 'estacao', 'tipo', 'date', 'caminho']].copy()
        max_caminho_len = 120
        df_to_show['caminho'] = df_to_show['caminho'].apply(lambda x: x[:max_caminho_len] + '...' if len(x) > max_caminho_len else x)
        with pd.option_context('display.max_rows', None, 
              'display.max_columns', None, 
              'display.width', 2000):
            print(df_to_show.to_string(index=False))
        exit()
    
    # If scan_ftp is specified, scan the FTP directory for .dat files
    if args.scan_ftp:
        scan_ftp_main(args.ftp_dir)

    # If quarentena is specified, process the files in quarantine
    if args.quarentena:
        arquivos_quarentena = tratar_quarentena(args.quarentena, args.output)
        exit()

    # Pegue os dados que serão processados
    dat_files_to_process = dat_files_df['caminho'].tolist()
    # Pegue os tipos de dados que serão processados
    dat_files_types = dat_files_df['tipo'].tolist()
    # Pega todas as estações que serão processadas
    dat_files_stations = dat_files_df['estacao'].tolist()

    # Configura o logger
    logger = setup_logger()
    # Carrega os cabeçalhos e os sensores a partir de arquivos JSON.
    headers, header_sensor = carregaCabecalhos()

    # Monta barra de progresso
    pbar = tqdm.tqdm(total=len(dat_files_to_process), desc="Processing files", unit="file")

    # Process files
    if args.parallel:
        # Use multiprocessing to process files in parallel
        with Pool(6) as pool:
            results = []
            for result in pool.imap(processarArquivo, 
                                    zip(dat_files_to_process, 
                                        dat_files_stations,
                                        dat_files_types, 
                                        [args.output] * len(dat_files_to_process), 
                                        [args.overwrite] * len(dat_files_to_process),
                                        [logger] * len(dat_files_to_process),
                                        [headers] * len(dat_files_to_process),
                                        [header_sensor] * len(dat_files_to_process))):
                results.append(result)
                pbar.update()
        pool.close()
        pool.join()
    else:
        # Process files sequentially
        for file_path, file_type, estacao in zip(dat_files_to_process,
                                        dat_files_types,
                                        dat_files_stations):
            processarArquivo((file_path, estacao,
                        file_type, args.output,
                        args.overwrite, logger, headers, header_sensor))
            pbar.update()
    pbar.close()
    print("Processing complete.")



