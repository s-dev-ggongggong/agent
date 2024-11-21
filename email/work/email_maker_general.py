import sys
import requests
import json
import sqlite3
from datetime import datetime
import subprocess
import re

# phishing_link 경로를 Python 경로에 추가
sys.path.append('/home/ec2-user/Agent/phishing_link')  # phishing_link 폴더 경로 추가

# phishing_service.py에서 PhishingEvent 클래스 임포트
from phishing_service import PhishingEvent

# DB_connect.py 경로 추가
sys.path.append('/home/ec2-user/Agent/DB')

from DB_connect import connect_to_db, close_connection  # DB_connect.py에서 함수 가져오기


def request_openai(prompt):
    """OpenAI API 요청"""
    api_key = "" 
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "gpt-4-turbo",
        "messages": [
            {"role": "system", "content": "같은 부서 사람끼리 주고받을 만한 업무 관련된 내용의 메일을 작성해주세요."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
    return response.json()


def get_email_by_id(cursor, email_id):
    """주어진 ID로 이메일을 데이터베이스에서 조회"""
    cursor.execute("SELECT sender, recipient, subject, body FROM emails WHERE id = ?", (email_id,))
    return cursor.fetchone()


def clean_email_content(subject, body):
    """이메일 제목과 본문에서 피싱 관련 태그를 제거"""
    subject = subject.replace("이메일 제목:", "").replace("제목:", "").replace("## 이메일 제목", "").strip()
    body = body.replace("이메일 본문:", "").replace("본문:", "").replace("## 이메일 본문", "").replace("템플릿 종류:", "").strip()
    return subject, body


def save_phishing_email(cursor, original_email, phishing_subject, phishing_body, phishing_link, making_phishing_id, training_id, department_id):
    """피싱 이메일을 데이터베이스에 저장"""
    # 발신자와 수신자를 바꾸기
    sender = original_email[1]  # 원래 수신자
    recipient = original_email[0]  # 원래 발신자

    clean_subject, clean_body = clean_email_content(phishing_subject, phishing_body)
    

    # 피싱 이메일 저장
    cursor.execute("""
        INSERT INTO emails (sender, recipient, subject, body, sent_date, is_phishing, making_phishing, training_id, department_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sender, 
        recipient, 
        clean_subject, 
        clean_body, 
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
        1, 
        making_phishing_id, 
        training_id, 
        department_id
    ))

    # 피싱 이메일이 저장된 후, 생성된 이메일 ID 반환(user_event_logs 테이블에 email_id 필드 때문에 추가함)
    return cursor.lastrowid

def get_employee_info_by_email(cursor, email):
    """이메일을 사용하여 employees 테이블에서 직원 정보를 조회"""
    cursor.execute("SELECT id, name, department_id, email FROM employees WHERE email = ?", (email,))
    return cursor.fetchone()

def main():
    if len(sys.argv) != 4:  # 인자 수 변경
        print("Usage: python email_maker.py <email_id> <training_id> <department_id>")
        sys.exit(1)

    email_id = int(sys.argv[1])
    training_id = int(sys.argv[2])
    department_id = int(sys.argv[3])  # 부서 ID 추가

    # DB 연결
    conn, cursor = connect_to_db()

    try:
        # 이메일 조회
        original_email = get_email_by_id(cursor, email_id)
        if not original_email:
            print("이메일을 찾을 수 없습니다.")
            return

        from_text, to_text, subject_text, body_text = original_email


        # from_text에 담긴 이메일을 기준으로 employee 정보 조회
        employee_info = get_employee_info_by_email(cursor, from_text)

        if not employee_info:
            print(f"{from_text}에 해당하는 직원 정보를 찾을 수 없습니다.")
            return
        
        employee_id, employee_name, employee_department_id, employee_email = employee_info

        cursor.execute("SELECT korean_name FROM departments WHERE id = ?", (department_id,))
        department_name = cursor.fetchone()


        # 피싱 이메일 생성 프롬프트 작성
        phishing_prompt = (
            f"부서 이름: {department_name}\n"
            f"같은 부서 사람끼리 주고받을 만한 링크를 포함한 다양한 내용의 업무 메일을 작성해주세요.\n"
            f"발신자와 수신자는 같은 부서의 직원입니다.\n"
            f"상대방을 부르는 호칭은 생략합니다.\n"
            f"내용에 무조건 링크를 넣으며, 링크는 [example.com]이며 단 한번만 들어있어야 합니다.\n"
            f"원본 메일 내용에 따라 맥락을 파악하여 템플릿 종류를 반환해줍니다. 템플릿 종류는 JSON 형식으로 함께 반환해 주세요.\n"
            f"반환 할 수 있는 템플릿의 종류는 다음과 같습니다. NAVER ,DAUM ,GITHUB ,MSOFFICE ,ZOOM ,GOOGLE ,DROPBOX ,FACEBOOK ,COUPANG.\n"
            f"그 이외에 자체 다운로드 링크면 DOWNLOAD, 모두 해당하지 않을 경우 DEFAULT를 반환합니다.\n"
            f"발신자: {from_text}\n"
            f"수신자: {to_text}\n"
            f"제목: {subject_text}\n"
            f"본문:\n{body_text}\n\n"
            f"이메일 제목과 본문을 구분하여 작성해 주세요.\n"
        )

        # 피싱 이메일 생성 요청
        phishing_response = request_openai(phishing_prompt)
        generated_email = phishing_response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

        # 템플릿 정보 추출
        template_match = re.search(r'"template_type":\s*"(.+?)"', generated_email) 
        template_type = template_match.group(1).strip() if template_match else None

        # 템플릿 정보 제거
        generated_email = re.sub(r'\n\n템플릿 종류 JSON:\n```json\n{\s*"template_type":\s*".+?"\s*}\n```', '', generated_email, flags=re.DOTALL).strip()
        generated_email = re.sub(r'{"template_type":\s*"(.+?)"}', '', generated_email, flags=re.DOTALL).strip()

        # 제목과 본문을 구분하기 위한 로직
        split_index = generated_email.find('\n\n')
        if split_index != -1:
            phishing_subject = generated_email[:split_index].strip()
            phishing_body = generated_email[split_index + 2:].strip()
        else:
            phishing_subject = "제목 없음"
            phishing_body = generated_email.strip()

        # 피싱 이메일 저장 (피싱 링크 포함)
        email_id_generated = save_phishing_email(cursor, original_email, phishing_subject, phishing_body, None, email_id, training_id, department_id)
        conn.commit()

        print("생성된 피싱 이메일 템플릿 정보:", template_type)

        print("피싱 이메일이 데이터베이스에 저장되었습니다.")

        # 피싱 링크를 생성할 user_data 준비
        user_data = {
            "employee_id": employee_id,  # employee 테이블에서 조회된 직원의 ID
            "id": email_id,  # 피싱 링크 생성에 필요한 ID
            "name": employee_name,  # 발신자(훈련 대상자)
            "training_id": training_id,  # 훈련 ID
            "email_id": email_id_generated,
            "department_id": department_id,  # 부서 ID
            "template" : template_type
        }

        # PhishingEvent 클래스를 사용해 피싱 링크 생성
        phishing_event = PhishingEvent()  # 이미 정의된 PhishingEvent 사용
        phishing_link, _ = phishing_event.generate_phishing_link(user_data)
        

        # 피싱 이메일에 피싱 링크 삽입 시, 본문 내 example.com을 phishing_link로 대체
        cursor.execute("""
            UPDATE emails
            SET body = REPLACE(body, 'example.com', ?)
            WHERE id = ?
        """, (phishing_link, email_id_generated))


        conn.commit()
        

        # email_sender.py 실행
        subprocess.run(["python3", "/home/ec2-user/Agent/email/work/email_sender_general.py"], check=True)

    finally:
        close_connection(conn)


if __name__ == "__main__":
    main()
