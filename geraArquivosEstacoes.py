import json
from ftplib import FTP
import os
import time
import re

def listar_pastas(ftp, caminho):
    """
    Lista todas as pastas dentro de um diretório no FTP.
    """
    pastas = []
    try:
        print(f"Tentando acessar diretório: {caminho}")
        ftp.cwd(caminho)
        print(f"Diretório atual: {ftp.pwd()}")
        
        # Usar uma abordagem mais robusta para listar diretórios
        linhas = []
        ftp.retrlines('LIST', lambda line: linhas.append(line))
        
        for linha in linhas:
            # Verificar se a entrada é um diretório (começando com 'd')
            if linha.startswith('d'):
                partes = linha.split()
                nome_pasta = partes[-1]
                # Evitar pastas com nome 'camera' e 'security'
                if nome_pasta not in ['.', '..'] and nome_pasta.lower() != 'camera' and nome_pasta.lower() != 'security':
                    pastas.append(nome_pasta)
        
        # Volta para o diretório anterior para não afetar navegações subsequentes
        ftp.cwd('..')
        # Constrói caminhos completos
        return [f"{caminho}/{pasta}" for pasta in pastas]
    except Exception as e:
        print(f"Erro ao listar o diretório {caminho}: {e}")
        return []

def extrair_estacao(caminho_arquivo):
    """
    Extrai a estação do caminho do arquivo.
    Assumindo formato como /restricted/coleta/ESTACAO/data/arquivo.dat
    """
    partes = caminho_arquivo.split('/')
    # A estação seria o componente após 'coleta'
    for i, parte in enumerate(partes):
        if parte == 'coleta' and i+1 < len(partes):
            return partes[i+1]
    return "Estação desconhecida"

def identificar_tipo_dado(caminho_arquivo, nome_arquivo):
    """
    Identifica o tipo de dado baseado no nome do arquivo e caminho.
    
    Tipos possíveis: SD, MD, TD, RAD, AMB, ANE, 10, 25, 50
    Se nenhum tipo for identificado, classifica como RAW.
    """
    # Cria uma string única em maiúsculas com o caminho completo e o nome do arquivo
    caminho_completo = (caminho_arquivo + "/" + nome_arquivo).upper()
    
    # Define os tipos possíveis
    tipos_possiveis = ["SD", "MD", "TD", "RAD", "AMB", "ANE", "10", "25", "50"]
    
    # Procura pelos tipos no caminho completo
    for tipo in tipos_possiveis:
        # Usando expressão regular para garantir que encontramos o tipo como uma palavra completa
        # ou parte de uma palavra delimitada por caracteres não alfanuméricos
        pattern = r'[^a-zA-Z0-9]' + tipo + r'[^a-zA-Z0-9]|\b' + tipo + r'\b'
        if re.search(pattern, caminho_completo):
            return tipo
    
    # Se nenhum tipo for encontrado, retorna "RAW"
    return "RAW"

def buscar_arquivos_dat_recursivo(ftp, diretorio_atual, estacao_base, nivel_max=3, nivel_atual=0):
    """
    Busca recursivamente por arquivos .dat em um diretório e suas subpastas.
    
    Args:
        ftp: Conexão FTP
        diretorio_atual: Caminho do diretório atual
        estacao_base: Nome da estação base
        nivel_max: Profundidade máxima de recursão
        nivel_atual: Nível atual de recursão
    """
    if nivel_atual > nivel_max:
        return []
    
    # Verificar se o diretório atual contém 'camera' ou 'security' no nome
    if '/camera' in diretorio_atual.lower() or diretorio_atual.lower().endswith('/camera') or \
       '/security' in diretorio_atual.lower() or diretorio_atual.lower().endswith('/security'):
        print(f"Ignorando diretório: {diretorio_atual}")
        return []
    
    arquivos_dat = []
    try:
        print(f"Explorando diretório: {diretorio_atual} (nível {nivel_atual})")
        
        # Restaurar posição para o diretório raiz para evitar problemas de navegação
        ftp.cwd('/')
        
        # Navegar para o caminho absoluto
        ftp.cwd(diretorio_atual)
        
        # Listar conteúdo do diretório
        itens = []
        ftp.retrlines('LIST', lambda line: itens.append(line))
        
        # Processar arquivos
        for item in itens:
            partes = item.split()
            nome_item = partes[-1]
            
            # Verificar se é um diretório e não é . ou .. ou camera ou security
            if item.startswith('d') and nome_item not in ['.', '..'] and \
               nome_item.lower() != 'camera' and nome_item.lower() != 'security':
                # É um diretório, explorar recursivamente
                caminho_subdiretorio = f"{diretorio_atual}/{nome_item}"
                subdir_arquivos = buscar_arquivos_dat_recursivo(
                    ftp, caminho_subdiretorio, estacao_base, 
                    nivel_max, nivel_atual + 1
                )
                arquivos_dat.extend(subdir_arquivos)
            elif nome_item.lower().endswith('.dat'):
                # É um arquivo .dat
                caminho_completo = f"{diretorio_atual}/{nome_item}"
                
                # Verificar se 'historico' está no nome ou caminho do arquivo
                is_historico = 'historico' in caminho_completo.lower() or 'historico' in nome_item.lower()
                
                # Identificar tipo de dado
                tipo_dado = identificar_tipo_dado(diretorio_atual, nome_item)
                
                arquivos_dat.append({
                    "caminho": caminho_completo, 
                    "estacao": estacao_base,
                    "is_historico": is_historico,
                    "tipo_dado": tipo_dado
                })
    
    except Exception as e:
        print(f"Erro ao explorar diretório {diretorio_atual}: {e}")
    
    return arquivos_dat

def buscar_arquivos_em_pastas(ftp, caminho_inicial):
    """
    Para cada pasta dentro de '/restricted/coleta/', procura por arquivos .dat recursivamente.
    """
    pastas = listar_pastas(ftp, caminho_inicial)
    print(f"Pastas encontradas em {caminho_inicial}: {pastas}")
    
    if not pastas:
        print(f"Atenção: Nenhuma pasta encontrada em {caminho_inicial}!")
        try:
            print(f"Listando conteúdo direto de {caminho_inicial}:")
            ftp.cwd(caminho_inicial)
            items = []
            ftp.retrlines('LIST', lambda line: items.append(line))
            for item in items:
                print(f"  {item}")
        except Exception as e:
            print(f"Erro ao listar conteúdo direto: {e}")

    arquivos_encontrados = []
    
    # Processar uma estação por vez para evitar problemas de concorrência
    for pasta in pastas:
        # Extrair o nome da estação da pasta
        estacao = extrair_estacao(pasta)
        print(f"Processando estação: {estacao} (pasta: {pasta})")
        
        # Iniciar busca recursiva a partir da raiz da estação
        arquivos = buscar_arquivos_dat_recursivo(ftp, pasta, estacao)
        arquivos_encontrados.extend(arquivos)
        
        # Adicionar uma pequena pausa para evitar sobrecarregar o servidor
        time.sleep(0.5)

    return arquivos_encontrados

def main():
    try:
        print("Carregando configurações do arquivo conexaoFTP.json...")
        with open('json/conexaoFTP.json', 'r') as f:
            config = json.load(f)
        
        # Conectar ao servidor FTP
        print(f"Tentando conectar ao servidor FTP: {config['host']}...")
        ftp = FTP(config['host'])
        print("Conexão estabelecida, tentando login...")
        
        ftp.login(config['user'], config['passwd'])
        print(f"Login bem-sucedido como {config['user']}")
        
        # Mostrar diretório inicial após login
        diretorio_inicial = ftp.pwd()
        print(f"Diretório inicial: {diretorio_inicial}")
        
        # Iniciar a busca no diretório /restricted/coleta/
        caminho_inicial = '/restricted/coleta'
        print(f"Iniciando busca em: {caminho_inicial}")
        arquivos_encontrados = buscar_arquivos_em_pastas(ftp, caminho_inicial)

        # Exibir resultados
        total_arquivos = len(arquivos_encontrados)
        historicos = sum(1 for arquivo in arquivos_encontrados if arquivo.get("is_historico", False))
        raw = total_arquivos - historicos
        
        print(f"\nTotal de {total_arquivos} arquivos .dat encontrados:")
        print(f"- {historicos} arquivos históricos")
        print(f"- {raw} arquivos raw")
        
        # Informações sobre tipos de dados encontrados
        tipos_dados = {}
        for arquivo in arquivos_encontrados:
            tipo = arquivo["tipo_dado"]
            tipos_dados[tipo] = tipos_dados.get(tipo, 0) + 1
            
        print("\nDistribuição por tipo de dado:")
        for tipo, quantidade in tipos_dados.items():
            print(f"- {tipo}: {quantidade} arquivos")

        # Cria diretório json se não existir
        if not os.path.exists('json'):
            os.makedirs('json')

        # Salvar todos os arquivos encontrados em um único arquivo JSON
        with open('json/arquivos_ftp.json', 'w') as f:
            json.dump(arquivos_encontrados, f, indent=2)
        print("Todos os arquivos salvos em 'json/arquivos_ftp.json'")

        # Fechar a conexão FTP
        ftp.quit()
        print("Conexão FTP encerrada com sucesso")
        
    except Exception as e:
        print(f"Erro durante a execução: {e}")

if __name__ == "__main__":
    main()