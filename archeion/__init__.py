#added line 2 and 3
import pymysql
pymysql.install_as_MySQLdb()
import pymysql
import os

if os.environ.get('DB_ENGINE') == 'mysql':
    import pymysql
    pymysql.install_as_MySQLdb()