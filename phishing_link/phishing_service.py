import base64
import json
import sqlite3
from datetime import datetime

# DB 경로 설정
db_path = '/home/ec2-user/Agent/e_sol.db'

# DB 연결 함수
def connect_to_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    return conn, cursor

def close_connection(conn):
    conn.close()


class PhishingEvent:
    def generate_phishing_link(self, user_data):
        """
        피싱 링크 생성 후, 결과를 반환합니다.
        """
        try:
            # 유저 정보를 JSON으로 변환 후 Base64로 인코딩
            encoded_user_data = base64.urlsafe_b64encode(json.dumps(user_data).encode()).decode().rstrip("=")

            # 피싱 링크 생성 - 주의: /click 뒤에 ?user= 쿼리 파라미터를 제대로 붙여줍니다.
            server_url = "http://127.0.0.1:7777"
            phishing_link = f"{server_url}/click?user={encoded_user_data}"  # 수정된 부분

            return phishing_link, 200

        except Exception as e:
            # 오류가 발생하면 피싱 링크 생성 실패 메시지 반환
            return f"Error generating phishing link: {str(e)}", 500


    def log_click_event(self, user_data):
        """
        피싱 링크 클릭 여부를 user_event_log 테이블에 기록합니다.
        """
        conn, cursor = connect_to_db()

        try:
            timestamp_kst = datetime.utcnow().isoformat()

            # 로그 삽입
            cursor.execute("""
                INSERT INTO user_event_log (id, name, department_id, email_id, event_type, timestamp, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_data['id'],
                user_data['name'],
                user_data['department_id'],
                user_data['email_id'],
                'link_clicked',
                timestamp_kst,
                json.dumps({"action": "clicked_link"})
            ))

            conn.commit()

        finally:
            close_connection(conn)
