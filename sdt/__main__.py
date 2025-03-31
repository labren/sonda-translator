import argparse
import json
import os
import pandas as pd
import tqdm
from distutils.util import strtobool
from multiprocessing import Pool
from lerDat import lerArquivo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--estacao', nargs='+', type=lambda s: s.lower(), 
                        help='Nome da estação ou lista de estações', default=[])
    parser.add_argument('-hist', '--historico', 
                        type=lambda x: bool(strtobool(x)), 
                        help='Se True, irá buscar os dados históricos')
    parser.add_argument('-ano', '--ano', type=str,
                        help='Ano do dado a ser buscado. Aceita: YYYY, YYYY-MM, YYYY-MM-DD',
                        default='')
    parser.add_argument('-tipo', '--tipo', type=str,
                help='Tipo de dado a ser buscado. Aceita: SD, MD, WD, INDEFINIDO, TD',
                choices=['SD', 'MD', 'WD', 'INDEFINIDO', 'TD'])
    parser.add_argument('-exibir', '--exibir', action='store_true',
                        help='Exibe os dados filtrados')
    parser.add_argument('-p', '--paralelizar', action='store_true',
                        help='Paraleliza o processamento dos arquivos')
    parser.add_argument('-id', '--id', type=int,
                        help='ID do arquivo a ser buscado')

    args = parser.parse_args()
    
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dat_file_path = os.path.join(script_dir, 'json', 'arquivos_dat.json')
    
    if os.path.exists(dat_file_path):
        with open(dat_file_path, 'r') as f:
            dat_files = json.load(f)
            dat_files_df = pd.DataFrame(dat_files)
            # cast column date to 
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
        print(dat_files_df.reset_index(drop=True).to_string(index=False))

    # Pegue os dados que serão processados
    dat_files_to_process = dat_files_df['caminho'].tolist()
    # Pegue os tipos de dados que serão processados
    dat_files_types = dat_files_df['tipo'].tolist()

    # Monta barra de progresso
    pbar = tqdm.tqdm(total=len(dat_files_to_process), desc="Processing files", unit="file")

    # Process files
    if args.paralelizar:
        # Use multiprocessing to process files in parallel
        with Pool() as pool:
            results = []
            for result in pool.imap(lerArquivo, zip(dat_files_to_process, dat_files_types)):
                results.append(result)
                pbar.update()
        pool.close()
        pool.join()
    else:
        # Process files sequentially
        for file_path, file_type in zip(dat_files_to_process, dat_files_types):
            lerArquivo((file_path, file_type))
            break
            pbar.update()
    pbar.close()
    # Finalize the progress bar
    print("Processing complete.")



