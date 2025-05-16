import pandas as pd
from pathlib import Path
import os
import pathlib
from carregaCabecalhos import carregaCabecalhos

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
    # Verifica se arquivo de quarentena existe
    quarentena_file = Path(output) / 'sonda-quarentena' / 'quarentena.csv'
    if not quarentena_file.exists():
        print(f"Arquivo de quarentena não encontrado: {quarentena_file}")
        return
    
    # Lê o arquivo de quarentena
    quarentena_df_main = pd.read_csv(quarentena_file)

    try:
        quarentena_id = [int(i) for i in quarentena_id]
    except Exception:
        pass

    # Filtra pelo ID de quarentena
    if len(quarentena_id) > 0:
        quarentena_df = quarentena_df_main[quarentena_df_main['qid'].isin(quarentena_id)]
    else:
        quarentena_df = quarentena_df_main.copy()

    max_len = 45
    quarentena_display = quarentena_df.copy()
    quarentena_display['path'] = quarentena_display['path'].apply(lambda x: '...'+ x[-max_len:] if len(x) > max_len else x)
    print(f"Lista de arquivos de quarentena para a estação {estacao.upper()} e tipo {tipo}:")
    print(quarentena_display[['qid', 'estacao', 'tipo', 'status','data_tratamento','problema','path']].to_string(index=False))
    print('-'*50)
    print('')
    # input("Pressione Enter para continuar ou Ctrl+C para cancelar...")
    
    # Carrega os cabeçalhos e os sensores a partir de arquivos JSON.
    _, header_sensor = carregaCabecalhos()

    # Loop por arquivos de quarentena
    for index, row in quarentena_df.iterrows():
        # Pega o caminho do arquivo
        caminho = row['path']
        # Verifica se o arquivo existe
        if not os.path.exists(caminho):
            print(f"Arquivo não encontrado: {caminho}")
            continue
        # Abrindo o arquivo
        df_q_orig = pd.read_csv(caminho)
        # Seta colunas de timestamp
        df_q_orig['timestamp'] = pd.to_datetime(df_q_orig['timestamp'], errors='coerce')
        df_q = df_q_orig.copy() # Cria uma copia do arquivo de quarentena
        # Encontra o ano mais comum no arquivo de quarentena baseado no timestamp
        common_year = str(df_q['timestamp'].dt.year.mode()[0])
        # Encontra o mes mais comum no arquivo de quarentena baseado no timestamp com zfill
        common_month = str(df_q['timestamp'].dt.month.mode()[0]).zfill(2)
        # Seta arquivo de quarentena apenas para o ano mais comum e mes mais comum
        df_q = df_q[(df_q['timestamp'].dt.year == int(common_year)) & (df_q['timestamp'].dt.month == int(common_month))]
        # Montar nome do arquivo de referencia
        arqv_ref = output + 'sonda-formatados/' + estacao.upper() + '/' + row['tipo_completo'] + '/'
        arqv_ref += common_year + '/' + estacao.upper() + '_' + common_year + '_' + common_month + '_' + row['tipo'] + '_formatado.csv'

        print('-'*50)
        print(f"Tratando arquivo com qid: \t{row['qid']} \tda estacao {estacao.upper()} e tipo {tipo}")
        print(f"O status atual do arquivo é: \t{row['status']}")
        print(f"O tipo de problema do arquivo é: \t{row['problema']}")
        print(f"Tratando arquivo de quarentena: \t{row['path']}...")
        resposta = input(f"O arquivo a ser alterado é: \t\t{arqv_ref} ? \n(s/n): ")
        if resposta.lower() != 's':
            print("Arquivo ignorado.")
            print('-'*50)
            continue
        
        # Verifica se o arquivo de referencia existe
        if not os.path.exists(arqv_ref):
            print(f"Arquivo de referencia não encontrado: {arqv_ref}")
            print(f"Arquivo de quarentena: {caminho}")
            # perguntar se deseja criar o arquivo de referencia
            resposta = input(f"Arquivo de referencia não encontrado: {arqv_ref}. Deseja criar o arquivo de referencia? (s/n): ")
            if resposta.lower() == 's':
                # Pega subcabeçalho do arquivo de quarentena
                sub_header = header_sensor[estacao.lower()][tipo]
                sub_header = ['', '', '', '', ''] + sub_header
                df_q.columns = pd.MultiIndex.from_tuples(list(zip(df_q.columns,sub_header)))
                # Cria diretorio caso não exista
                pathlib.Path(arqv_ref).parent.mkdir(parents=True, exist_ok=True)
                # Salva o arquivo de referencia
                df_q.to_csv(arqv_ref, index=False)
                print(f"Arquivo de referencia criado: {arqv_ref}")
                # Atualiza o arquivo de quarentena com o status 'tratado'
                quarentena_df_main.loc[quarentena_df_main['qid'] == row['qid'], 'status'] = 'tratado'
                # quarentena_df_main o arquivo de quarentena com a data de tratamento
                quarentena_df_main.loc[quarentena_df_main['qid'] == row['qid'], 'data_tratamento'] = pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S')
                # Salva o arquivo de quarentena atualizado
                quarentena_df_main.to_csv(quarentena_file, index=False)
                print(f"Novo arquivo formatado criado: {arqv_ref}")
                print('-'*50)
            else:
                continue
        # Lê o arquivo de referencia, primeira linha é o cabeçalho segunda linha é o subcabeçalho
        df_ref = pd.read_csv(arqv_ref, header=[0, 1])
        # Separa subcabeçalho em uma variável e remove do DataFrame
        sub_header = df_ref.columns.get_level_values(1)
        # Remove qualquer 'Unnamed' que possa existir no sub_header e deixa vazio
        sub_header = ['' if 'Unnamed' in i else i for i in sub_header]
        df_ref.columns = df_ref.columns.get_level_values(0)
        # Salva posicao das colunas
        pos_col = df_ref.columns.tolist()

        # Seta colunas de timestamp
        df_ref['timestamp'] = pd.to_datetime(df_ref['timestamp'], errors='coerce')

        # Verifica se o cabeçalho do arquivo de quarentena é igual ao do arquivo de referencia
        if not df_q.columns.equals(df_ref.columns):
            print(f"Arquivo de quarentena {caminho} não possui o mesmo cabeçalho que o arquivo de referencia {arqv_ref}")
            continue

        # Verifica se o arquivo de quarentena tem os mesmos dados que o arquivo de referencia
        if df_q.equals(df_ref):
            print(f"Arquivo de quarentena {caminho} é igual ao arquivo de referencia {arqv_ref}")
            continue

        # Encontra os dados que estão no arquivo de quarentena e não estão no arquivo de referencia
        df_q = df_q[~df_q['timestamp'].isin(df_ref['timestamp'])]

        # Seta colunas de timestamp como index para comparação
        df_q.set_index('timestamp', inplace=True)
        # Salva lista de datas para comparação
        lista_datas = df_q.index.tolist()
        df_ref.set_index('timestamp', inplace=True)

        # Adiciona os dados do arquivo de quarentena no arquivo de referencia baseado no timestamp
        df_ref = df_ref.combine_first(df_q)

        # Reseta o index, retorna posicao das colunas e retorna o subcabeçalho 
        df_ref.reset_index(inplace=True)
        df_ref = df_ref[pos_col]
        # Adiciona o subcabeçalho de volta
        df_ref.columns = pd.MultiIndex.from_tuples(list(zip(df_ref.columns, sub_header)))

        # Sobreescreve o arquivo de referencia se o overwrite for True
        if overwrite:
            # Salva o arquivo de referencia
            df_ref.to_csv(arqv_ref, index=False)
            print(f"Arquivo de referencia {arqv_ref}...\nAtualizado com os dados do arquivo de quarentena {caminho}")
        else:
            print(f"Arquivo de referencia {arqv_ref} não foi atualizado, use o parametro --overwrite para atualizar")

        # Atualiza o arquivo de quarentena com o status 'tratado'
        quarentena_df_main.loc[quarentena_df_main['qid'] == row['qid'], 'status'] = 'tratado'
        # Atualiza o arquivo de quarentena com a data de tratamento
        quarentena_df_main.loc[quarentena_df_main['qid'] == row['qid'], 'data_tratamento'] = pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S')
        # Salva o arquivo de quarentena atualizado
        quarentena_df_main.to_csv(quarentena_file, index=False)
        print('-'*50)
        print('\n')


    

