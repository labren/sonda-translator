import os
import glob
import duckdb
import pandas as pd
import pathlib
import warnings
warnings.filterwarnings("ignore")


def tratar_quarentena(quarentena_path, output_dir):
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

    # Remove arquivos duplicados
    arquivos_quarentena = list(set(arquivos_quarentena))

    # Verifica se a lista de arquivos em quarentena está vazia
    if not arquivos_quarentena:
        print("Nenhum arquivo em quarentena encontrado.")
        return []
    
    # Cria conexão com o banco de dados DuckDB
    con = duckdb.connect(database=':memory:')
        
    # Processa os arquivos em quarentena
    processar_arquivos_quarentena(con, arquivos_quarentena, output_dir)

    return []

def processar_arquivos_quarentena(con, arquivos_quarentena, output_dir):
    """
    Processa arquivos em quarentena e salva os resultados em um diretório de saída.
    
    Args:
        arquivos_quarentena: Lista de arquivos em quarentena
        output_dir: Diretório onde os arquivos processados serão salvos
    """
    for arquivo in arquivos_quarentena:
        # Lógica para processar cada arquivo
        # Exemplo: ler o arquivo, aplicar transformações, salvar no output_dir
        print(f"Processando arquivo: {arquivo}")
        # Lê arquivo CSV
        try:
            df = con.query(f"SELECT * FROM read_csv_auto('{arquivo}', ignore_errors=true)").df()
        except Exception as e:
            print(f"Erro ao ler o arquivo {arquivo}: {e}")
            continue

        print(df)
        break