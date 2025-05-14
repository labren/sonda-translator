import pandas as pd
from pathlib import Path
import os

def tratar_quarentena(estacao, tipo, quarentena_id, output, overwrite=False, exibir=False):

    # Pega primeiro elemento da estacao
    estacao = estacao[0]
    # Verifica se estacao é uma string
    if not isinstance(estacao, str):
        raise ValueError("A estação deve ser uma string, voce passou: {}".format(type(estacao)))
    # Verifica se tipo é uma string
    if not isinstance(tipo, str):
        raise ValueError("O tipo deve ser uma string, voce passou: {}".format(type(tipo)))
    
    # Remove 'sonda-formatados/' que existe no output
    output = output.replace('sonda-formatados/', '')
    
    # Verifica se arquivo de quarentena existe com base no output/sonda_quarentena/estacao/{estacao}_{tipo}_sumario_problemas.csv
    quarentena_file = Path(output) / 'sonda_quarentena' / estacao.upper() / f"{estacao.upper()}_{tipo}_sumario_problemas.csv"
    if not quarentena_file.exists():
        print(f"Arquivo de quarentena não encontrado: {quarentena_file}")
        return
    
    # Lê o arquivo de quarentena
    quarentena_df = pd.read_csv(quarentena_file)

    # Filtra pelo ID de quarentena
    if quarentena_id:
        quarentena_id = [int(i) for i in quarentena_id]
        quarentena_df = quarentena_df[quarentena_df['qid'].isin(quarentena_id)]

    # Verificar se exibir é True
    if exibir:
        # Limita o número de caracteres da coluna 'path' para exibição
        max_path_len = 150
        quarentena_df['path'] = quarentena_df['path'].apply(lambda x: x[:max_path_len] + '...' if len(x) > max_path_len else x)
        with pd.option_context('display.max_rows', None, 
                               'display.max_columns', None, 
                               'display.width', 2000):
            print(quarentena_df.to_string(index=False))
        return

    print(quarentena_df)