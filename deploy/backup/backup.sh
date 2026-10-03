#!/bin/sh
# PostgreSQL backups for the clinic database.
# Dumps are kept in /backups for a few days and copied to S3 when BACKUP_S3_BUCKET is set.
#
#   schedule          back up once a day at BACKUP_TIME (default)
#   backup-now        back up immediately
#   list              show backups on this server and in S3
#   restore <source>  restore a dump: a file name in /backups or an s3:// URI
set -eu

export PGHOST="${PGHOST:-db}"
export PGUSER="$POSTGRES_USER"
export PGPASSWORD="$POSTGRES_PASSWORD"
export PGDATABASE="$POSTGRES_DB"
export TZ="${TZ:-${CLINIC_TIMEZONE:-UTC}}"

BACKUP_DIR=/backups
BACKUP_TIME="${BACKUP_TIME:-02:00}"
KEEP_LOCAL_DAYS="${BACKUP_KEEP_LOCAL_DAYS:-7}"
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
S3_PREFIX="${BACKUP_S3_PREFIX:-postgres}"
LAST_SUCCESS="$BACKUP_DIR/.last-success"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*"
}

backup_now() {
    rm -f "$BACKUP_DIR"/.*.partial
    name="${PGDATABASE}_$(date -u +%Y%m%dT%H%M%SZ).dump"
    partial="$BACKUP_DIR/.$name.partial"

    log "Dumping $PGDATABASE"
    pg_dump --format=custom --compress=9 --file="$partial"
    # A dump that pg_restore cannot read is not a backup.
    pg_restore --list "$partial" > /dev/null
    mv "$partial" "$BACKUP_DIR/$name"
    log "Wrote $name ($(du -h "$BACKUP_DIR/$name" | cut -f1))"

    if [ -n "$S3_BUCKET" ]; then
        aws s3 cp --only-show-errors --sse AES256 "$BACKUP_DIR/$name" "s3://$S3_BUCKET/$S3_PREFIX/$name"
        log "Uploaded to s3://$S3_BUCKET/$S3_PREFIX/$name"
    else
        log "WARNING: BACKUP_S3_BUCKET is empty, so this backup exists only on this server"
    fi

    find "$BACKUP_DIR" -name "${PGDATABASE}_*.dump" -mtime +"$KEEP_LOCAL_DAYS" -delete
    touch "$LAST_SUCCESS"
}

# Runs in its own process so `set -e` stops a failed backup without stopping the scheduler.
run_backup() {
    clinic-backup backup-now || log "ERROR: backup failed"
}

seconds_until_next_run() {
    now=$(date +%s)
    next=$(date -d "$(date +%Y-%m-%d) $BACKUP_TIME" +%s)
    [ "$next" -gt "$now" ] || next=$((next + 86400))
    echo $((next - now))
}

schedule() {
    log "Daily backups at $BACKUP_TIME ($TZ)"
    # Back up straight away after a deploy if the last good backup is more than a day old.
    if [ -z "$(find "$LAST_SUCCESS" -mmin -1440 2>/dev/null)" ]; then
        run_backup
    fi
    while true; do
        sleep "$(seconds_until_next_run)"
        run_backup
    done
}

list() {
    echo "On this server ($BACKUP_DIR):"
    ls -lh "$BACKUP_DIR"/*.dump 2>/dev/null || echo "  none"
    if [ -n "$S3_BUCKET" ]; then
        echo "In s3://$S3_BUCKET/$S3_PREFIX/:"
        aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/"
    fi
}

restore() {
    source="${1:?usage: restore <file in /backups | s3://bucket/key>}"
    case "$source" in
        s3://*)
            file="$BACKUP_DIR/$(basename "$source")"
            aws s3 cp --only-show-errors "$source" "$file"
            ;;
        /*) file="$source" ;;
        *) file="$BACKUP_DIR/$source" ;;
    esac

    pg_restore --list "$file" > /dev/null
    log "Restoring $file into $PGDATABASE (existing tables are replaced)"
    pg_restore --clean --if-exists --no-owner --single-transaction --exit-on-error \
        --dbname="$PGDATABASE" "$file"
    log "Restore finished"
}

command="${1:-schedule}"
[ $# -gt 0 ] && shift
case "$command" in
    schedule) schedule ;;
    backup-now) backup_now ;;
    list) list ;;
    restore) restore "$@" ;;
    *)
        echo "Unknown command: $command (use schedule, backup-now, list or restore)" >&2
        exit 2
        ;;
esac
