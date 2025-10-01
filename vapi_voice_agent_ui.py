import gradio as gr
import pandas as pd
import requests, certifi
from config import messages
import tempfile
import os

API_KEY = "0a4d8aad-ddad-4a47-9484-9c64843f59ff"
PHONE_NUMBER_ID = "80db5c92-ebf7-4bfd-afc9-615c50ada458"
url = "https://api.vapi.ai/call"


def trigger_calls(file):
    df = pd.read_excel(file.name)
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

        result = f"Called {customer_number} in {language}: {response.status_code}, {response.json()}"
        results.append(result)

    # Save updated Excel to a temp file
    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "call_results.xlsx")
    df.to_excel(output_path, index=False)

    return "\n".join(results), output_path


with gr.Blocks() as demo:
    gr.Markdown("## 📞 EMI Reminder Voice Agent")
    gr.Markdown("Upload an Excel sheet with columns: **Phone, Language**")

    file_input = gr.File(label="Upload Excel", file_types=[".xlsx"])
    output_box = gr.Textbox(label="Logs", lines=15)
    
    run_button = gr.Button("Trigger Calls")
    download_link = gr.File(label="Download Updated Excel")
    run_button.click(trigger_calls, inputs=file_input, outputs=[output_box, download_link])


if __name__ == "__main__":
    demo.launch()
