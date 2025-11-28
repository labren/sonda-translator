

# **Documentação de um Produto de Software**

Produto: SONDA Translator (SDT)  
Versão do Documento: 1.0  
Autor: Helvécio Bezerra Leal Neto  
Instituição: LABREN / INPE

---

## **1\. INTRODUÇÃO AO DOCUMENTO**

### **1.1. Tema**

O tema deste projeto é o **Desenvolvimento de ferramenta para o LABREN \- Laboratório de Modelagem e Estudos de Recursos Renováveis de Energia**. O projeto foca na engenharia de dados e na automação de processos para a rede SONDA.

### **1.2. Objetivo do Projeto**

Objetivo Geral:  
Prover uma solução de software para formatação de dados brutos da rede SONDA e estabelecer procedimentos para automação e processamento de dados formatados para a rede.  
**Objetivos Específicos:**

* Garantir a **Interoperabilidade** através da tradução de formatos proprietários para padrões abertos.  
* Implementar a **Automação** do fluxo de coleta e organização, eliminando processos manuais.  
* Otimizar a **Eficiência de Armazenamento** e consulta para grandes séries temporais.

### **1.3. Delimitação do Problema**

O escopo do projeto é delimitado pelas etapas de pré-processamento de dados.  
Primeiramente, o sistema deve realizar a sincronização dos dados da rede com o FTP e deixar os dados salvos em um diretório local seguro. Somente após esta etapa de segurança o software atua na formatação.  
O sistema abrange os dados das estações da rede SONDA (Solar, Eólica e Meteorológica).

### **1.4. Método de Trabalho**

O método de desenvolvimento adotado é a Programação Funcional.  
A escolha visa facilitar a manutenção e o teste dos algoritmos de transformação de dados, garantindo que as funções de conversão sejam puras (sem efeitos colaterais) e que os dados originais sejam imutáveis.

### **1.5. Organização do Trabalho**

Este documento está organizado conforme o padrão ESOF, detalhando desde a visão geral e requisitos até a implementação, testes e manuais de uso.

### **1.6. Glossário**

**Variáveis Informativas**

* **acronym**: Código identificador da estação.  
* **timestamp**: Data no calendário Gregoriano e hora:minuto:segundo no horário UTC (Universal Time Coordinated). *Obs: a partir da versão 3.3 do software de validação de dados, esta coluna não existe mais na entrada.*  
* **year**: Ano corrente da coleta dos dados.  
* **day**: Dia sequencial \- calendário Juliano.  
* **min**: Minuto sequencial no horário UTC.

Variáveis Anemométricas e Meteorológicas (Intervalo 10 min)  
O minuto especificado (de 0 a 1430\) indica a média dos 10 minutos posteriores.

* **ws10\_avg**: Velocidade média do vento a 10 m em $ms^{-1}$.  
* **wd10\_avg**: Direção média do vento a 10 m de 0° (Norte) a 360° (sentido horário).  
* **ws25\_avg**: Velocidade média do vento a 25 m em $ms^{-1}$.  
* **wd25\_avg**: Direção média do vento a 25 m de 0° (Norte) a 360° (sentido horário).  
* **tp\_25**: Temperatura média do ar a 25 m em °C.  
* **ws50\_avg**: Velocidade média do vento a 50 m em $ms^{-1}$.  
* **wd50\_avg**: Direção média do vento a 50 m de 0° (Norte) a 360° (sentido horário).  
* **tp\_50**: Temperatura média do ar a 50 m em °C.

**Variáveis Meteorológicas de Superfície (Intervalo 10 min)**

* **tp\_sfc**: Temperatura média do ar a 2m em °C.  
* **humid\_sfc**: Umidade relativa média do ar em %.  
* **press**: Pressão atmosférica média em milibares.  
* **rain**: Precipitação acumulada de chuva em milímetros.

Variáveis Solarimétricas (Intervalo 1 min)  
O minuto especificado (de 0 a 1439\) indica a média dos 60 segundos posteriores.

* **glo\_avg**: Radiação global horizontal média em $Wm^{-2}$.  
* **dir\_avg**: Radiação direta normal média em $Wm^{-2}$.  
* **dif\_avg**: Radiação difusa média em $Wm^{-2}$.  
* **lw\_avg**: Radiação de Onda Longa descendente média em $Wm^{-2}$ com correção.  
* **par\_avg**: Radiação fotossinteticamente ativa média em $\\mu mols \\cdot s^{-1}m^{-2}$.  
* **lux\_avg**: Iluminância média em kLux.

---

## **2\. DESCRIÇÃO GERAL DO SISTEMA**

### **2.1. Descrição do Problema**

O SONDA Translator é uma ferramenta especializada para formatação, padronização e qualificação de dados brutos provenientes da rede SONDA. Esta ferramenta converte dados em formatos brutos (.dat) para estruturas padronizadas, realiza pré-qualificação dos dados e permite o tratamento de dados classificados em quarentena.

* **Quem é afetado?** Pesquisadores e o setor de energia que dependem de dados confiáveis.  
* **Impacto:** Facilita o trabalho científico com extensos conjuntos de dados coletados pelas estações da rede SONDA em todo o Brasil.  
* **Solução:** Uma aplicação que normaliza diferentes formatos em uma estrutura consistente e organiza os dados para análise científica.

### **2.2. Principais Envolvidos**

* **Pesquisadores:** Usuários da informação gerada.  
* **Tecnologistas:** Responsáveis pela infraestrutura.  
* **Bolsistas da Rede SONDA:** Responsáveis pela operação e validação.

### **2.3. Regras de Negócio**

1. **Imutabilidade:** O dado bruto original jamais deve ser alterado.  
2. **Segurança:** A sincronização FTP deve garantir a cópia exata antes do processamento.  
3. **Rastreabilidade:** O dado final deve permitir rastrear a estação e arquivo de origem.

### **2.4. Qualificação**

A funcionalidade de **Qualificação de Dados (Quality Control)** encontra-se **em desenvolvimento** na ferramenta. O sistema atual realiza apenas uma verificação básica de colunas temporais e identificação de problemas na estrutura (pré-qualificação estrutural) para preparar os arquivos para o tratamento posterior.

---

## **3\. REQUISITOS DO SISTEMA**

### **3.1. Requisitos Funcionais Detalhados**

**Formatação e Padronização de Dados**

* Conversão de dados brutos (.dat) para formatos padronizados.  
* Organização estruturada dos dados para análise científica.  
* Normalização de diferentes formatos em uma estrutura consistente.

**Pré-qualificação de Dados**

* Verificação básica de colunas temporais.  
* Identificação de problemas na estrutura temporal dos dados.  
* Classificação de arquivos para tratamento posterior.

**Tratamento de Dados em Quarentena**

* Gerenciamento específico para dados classificados em quarentena.  
* Rotinas de análise e recuperação de dados problemáticos.  
* Opções para revisão manual ou automática.

**Seleção e Filtragem**

* **Por estação:** Processamento seletivo por estação meteorológica.  
* **Por tipo de dado:** Solar (SD), Meteorológico (MD), Vento (WD), Temperatura (TD).  
* **Por período:** Seleção por ano, mês ou data específica.  
* **Por histórico:** Diferenciação entre dados atuais e históricos.

**Modos de Processamento**

* **Processamento sequencial:** Para volumes menores de dados.  
* **Processamento paralelo:** Para alto desempenho com grandes conjuntos de dados.

**Gerenciamento de Arquivos**

* Verificação de arquivos existentes.  
* Opção de sobrescrita controlada.  
* Especificação de diretórios de saída personalizados.

**Funcionalidades Especiais**

* Escaneamento automático de diretórios FTP.  
* Visualização prévia dos dados selecionados antes do processamento.  
* Geração de logs e estatísticas detalhadas.

**Geração de Base de Dados**

* Consolidação de dados formatados em arquivos Parquet.  
* Otimização para análises e consultas de grandes volumes de dados.  
* Suporte à compressão e esquemas estruturados para melhor desempenho.

### **3.2. Pré-requisitos de Ambiente (RNF)**

* Python 3.8 ou superior.  
* Bibliotecas: pandas, tqdm, numpy, pyarrow, duckdb, sshfs.  
* Acesso aos arquivos de dados (local ou via FTP).  
* Sistema Operacional Linux (recomendado para uso de sshfs).

---

## **4\. ANÁLISE E DESIGN**

### **4.1. Arquitetura do Sistema**

Arquitetura baseada em *pipelines* funcionais:

1. **Pipeline de Ingestão:** scan\_ftp.py (Rede \-\> Disco Local).  
2. **Pipeline de Transformação:** processaDado.py (Disco Local \-\> Memória).  
3. **Pipeline de Saída:** geraArquivos.py (Memória \-\> Formatos Finais).

### **4.8. Modelo de Dados (Configuração)**

O SONDA Translator permite configurar os possíveis nomes de cabeçalhos para os diferentes tipos de estações através do arquivo cabecalhos.json. Este arquivo contém mapeamentos para cada tipo de dados (SD, MD, WD, CD) e suas respectivas variáveis.

Exemplo de configuração para dados solares (SD):

"SD": {  
    "timestamp":,  
    "glo\_avg": \["GLO\_AVG", "glo\_avg"\],  
    "dir\_avg":,  
   ...  
}

Isso permite que a ferramenta funcione corretamente mesmo quando há variações na nomenclatura dos arquivos de diferentes estações ou períodos.

---

## **5\. IMPLEMENTAÇÃO**

A implementação utiliza **Programação Funcional** e organiza o projeto na seguinte estrutura de arquivos e diretórios:

### **5.1 Estrutura do Projeto**

sdt/  
    \_\_main\_\_.py             \# Script principal (CLI)  
    carregaCabecalhos.py    \# Carregamento de cabeçalhos e sensores  
    processaDado.py         \# Função de processamento dos arquivos  
    logger.py               \# Configuração de logs  
    geraArquivos.py         \# Geração e estatísticas dos arquivos  
    qualificaDado.py        \# Qualificação dos dados  
    scan\_ftp.py             \# Escaneamento de diretórios FTP  
    tratar\_quarentena.py    \# Tratamento de arquivos em quarentena  
    json/  
        arquivos\_ftp.json   \# Metadados dos arquivos encontrados no FTP  
        cabecalhos.json     \# Configuração dos possíveis nomes de cabeçalhos  
        cabecalhos\_sensores.json \# Configuração dos sensores das estações  
output/  
    sonda-formatados/       \# Saída padrão dos arquivos processados

---

## **6\. TESTES**

### **6.1. Estratégia de Testes**

Os testes de validação dos dados formatados utilizam como referência o **Repositório de Curadoria da Rede SONDA**.

**Referência:** https://github.com/labren/sonda-curadoria/

O software deve gerar saídas que sejam validadas com sucesso pelos scripts de verificação de integridade e consistência física disponíveis neste repositório.

---

## **7\. IMPLANTAÇÃO E INSTALAÇÃO**

### **7.1. Manual de Instalação**

**Passo 1: Clone do Repositório**

git clone https://github.com/labren/sonda-translator.git  
cd sonda-translator

**Passo 2: Instalação de Dependências**

pip install \-r requirements.txt

Passo 3: Configuração de Acesso FTP (Opcional)  
Se os dados não estiverem locais, configure o sshfs:

sudo apt-get install sshfs  
mkdir ftp  
sshfs \-p 22 usuario@servidor:/mnt/ftp/ ftp/

---

## **8\. MANUAL DO USUÁRIO**

Para processar arquivos, execute o comando com as opções desejadas:  
python sdt \[opções\]

### **8.1. Opções de Linha de Comando**

| Opção | Argumento | Descrição |
| :---- | :---- | :---- |
| \-estacao | \[nomes\] | Nome(s) da(s) estação(ões) a processar (ex: \-estacao brb cai) |
| \-historico | True/False | Seleciona dados históricos ou atuais |
| \-ano | YYYY\] | Ano, mês ou dia dos dados (ex: 2020, 2020-05) |
| \-tipo | SD/MD/WD/TD/INDEFINIDO | Tipo de dado (Solar, Meteorológico, Vento, Temperatura) |
| \-parallel | \- | Processa arquivos em paralelo |
| \-id | número | Processa arquivo específico por ID |
| \-output | caminho | Caminho de saída dos arquivos processados |
| \-formatar | \- | Ativa a formatação para os arquivos de saída |
| \-overwrite | \- | Sobrescreve arquivos existentes |
| \-ftp\_dir | caminho | Diretório base dos arquivos a serem processados |
| \-scan\_ftp | \- | Escaneia o diretório FTP para encontrar arquivos.dat |
| \-quarentena | \[ids\] | Trata arquivos em quarentena pelos seus IDs |
| \-gerar\_base | \- | Gera base de dados consolidada em formato Parquet |

### **8.2. Fluxo de Processamento**

1. **Escaneamento (Scan):** Primeiro, escaneie o diretório FTP para criar o arquivo de metadados.

   python sdt \-scan\_ftp \-ftp\_dir /caminho/para/dados/

2. **Processamento:** Em seguida, processe os arquivos conforme necessário usando as opções abaixo.

### **8.3. Utilitários**

**Após a instalação, de todas as dependências, rode o comando abaixo para chamar um help das funções.**

\# Visualiza help  
python sdt –help

![][image1]  
**Figura 1\. Exibição de todas as funções disponíveis no SDT**

**Listar todos os itens do diretório ftp: Basta chamar o SDT sem nenhum parâmetro. Caso ele encontre os arquivos serão listados, os arquivos e a classe de dados a qual eles pertencem (WD, SD, MD)**

\# Visualiza help  
python sdt 

### **8.3. Casos de Uso**

**Visualização de Arquivos Disponíveis**

\# Listar todos os arquivos disponíveis  
python sdt  
\# Selecionar por estação e tipo  
python sdt \-estacao brb \-tipo SD

**Formatação e Padronização Básica**

\# Formatar e padronizar dados de uma estação específica  
python sdt \-estacao brb \-formatar  
\# Formatar dados de múltiplas estações de um tipo específico  
python sdt \-estacao brb cai pet \-tipo SD \-formatar

**Processamento por Período**

\# Processar dados de um ano específico  
python sdt \-estacao brb \-ano 2020 \-formatar  
\# Processar dados de um mês específico  
python sdt \-estacao brb \-ano 2020-06 \-formatar

**Processamento de Grande Volume (Paralelo)**

\# Processar grande quantidade de dados em paralelo  
python sdt \-estacao brb cai pet \-tipo SD \-ano 2020 \-parallel \-formatar

**Tratamento de Quarentena**

\# Tratar todos os arquivos em quarentena  
python sdt \-quarentena \-overwrite  
\# Tratar arquivos específicos  
python sdt \-quarentena 123 456 \-overwrite

**Geração de Base de Dados (Arquivo Parquet)**

\# Gerar base de dados para todos os arquivos formatados  
python sdt \-gerar\_base

### **8.4. Saída e Resultados**

Os arquivos processados seguem uma estrutura padronizada:  
\[estação\]\_\[tipo\]\_\[data\]\_\[formato\].csv  
Exemplo: BRB\_SD\_20200615\_formatado.csv  
Os logs documentam detalhadamente qualquer erro, incluindo erros de leitura, problemas de formatação, problemas com colunas temporais e arquivos enviados para quarentena.

### **8.5. Troubleshooting** 

### **Arquivos não encontrados:**

* Verifique se o caminho FTP está corretamente montado.  
  * Execute o escaneamento FTP: python sdt \-scan\_ftp.  
1. **Erros na formatação:**  
   * Arquivos do tipo INDEFINIDO podem gerar erros caso não haja cabeçalho correspondente.  
   * Verifique a integridade dos arquivos de dados brutos.  
   * Consulte os logs para informações detalhadas.  
2. **Desempenho lento:**  
   * Para grandes volumes de dados, utilize a opção \-parallel.  
   * Considere processar por lotes usando filtros de data ou estação.

---

## **9\. CONCLUSÕES**

O **SONDA Translator** é um marco na formalização dos processos de dados do LABREN. Através de uma abordagem funcional e automatizada, a ferramenta garante a integridade e a padronização necessárias para suportar as pesquisas em energias renováveis da rede SONDA.

---

## **BIBLIOGRAFIA**

* LABREN/INPE. **Rede SONDA**. Disponível em: [http://sonda.ccst.inpe.br/](http://sonda.ccst.inpe.br/)  
* LABREN/INPE. **Repositório de Curadoria**. Disponível em: [https://github.com/labren/sonda-curadoria/](https://github.com/labren/sonda-curadoria/)

[image1]: <data:image/png;base64,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>