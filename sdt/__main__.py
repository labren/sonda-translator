import argparse
import json
import os
import pandas as pd
from distutils.util import strtobool


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--estacao', nargs='+', type=lambda s: s.lower(), 
                        help='Nome da estação ou lista de estações', default=[])
    parser.add_argument('-hist', '--historico', 
                        type=lambda x: bool(strtobool(x)), default=False ,
                        help='Se True, irá buscar os dados históricos')
    parser.add_argument('-ano', '--ano', type=int, default=2023,
                        help='Ano para buscar os dados')
    parser.add_argument('-tipo', '--tipo', type=str,
                help='Tipo de dado a ser buscado. Aceita: SD, MD, WD, INDEFINIDO, TD',
                choices=['SD', 'MD', 'WD', 'INDEFINIDO', 'TD'])

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
    
    # Filter by historical flag
    dat_files_df = dat_files_df[dat_files_df['is_historico'] == args.historico]
    

    # Filter by type if specified
    if args.tipo:
        dat_files_df = dat_files_df[dat_files_df['tipo'] == args.tipo]

    print(dat_files_df.date.unique())
    
