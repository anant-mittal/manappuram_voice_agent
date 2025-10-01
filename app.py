from flask import Flask, request, jsonify

# Flask app instance
app = Flask(__name__)

@app.route("/vapi-webhook", methods=["POST"])
def vapi_webhook():
    data = request.json
    print("Webhook received:", data)  # log to Render logs
    # You can later add Excel update code here
    return jsonify({"ok": True}), 200

# Only needed for local testing
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
