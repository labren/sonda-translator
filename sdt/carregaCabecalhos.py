import os
import json

def carregaCabecalhos():
    """
    Carrega os cabeçalhos e os sensores a partir de arquivos JSON.
    """
    # Carrega o arquivo JSON com os cabeçalhos
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dat_file_path = os.path.join(script_dir, 'json', 'cabecalhos.json')
    # Carrega o arquivo JSON com os sensores
    header_sensor_path = os.path.join(script_dir, 'json', 'cabecalho_sensor.json')
    if os.path.exists(dat_file_path):
        with open(dat_file_path, 'r') as f:
            headers = json.load(f)
    else:
        print(f"Arquivo {dat_file_path} não encontrado.")
        exit()
    if os.path.exists(header_sensor_path):
        with open(header_sensor_path, 'r') as f:
            header_sensor = json.load(f)
    else:
        print(f"Arquivo {header_sensor_path} não encontrado.")
        exit()
    
    return headers, header_sensor