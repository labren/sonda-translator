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
#   SRC, DEST, SSH_KEY, MAX_RETRIES, PARTIAL_RETRIES, BWLIMIT, IO_TIMEOUT,
#   CONN_TIMEOUT, DELETE, DRY_RUN, CHECKSUM, VERBOSE, INUSE  (true/false)
#
# Uso:
#   ./copy_ftp.sh                 # sincronização normal (já baixa arquivos em uso por padrão)
#   DRY_RUN=true ./copy_ftp.sh    # simula, sem transferir nada
#   INUSE=false ./copy_ftp.sh     # desliga o modo arquivos-em-uso (grava só arquivos completos)
#   CHECKSUM=true ./copy_ftp.sh   # compara por conteúdo (mais seguro, mais lento)
#   DELETE=true ./copy_ftp.sh     # (opcional) espelha: remove do DESTINO LOCAL os .DAT
#                                 # que sumiram no FTP. A origem/FTP nunca é alterada.

# Não usamos 'set -e' porque tratamos os códigos de saída do rsync manualmente.
set -uo pipefail

############################# Configuração #############################
SRC="${SRC:-labren@150.163.105.82:/mnt/ftp/restricted/coleta/}"
DEST="${DEST:-/media/helvecioneto/Barracuda/ftp/restricted/coleta/}"
SSH_KEY="${SSH_KEY:-}"                 # caminho para chave SSH (opcional)
MAX_RETRIES="${MAX_RETRIES:-20}"       # retries para falhas de conexão/transporte
PARTIAL_RETRIES="${PARTIAL_RETRIES:-2}" # passagens extras quando alguns arquivos não puderam ser lidos (código 23)
BWLIMIT="${BWLIMIT:-0}"                # limite de banda em KB/s (0 = ilimitado)
IO_TIMEOUT="${IO_TIMEOUT:-300}"        # timeout de I/O do rsync (segundos)
CONN_TIMEOUT="${CONN_TIMEOUT:-30}"     # timeout de conexão SSH (ConnectTimeout, segundos)
DELETE="${DELETE:-false}"              # false = só copia (nunca apaga nada no destino local; a ORIGEM/FTP nunca é tocada)
DRY_RUN="${DRY_RUN:-false}"            # true = simula sem transferir
CHECKSUM="${CHECKSUM:-false}"          # true = compara por conteúdo (checksum) em vez de tamanho+data
VERBOSE="${VERBOSE:-true}"             # true = lista cada arquivo transferido
INUSE="${INUSE:-true}"                 # true (padrão) = baixa arquivos em uso mantendo o trecho parcial (--inplace); INUSE=false para desligar

# Garante barra final nos caminhos (rsync é sensível a isso).
[[ "$SRC" == */ ]] || SRC="$SRC/"
[[ "$DEST" == */ ]] || DEST="$DEST/"

# Nome RELATIVO de propósito: o rsync cria um ".rsync-partial" dentro de CADA
# diretório, mantendo o parcial ao lado do arquivo final. Um caminho absoluto
# juntaria todos os parciais numa pasta plana e causaria colisão de nomes
# (ex.: dois SMS_10.DAT em pastas diferentes) e falhas de rename.
PARTIAL_DIR=".rsync-partial"           # arquivos parciais por diretório (para retomada)
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
        --info=progress2                # progresso global: %, velocidade, ETA (rsync 3.x)
        --stats                         # estatísticas finais da transferência
        --human-readable
        --timeout="$IO_TIMEOUT"
        --bwlimit="$BWLIMIT"
        --log-file="$LOG_FILE"
        --prune-empty-dirs              # não cria árvore de diretórios vazia
        -e "$ssh_cmd"
    )

    # Lista cada arquivo conforme é transferido (ajuda a saber o que está
    # acontecendo). Arquivos PULADOS não são listados — então, em execuções
    # seguintes, a tela fica naturalmente quieta quando não há nada novo.
    if [ "$VERBOSE" = "true" ]; then
        rsync_opts+=(--verbose)
    fi

    # Critério para considerar um arquivo "já sincronizado" e pular o download:
    #   - padrão: tamanho + data de modificação (rápido; o -a preserva a data,
    #     então re-execuções pulam o que é idêntico, sem baixar de novo).
    #   - CHECKSUM=true: compara o CONTEÚDO (checksum) — mais seguro, porém lê o
    #     arquivo inteiro nas duas pontas (lento em grandes volumes).
    if [ "$CHECKSUM" = "true" ]; then
        rsync_opts+=(--checksum)
    fi

    # Retomada + tratamento de arquivos EM USO (que mudam durante a cópia):
    #   - padrão: --partial-dir relativo; o parcial fica numa pasta oculta por
    #     diretório e o arquivo só aparece no destino quando completo (atômico).
    #   - INUSE=true: --inplace escreve direto no arquivo de destino, então o
    #     trecho já baixado de um arquivo em uso/crescendo é MANTIDO (não é
    #     descartado na verificação). Aceita-se um instantâneo parcial, que pode
    #     não ser a parte final do arquivo. (--inplace não combina com partial-dir.)
    if [ "$INUSE" = "true" ]; then
        rsync_opts+=(--partial --inplace)
        log "Modo INUSE: arquivos em uso terão o trecho baixado mantido (snapshot parcial)."
    else
        rsync_opts+=(--partial --partial-dir="$PARTIAL_DIR")
    fi

    # IMPORTANTE: o rsync NUNCA apaga nada na ORIGEM (o FTP é somente-leitura).
    # O --delete só afetaria o DESTINO local. Por padrão fica DESLIGADO: este
    # script apenas COPIA. Se DELETE=true, ele removeria do destino local os
    # .DAT que sumiram no FTP (e pode gerar avisos "cannot delete non-empty
    # directory" para pastas que ainda têm arquivos não-.DAT protegidos).
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
        --exclude="$PARTIAL_DIR/"        # nunca trata a pasta de parciais como conteúdo
        --exclude='camera/'
        --exclude='security/'
        --include='*/'
        --include='*.DAT'
        --include='*.dat'
        --exclude='*'
    )

    local partial_attempt=0

    while [ "$attempt" -le "$MAX_RETRIES" ]; do
        log "Tentativa $attempt de $MAX_RETRIES..."
        log "Conectando e varrendo a árvore remota do FTP. A 1ª varredura pode"
        log "levar alguns minutos SEM mostrar progresso; arquivos já baixados e"
        log "idênticos são pulados automaticamente (não baixam de novo)."

        rsync "${rsync_opts[@]}" "${filters[@]}" "$SRC" "$DEST"
        local rc=$?

        # 0 = sucesso; 24 = arquivos sumiram na origem durante a cópia (benigno).
        if [ "$rc" -eq 0 ] || [ "$rc" -eq 24 ]; then
            log "Transferência concluída com sucesso (código $rc)."
            return 0
        fi

        # 23 = transferência parcial: ALGUNS arquivos não puderam ser lidos na
        # origem (ex.: "Permission denied" ou arquivo em uso que mudou durante a
        # cópia). Os demais JÁ foram baixados e ficam salvos (não serão rebaixados,
        # pois removemos o --delay-updates: o arquivo completo é promovido na hora).
        # Fazemos poucas passagens extras (pegam arquivos que estavam só
        # temporariamente em uso) e então concluímos com avisos — sem refazer a
        # varredura de minutos dezenas de vezes por causa de arquivos sem permissão.
        if [ "$rc" -eq 23 ]; then
            partial_attempt=$(( partial_attempt + 1 ))
            if [ "$partial_attempt" -gt "$PARTIAL_RETRIES" ]; then
                log "Concluído com AVISOS: alguns arquivos não puderam ser lidos na origem"
                log "(permissão negada ou em uso). Os arquivos legíveis foram baixados e salvos."
                log "Detalhes ('Permission denied' / 'failed verification') no log: $LOG_FILE"
                return 0
            fi
            log "Código 23: alguns arquivos ficaram para trás. Nova passagem para tentar"
            log "pegá-los (parcial $partial_attempt/$PARTIAL_RETRIES); o que já baixou é mantido..."
            sleep 5
            continue
        fi

        # Demais códigos: falha de conexão/transporte -> retry com backoff.
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
