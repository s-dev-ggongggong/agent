import sys
from datetime import datetime
import subprocess
import sqlite3
import random
import json  # JSON 파싱을 위한 모듈 추가

# DB_connect.py 경로 추가
sys.path.append('/home/ec2-user/Agent/DB')

from DB_connect import connect_to_db, close_connection  # DB_connect.py에서 함수 가져오기

def get_training_details(cursor, training_id):
    """training 테이블에서 훈련 제목 및 resource_user(int)를 추출"""
    cursor.execute("SELECT training_name, resource_user FROM trainings WHERE id = ?", (training_id,))
    result = cursor.fetchone()
    return result if result else (None, None)

def get_department_ids(cursor, training_id):
    """event_logs 테이블에서 training_id와 action이 targetSetting인 경우의 모든 department_id 추출"""
    cursor.execute("SELECT department_id FROM event_logs WHERE training_id = ? AND action = 'targetSetting'", (training_id,))
    results = cursor.fetchall()
    
    # department_id를 JSON으로 파싱하여 유효한 값만 리스트로 반환
    department_ids = []
    for row in results:
        try:
            department_json = json.loads(row[0])  # JSON 파싱
            if isinstance(department_json, list):
                department_ids.extend(department_json)  # 리스트 안의 값을 추가
            else:
                department_ids.append(department_json)  # 단일 값을 추가
        except json.JSONDecodeError:
            continue  # JSON 파싱이 실패하면 건너뜀
    
    return department_ids  # 모든 유효한 department_id를 리스트로 반환

def get_emails_by_department(cursor, department_id):
    """employees 테이블에서 department_id를 기반으로 부서 내 직원들의 이메일 주소를 추출"""
    cursor.execute("SELECT email FROM employees WHERE department_id = ?", (department_id,))
    results = cursor.fetchall()
    return [row[0] for row in results]  # 이메일 주소 리스트 반환

def main():
    if len(sys.argv) != 2:
        sys.exit(1)  # 잘못된 인수 개수로 종료

    training_id = sys.argv[1]

    # DB 연결
    conn, cursor = connect_to_db()

    try:
        # 훈련 제목 및 resource_user 값 추출
        training_name, resource_user = get_training_details(cursor, training_id)

        # training_id와 action이 targetSetting인 경우의 모든 department_id 추출
        department_ids = get_department_ids(cursor, training_id)
        if department_ids:
            emails = []
            # 각 department_id에 대해 부서 내 이메일 주소를 추출
            for department_id in department_ids:
                emails.extend(get_emails_by_department(cursor, department_id))

            if emails:
                # resource_user 값만큼의 이메일을 랜덤으로 선택
                selected_emails = random.sample(emails, resource_user)

                # 선택된 이메일 주소를 resource_user.txt에 저장
                resource_user_file_path = "/home/ec2-user/Agent/email/resource/resource_user.txt"
                with open(resource_user_file_path, "w") as resource_file:
                    for email in selected_emails:
                        resource_file.write(email + "\n")

                # email_address.txt에 남은 이메일 주소 저장 (resource_user 제외)
                remaining_emails = [email for email in emails if email not in selected_emails]
                email_file_path = "/home/ec2-user/Agent/email/resource/email_address.txt"
                with open(email_file_path, "w") as email_file:
                    for email in remaining_emails:
                        email_file.write(email + "\n")

                # scanner.py 경로
                scanner_path = "/home/ec2-user/Agent/email/work/scanner.py"

                # department_ids 중 첫 번째 값을 선택하거나 필요에 따라 변경
                selected_department_id = department_ids[0]  # 예시로 첫 번째 department_id 사용

                # scanner.py 호출, 이메일 주소 파일, resource_user 파일, training_id, department_id를 인자로 넘김
                subprocess.run(
                    ["python3", scanner_path, email_file_path, resource_user_file_path, training_id, str(selected_department_id)], 
                    check=True
                )

        # 변경 사항 저장
        conn.commit()

    finally:
        # DB 연결 종료
        close_connection(conn)

if __name__ == "__main__":
    main()
