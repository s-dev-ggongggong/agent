import sqlite3

# 하나의 고정된 DB 경로 설정
#db_path = '/home/ec2-user/BE/db/e_sol.db'
db_path = '/home/ec2-user/Agent/e_sol.db'

def connect_to_db():
    """DB에 연결하고 커서를 반환"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    return conn, cursor

def close_connection(conn):
    """DB 연결 종료"""
    conn.close()
