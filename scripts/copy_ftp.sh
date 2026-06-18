#!/bin/bash

SRC="labren@150.163.105.82:/mnt/ftp/restricted/coleta/"
DEST="/media/helvecioneto/Barracuda/ftp/restricted/coleta/"
MAX_RETRIES=20
PARTIAL_DIR="$DEST/.rsync-partial"
LOG_FILE="$DEST/.rsync.log"

# Função para executar o rsync com tentativas
sync_files() {
    local attempt=1
    
    # Cria diretório para arquivos parciais se não existir
    mkdir -p "$PARTIAL_DIR"
    
    # Define o comando SSH se a chave estiver definida
    local ssh_cmd=""
    if [ -n "$SSH_KEY" ]; then
        ssh_cmd="-e ssh $SSH_KEY"
    fi
    
    while [ $attempt -le $MAX_RETRIES ]; do
        echo "Tentativa $attempt de $MAX_RETRIES..."

        rsync -avz --progress --partial --partial-dir="$PARTIAL_DIR" \
            --delay-updates --timeout=300 --bwlimit=0 \
            --log-file="$LOG_FILE" \
            $ssh_cmd \
            --exclude='camera/' \
            --exclude='security/' \
            --exclude='*/camera/' \
            --exclude='*/security/' \
            --exclude='*.jpg' \
            --exclude='*.jpeg' \
            --exclude='*.JPG' \
            --exclude='*.png' \
            --exclude='*.gif' \
            --exclude='*.bmp' \
            --exclude='*.tiff' \
            --exclude='*.svg' \
            --exclude='*.webp' \
            --exclude='*.pdf' \
            --exclude='*.nc' \
            --prune-empty-dirs \
            --delete-delay \
            --size-only \
            --info=progress2 "$SRC" "$DEST"

        if [ $? -eq 0 ]; then
            echo "Transferência concluída com sucesso!"
            return 0
        else
            echo "Falha na transferência. Tentando novamente em 10 segundos..."
            sleep 10
        fi
        ((attempt++))
    done
    echo "Falha após $MAX_RETRIES tentativas. Verifique a conexão e tente novamente."
    return 1
}

# Executa a sincronização
sync_files
