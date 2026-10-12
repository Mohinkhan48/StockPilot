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

# TiDB compatibility:
# TiDB does not support combining ADD COLUMN and ADD CONSTRAINT FOREIGN KEY in a single
# multi-clause ALTER TABLE statement (raising Error 1072: Key column doesn't exist).
# When connected to TiDB (detected via host, server version, or TIDB env var),
# set sql_create_column_inline_fk = None so Django adds foreign-key columns first,
# then adds the foreign key constraints as separate ALTER TABLE statements.
from django.db.backends.mysql.schema import DatabaseSchemaEditor

_orig_schema_editor_init = DatabaseSchemaEditor.__init__


def _tidb_schema_editor_init(self, connection, collect_sql=False, atomic=True):
    _orig_schema_editor_init(self, connection, collect_sql=collect_sql, atomic=atomic)
    host = connection.settings_dict.get('HOST', '').lower()
    is_tidb = 'tidb' in host
    if not is_tidb:
        import os
        if os.environ.get('TIDB', '').lower() in ('1', 'true', 'yes'):
            is_tidb = True
    if not is_tidb:
        try:
            if 'tidb' in str(getattr(connection, 'mysql_server_info', '')).lower():
                is_tidb = True
        except Exception:
            pass
    if is_tidb:
        self.sql_create_column_inline_fk = None


DatabaseSchemaEditor.__init__ = _tidb_schema_editor_init
