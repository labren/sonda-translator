# sonda-translator

Ferramenta para filtrar, qualificar e converter arquivos de dados meteorológicos da rede SONDA, organizando e padronizando informações provenientes de diferentes estações e formatos.

## Funcionalidades

- Filtragem de arquivos `.dat` por estação, tipo, ano, histórico e ID.
- Processamento sequencial ou paralelo dos arquivos.
- Conversão e padronização dos dados para formatos organizados.
- Geração de estatísticas e logs de processamento.
- Exibição dos dados filtrados antes do processamento.

## Estrutura do Projeto

```
sdt/
    __main__.py           # Script principal (CLI)
    carregaCabecalhos.py  # Carregamento de cabeçalhos e sensores
    processaDado.py       # Função de processamento dos arquivos
    logger.py             # Configuração de logs
    geraArquivos.py       # Geração e estatísticas dos arquivos
    qualificaDado.py      # Qualificação dos dados
    json/
        arquivos_dat.json # Metadados dos arquivos .dat
output/
    ...                   # Saída dos arquivos processados
notebooks/
    explorer.ipynb        # Notebook de exploração dos dados
```

## Instalação

1. Clone o repositório:
    ```bash
    git clone https://github.com/seu-usuario/sonda-translator.git
    cd sonda-translator
    ```

2. Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

3. (Opcional) Monte o diretório remoto do servidor FTP:
    ```bash
    sudo apt-get install sshfs
    mkdir ftp
    sshfs -p 22 usuario@servidor:/mnt/ftp/ ftp/
    ```

## Uso

Execute o script principal para processar os arquivos:

```bash
python -m sdt [opções]
```

### Principais opções

- `-e`, `--estacao`: Nome(s) da(s) estação(ões) a filtrar (ex: `-e brb cai`).
- `-hist`, `--historico`: Filtra por dados históricos (`True` ou `False`).
- `-ano`, `--ano`: Ano, mês ou dia dos dados (ex: `2020`, `2020-05`, `2020-05-01`).
- `-tipo`, `--tipo`: Tipo de dado (`SD`, `MD`, `WD`, `INDEFINIDO`, `TD`).
- `-exibir`, `--exibir`: Exibe os dados filtrados e sai.
- `-p`, `--paralelizar`: Processa arquivos em paralelo.
- `-id`, `--id`: Filtra por ID do arquivo.
- `-out`, `--output`: Caminho de saída dos arquivos processados.
- `-ovrwrite`, `--overwrite`: Sobrescreve arquivos existentes.
- `-ftp_dir`, `--ftp_dir`: Diretório base dos arquivos a serem processados.

### Exemplo de uso

```bash
python -m sdt -e brb cai -ano 2020 -tipo SD -p --exibir
```

## Saída

- Os arquivos processados são salvos no diretório especificado por `--output`.
- Logs detalhados são gerados para acompanhamento de erros e progresso.
- Estatísticas do processamento podem ser encontradas em `sdt/estatisticas.txt`.

## Observações

- Arquivos do tipo `INDEFINIDO` podem gerar erros caso não haja cabeçalho correspondente.
- O arquivo [`sdt/json/arquivos_dat.json`](sdt/json/arquivos_dat.json) é utilizado como base para os metadados dos arquivos a serem processados.
- Para explorar os dados, utilize o notebook em [`notebooks/explorer.ipynb`](notebooks/explorer.ipynb).

---

**Desenvolvido por:**  
Equipe SONDA / Labren / INPE