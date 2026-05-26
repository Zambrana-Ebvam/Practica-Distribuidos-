import os
# pyrefly: ignore [missing-import]
from cassandra.cluster import Cluster
# pyrefly: ignore [missing-import]
from cassandra.query import dict_factory

# Carga de configuración de Cassandra desde variables de entorno con defaults para Windows local / Docker Desktop
CASSANDRA_HOST_ENV = os.getenv("CASSANDRA_HOST", "127.0.0.1")
CASSANDRA_HOSTS = [host.strip() for host in CASSANDRA_HOST_ENV.split(",") if host.strip()]
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "semapa")


def get_session():
    cluster = Cluster(
        contact_points=CASSANDRA_HOSTS,
        port=CASSANDRA_PORT
    )

    session = cluster.connect(KEYSPACE)
    session.row_factory = dict_factory
    session.default_timeout = 60
    return session