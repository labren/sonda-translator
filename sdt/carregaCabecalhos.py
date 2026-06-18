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

def cabecalhoManual(manual_header, logger=None):
    """
    Encontra o cabeçalho correspondente a uma estação.
    """
    # Leia manual_header.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    periodic_header_path = os.path.join(script_dir, 'json', 'manual_header.json')
    if os.path.exists(periodic_header_path):
        with open(periodic_header_path, 'r') as f:
            header_file = json.load(f)
    else:
        print(f"Arquivo {periodic_header_path} não encontrado.")
        exit()

    # Seleciona o cabeçalho correto baseado no manual_header
    estacao, tipo, fsl_id = manual_header
    # Busca baseado em name, type e id ignora case
    #if (header_file['name'].lower() == estacao.lower()) and (header_file['type'].lower() == tipo.lower()):
    #    if str(fsl_id) in header_file['id']:
    #        return header_file['id'][str(fsl_id)]
    #    else:
    #        logger.error(f"Error 3 - Estação {estacao} com tipo {tipo} e id {fsl_id} não encontrado no arquivo {periodic_header_path}.")
    #        return None
    #else:
    #    logger.error(f"Error 4 - Estação {estacao} com tipo {tipo} não encontrado no arquivo {periodic_header_path}.")
    #    return None
    # ALTERAÇÕES PARA LEITURA DE JSON COM MAIS DE UMA ESTAÇÃO
    # Busca a estação ignorando maiúsculas/minúsculas
    station_key = next(
        (k for k in header_file.keys() if k.lower() == estacao.lower()),
        None
    )
    if station_key is None:
        logger.error(
            f"Error 4 - Estação {estacao} não encontrada no arquivo {periodic_header_path}."
        )
        return None
    station = header_file[station_key]
    if station['type'].lower() == tipo.lower():
        if str(fsl_id) in station['id']:
            return station['id'][str(fsl_id)]
        else:
            logger.error(
                f"Error 3 - Estação {estacao} com tipo {tipo} e id {fsl_id} não encontrado no arquivo {periodic_header_path}."
            )
            return None
    else:
        logger.error(
            f"Error 4 - Estação {estacao} com tipo {tipo} não encontrada no arquivo {periodic_header_path}."
        )
        return None

