import os
import json
import time
from tqdm import tqdm
import threading
import concurrent.futures

def processar_arquivo(args):
    """Processa um único arquivo e retorna suas informações categorizadas"""
    caminho_completo = args
    arquivo = os.path.basename(caminho_completo)
    partes_caminho = caminho_completo.split('/')
    
    # Extrair estação (diretório após 'coleta')
    indice_coleta = partes_caminho.index('coleta') if 'coleta' in partes_caminho else -1
    
    if indice_coleta != -1 and indice_coleta + 1 < len(partes_caminho):
        estacao = partes_caminho[indice_coleta + 1]
    else:
        estacao = "desconhecido"
    
    # Verificar se é histórico (verifica se contém a palavra 'historico' no caminho)
    is_historico = 'historico' in caminho_completo.lower()
    
    # Retornar informações do arquivo
    return {
        "caminho": caminho_completo,
        "estacao": estacao,
        "is_historico": is_historico
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

def processar_lote(lote, pbar, resultados, lock):
    """Processa um lote de arquivos e atualiza o progresso"""
    lote_resultados = []
    for caminho in lote:
        resultado = processar_arquivo(caminho)
        lote_resultados.append(resultado)
        with lock:
            pbar.update(1)
    
    # Adicionar resultados à lista compartilhada de forma thread-safe
    with lock:
        resultados.extend(lote_resultados)

def listar_arquivos_dat():
    inicio = time.time()
    diretorio_base = "ftp/restricted/coleta/"
    extensao = ".dat"
    
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
                args=(lote, pbar, resultados, lock)
            )
            threads.append(thread)
            thread.start()
        
        # Aguardar todas as threads terminarem
        for thread in threads:
            thread.join()
    
    fim = time.time()
    print(f"Tempo de processamento: {fim - inicio:.2f} segundos")
    
    return resultados

def salvar_json(dados, nome_arquivo="arquivos_dat.json"):
    """Salva os dados em um arquivo JSON"""
    print(f"Salvando {len(dados)} registros em {nome_arquivo}...")
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2)
    print(f"✓ Dados salvos com sucesso em {nome_arquivo}")

def salvar_estatisticas(total_arquivos, estacoes, historicos, tempo_execucao, nome_arquivo="estatisticas.txt"):
    """Salva as estatísticas em um arquivo de texto"""
    print(f"Salvando estatísticas em {nome_arquivo}...")
    
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        f.write("📊 ESTATÍSTICAS DE ARQUIVOS DAT\n")
        f.write("=" * 40 + "\n\n")
        
        f.write(f"Total de arquivos .dat encontrados: {total_arquivos}\n\n")
        
        f.write("Arquivos por estação:\n")
        for estacao, contagem in sorted(estacoes.items(), key=lambda x: x[1], reverse=True):
            f.write(f"  {estacao}: {contagem}\n")
        
        f.write("\nArquivos históricos vs. atuais:\n")
        f.write(f"  Históricos: {historicos['sim']}\n")
        f.write(f"  Atuais: {historicos['não']}\n")
        
        f.write(f"\nTempo total de execução: {tempo_execucao:.2f} segundos\n")
        
        # Adicionar timestamp
        f.write(f"\nRelatório gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
    
    print(f"✓ Estatísticas salvas com sucesso em {nome_arquivo}")

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
        
        # Contar por estação
        estacoes = {}
        historicos = {"sim": 0, "não": 0}
        
        for arquivo in arquivos_dat:
            estacao = arquivo["estacao"]
            is_historico = arquivo["is_historico"]
            
            estacoes[estacao] = estacoes.get(estacao, 0) + 1
            if is_historico:
                historicos["sim"] += 1
            else:
                historicos["não"] += 1
        
        # Calcular tempo total de execução
        tempo_total = time.time() - inicio_total
        
        # Exibir estatísticas no console
        print("\nArquivos por estação:")
        for estacao, contagem in sorted(estacoes.items(), key=lambda x: x[1], reverse=True):
            print(f"  {estacao}: {contagem}")
            
        print("\nArquivos históricos vs. atuais:")
        print(f"  Históricos: {historicos['sim']}")
        print(f"  Atuais: {historicos['não']}")
            
        print(f"\n⏱️ Tempo total de execução: {tempo_total:.2f} segundos")
        
        # Salvar estatísticas em arquivo
        salvar_estatisticas(
            total_arquivos=len(arquivos_dat),
            estacoes=estacoes,
            historicos=historicos,
            tempo_execucao=tempo_total
        )
        
    except Exception as e:
        import traceback
        print(f"❌ Erro ao processar arquivos: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()