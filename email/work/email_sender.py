import sys
import sqlite3
import subprocess
import imaplib
sys.path.append('/home/ec2-user/Agent/DB')
from DB_connect import connect_to_db, close_connection

def send_email_via_mailx(imap_server, username, password, sender, recipient, subject, body):
    """mailx를 통해 이메일 전송"""
    try:
        # IMAP 서버에 로그인
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(username, password)

        # mailx를 사용하여 이메일 전송
        command = f'echo "{body}" | mailx -s "{subject}" -r "{sender}" {recipient}'
        subprocess.run(command, shell=True, check=True)
        print("이메일이 성공적으로 전송되었습니다.")

    except subprocess.CalledProcessError as e:
        print(f"이메일 전송 중 오류 발생: {e}")
    except imaplib.IMAP4.error as e:
        print(f"IMAP 로그인 중 오류 발생: {e}")
    finally:
        # 연결 종료
        if 'mail' in locals():
            mail.logout()

def get_phishing_email(cursor):
    """데이터베이스에서 피싱 이메일 조회"""
    cursor.execute("SELECT sender, recipient, subject, body, making_phishing FROM emails WHERE is_phishing = 1 ORDER BY id DESC LIMIT 1")
    return cursor.fetchone()

def get_original_email(cursor, email_id):
    """making_phishing 필드에 해당하는 원본 이메일 조회"""
    cursor.execute("SELECT sender, recipient, subject, body, sent_date FROM emails WHERE id = ?", (email_id,))
    return cursor.fetchone()

def main():
    # DB 연결
    conn, cursor = connect_to_db()

    try:
        # 피싱 이메일 조회
        phishing_email = get_phishing_email(cursor)
        if not phishing_email:
            print("전송할 피싱 이메일이 없습니다.")
            return

        sender, recipient, subject, body, making_phishing = phishing_email
        
        # making_phishing 필드를 사용하여 원본 이메일 조회
        original_email = get_original_email(cursor, making_phishing)
        if original_email:
            orig_sender, orig_recipient, orig_subject, orig_body, orig_sent_date = original_email
            # 원본 이메일 정보 추가
            body += f"\n\n--------- Original Message ---------\n" \
                    f"From: {orig_sender}\n" \
                    f"To: {orig_recipient}\n" \
                    f"Date: {orig_sent_date}\n" \
                    f"Subject: {orig_subject}\n\n" \
                    f"{orig_body.replace('^M', '').strip()}"

        # IMAP 서버 정보
        imap_server = '10.0.10.162'
        password = 'igloo1234'  # 실제 비밀번호로 교체

        # sender에서 도메인 제거하여 사용자명 생성
        username = sender.split('@')[0]

        # 이메일 전송
        send_email_via_mailx(imap_server, username, password, sender, recipient, subject, body)

    finally:
        close_connection(conn)

if __name__ == "__main__":
    main()
