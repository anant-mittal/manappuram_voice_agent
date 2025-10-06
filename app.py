from flask import Flask, render_template, request, jsonify
import pandas as pd
from datetime import datetime
import os
from config import messages, language_map
import requests
from flask import render_template_string

# ==============================
# HTML + Flask UI
# ==============================

# HTML_PAGE = """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <title>📞 EMI Reminder Voice Agent</title>
#     <style>
#         body {
#             font-family: Arial, sans-serif;
#             background-color: #f5f6fa;
#             color: #333;
#             margin: 0;
#             padding: 0;
#         }
#         .container {
#             width: 90%;
#             max-width: 700px;
#             margin: 40px auto;
#             background: white;
#             padding: 25px 40px;
#             border-radius: 12px;
#             box-shadow: 0 4px 20px rgba(0,0,0,0.1);
#         }
#         h1 {
#             text-align: center;
#             color: #0077b6;
#         }
#         form {
#             margin-top: 30px;
#             text-align: center;
#         }
#         input[type="file"] {
#             margin: 20px 0;
#             padding: 8px;
#         }
#         button {
#             background-color: #0077b6;
#             color: white;
#             border: none;
#             border-radius: 8px;
#             padding: 10px 20px;
#             cursor: pointer;
#             font-size: 16px;
#             margin: 10px;
#         }
#         button:hover {
#             background-color: #0096c7;
#         }
#         .output {
#             margin-top: 30px;
#             background: #eef7fb;
#             border-radius: 8px;
#             padding: 15px;
#             font-family: monospace;
#             white-space: pre-wrap;
#         }
#         .log-box {
#             background: #eef7fb;
#             border-radius: 8px;
#             padding: 15px;
#             font-family: monospace;
#             white-space: pre-wrap;
#         }
#         a.download {
#             display: inline-block;
#             margin-top: 15px;
#             background: #00b4d8;
#             color: white;
#             padding: 10px 20px;
#             text-decoration: none;
#             border-radius: 8px;
#         }
#         a.download:hover {
#             background: #0077b6;
#         }

#     </style>
# </head>
# <body>
#     <div class="container">
#         <h1>📞 EMI Reminder Voice Agent</h1>
#         <p>Upload an Excel file with columns: <b>Phone</b> and <b>Language</b>.</p>
#         <form action="/trigger-calls" method="post" enctype="multipart/form-data">
#             <input type="file" name="file" accept=".xlsx" required><br>
#             <button type="submit">Trigger Calls</button>
#         </form>

#         {% if result %}
#             <div class="output">
#                 <h3>Logs:</h3>
#                 <div class="log-box">{{ result | replace('\n', '<br>') | safe }}</div>
#                 <a href="/download-report" class="download">📥 Download Call Status Excel</a>
#             </div>
#         {% endif %}
#     </div>
# </body>
# </html>
# """

# Flask app instance
#app = Flask(__name__)
app = Flask(__name__, static_folder="static", template_folder="templates")
API_KEY = "0a4d8aad-ddad-4a47-9484-9c64843f59ff"
PHONE_NUMBER_ID = "80db5c92-ebf7-4bfd-afc9-615c50ada458"
EXCEL_FILE = "vapi.xlsx"
OUTPUT_EXCEL = "call_status_log.xlsx"
url = "https://api.vapi.ai/call"
VAPI_WEBHOOK_URL = "https://manappuram-voice-agent.onrender.com/vapi-webhook"

# Initialize output Excel if it doesn't exist
def initialize_output_excel():
    if not os.path.exists(OUTPUT_EXCEL):
        df = pd.DataFrame(columns=[
            'name', 'phone_number', 'language', 'call_id', 'status', 
            'duration_seconds', 'call_start_time', 'call_end_time',
            'cost', 'error_message', 'timestamp'
        ])
        df.to_excel(OUTPUT_EXCEL, index=False, engine='openpyxl')
        print(f"✓ Created new Excel file: {OUTPUT_EXCEL}")

def log_call_status(name, phone_number, language, call_id, status, duration_seconds=0, 
                    call_start_time=None, call_end_time=None, cost=None, error_message=None):
    """Append or update call status in Excel"""
    
    # Read existing data
    #df = pd.read_excel(OUTPUT_EXCEL)
    try:
        # Read existing data or create new DataFrame
        if os.path.exists(OUTPUT_EXCEL) and os.path.getsize(OUTPUT_EXCEL) > 0:
            print('Inside if block of log_call_status')
            df = pd.read_excel(OUTPUT_EXCEL, engine='openpyxl')
        else:
            print('Inside else block of log_call_status')
            # File doesn't exist or is empty, create new DataFrame
            df = pd.DataFrame(columns=[
                'name', 'phone_number', 'language', 'call_id', 'status', 
                'duration_seconds', 'call_start_time', 'call_end_time',
                'cost', 'error_message', 'timestamp'
            ])
    
        # Check if this call_id already exists (for updates)
        if call_id != 'N/A' and call_id in df['call_id'].values:
            # Update existing record
            idx = df[df['call_id'] == call_id].index[0]
            df.at[idx, 'status'] = status
            if duration_seconds:
                df.at[idx, 'duration_seconds'] = duration_seconds
            if call_start_time:
                df.at[idx, 'call_start_time'] = call_start_time
            if call_end_time:
                df.at[idx, 'call_end_time'] = call_end_time
            if cost:
                df.at[idx, 'cost'] = cost
            df.at[idx, 'timestamp'] = datetime.now().isoformat()
        else:
            # Create new record
            new_row = {
                'name': name,
                'phone_number': phone_number,
                'language': language,
                'call_id': call_id,
                'status': status,
                'duration_seconds': duration_seconds,
                'call_start_time': call_start_time,
                'call_end_time': call_end_time,
                'cost': cost,
                'error_message': error_message,
                'timestamp': datetime.now().isoformat()
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    
        # Save to Excel
        df.to_excel(OUTPUT_EXCEL, index=False)
        print(f"📊 Updated Excel: {name} - Status: {status}")

    except Exception as e:
        print(f"❌ Error logging call status: {str(e)}")
        # Re-initialize the Excel file if there's an error
        initialize_output_excel()
        # Try again
        log_call_status(name, phone_number, language, call_id, status, duration_seconds, 
                       call_start_time, call_end_time, cost, error_message)
        
def trigger_calls(file):
    df = pd.read_excel(file)
    results = []

    for idx, row in df.iterrows():
        customer_number = '+' + str(row["Phone"])
        language = row["Language"]  # "ka", "ta", "te", "ma", or "en"

        # Pick Tamil/Telugu/Malayalam/Kannada/English message
        message = messages.get(language, messages["en"])

        payload = {
            "phoneNumberId": PHONE_NUMBER_ID,
            "customer": {"number": customer_number},
            "assistant": {
                "name": "EMIReminderBot",
                "voice": {
                    "provider": "azure",
                    "voiceId": "zh-CN-XiaoxiaoMultilingualNeural"  # Xiaoxiao works for multiple langs
                },
                "model": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an automated reminder bot. Your only task is to deliver the firstMessage and immediately end the call. Do NOT wait for user response. Do NOT engage in conversation. As soon as you finish speaking the firstMessage, immediately call the endCall function."
                        
                        }
                    ],
                    "tools": [{"type": "endCall"}],

                },
                
                "serverUrl": "https://manappuram-voice-agent.onrender.com/vapi-webhook",
                "firstMessage": message,
                "silenceTimeoutSeconds": 30,
                "endCallMessage": " ",
                "endCallPhrases": []
            }
        }

        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, verify=False)

        status_code = response.status_code
        resp_json = response.json()

        # Save call status in Excel
        df.loc[idx, "CallStatus"] = f"{status_code} | {resp_json.get('status', resp_json.get('message', 'Unknown'))}"
        language_name = language_map.get(language, "en")
        result = f"Called {customer_number} in {language_name}: {response.status_code}"
        results.append(result)

    return results


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/trigger-calls", methods=["POST"])
def trigger_calls_ui():
    file = request.files.get("file")
    if not file:
        return render_template("index.html", result="❌ No file uploaded")
    results = trigger_calls(file)
    return render_template("index.html", result=results)

@app.route("/vapi-webhook", methods=["POST"])
def vapi_webhook():
    data = request.json
    message = data.get('message', {})
    print("Webhook received:", data)  # log to Render logs
    # Get call details
    call = message.get('call', {})
    call_id = call.get('id', 'N/A')
    customer = call.get('customer', {})
    phone_number = customer.get('number', 'Unknown')
    event_type = data.get('message', {}).get('type')

    
    df_customers = pd.read_excel(EXCEL_FILE, engine='openpyxl')
    df_customers['Phone'] = df_customers['Phone'].astype(str).str.strip()
    phn = phone_number[1:]
    customer_row = df_customers[df_customers['Phone'] == phn]

    name = customer_row['Name'].values[0] if not customer_row.empty else 'Unknown'
    language = customer_row['Language'].values[0] if not customer_row.empty else 'en'

    
    # Handle different event types
    if event_type == 'status-update':
        status = message.get('status')
        call_start_time = message.get('startedAt')
        
        log_call_status(
            name=name,
            phone_number=phone_number,
            language = language,
            call_id=call_id,
            status=status,
            call_start_time=call_start_time
        )

        
    elif event_type == 'end-of-call-report':
        ended_reason = message.get('endedReason', 'completed')
        duration = message.get('durationSeconds', 0)  # in seconds
        cost = message.get('cost', 0)
        started_at = message.get('startedAt')
        print('json start time ', message.get('startedAt'))
        print('call start time ', started_at)
        ended_at = message.get('endedAt')
    
        log_call_status(
            name=name,
            phone_number=phone_number,
            language = language,
            call_id=call_id,
            status=ended_reason,
            duration_seconds=duration,
            call_start_time=started_at,
            call_end_time=ended_at,
            cost=cost
        )
    elif event_type == 'function-call':
        # Log when endCall is triggered
        function_name = message.get('functionCall', {}).get('name')
        if function_name == 'endCall':
            log_call_status(
                name=name,
                phone_number=phone_number,
                language = language,
                call_id=call_id,
                status='ending'
            )
    # You can later add Excel update code here
    return jsonify({"ok": True}), 200

# Route to download call status Excel file
@app.route('/download-report', methods=['GET'])
def download_report():
    """Download the call status log Excel file"""
    try:
        from flask import send_file
        
        if not os.path.exists(OUTPUT_EXCEL):
            return jsonify({"error": "No call status log found"}), 404
        
        return send_file(
            OUTPUT_EXCEL,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'call_status_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# Only needed for local testing
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
