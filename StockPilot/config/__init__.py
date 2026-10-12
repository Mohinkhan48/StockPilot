# Ensure MySQL connectivity across all deployment environments.
# If mysqlclient is installed, it is used directly; otherwise fallback to PyMySQL.
try:
    import MySQLdb  # noqa: F401
except ImportError:
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
