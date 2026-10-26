import oracledb


def get_connection():
    """Create and return an Oracle Database connection."""
    connection = oracledb.connect(
        user="jobconnect",
        password="JobConnect2026",
        host="umashankar",
        port=1522,
        service_name="FREEPDB1"
    )

    return connection