import pandas as pd
import requests, certifi
from config import messages


API_KEY = "0a4d8aad-ddad-4a47-9484-9c64843f59ff"
PHONE_NUMBER_ID = "80db5c92-ebf7-4bfd-afc9-615c50ada458"
url = "https://api.vapi.ai/call"

# Load customers from Excel
df = pd.read_excel("vapi.xlsx")

for _, row in df.iterrows():
    customer_number = '+'+str(row["Phone"])
    #print('Phone number ', customer_number, type(customer_number))
    #emi_amount = row["amount"]
    #due_date = row["due_date"]
    language = row["Language"]   # e.g., "en-US", "zh-CN", "hi-IN"
    
    # Map locale → Xiaoxiao voice
    voice_id = "zh-CN-XiaoxiaoMultilingualNeural"
    
    # Build the reminder message in the right language
    # (In real system, you'd store translations in a dict or file)
    
    
    if language == "ka":
        message = messages["ka"]
    elif language == "ta":
        message = messages["ta"]
    elif language == "te":
        message = messages["te"]
    elif language == "ma":
        message = messages["ma"]
    else:
        message = messages["en"]
    
    #"assistantId": "71792de3-d056-4659-a2b1-a686530f80ad",
    # payload = {
        
    #     "phoneNumberId": PHONE_NUMBER_ID,
    #     "customer": {"number": customer_number},
    #     "assistant": {
    #         "name": "EMIReminderBot",
    #         "voice": {"provider": "azure", "voiceId": voice_id},
    #         "model": {
    #                   "provider": "openai", "model": "gpt-4o", 
    #                   "messages": [{"role": "system","content": "You are an automated reminder bot. Your only task is to deliver the firstMessage and immediately end the call. Do NOT wait for user response. Do NOT engage in conversation. As soon as you finish speaking the firstMessage, immediately call the endCall function."}],
    #                   "tools": [{"type": "endCall"}]
    #                   },
    #         "firstMessage": message,
    #     }
    # }

    payload = {
    "phoneNumberId": PHONE_NUMBER_ID,
    "customer": {"number": customer_number},
    "assistant": {
        "name": "EMIReminderBot",
        "voice": {"provider": "azure", "voiceId": voice_id},
        "model": {
            "provider": "openai", 
            "model": "gpt-4o",
            "maxTokens": 1000,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an automated reminder bot. Your only task is to deliver the firstMessage and immediately end the call. Do NOT wait for user response. Do NOT engage in conversation. As soon as you finish speaking the firstMessage, immediately call the endCall function."
                }
            ],
            "tools": [{"type": "endCall"}],
        },
        "firstMessage": message,
        "silenceTimeoutSeconds": 30,  # Reduce silence timeout
        "endCallMessage": " ",       # No end call message
        "endCallPhrases": []
    }
}

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers, verify=False)

    print(f"Called {customer_number} in {language}: {response.status_code}, {response.json()}")
