import os
import json
import time
from tqdm import tqdm
import threading
import concurrent.futures

def processar_arquivo(args):
    """Processa um único arquivo e retorna suas informações categorizadas"""
    caminho_completo, tipos_dados = args
    arquivo = os.path.basename(caminho_completo)
    partes_caminho = caminho_completo.split('/')
    
    # Extrair estação (diretório após 'coleta')
    indice_coleta = partes_caminho.index('coleta') if 'coleta' in partes_caminho else -1
    
    if indice_coleta != -1 and indice_coleta + 1 < len(partes_caminho):
        estacao = partes_caminho[indice_coleta + 1]
    else:
        estacao = "desconhecido"
    
    # Verificar se é histórico (está em subdiretório além do estação)
    is_historico = len(partes_caminho) > indice_coleta + 2
    
    # Determinar tipo de dado com base no nome do arquivo
    tipo_dado = "RAW"
    for tipo in tipos_dados:
        if tipo in arquivo.upper():
            tipo_dado = tipo
            break
    
    # Retornar informações do arquivo
    return {
        "caminho": caminho_completo,
        "estacao": estacao,
        "is_historico": is_historico,
        "tipo_dado": tipo_dado
    }

def buscar_arquivos_estacao(args):
    """Busca arquivos em uma estação específica"""
    diretorio_base, estacao, extensao, lock = args
    caminhos_arquivos = []
    diretorio_estacao = os.path.join(diretorio_base, estacao)
    
    # Buscar arquivos em toda a árvore dessa estação
    for raiz, _, arquivos in os.walk(diretorio_estacao):
        for arquivo in arquivos:
            if arquivo.lower().endswith(extensao):
                caminhos_arquivos.append(os.path.join(raiz, arquivo))
    
    # Atualizar a barra de progresso de maneira thread-safe
    with lock:
        buscar_arquivos_estacao.pbar.update(1)
        buscar_arquivos_estacao.pbar.set_description(f"Escaneada: {estacao} ({len(caminhos_arquivos)} arquivos)")
    
    return caminhos_arquivos

def encontrar_arquivos_dat(diretorio_base, extensao=".dat"):
    """Encontra todos os arquivos com a extensão especificada em paralelo"""
    print(f"Buscando arquivos {extensao} em {diretorio_base}...")
    
    # Identificar as estações (diretórios logo após diretorio_base)
    try:
        estacoes = [item for item in os.listdir(diretorio_base) 
                  if os.path.isdir(os.path.join(diretorio_base, item))]
        print(f"Encontradas {len(estacoes)} estações para processar")
    except FileNotFoundError:
        print(f"Erro: Diretório base '{diretorio_base}' não encontrado")
        return []
    
    if not estacoes:
        return []
    
    # Lock para atualizações thread-safe da barra de progresso
    lock = threading.Lock()
    
    # Inicializar barra de progresso como atributo estático da função
    buscar_arquivos_estacao.pbar = tqdm(total=len(estacoes), desc="Escaneando estações", unit="estação")
    
    # Processar estações em paralelo
    todos_arquivos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, len(estacoes))) as executor:
        args_list = [(diretorio_base, estacao, extensao, lock) for estacao in estacoes]
        resultados = list(executor.map(buscar_arquivos_estacao, args_list))
        
        # Combinar resultados
        for arquivos_estacao in resultados:
            todos_arquivos.extend(arquivos_estacao)
    
    # Fechar a barra de progresso
    buscar_arquivos_estacao.pbar.close()
    
    print(f"Encontrados {len(todos_arquivos)} arquivos {extensao} no total")
    return todos_arquivos

def processar_lote(lote, tipos_dados, pbar, resultados, lock):
    """Processa um lote de arquivos e atualiza o progresso"""
    lote_resultados = []
    for caminho in lote:
        resultado = processar_arquivo((caminho, tipos_dados))
        lote_resultados.append(resultado)
        with lock:
            pbar.update(1)
    
    # Adicionar resultados à lista compartilhada de forma thread-safe
    with lock:
        resultados.extend(lote_resultados)

def listar_arquivos_dat():
    inicio = time.time()
    diretorio_base = "../ftp/restricted/coleta/"
    extensao = ".dat"
    tipos_dados = ['AMB', 'MD', 'RAD', 'SD', 'TD', 'ANE', '10', '25', '50']
    
    # Agora a busca já é paralela
    caminhos_arquivos = encontrar_arquivos_dat(diretorio_base, extensao)
    
    if not caminhos_arquivos:
        return []
    
    # Processar arquivos em paralelo com barra de progresso melhorada
    print("Processando informações dos arquivos em paralelo...")
    num_workers = os.cpu_count() * 4  # Multiplicador para tarefas I/O bound
    
    # Dividir arquivos em lotes para melhor balanceamento
    tamanho_lote = max(1, len(caminhos_arquivos) // (num_workers * 2))
    lotes = [caminhos_arquivos[i:i+tamanho_lote] for i in range(0, len(caminhos_arquivos), tamanho_lote)]
    
    resultados = []
    lock = threading.Lock()  # Lock para acesso thread-safe à barra de progresso e resultados
    
    # Usar barra de progresso compartilhada
    with tqdm(total=len(caminhos_arquivos), desc="Processando arquivos", unit="arquivo") as pbar:
        threads = []
        for lote in lotes:
            thread = threading.Thread(
                target=processar_lote,
                args=(lote, tipos_dados, pbar, resultados, lock)
            )
            threads.append(thread)
            thread.start()
        
        # Aguardar todas as threads terminarem
        for thread in threads:
            thread.join()
    
    fim = time.time()
    print(f"Tempo de processamento: {fim - inicio:.2f} segundos")
    
    return resultados

def salvar_json(dados, nome_arquivo="json/arquivos_dat.json"):
    """Salva os dados em um arquivo JSON"""
    print(f"Salvando {len(dados)} registros em {nome_arquivo}...")
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2)
    print(f"✓ Dados salvos com sucesso em {nome_arquivo}")

def main():
    try:
        inicio_total = time.time()
        
        # Listar arquivos .dat e categorizar
        arquivos_dat = listar_arquivos_dat()
        
        # Verificar se encontrou arquivos
        if not arquivos_dat:
            print("Nenhum arquivo .dat encontrado no diretório ftp/restricted/coleta/")
            return
        
        # Salvar no arquivo JSON
        salvar_json(arquivos_dat)
        
        # Exibir estatísticas
        print(f"\n📊 Estatísticas:")
        print(f"Total de arquivos .dat encontrados: {len(arquivos_dat)}")
        
        # Contar por estação e tipo
        estacoes = {}
        tipos = {}
        historicos = {"sim": 0, "não": 0}
        
        for arquivo in arquivos_dat:
            estacao = arquivo["estacao"]
            tipo = arquivo["tipo_dado"]
            is_historico = arquivo["is_historico"]
            
            estacoes[estacao] = estacoes.get(estacao, 0) + 1
            tipos[tipo] = tipos.get(tipo, 0) + 1
            if is_historico:
                historicos["sim"] += 1
            else:
                historicos["não"] += 1
        
        print("\nArquivos por estação:")
        for estacao, contagem in sorted(estacoes.items(), key=lambda x: x[1], reverse=True):
            print(f"  {estacao}: {contagem}")
            
        print("\nArquivos por tipo de dado:")
        for tipo, contagem in sorted(tipos.items(), key=lambda x: x[1], reverse=True):
            print(f"  {tipo}: {contagem}")
            
        print("\nArquivos históricos vs. atuais:")
        print(f"  Históricos: {historicos['sim']}")
        print(f"  Atuais: {historicos['não']}")
            
        print(f"\n⏱️ Tempo total de execução: {time.time() - inicio_total:.2f} segundos")
        
    except Exception as e:
        import traceback
        print(f"❌ Erro ao processar arquivos: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()