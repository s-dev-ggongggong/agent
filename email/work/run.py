from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, re

app = Flask(__name__)
CORS(app)  # 모든 도메인에서의 CORS 허용

# OpenAI API 호출 함수
def request_openai(from_text, to_text, subject_text, body_text):
    """OpenAI API 요청"""
    api_key = ""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }



    phishing_prompt = (
        f"다음 원본 이메일 내용을 분석해서 답장하는 내용의 이메일을 작성해 주세요.\n"
        f"발신자와 수신자는 같은 부서의 직원입니다.\n"
        f"상대방을 부르는 호칭은 생략합니다.\n"
        f"답장 이메일 내용에는 기존 이메일에서 원했던 요청에 대한 답변 내용이 들어가 있어야 합니다.\n"
        f"답변에 따라 링크를 무조건 넣으며, 링크는 [example.com]이며 단 한번만 들어있어야 합니다.\n"
        f"원본 메일 내용에 따라 맥락을 파악하여 템플릿 종류를 반환해줍니다. 템플릿 종류는 별도의 JSON 형식으로 함께 반환해 주세요. JSON의 키는 'template_type' 입니다.\n"
        f"반환 할 수 있는 템플릿의 종류는 다음과 같습니다. NAVER ,DAUM ,GITHUB ,MSOFFICE ,ZOOM ,GOOGLE ,DROPBOX ,FACEBOOK ,COUPANG., SLACK\n"
        f"그 이외에 자체 다운로드 링크면 DOWNLOAD, 모두 해당하지 않을 경우 DEFAULT를 반환합니다.\n"
        f"답장 이메일의 제목은 RE: (기존 이메일의 제목) 형식이어야 합니다.\n"
        f"발신자: {from_text}\n"
        f"수신자: {to_text}\n"
        f"제목: {subject_text}\n"
        f"본문:\n{body_text}\n\n"
        f"템플릿을 이메일 본문과 구문하여 쉽게 분리할 수 있게 작성해주세요.\n"
        f"이메일 제목과 본문을 구분하여 작성해 주세요.\n"
        f"제목은 반드시 제목: 으로 시작하고, 본문은 반드시 본문: 으로 시작해야 합니다."
    )
    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "다음 원본 이메일을 분석해서 답장하는 내용의 이메일을 작성해 주세요."},
            {"role": "user", "content": phishing_prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
    return response.json()

@app.route('/api/generate', methods=['POST'])
def generate_response():
    try:
        # 요청 데이터에서 이메일 구성 요소 가져오기
        data = request.json
        from_text = data.get('from', '')
        to_text = data.get('to', '')
        subject_text = data.get('subject', '')
        body_text = data.get('body', '')

        if not all([from_text, to_text, subject_text, body_text]):
            return jsonify({"error": "Missing email components"}), 400

        # OpenAI API 호출
        response = request_openai(from_text, to_text, subject_text, body_text)
        answer = response['choices'][0]['message']['content']
        
        # 템플릿 타입 추출
        template_type = "DEFAULT"
        match = re.search(r'["\']template_type["\']\s*:\s*[\'"]([^\'"]+)[\'"]', answer, re.DOTALL)
        if match:
            template_type = match.group(1)  # 첫 번째 캡처 그룹
        
        # 링크 추가
        new_domain = 'www.example.com'
        template_sites= {
            "LINKEDIN":"http://cifrar.cju.ac.kr:25577/%EB%A7%81%ED%81%AC%EB%93%9C%EC%9D%B8%EC%97%90%20%EB%A1%9C%EA%B7%B8%EC%9D%B8.html",
            "GOOGLE":"http://cifrar.cju.ac.kr:25577/%EB%A1%9C%EA%B7%B8%EC%9D%B8%20-%20%EA%B5%AC%EA%B8%80%20%EA%B3%84%EC%A0%95.html",
            "DROPBOX":"http://cifrar.cju.ac.kr:25577/%EB%A1%9C%EA%B7%B8%EC%9D%B8%20-%20%EB%93%9C%EB%A1%AD%EB%B0%95%EC%8A%A4.html",
            "MSOFFICE":"http://cifrar.cju.ac.kr:25577/%EB%A7%88%EC%9D%B4%ED%81%AC%EB%A1%9C%EC%86%8C%ED%94%84%ED%8A%B8%EC%97%90%20%EB%A1%9C%EA%B7%B8%EC%9D%B8.html",
            "GITHUB":"http://cifrar.cju.ac.kr:25577/GitHub%20-%20Login.html",
            "ZOOM":"http://cifrar.cju.ac.kr:25577/%EC%A4%8C%20-%20%EB%A1%9C%EA%B7%B8%EC%9D%B8.html",   
            "FACEBOOK":"http://cifrar.cju.ac.kr:25577/Log%20into%20Facebook%20_%20Facebook.html",
            "DOWNLOAD":"https://www.kisia.or.kr/",
            "DEFALUT":"https://www.kisia.or.kr/"
        }
        answer = answer.replace(
     "[example.com]",
    f'<a target="_blank" href="{template_sites[template_type]}" style="text-decoration: underline;">여기</a>'
        )
        
        # 템플릿 JSON 제거
        answer = re.sub(r'\{.*?"template_type".*?\}', '', answer, flags=re.DOTALL).strip()
        
        # 원본 메시지 추가
        original_message = (
            "\n\n---Original Message---\n"
            f"From: {from_text}\n"
            f"To: {to_text}\n"
            f"Subject: {subject_text}\n\n"
            f"{body_text}"
        )
        answer += original_message
        print(answer)
        return jsonify({"result": answer})

    except requests.exceptions.RequestException as e:
        # HTTP 요청 오류 처리
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        # 기타 예외 처리
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7777, debug=True)
