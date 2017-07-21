#!/usr/bin/env bash

# export variables that are needed by the Docker image.
export FIREBIRD_AARDVARK=http://localhost:5678
export FIREBIRD_CASSANDRA_CONTACT_POINTS=127.0.0.1,127.0.1.1
export FIREBIRD_CASSANDRA_USER=cassandra
export FIREBIRD_CASSANDRA_PASS=cassandra
export FIREBIRD_CASSANDRA_KEYSPACE=lcmap_changes_local
export FIREBIRD_INITIAL_PARTITION_COUNT=1
export FIREBIRD_PRODUCT_PARTITION_COUNT=1
export FIREBIRD_STORAGE_PARTITION_COUNT=1
export FIREBIRD_LOG_LEVEL=WARN

# Mesos authentication over SSL only.
# Mount docker volume paths to match certificate and key file paths.
# These are obtained from sysadmins.  Do not commit to public repos.
# export LIBPROCESS_SSL_ENABLED	1
# export LIBPROCESS_SSL_SUPPORT_DOWNGRADE	true
# export LIBPROCESS_SSL_VERIFY_CERT	0
# export LIBPROCESS_SSL_CERT_FILE	/certs/mesos.cert
# export LIBPROCESS_SSL_KEY_FILE	/certs/mesos.key
# export LIBPROCESS_SSL_CA_DIR	/certs/mesos_certpack/
# export LIBPROCESS_SSL_CA_FILE	/certs/cacert.crt
# export LIBPROCESS_SSL_ENABLE_SSL_V3	0
# export LIBPROCESS_SSL_ENABLE_TLS_V1_0	0
# export LIBPROCESS_SSL_ENABLE_TLS_V1_1	0
# export LIBPROCESS_SSL_ENABLE_TLS_V1_2	1

IMAGE=lcmap-firebird:2017.04.25
VOLUME=`echo ~/.certs`:/certs
BASE="docker run -v $VOLUME --network=host -it --rm $IMAGE"

alias firebird-version="$BASE firebird show version"
alias firebird-products="$BASE firebird show products"
alias firebird-algorithms="$BASE firebird show algorithms"
alias firebird-notebook="$BASE jupyter --ip=$HOSTNAME notebook"
alias firebird-shell="$BASE /bin/bash"

# Spark runtime configuration options are available at
# https://spark.apache.org/docs/latest/configuration.html
#
# This constrains the number of cores Spark requests from Mesos
# (or a standalone cluster).  If unset it asks for all of them.
# --conf spark.cores.max=500
#
alias firebird-save="$BASE spark-submit \
                           --conf spark.app.name='A clever name with timestamp' \
                           --conf spark.executor.cores=1 \
                           --conf spark.master=mesos://localhost:7077 \
                           --conf spark.mesos.principal=mesos \
                           --conf spark.mesos.secret=mesos \
                           --conf spark.mesos.role=mesos \
                           --conf spark.mesos.executor.docker.forcePullImage=false \
                           --conf spark.mesos.executor.docker.image=$IMAGE \
                           --conf spark.submit.pyFiles=local:///algorithms/pyccd-v2017.06.20.zip \
                           /app/firebird/cmdline.py save"
