import sys
import sqlite3
import subprocess
from datetime import datetime

# DB_connect.py 경로 추가
sys.path.append('/home/ec2-user/Agent/DB')

# DB 연결 함수 가져오기
from DB_connect import connect_to_db, close_connection

def update_status():
    # 현재 날짜 가져오기
    current_date = datetime.now().date()

    # DB 연결
    conn, cursor = connect_to_db()

    # trainings 테이블의 필요한 데이터 가져오기
    cursor.execute("SELECT id, training_start, training_end, status FROM trainings")
    rows = cursor.fetchall()
    

    # 상태 업데이트 여부를 저장할 리스트
    training_ids_to_notify = []


    #print(rows)
    # 각 행에 대해 상태 업데이트
    for row in rows:
        record_id, training_start, training_end, status = row
        start_date = datetime.strptime(training_start, "%Y-%m-%d %H:%M:%S.%f").date()
        end_date = datetime.strptime(training_end, "%Y-%m-%d %H:%M:%S.%f").date()

        # 상태 갱신 로직
        if current_date < start_date:
            new_status = "PLAN"
        elif start_date <= current_date <= end_date:
            new_status = "RUN"
        else:
            new_status = "FIN"

        # 상태가 변경된 경우 업데이트
        if new_status != status:
            cursor.execute("UPDATE trainings SET status = ? WHERE id = ?", (new_status, record_id))
            print(f"Record {record_id}: status updated to {new_status}")

            # 상태가 RUN인 경우에는 항상 agent.py 호출 리스트에 추가
            if new_status == "RUN" or status == "RUN":
                training_ids_to_notify.append(record_id)

    # 변경 사항 저장 및 DB 연결 종료
    conn.commit()
    close_connection(conn)

    # 상태가 RUN으로 변경된 훈련이 있다면 agent.py 호출
    for training_id in training_ids_to_notify:
        # 절대 경로를 사용하여 agent.py 호출
        subprocess.run(["/usr/bin/python3", "/home/ec2-user/Agent/agent_work/agent.py", str(training_id)], check=True)

# 상태 업데이트 함수 실행
update_status()
