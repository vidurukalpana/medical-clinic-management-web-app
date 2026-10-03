# Same PostgreSQL major version as the db service, so pg_dump and pg_restore match the server.
FROM postgres:17-alpine

RUN apk add --no-cache aws-cli tzdata

COPY --chmod=0755 backup.sh /usr/local/bin/clinic-backup

RUN mkdir -p /backups && chown postgres:postgres /backups
USER postgres
WORKDIR /backups

# Runs a backup once a day. Other commands: backup-now, list, restore <file|s3-uri>.
ENTRYPOINT ["clinic-backup"]
CMD ["schedule"]
