#!/bin/bash
FECHA=$(date +"%Y-%m-%d_%H%M")
ORIGEN="/home/jimena_martinez/fng_app/control_maestro_v6.db"
DESTINO="/home/jimena_martinez/respaldos_fng/backup_fng_$FECHA.db"

# Respaldo en caliente atómico usando Python nativo
python3 -c "import sqlite3; s=sqlite3.connect('$ORIGEN'); d=sqlite3.connect('$DESTINO'); s.backup(d); d.close(); s.close()"

# Conservar solo los respaldos de los últimos 15 días
find /home/jimena_martinez/respaldos_fng/ -type f -name "*.db" -mtime +15 -delete
