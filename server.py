import os
import socket
from flask import Flask, request, jsonify
from PIL import Image
import numpy as np
import tensorflow as tf

app = Flask(__name__)

# TFLITE MODEL CONFIG 
# This completely bypasses all Keras .h5 errors!
MODEL_PATH = "model.tflite"
LABELS_PATH = "labels.txt"

interpreter = None
input_details = None
output_details = None
labels = []

print("="*60)
print(" 🏥 SMART CARE APP - AI BASE STATION SERVER (TFLITE V2) ")
print("="*60)

# 1. Load TFLite Model
print(f"Loading AI Model from: {MODEL_PATH} ...")
if os.path.exists(MODEL_PATH):
    try:
        # TFLite never throws Keras 'Functional' shape errors!
        interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        print("✅ Core TFLite AI Model loaded successfully!")
    except Exception as e:
        print("❌ Error loading TFLite model:", e)
else:
    print(f"❌ '{MODEL_PATH}' NOT FOUND!")
    print("👉 PLEASE DOWNLOAD 'model.tflite' FROM COLAB AND PUT IT IN THIS FOLDER!")

# 2. Load Labels
if os.path.exists(LABELS_PATH):
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels = [line.strip() for line in f.readlines()]
    print(f"✅ Loaded {len(labels)} medicine names.")
else:
    print(f"⚠️ '{LABELS_PATH}' not found!")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"
        
MY_IP = get_local_ip()

@app.route('/predict', methods=['POST'])
def predict():
    """Endpoint for Android app to hit"""
    if interpreter is None:
        return jsonify({"prediction": "Server Model Error (TFLite missing)", "confidence": 0}), 500
        
    if 'image' not in request.files:
        return jsonify({"prediction": "No Image sent", "confidence": 0}), 400
        
    try:
        file = request.files['image']
        image = Image.open(file.stream).convert('RGB')
        
        # Preprocessing for Teachable Machine TFLite Models (224x224, float32, -1 to 1)
        image = image.resize((224, 224), Image.Resampling.LANCZOS)
        img_array = np.array(image, dtype=np.float32)
        img_array = np.expand_dims(img_array, axis=0) 
        img_array = (img_array / 127.5) - 1.0 
        
        # TFLite Inference
        interpreter.set_tensor(input_details[0]['index'], img_array)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])
        
        index = np.argmax(output_data)
        confidence = float(output_data[0][index]) * 100
        
        raw_label = labels[index] if index < len(labels) else f"Class {index}"
        clean_name = raw_label.split(" ", 1)[1] if " " in raw_label and raw_label.split(" ", 1)[0].isdigit() else raw_label
            
        print(f"\n[AI SCANNER]: Image Scanned -> {clean_name} ({confidence:.1f}%)")
        
        return jsonify({
            "prediction": clean_name,
            "confidence": round(confidence, 1)
        })
        
    except Exception as e:
        print("❌ Server Error:", e)
        return jsonify({"prediction": "Error reading image", "confidence": 0}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 BASE STATION READY TO RECEIVE IMAGES OVER WIFI!")
    print(f"⚠️ TYPE THIS IP INTO THE ANDROID APP:  {MY_IP}")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000)

