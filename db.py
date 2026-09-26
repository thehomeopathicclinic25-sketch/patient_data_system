import os
import psycopg2
import psycopg2.extras


def get_connection():
    """Opens a new connection to the Postgres (Supabase) database."""
    database_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(database_url)


def get_dict_connection():
    """Same as get_connection, but rows come back as dictionaries (easier to work with)."""
    database_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
