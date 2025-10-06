from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import os
from config import messages, language_map
import requests
import secrets
from datetime import datetime, timezone, timedelta

WEBHOOK_SECRET = secrets.token_urlsafe(32)
# Flask app instance
app = Flask(__name__, static_folder="static", template_folder="templates")

API_KEY = "0a4d8aad-ddad-4a47-9484-9c64843f59ff"
PHONE_NUMBER_ID = "80db5c92-ebf7-4bfd-afc9-615c50ada458"
EXCEL_FILE = "vapi.xlsx"
OUTPUT_EXCEL = "call_status_log.xlsx"
url = "https://api.vapi.ai/call"
VAPI_WEBHOOK_URL = "https://manappuram-voice-agent.onrender.com/vapi-webhook"

def convert_to_ist(utc_time_str):
    """Convert ISO 8601 UTC timestamp (from VAPI) to IST (UTC+5:30)."""
    if not utc_time_str:
        return None
    try:
        # Parse and ensure timezone awareness
        dt_utc = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        # Convert to IST
        ist = timezone(timedelta(hours=5, minutes=30))
        dt_ist = dt_utc.astimezone(ist)
        return dt_ist.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"⚠️ Timestamp parse error ({utc_time_str}): {e}")
        return utc_time_str  # fallback to raw value


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
                'cost', 'error_message'
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
                'error_message': error_message
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    
        # Save to Excel
        df.to_excel(OUTPUT_EXCEL, index=False)
        print(f"📊 Updated Excel: {name} - Status: {status}")

    except Exception as e:
        print(f"❌ Error logging call status: {str(e)}")
        # Re-initialize the Excel file if there's an error
        # initialize_output_excel()
        # # Try again
        # log_call_status(name, phone_number, language, call_id, status, duration_seconds, 
        #                call_start_time, call_end_time, cost, error_message)
        
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
                "serverUrlSecret": WEBHOOK_SECRET,
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
    
    # ✅ Remove old call log
    if os.path.exists(OUTPUT_EXCEL):
        os.remove(OUTPUT_EXCEL)
    
    df = pd.read_excel(file, dtype=str)
    #df["Phone"] = df["Phone"].astype(str).str.strip().str.replace("+", "", regex=False)
    df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

    results = trigger_calls(EXCEL_FILE)
    print('Result of trigger calls api ', results)
    return render_template("index.html", result="\n".join(results))

@app.route("/vapi-webhook", methods=["POST"])
def vapi_webhook():
    received_secret = request.headers.get('x-vapi-secret')
    if received_secret != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
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
        print('Inside event type status update')
        status = message.get('status')
        call_start_time = convert_to_ist(message.get('startedAt'))
        
        log_call_status(
            name=name,
            phone_number=phone_number,
            language = language,
            call_id=call_id,
            status=status,
            call_start_time=call_start_time
        )

        
    elif event_type == 'end-of-call-report':
        print('Inside event type end of call report')
        ended_reason = message.get('endedReason', 'completed')
        duration = message.get('durationSeconds', 0)  # in seconds
        cost = message.get('cost', 0)
        started_at = convert_to_ist(message.get('startedAt'))
        print('call start time ', started_at)
        ended_at = convert_to_ist(message.get('endedAt'))
    
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
        print('Inside enent type function call')
        function_name = message.get('functionCall', {}).get('name')
        if function_name == 'endCall':
            log_call_status(
                name=name,
                phone_number=phone_number,
                language = language,
                call_id=call_id,
                status='ending'
            )
    return jsonify({"ok": True}), 200

# Route to download call status Excel file
@app.route('/download-report', methods=['GET'])
def download_report():
    """Download the call status log Excel file"""
    try:
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
