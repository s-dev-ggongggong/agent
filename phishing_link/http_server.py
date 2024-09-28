import sys
import base64
import json
import sqlite3
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer

# phishing_link 경로 추가
sys.path.append('/home/ec2-user/Agent/phishing_link')

from phishing_service import PhishingEvent

# DB 경로 설정
db_path = '/home/ec2-user/Agent/e_sol.db'

def connect_to_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    return conn, cursor

def close_connection(conn):
    conn.close()

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        # favicon.ico 요청 무시
        if parsed_url.path == '/favicon.ico':
            self.send_response(204)  # No Content
            self.end_headers()
            return

        if parsed_url.path == '/click':
            query_params = parse_qs(parsed_url.query)
            user_param = query_params.get('user', [None])[0]

            if user_param:
                try:
                    # 패딩 추가 후 Base64 디코딩
                    padding = "=" * ((4 - len(user_param) % 4) % 4)
                    decoded_user_data = base64.urlsafe_b64decode(user_param + padding).decode('utf-8')
                    user_data = json.loads(decoded_user_data)

                    # 피싱 클릭 로그 기록
                    phishing_event = PhishingEvent()
                    phishing_event.log_click_event(user_data)

                    # 성공 응답
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"message": "Phishing link clicked! Thank you."}
                    self.wfile.write(json.dumps(response).encode())

                except (base64.binascii.Error, json.JSONDecodeError) as e:
                    # Base64 디코딩 또는 JSON 파싱 오류 처리
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    error_message = {"error": f"Invalid user data: {str(e)}"}
                    self.wfile.write(json.dumps(error_message).encode())
            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing user parameter."}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode())


# HTTP 서버 실행 함수
def run_server(port=7777):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"Server running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
