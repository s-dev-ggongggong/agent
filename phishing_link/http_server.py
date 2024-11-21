from flask import Flask, request, jsonify,  render_template 
from flask_cors import CORS  # CORS 라이브러리 추가
import sys
import base64
import json
import sqlite3

# phishing_link 경로 추가
sys.path.append('/home/ec2-user/Agent/phishing_link')

from phishing_service import PhishingEvent

app = Flask(__name__)

# CORS 설정 추가
CORS(app)  # 모든 도메인에서의 CORS 요청을 허용합니다.

#db_path = '/home/ec2-user/whd/BE/db/e_sol.db'

db_path = '/home/ec2-user/whd/BE/db/e_sol2.db' 

# DB 연결 함수
def connect_to_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    return conn, cursor

def close_connection(conn):
    conn.close()

@app.route('/click', methods=['GET'])
def handle_click():
    user_param = request.args.get('user')

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
            return render_template('GitHub - Login.html')
            #return jsonify({"message": "Phishing link clicked! Thank you."}), 200

        except (base64.binascii.Error, json.JSONDecodeError) as e:
            # Base64 디코딩 또는 JSON 파싱 오류 처리
            return jsonify({"error": f"Invalid user data: {str(e)}"}), 400
    else:
        return jsonify({"error": "Missing user parameter."}), 400

@app.route('/training/<int:training_id>', methods=['GET'])
def get_training(training_id):
    """ GET /training/:id 요청을 처리하는 메서드 """
    try:
        # DB 연결 및 데이터 조회
        conn, cursor = connect_to_db()

        # training 테이블에서 데이터 가져오기
        cursor.execute("SELECT * FROM trainings WHERE id = ?", (training_id,))
        training_data = cursor.fetchone()

        if training_data:
            # training 데이터를 딕셔너리로 변환
            training_dict = dict(training_data)

            # event_logs 테이블에서 관련 데이터 가져오기
            cursor.execute("SELECT * FROM event_logs WHERE training_id = ?", (training_id,))
            event_logs = [dict(row) for row in cursor.fetchall()]

            # emails 테이블에서 관련 데이터 가져오기
            cursor.execute("SELECT * FROM emails WHERE training_id = ?", (training_id,))
            emails = [dict(row) for row in cursor.fetchall()]

            # user_event_logs 테이블에서 관련 데이터 가져오기
            cursor.execute("SELECT * FROM user_event_logs WHERE training_id = ?", (training_id,))
            user_event_logs = [dict(row) for row in cursor.fetchall()]

            # 응답 데이터 구성
            response_data = {
                "training": training_dict,
                "event_logs": event_logs,
                "emails": emails,
                "user_event_logs": user_event_logs
            }

            return jsonify(response_data), 200

        else:
            return jsonify({"error": f"Training with ID {training_id} not found"}), 404

    except sqlite3.Error as e:
        # 데이터베이스 오류 처리
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    finally:
        # 연결 종료
        close_connection(conn)

# Flask 앱 실행 함수
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7777, debug=True)
