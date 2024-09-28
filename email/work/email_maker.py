import sys
import requests
import json
import sqlite3
from datetime import datetime
import subprocess

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
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "다음 원본 이메일을 분석해서 답장하는 내용의 이메일을 작성해 주세요."},
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
    body = body.replace("이메일 본문:", "").replace("본문:", "").replace("## 이메일 본문", "").strip()
    return subject, body


def save_phishing_email(cursor, original_email, phishing_subject, phishing_body, phishing_link, making_phishing_id, training_id, department_id):
    """피싱 이메일을 데이터베이스에 저장"""
    # 발신자와 수신자를 바꾸기
    sender = original_email[1]  # 원래 수신자
    recipient = original_email[0]  # 원래 발신자

    # 중복되지 않도록 피싱 링크만 본문에 한 번만 삽입
    if "http" not in phishing_body:
        phishing_body_with_link = phishing_body + f"\n\n링크: {phishing_link}"
    else:
        phishing_body_with_link = phishing_body  # 이미 링크가 있으면 추가하지 않음

    # 피싱 이메일 저장
    cursor.execute("""
        INSERT INTO emails (sender, recipient, subject, body, sent_date, is_phishing, making_phishing, training_id, department_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sender, 
        recipient, 
        phishing_subject, 
        phishing_body_with_link, 
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
        1, 
        making_phishing_id, 
        training_id, 
        department_id
    ))


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

        # 피싱 링크를 생성할 user_data 준비
        user_data = {
            "id": email_id,  # 피싱 링크 생성에 필요한 ID
            "name": from_text,  # 발신자(훈련 대상자)
            "training_id": training_id,  # 훈련 ID
            "email_id": from_text,  # 이메일 ID
            "department_id": department_id  # 부서 ID
        }

        # PhishingEvent 클래스를 사용해 피싱 링크 생성
        phishing_event = PhishingEvent()  # 이미 정의된 PhishingEvent 사용
        phishing_link, _ = phishing_event.generate_phishing_link(user_data)

        # 피싱 이메일 생성 프롬프트 작성
        phishing_prompt = (
            f"다음 원본 이메일 내용을 분석해서 한국어로 그 이메일 내용에 답장을 하기 위한 이메일을 작성해 주세요.\n"
            f"발신자와 수신자는 같은 부서의 직원입니다.\n"
            f"답장 이메일 내용에는 기존 이메일에서 원했던 요청에 대한 답변 내용이 들어가 있어야 합니다.\n"
            f"답변에 따라 링크를 넣을 경우, example.com이라는 url이 들어있어야 합니다.\n"
            f"답장 이메일의 제목은 RE: (기존 이메일의 제목) 형식이어야 합니다.\n"
            f"발신자: {from_text}\n"
            f"수신자: {to_text}\n"
            f"제목: {subject_text}\n"
            f"본문:\n{body_text}\n\n"
            f"이메일 제목과 본문을 구분하여 작성해 주세요."
        )

        # 피싱 이메일 생성 요청
        phishing_response = request_openai(phishing_prompt)
        generated_email = phishing_response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

        # 제목과 본문을 구분하기 위한 로직
        split_index = generated_email.find('\n\n')
        if split_index != -1:
            phishing_subject = generated_email[:split_index].strip()
            phishing_body = generated_email[split_index + 2:].strip()
        else:
            phishing_subject = "제목 없음"
            phishing_body = generated_email.strip()

        # 피싱 이메일 저장 (피싱 링크 포함)
        save_phishing_email(cursor, original_email, phishing_subject, phishing_body, phishing_link, email_id, training_id, department_id)
        conn.commit()

        print("피싱 이메일이 데이터베이스에 저장되었습니다.")

        # email_sender.py 실행
        subprocess.run(["python3", "/home/ec2-user/Agent/email/work/email_sender.py"], check=True)

    finally:
        close_connection(conn)


if __name__ == "__main__":
    main()
