import numpy as np
import sounddevice as sd
import scipy.signal as signal
import time
import datetime
import sqlite3
import smtplib
import ssl
import wave
from email.message import EmailMessage
import whisper
from twilio.rest import Client

# ===============================
# CONFIGURATION
# ===============================

TONE_A = 1188
TONE_B = 1000
SAMPLE_RATE = 44100
TONE_DURATION = 1.0
RESET_TIME = 180  # 3 minute false-trigger lockout

EMAIL_SENDER = "youremail@gmail.com"
EMAIL_PASSWORD = "app password"

EMAIL_RECIPIENTS = [
    "members email"
]

SMS_GATEWAYS = [
    "+1xxxxxxxxxx",  # Example: Verizon
]

WHISPER_MODEL = whisper.load_model("base")

# ===============================
# TWILIO CONFIGURATION
# ===============================

TWILIO_ACCOUNT_SID = "xxxxxxx"
TWILIO_AUTH_TOKEN = "xxxxxxx"
TWILIO_PHONE_NUMBER = "xxxxxx"

last_trigger_time = 0

# ===============================
# DATABASE SETUP
# ===============================

conn = sqlite3.connect("dispatch_log.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS dispatch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    transcription TEXT,
    email_sent INTEGER
)
""")
conn.commit()

# ===============================
# AUDIO FUNCTIONS
# ===============================

def detect_tone(audio_data, target_freq):
    fft = np.fft.fft(audio_data)
    freqs = np.fft.fftfreq(len(fft), 1/SAMPLE_RATE)
    idx = np.argmax(np.abs(fft))
    freq_detected = abs(freqs[idx])
    return abs(freq_detected - target_freq) < 10

def record_audio(filename, duration=40):
    print("Recording dispatch audio...")
    recording = sd.rec(int(duration * SAMPLE_RATE),
                       samplerate=SAMPLE_RATE,
                       channels=1)
    sd.wait()
    recording = np.int16(recording * 32767)
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(recording.tobytes())
    print("Recording saved.")

# ===============================
# EMAIL + SMS
# ===============================

def send_alert(subject, body, audio_file, transcription):
    # Send Email (with both transcription and audio file)
    msg = EmailMessage()
    msg["From"] = EMAIL_SENDER
    msg["To"] = ", ".join(EMAIL_RECIPIENTS)
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach the audio file
    with open(audio_file, "rb") as f:
        file_data = f.read()
        msg.add_attachment(file_data,
                           maintype="audio",
                           subtype="wav",
                           filename="dispatch.wav")

    # Send email
    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=context)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

    print("Email sent!")

    # Send SMS (only the transcription)
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    for number in SMS_GATEWAYS:
        # Ensure the number is in the correct E.164 format
        to_number = number if number.startswith('+') else f"+1{number}"  # assuming US numbers
        
        message = client.messages.create(
            body=transcription,  # Send only the transcription in the SMS
            from_=TWILIO_PHONE_NUMBER,  # Your Twilio phone number
            to=to_number
        )
        print(f"SMS sent to {to_number} - SID: {message.sid}")

# ===============================
# TRANSCRIPTION
# ===============================

def transcribe_audio(audio_file):
    print("Transcribing...")
    result = WHISPER_MODEL.transcribe(audio_file)
    return result["text"]

# ===============================
# MAIN LOOP
# ===============================

print("🚒 Dispatch system running...")

while True:
    audio = sd.rec(int(TONE_DURATION * SAMPLE_RATE),
                   samplerate=SAMPLE_RATE,
                   channels=1)
    sd.wait()
    audio = audio.flatten()

    if detect_tone(audio, TONE_A):
        print("Tone A detected")
        time.sleep(1)

        audio2 = sd.rec(int(TONE_DURATION * SAMPLE_RATE),
                        samplerate=SAMPLE_RATE,
                        channels=1)
        sd.wait()
        audio2 = audio2.flatten()

        if detect_tone(audio2, TONE_B):
            current_time = time.time()

            if current_time - last_trigger_time > RESET_TIME:
                last_trigger_time = current_time

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                filename = f"dispatch_{int(current_time)}.wav"

                record_audio(filename)
                transcription = transcribe_audio(filename)

                # Print the transcription for debugging/verification
                print("Transcription: ", transcription)
                
                subject = "🚒 Fire Dispatch Alert"
                body = f"""
Dispatch Alert
Time: {timestamp}

Transcription:
{transcription}
"""

                send_alert(subject, body, filename, transcription)

                cursor.execute("""
                INSERT INTO dispatch_log (timestamp, transcription, email_sent)
                VALUES (?, ?, ?)
                """, (timestamp, transcription, 1))
                conn.commit()

                print("Dispatch logged.")

            else:
                print("Trigger blocked (within 3 min window)")
