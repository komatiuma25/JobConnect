
import os
import oracledb


def get_connection():
    """Create and return an Oracle Database connection."""
    connection = oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        host=os.environ["ORACLE_HOST"],
        port=int(os.environ.get("ORACLE_PORT", "1522")),
        service_name=os.environ.get("ORACLE_SERVICE_NAME", "FREEPDB1")
    )

    return connection
