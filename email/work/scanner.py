import sys
import imaplib
import email
from email.header import decode_header
import json
import sqlite3
from datetime import datetime
import time
import subprocess

# DB_connect.py 경로 추가
sys.path.append('/home/ec2-user/Agent/DB')
from DB_connect import connect_to_db, close_connection

def get_resource_users(resource_user_file):
    """리소스 유저 파일에서 사용자 이름을 읽어 반환"""
    with open(resource_user_file, 'r') as f:
        return [line.strip().split('@')[0] for line in f]

def get_training_end_time(cursor, training_id):
    """훈련 종료 시간을 가져오는 함수"""
    cursor.execute("SELECT training_end FROM trainings WHERE id = ?", (training_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def email_exists(cursor, sender, subject, date):
    """이메일이 데이터베이스에 존재하는지 확인하는 함수"""
    cursor.execute(""" 
        SELECT COUNT(*) FROM emails 
        WHERE sender = ? AND subject = ? AND sent_date = ?
    """, (sender, subject, date))
    return cursor.fetchone()[0] > 0

def scan_emails(imap_server, username, password, mailbox='INBOX', filter_emails=None):
    """IMAP 서버에서 이메일을 스캔하고 JSON으로 변환"""
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(username, password)
        mail.select(mailbox)

        status, messages = mail.search(None, 'ALL')
        if status != 'OK':
            return []

        mail_ids = messages[0].split()
        new_emails = []

        for mail_id in mail_ids:
            status, msg_data = mail.fetch(mail_id, '(RFC822)')
            if status != 'OK':
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            from_ = msg.get('From')
            to_ = msg.get('To')  # 수신자 이메일 가져오기
            date_ = msg.get('Date')
            subject = decode_header(msg['Subject'])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()

            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body += part.get_payload(decode=True).decode(errors='ignore')
            else:
                body = msg.get_payload(decode=True).decode(errors='ignore')

            # 조건에 맞는 이메일만 추가
            if filter_emails and any(email in from_ for email in filter_emails):
                email_data = {
                    'from': from_,
                    'date': date_,
                    'subject': subject,
                    'body': body,
                    'to': to_  # 수신자 이메일 추가
                }
                new_emails.append(email_data)

        return new_emails

    except imaplib.IMAP4.error as e:
        print(f"IMAP error: {e}")
        return []
    finally:
        mail.logout()

def save_new_emails_to_db(cursor, emails, training_id, department_id):
    """새로운 이메일을 DB에 저장"""
    inserted_ids = []
    for email_data in emails:
        if not email_exists(cursor, email_data['from'], email_data['subject'], email_data['date']):
            cursor.execute(""" 
                INSERT INTO emails (training_id, sender, recipient, subject, body, sent_date, is_phishing, making_phishing, department_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) 
            """, (
                training_id,
                email_data['from'],
                email_data['to'],  # 수신자 이메일 자동으로 가져오도록 수정
                email_data['subject'],
                email_data['body'],
                email_data['date'],
                0,  # is_phishing 필드를 0으로 설정
                0,  # making_phishing 필드에 기본값 0 설정
                department_id  # department_id 추가
            ))
            inserted_ids.append(cursor.lastrowid)  # 생성된 ID를 리스트에 추가
    return inserted_ids

def check_reply_conditions(email_body):
    """회신을 요구하는 조건을 검사하는 함수"""
    reply_conditions = [
        "답변", 
        "답변을 바랍니다", 
        "회신 부탁드립니다", 
        "답변해 주세요", 
        "피드백 부탁드립니다", 
        "검토 후 회신 바랍니다", 
        "의견 주시면 감사하겠습니다", 
        "확인 부탁드립니다", 
        "부탁드립니다", 
        "이메일 회신 부탁드립니다",
        "검토",
        "회신",
        "알려주시면",
        "제출해 주시기 바랍니다",
        "검토해 주세요",
        "공유해 주세요"
    ]
    return any(condition in email_body for condition in reply_conditions)

def main():
    if len(sys.argv) != 5:  # 인자 수 수정
        print("Usage: python scanner.py <email_file> <resource_user_file> <training_id> <department_id>")
        sys.exit(1)

    email_file = sys.argv[1]
    resource_user_file = sys.argv[2]
    training_id = int(sys.argv[3])
    department_id = int(sys.argv[4])  # department_id 추가

    # DB 연결
    conn, cursor = connect_to_db()

    try:
        # 훈련 종료 시간 가져오기
        training_end_time = get_training_end_time(cursor, training_id)
        
        # 밀리초 포함된 datetime 문자열로 변환
        training_end_time = datetime.strptime(training_end_time, "%Y-%m-%d %H:%M:%S.%f")

        while True:
            current_time = datetime.now()
            if current_time >= training_end_time:
                print("Training has ended. Exiting scan.")
                break

            # 이메일 주소 목록 읽기
            with open(email_file, 'r') as f:
                email_addresses = [line.strip() for line in f]

            # 리소스 유저 이메일 주소 읽기
            resource_users = get_resource_users(resource_user_file)
            all_new_emails = []

            for resource_user in resource_users:
                username = resource_user
                password = 'igloo1234'  # 실제 비밀번호로 교체하세요

                # 이메일 주소 목록 필터링
                new_emails = scan_emails(imap_server='10.0.10.162', username=username, password=password, filter_emails=email_addresses)
                all_new_emails.extend(new_emails)

            # 새로운 이메일을 DB에 저장하고 생성된 ID 가져오기
            inserted_ids = save_new_emails_to_db(cursor, all_new_emails, training_id, department_id)  # department_id 추가
            conn.commit()

            # 새로운 이메일이 추가되었을 때 조건 검사 및 email_maker.py 실행
            for email_data, email_id in zip(all_new_emails, inserted_ids):
                if check_reply_conditions(email_data['body']):
                    subprocess.run(["python3", "/home/ec2-user/Agent/email/work/email_maker.py", str(email_id), str(training_id), str(department_id)])  # department_id 추가

            time.sleep(600)  # 10분 대기

    finally:
        close_connection(conn)

if __name__ == "__main__":
    main()
