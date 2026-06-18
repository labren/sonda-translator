#!/bin/bash
#
# copy_ftp.sh - Sincroniza a estrutura de dados do FTP da rede SONDA para o
# repositório local, transferindo SOMENTE arquivos .DAT/.dat.
#
# Características:
#   - Inclui apenas arquivos .DAT/.dat (ignora imagens, PDFs, .nc, etc.)
#   - Redundância de falhas: várias tentativas com backoff exponencial
#   - Retomada: arquivos já sincronizados são pulados e transferências
#     interrompidas no meio do arquivo continuam de onde pararam (--partial)
#
# Configuração por variáveis de ambiente (com valores padrão):
#   SRC, DEST, SSH_KEY, MAX_RETRIES, BWLIMIT, IO_TIMEOUT, CONN_TIMEOUT,
#   DELETE (true/false), DRY_RUN (true/false)
#
# Uso:
#   ./copy_ftp.sh                 # sincronização normal
#   DRY_RUN=true ./copy_ftp.sh    # simula, sem transferir nada
#   DELETE=false ./copy_ftp.sh    # não apaga arquivos locais removidos no FTP

# Não usamos 'set -e' porque tratamos os códigos de saída do rsync manualmente.
set -uo pipefail

############################# Configuração #############################
SRC="${SRC:-labren@150.163.105.82:/mnt/ftp/restricted/coleta/}"
DEST="${DEST:-/media/helvecioneto/Barracuda/ftp/restricted/coleta/}"
SSH_KEY="${SSH_KEY:-}"                 # caminho para chave SSH (opcional)
MAX_RETRIES="${MAX_RETRIES:-20}"
BWLIMIT="${BWLIMIT:-0}"                # limite de banda em KB/s (0 = ilimitado)
IO_TIMEOUT="${IO_TIMEOUT:-300}"        # timeout de I/O do rsync (segundos)
CONN_TIMEOUT="${CONN_TIMEOUT:-30}"     # timeout de conexão do rsync (segundos)
DELETE="${DELETE:-true}"               # espelhar remoções de .DAT do FTP
DRY_RUN="${DRY_RUN:-false}"            # true = simula sem transferir

# Garante barra final nos caminhos (rsync é sensível a isso).
[[ "$SRC" == */ ]] || SRC="$SRC/"
[[ "$DEST" == */ ]] || DEST="$DEST/"

PARTIAL_DIR="${DEST}.rsync-partial"    # arquivos parciais (para retomada)
LOG_FILE="${DEST}.rsync.log"
LOCK_DIR="${DEST}.rsync.lock"          # trava contra execuções simultâneas

############################# Funções #############################
log() {
    # Mensagem com timestamp, no stdout e no arquivo de log.
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

cleanup() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}

# Monta o comando SSH com keepalive e timeouts (mais resistente a quedas).
build_ssh_cmd() {
    local ssh="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=5"
    ssh="$ssh -o ConnectTimeout=${CONN_TIMEOUT} -o StrictHostKeyChecking=accept-new"
    if [ -n "$SSH_KEY" ]; then
        ssh="$ssh -i $SSH_KEY"
    fi
    echo "$ssh"
}

sync_files() {
    local attempt=1
    local backoff=10                   # segundos; cresce exponencialmente até um teto
    local ssh_cmd
    ssh_cmd="$(build_ssh_cmd)"

    # Opções base do rsync.
    local rsync_opts=(
        -a                              # modo arquivo (preserva estrutura/permissões/tempos)
        --info=progress2                # barra de progresso global (rsync 3.x)
        --stats                         # estatísticas finais da transferência
        --human-readable
        --partial                       # mantém arquivos parciais para retomar
        --partial-dir="$PARTIAL_DIR"    # guarda os parciais fora do caminho final
        --delay-updates                 # só "promove" o arquivo quando completo
        --timeout="$IO_TIMEOUT"
        --contimeout="$CONN_TIMEOUT"
        --bwlimit="$BWLIMIT"
        --log-file="$LOG_FILE"
        --prune-empty-dirs              # não cria árvore de diretórios vazia
        -e "$ssh_cmd"
    )

    # Espelha remoções de .DAT (sem nunca apagar arquivos locais que NÃO são
    # alvo do filtro — eles são protegidos por padrão, pois ficam excluídos).
    if [ "$DELETE" = "true" ]; then
        rsync_opts+=(--delete-delay)
    fi

    if [ "$DRY_RUN" = "true" ]; then
        rsync_opts+=(--dry-run)
        log "MODO SIMULAÇÃO (DRY_RUN): nenhum arquivo será transferido."
    fi

    # ---- Filtros: transferir APENAS .DAT/.dat ----
    # A ordem importa (primeira regra que casa vence):
    #   1) Pula diretórios pesados que nunca têm .DAT (acelera a varredura).
    #   2) Desce em todos os demais diretórios.
    #   3) Inclui os arquivos .DAT/.dat (ambas as grafias).
    #   4) Exclui todo o resto.
    local filters=(
        --exclude='camera/'
        --exclude='security/'
        --include='*/'
        --include='*.DAT'
        --include='*.dat'
        --exclude='*'
    )

    mkdir -p "$PARTIAL_DIR"

    while [ "$attempt" -le "$MAX_RETRIES" ]; do
        log "Tentativa $attempt de $MAX_RETRIES..."

        rsync "${rsync_opts[@]}" "${filters[@]}" "$SRC" "$DEST"
        local rc=$?

        # 0 = sucesso; 24 = arquivos sumiram na origem durante a cópia (benigno).
        if [ "$rc" -eq 0 ] || [ "$rc" -eq 24 ]; then
            log "Transferência concluída com sucesso (código $rc)."
            return 0
        fi

        log "Falha na transferência (código rsync $rc)."
        if [ "$attempt" -lt "$MAX_RETRIES" ]; then
            log "Nova tentativa em ${backoff}s (retoma de onde parou)..."
            sleep "$backoff"
            # Backoff exponencial com teto de 300s.
            backoff=$(( backoff * 2 ))
            [ "$backoff" -gt 300 ] && backoff=300
        fi
        attempt=$(( attempt + 1 ))
    done

    log "Falha após $MAX_RETRIES tentativas. Verifique a conexão e tente novamente."
    return 1
}

############################# Execução #############################
mkdir -p "$DEST" 2>/dev/null || true

# Trava simples e atômica (mkdir) contra duas execuções concorrentes.
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    log "Outra sincronização parece estar em andamento (trava: $LOCK_DIR). Abortando."
    exit 1
fi
trap cleanup EXIT INT TERM

log "Iniciando sincronização: $SRC -> $DEST"
sync_files
rc=$?
log "Finalizado com código $rc."
exit "$rc"
