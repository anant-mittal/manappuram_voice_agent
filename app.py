from typing import Dict
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import os
from config import messages, language_map
import requests
import secrets
from datetime import datetime, timezone, timedelta
from threading import Thread
import time
from apscheduler.schedulers.background import BackgroundScheduler
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content, Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64
import os
from dotenv import load_dotenv

# Load .env only if it exists (i.e., in local development)
if os.path.exists(".env"):
    load_dotenv()
    print("Loaded environment variables from .env")
else:
    print("Running in Render environment — using system environment variables")


WEBHOOK_SECRET = secrets.token_urlsafe(32)
# Flask app instance
app = Flask(__name__, static_folder="static", template_folder="templates")

EXCEL_FILE = "vapi.xlsx"
OUTPUT_EXCEL = "call_status_log.xlsx"
url = "https://api.vapi.ai/call"
VAPI_WEBHOOK_URL = "https://manappuram-voice-agent.onrender.com/vapi-webhook"

# Track ongoing calls for polling
ongoing_calls = {}  # {call_id: {'name': ..., 'phone_number': ...}}



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

# Function to fetch call status from Vapi API
def fetch_call_status(call_id):
    """Fetch call details from Vapi API"""
    try:
        response = requests.get(
            f"https://api.vapi.ai/call/{call_id}",
            headers={
                "Authorization": f"Bearer {os.getenv("VAPI_API_KEY")}"
            }
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error fetching call {call_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Exception fetching call {call_id}: {str(e)}")
        return None

# Function to poll call status until it ends
def poll_call_status(call_id, name, phone_number, language, max_attempts=60, interval=5):
    """
    Poll Vapi API to check call status
    max_attempts: Maximum number of polling attempts (60 * 5s = 5 minutes)
    interval: Seconds between each poll
    """
    print(f"🔄 Starting to poll call {call_id} for {name}")

    # Check at the start of each poll cycle
    if call_id not in ongoing_calls:
        print(f"✋ Webhook already handled call {call_id}, stopping poll")
        return  # Exit the polling function
    
    for attempt in range(max_attempts):
        time.sleep(interval)
        
        call_data = fetch_call_status(call_id)
        
        if not call_data:
            continue
        
        status = call_data.get('status')
        ended_reason = call_data.get('endedReason')
        
        print(f"📊 Poll {attempt + 1}/{max_attempts} - Call {call_id}: status={status}, endedReason={ended_reason}")
        
        # Update status in Excel
        if status == 'ended':
            # Call has ended, get final details
            duration = call_data.get('duration', 0)
            cost = call_data.get('cost', 0)
            started_at = convert_to_ist(call_data.get('startedAt'))
            ended_at = convert_to_ist(call_data.get('endedAt'))
            
            # Determine final status
            if ended_reason:
                final_status = ended_reason
            elif duration == 0:
                final_status = 'not-answered'
            else:
                final_status = 'completed'
            
            log_call_status(
                name=name,
                phone_number=phone_number,
                language=language,
                call_id=call_id,
                status=final_status,
                duration_seconds=duration,
                call_start_time=started_at,
                call_end_time=ended_at,
                cost=cost,
                error_message=ended_reason if final_status in ['customer-did-not-answer', 'voicemail', 'customer-busy'] else None
            )
            
            # Remove from ongoing calls
            if call_id in ongoing_calls:
                del ongoing_calls[call_id]
            
            print(f"✅ Call {call_id} ended: {final_status}")
            break
        
        elif status in ['queued', 'ringing', 'in-progress']:
            # Call is still ongoing, continue polling
            log_call_status(
                name=name,
                phone_number=phone_number,
                language=language,
                call_id=call_id,
                status=status,
                call_start_time=convert_to_ist(call_data.get('startedAt'))
            )
    
    else:
        # Max attempts reached, mark as timeout
        print(f"⏰ Polling timeout for call {call_id}")
        log_call_status(
            name=name,
            phone_number=phone_number,
            language=language,
            call_id=call_id,
            status='polling-timeout',
            error_message='Could not determine final call status'
        )


def email_report_sendgrid(file_path):
    """Send the Excel report via SendGrid email."""
    try:
        sg_api_key = os.getenv("SENDGRID_API_KEY")
        to_email = "anantmittal1996@gmail.com"
        from_email = "anantmittal1996@gmail.com"

        if not all([sg_api_key, to_email, from_email]):
            print("⚠️ Missing SendGrid environment variables. Email not sent.")
            return

        if not os.path.exists(file_path):
            print(f"⚠️ Report file not found: {file_path}")
            return

        with open(file_path, "rb") as f:
            file_data = f.read()
            encoded_file = base64.b64encode(file_data).decode()

        # Create email
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject="📊 Daily VAPI Call Report",
            html_content="<p>Attached is the latest VAPI call status report.</p>"
        )

        attachment = Attachment()
        attachment.file_content = FileContent(encoded_file)
        attachment.file_type = FileType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        attachment.file_name = FileName(os.path.basename(file_path))
        attachment.disposition = Disposition("attachment")
        message.attachment = attachment

        sg = sendgrid.SendGridAPIClient(api_key=sg_api_key)
        response = sg.send(message)

        if response.status_code in [200, 202]:
            print(f"📧 Report emailed successfully to {to_email}")
        else:
            print(f"❌ SendGrid failed: {response.status_code} - {response.body}")

    except Exception as e:
        print(f"❌ Error sending email via SendGrid: {str(e)}")




# ======================================================
# AUTO-DOWNLOAD REPORT
# ======================================================
def auto_download_report():
    if not os.path.exists(OUTPUT_EXCEL):
        print("⚠️ No call status log found yet.")
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"call_status_log_{timestamp}.xlsx"
    print('New name = ', new_name)
    os.system(f"cp {OUTPUT_EXCEL} {new_name}")
    email_report_sendgrid(new_name)
    print(f"📂 Auto-saved report as {new_name}")


def trigger_calls(file):
    df = pd.read_excel(file)
    results = []

    for idx, row in df.iterrows():
        customer_number = '+' + str(row["Phone"])
        name = row['Name']
        language = row["Language"]  # "ka", "ta", "te", "ma", or "en"

        # Pick Tamil/Telugu/Malayalam/Kannada/English message
        message = messages.get(language, messages["en"])

        payload = {
            "phoneNumberId": os.getenv("PHONE_NUMBER_ID"),
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
                            "content": "You are an automated reminder bot. Your only task is to deliver the firstMessage and immediately end the call. Do NOT wait for user response. Do NOT engage in any conversation. Do NOT respond to any message from the user. As soon as you finish speaking the firstMessage, immediately call the endCall function."
                        
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

        headers = {"Authorization": f"Bearer {os.getenv("VAPI_API_KEY")}", "Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, verify=False)

        status_code = response.status_code
        resp_json = response.json()

        ## ----------------Polling logic----------------##
        if status_code == 201:
            call_data = response.json()
            call_id = call_data.get('id', 'N/A')
            
            # Log initial call attempt
            log_call_status(
                name=name,
                phone_number=customer_number,
                language=language,
                call_id=call_id,
                status='initiated',
                duration_seconds=0,
                call_start_time=convert_to_ist(datetime.now().isoformat())
            )
            
            # Add to ongoing calls for polling
            ongoing_calls[call_id] = {
                'name': name,
                'phone_number': customer_number
            }
            
            # Start polling in background thread
            poll_thread = Thread(target=poll_call_status, args=(call_id, name, customer_number, language))
            poll_thread.daemon = True
            poll_thread.start()
            
            # results.append({
            #     'name': name,
            #     'phone_number': customer_number,
            #     'call_id': call_id,
            #     'status': 'success'
            # })
            print(f"✓ Call initiated for {name} ({customer_number}) - Call ID: {call_id}")
        else:
            error_msg = response.text
            log_call_status(
                name=name,
                phone_number=customer_number,
                language=language,
                call_id='N/A',
                status='failed',
                error_message=error_msg
            )
            # results.append({
            #     'name': name,
            #     'phone_number': customer_number,
            #     'status': 'failed',
            #     'error': error_msg
            # })
            print(f"✗ Failed to initiate call for {name}: {error_msg}")

        ##----------End of polling logic-----------

        # Save call status in Excel
        #df.loc[idx, "CallStatus"] = f"{status_code} | {resp_json.get('status', resp_json.get('message', 'Unknown'))}"
        language_name = language_map.get(language, "en")
        result = f"Called {customer_number} in {language_name}: {response.status_code}"
        results.append(result)
    print("⏳ Waiting for webhooks (0.5 min)...")
    time.sleep(60)
    auto_download_report()
    return results

# ======================================================
# SCHEDULER SETUP
# ======================================================
# scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

# def scheduled_trigger():
#     print(f"Scheduled trigger running at {datetime.now()}")
#     try:
#         trigger_calls(EXCEL_FILE)
#     except Exception as e:
#         print(f"Scheduled trigger failed: {e}")

# # Default: 10:00 AM IST daily
# scheduler.add_job(scheduled_trigger, 'cron', hour=18, minute=40, id='daily_call_job')
# scheduler.start()


# # ======================================================
# # DYNAMIC SCHEDULING API
# # ======================================================
# @app.route("/schedule-call", methods=["POST"])
# def schedule_call():
#     """Set a new daily schedule for outbound calls."""
#     try:
#         data = request.json or {}
#         hour = int(data.get("hour", 10))
#         minute = int(data.get("minute", 0))

#         # Remove existing job if present
#         if scheduler.get_job("daily_call_job"):
#             scheduler.remove_job("daily_call_job")

#         # Add new job
#         scheduler.add_job(scheduled_trigger, 'cron', hour=hour, minute=minute, id="daily_call_job")
#         next_run = scheduler.get_job("daily_call_job").next_run_time

#         return jsonify({
#             "message": f"✅ Daily call schedule updated to {hour:02d}:{minute:02d} IST",
#             "next_run": str(next_run)
#         }), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

@app.route("/schedule-call", methods=["GET"])
def schedule_call():
    hour = int(request.args.get("hour", 10))
    minute = int(request.args.get("minute", 0))

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(trigger_calls, 'cron', args=[EXCEL_FILE], hour=hour, minute=minute, id='daily_call_job')
    scheduler.start()
    next_run = scheduler.get_job("daily_call_job").next_run_time

    return jsonify({
        "message": f"Daily call schedule set to {hour:02d}:{minute:02d} IST",
        "next_run": str(next_run)
    })
    


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/trigger-calls", methods=["POST"])
def trigger_calls_ui():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    
    # ✅ Remove old call log
    if os.path.exists(OUTPUT_EXCEL):
        os.remove(OUTPUT_EXCEL)
    
    df = pd.read_excel(file, dtype=str)
    #df["Phone"] = df["Phone"].astype(str).str.strip().str.replace("+", "", regex=False)
    df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

    # results = trigger_calls(EXCEL_FILE)
    # print('Result of trigger calls api ', results)
    # return render_template("index.html", result="\n".join(results))
    Thread(target=trigger_calls, args=(EXCEL_FILE,)).start()
    #return render_template("index.html", result="🚀 Calls triggered in background...")
    return jsonify({
        "message": "🚀 Calls triggered in background!"
    }), 200

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

    if call_id in ongoing_calls:
        del ongoing_calls[call_id]  # This stops the polling!
        print(f"🛑 Stopped polling for call {call_id}")

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
