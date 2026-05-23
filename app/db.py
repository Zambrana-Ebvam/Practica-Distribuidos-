from cassandra.cluster import Cluster
from cassandra.query import dict_factory

CASSANDRA_HOSTS = ["127.0.0.1"]
CASSANDRA_PORT = 9042
KEYSPACE = "semapa"


def get_session():
    cluster = Cluster(
        contact_points=CASSANDRA_HOSTS,
        port=CASSANDRA_PORT
    )

    session = cluster.connect(KEYSPACE)
    session.row_factory = dict_factory
    session.default_timeout = 60
    return session