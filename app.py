from flask import Flask, request, jsonify
import pandas as pd
import datetime
import os

# Flask app instance
app = Flask(__name__)
EXCEL_FILE = "vapi.xlsx"
OUTPUT_EXCEL = "call_status_log.xlsx"

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
            df = pd.read_excel(OUTPUT_EXCEL, engine='openpyxl')
        else:
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
                'call_start_time': call_start_time or datetime.now().isoformat(),
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

@app.route("/", methods=["GET"])
def index():
    return "Webhook server is running 🚀"


@app.route("/vapi-webhook", methods=["POST"])
def vapi_webhook():
    df = pd.read_excel('vapi.xlsx')
    
    results = []
    data = request.json
    message = data.get('message', {})
    print("Webhook received:", data)  # log to Render logs
    # Get call details
    call = message.get('call', {})
    call_id = call.get('id', 'N/A')
    customer = call.get('customer', {})
    phone_number = customer.get('number', 'Unknown')
    event_type = data.get('message', {}).get('type')

    try:
        df_customers = pd.read_excel('vapi.xlsx')
        customer_row = df_customers[df_customers['Phone'] == phone_number]
        name = customer_row['Name'].values[0] if not customer_row.empty else 'Unknown'
        language = customer_row['Language'].values[0] if not customer_row.empty else 'en'
    except:
        name = 'Unknown'
        language = 'en'
    
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
        duration = call.get('duration', 0)  # in seconds
        cost = call.get('cost', 0)
        started_at = call.get('startedAt')
        ended_at = call.get('endedAt')
        
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
