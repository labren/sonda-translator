import os
import glob

def tratar_quarentena(quarentena_path):
    """
    Unifica arquivos em quarentena a partir de um caminho que pode ser um diretório ou arquivo específico.
    
    Args:
        quarentena_path: Caminho para um diretório contendo arquivos em quarentena ou para um arquivo específico
        
    Returns:
        list: Lista com todos os arquivos em quarentena
    """
    arquivos_quarentena = []
    
    # Verifica se o caminho existe
    if not quarentena_path:
        print("Nenhum caminho de quarentena fornecido.")
        return []
    
    # Caso seja um diretório, busca todos os arquivos .csv recursivamente
    if os.path.isdir(quarentena_path):
        padrao_busca = os.path.join(quarentena_path, '**', '*.csv')
        arquivos_quarentena = [f for f in glob.glob(padrao_busca, recursive=True) if os.path.isfile(f)]
    # Caso seja um arquivo, adiciona diretamente à lista
    elif os.path.isfile(quarentena_path):
        arquivos_quarentena = [quarentena_path]
    else:
        print(f"Caminho de quarentena inválido: {quarentena_path}")
    
    print(arquivos_quarentena)


    return arquivos_quarentena
