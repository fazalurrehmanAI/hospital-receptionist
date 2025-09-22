import json
import difflib
import datetime
from transformers import pipeline
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from rapidfuzz import process
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Get the API key from environment variables
api_key= os.getenv("OPENROUTER_API_KEY")

# Check if the API key was loaded successfully
if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables")

# Initialize the OpenAI client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

# === JSON Load/Save Helpers ===
def load_json(path): 
    return json.load(open(path, encoding='utf-8'))

def save_json(path, data): 
    json.dump(data, open(path, 'w', encoding='utf-8'), indent=4)

# Load data
patients = load_json("data/patients.json")
appointments = load_json("data/appointments.json")
faqs = load_json("data/faqs.json")
doctors = load_json("data/doctors.json")
disease_specialty_map = load_json("data/disease_map.json")

# Create lookups
patient_lookup = {p["patient_id"]: p["name"] for p in patients}
doctor_email_lookup = {doc["name"]: doc["contact"] for doc in doctors}

# Add patient_name to each appointment if not exists
for appt in appointments:
    if "patient_name" not in appt:
        pid = appt.get("patient_id")
        appt["patient_name"] = patient_lookup.get(pid, "Unknown")

# === Patient Functions ===
def get_patient_id(name): 
    return next((p["patient_id"] for p in patients if p["name"].lower() == name.lower()), None)

def register_patient(name, dob, address, phone, email):
    pid = f"P{len(patients)+1:03d}"
    new_patient = {
        "patient_id": pid,
        "name": name,
        "dob": dob,
        "phone": phone,
        "email": email,
        "address": address,
        "medical_history": []
    }
    patients.append(new_patient)
    save_json("data/patients.json", patients)
    return pid

# === Doctor Suggestion by Disease ===
def suggest_doctor_by_disease(symptom):
    symptom = symptom.lower()

    # 1. Try direct substring match
    for keyword, specialty in disease_specialty_map.items():
        if keyword in symptom:
            return get_doctor_by_specialty(specialty)

    # 2. Try word-by-word matching
    words = symptom.split()
    for word in words:
        if word in disease_specialty_map:
            specialty = disease_specialty_map[word]
            return get_doctor_by_specialty(specialty)

    # 3. Try fuzzy matching
    all_keywords = list(disease_specialty_map.keys())
    close = difflib.get_close_matches(symptom, all_keywords, n=1, cutoff=0.4)
    if close:
        specialty = disease_specialty_map[close[0]]
        return get_doctor_by_specialty(specialty)

    return {"error": "Sorry, we couldn't find a doctor for your condition. Please try describing it differently."}

def get_doctor_by_specialty(specialty):
    for doc in doctors:
        if specialty.lower() in doc["specialization"].lower():
            return {
                "specialty": specialty,
                "doctor": {
                    "name": doc['name'],
                    "specialization": doc['specialization'],
                    "education": doc['education'],
                    "experience": doc['experience'],
                    "fee": doc['fee'],
                    "contact": doc['contact'],
                    "bio": doc['bio']
                }
            }
    return {"error": f"No {specialty} available in our system."}

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def send_email_notification(to_email, patient_name, date, time, doctor, subject_type="booking"):
    sender_email = "abdulrehmangill127@gmail.com"
    sender_password = "qlwb uxab umxp dyeq"  # App password

    if subject_type == "booking":
        subject = "Appointment Booking Confirmation"
        body = f"Dear {patient_name},\n\nYour appointment has been successfully booked.\n\n"
    elif subject_type == "reschedule":
        subject = "Appointment Rescheduled Confirmation"
        body = f"Dear {patient_name},\n\nYour appointment has been successfully rescheduled.\n\n"
    else:
        subject = "Appointment Cancelled"
        body = f"Dear {patient_name},\n\nYour appointment has been cancelled.\n\n"

    body += (
        f"Details:\n"
        f"Doctor: {doctor}\n"
        f"Date: {date}\n"
        f"Time: {time}\n\n"
        "Thank you for choosing our hospital.\n"
    )

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        return False

def send_doctor_notification(subject, body, doctor_name):
    sender_email = "abdulrehmangill127@gmail.com"
    sender_password = "qlwb uxab umxp dyeq"

    doctor_email = doctor_email_lookup.get(doctor_name)
    if not doctor_email:
        return False

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = doctor_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        return False

# === Appointment Functions ===
def is_future_slot(date_str, time_str):
    now = datetime.datetime.now()
    slot_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return slot_time > now

def get_available_slots():
    available_slots = []
    for slot in appointments:
        if slot["status"] == "available" and is_future_slot(slot["date"], slot["time"]):
            available_slots.append(slot)
    return available_slots

def book_appointment(patient_id, doctor_name, payment_confirmed=False):
    if not payment_confirmed:
        return {
            "success": False,
            "message": "Payment confirmation required",
            "payment_details": "Please send the consultation fee to Bank Account 1234-5678-9012 at XYZ Bank."
        }

    now = datetime.datetime.now()
    print('pass1')
    # Reset expired booked appointments
    for slot in appointments:
        slot_time = datetime.datetime.strptime(f"{slot['date']} {slot['time']}", "%Y-%m-%d %H:%M")
        if slot_time < now:
            slot_time += datetime.timedelta(days=1)
            slot_time = str(slot_time).split(' ')[0]
            slot['date'] = slot_time
            slot["status"] = "available"
            slot["patient_id"] = None

    # Find doctor using fuzzy matching
    doctor_names = list({slot["doctor"].strip() for slot in appointments})
    match_result = process.extractOne(doctor_name.strip(), doctor_names, score_cutoff=60)
    print('pass2')
    if not match_result:
        return {
            "success": False,
            "message": f"No close match found for doctor name '{doctor_name}'. Please try again.",
            "available_doctors": [slot['doctor'] for slot in appointments if slot['status'] == 'available']
        }

    matched_name = match_result[0].strip().lower()
    print('pass3')
    # Book the next future slot with matched doctor name
    for i, slot in enumerate(appointments):
        slot_doctor_clean = slot["doctor"].strip().lower()
        if (slot["status"] == "available" and 
            is_future_slot(slot["date"], slot["time"]) and 
            slot_doctor_clean == matched_name):
            
            appointments[i]["status"] = "booked"
            appointments[i]["patient_id"] = patient_id
            patient_data = next((p for p in patients if p["patient_id"] == patient_id), None)
            appointments[i]["patient_name"] = patient_data["name"] if patient_data else "Unknown"
            print(patient_data) 
            save_json("data/appointments.json", appointments)
            print('pass4')
            # Send notifications
            if patient_data and is_valid_email(patient_data["email"]):
                send_email_notification(
                    to_email=patient_data["email"],
                    patient_name=patient_data["name"],
                    date=slot["date"],
                    time=slot["time"],
                    doctor=slot["doctor"],
                    subject_type="booking"
                )
            print('pass5')
            doctor_subject = "New Appointment Booked"
            doctor_body = (
                f"Dear Dr. {slot['doctor']},\n\n"
                f"A new appointment has been booked for a patient.\n\n"
                f"Appointment Details:\n"
                f"Patient ID: {patient_id}\n"
                f"Date: {slot['date']}\n"
                f"Time: {slot['time']}\n\n"
                f"Thank you."
            )
            send_doctor_notification(doctor_subject, doctor_body, slot["doctor"])
            print('pass6')
            return {
                "success": True,
                "message": f"Appointment booked successfully",
                "appointment": {
                    "patient_name": patient_data["name"],
                    "patient_id": patient_id,
                    "date": slot["date"],
                    "time": slot["time"],
                    "doctor": slot["doctor"]
                }
            } 

    return {
        "success": False,
        "message": f"No future slots are available for {doctor_name} at the moment.",
        "available_doctors": [slot['doctor'] for slot in appointments if slot['status'] == 'available']
    }

def cancel_appointment(name):
    pid = get_patient_id(name)
    if not pid:
        return {"success": False, "message": "Patient not found"}

    for slot in appointments:
        if slot["patient_id"] == pid and slot["status"] == "booked":
            slot["status"] = "available"
            slot["patient_id"] = None
            slot["patient_name"] = None
            save_json("data/appointments.json", appointments)

            patient_data = next((p for p in patients if p["patient_id"] == pid), None)
            if patient_data and is_valid_email(patient_data["email"]):
                send_email_notification(
                    to_email=patient_data["email"],
                    patient_name=patient_data["name"],
                    date=slot["date"],
                    time=slot["time"],
                    doctor=slot["doctor"],
                    subject_type="cancellation"
                )

            doctor_subject = "Appointment Cancelled"
            doctor_body = (
                f"Dear Dr. {slot['doctor']},\n\n"
                f"An appointment has been cancelled.\n\n"
                f"Appointment Details:\n"
                f"Patient ID: {pid}\n"
                f"Date: {slot['date']}\n"
                f"Time: {slot['time']}\n\n"
                f"Thank you."
            )
            send_doctor_notification(doctor_subject, doctor_body, slot["doctor"])

            return {
                "success": True,
                "message": f"Appointment cancelled successfully",
                "cancelled_appointment": {
                    "patient_name": name,
                    "patient_id": pid,
                    "date": slot["date"],
                    "time": slot["time"],
                    "doctor": slot["doctor"]
                }
            }
    
    return {"success": False, "message": "No active appointment found"}

def get_reschedule_slots(name, doctor_name, same_doctor=True):
    pid = get_patient_id(name)
    if not pid:
        return {"success": False, "message": "Patient not found"}

    old_slot = None
    for slot in appointments:
        if slot["patient_id"] == pid and slot["status"] == "booked":
            old_slot = slot
            break

    if not old_slot:
        return {"success": False, "message": "No previous appointment found to reschedule"}

    if same_doctor:
        selected_doctor = old_slot["doctor"]
    else:
        selected_doctor = doctor_name

    doctor_slots = [
        s for s in appointments
        if s["doctor"].strip().lower() == selected_doctor.strip().lower()
        and s["status"] == "available"
        and is_future_slot(s["date"], s["time"])
    ]

    if not doctor_slots:
        return {"success": False, "message": f"No available future slots for Dr. {selected_doctor}"}

    return {
        "success": True,
        "current_appointment": old_slot,
        "available_slots": doctor_slots,
        "doctor": selected_doctor
    }

def reschedule_appointment(name, slot_index, new_doctor=None):
    pid = get_patient_id(name)
    if not pid:
        return {"success": False, "message": "Patient not found"}

    old_slot = None
    for slot in appointments:
        if slot["patient_id"] == pid and slot["status"] == "booked":
            old_slot = slot
            break

    if not old_slot:
        return {"success": False, "message": "No previous appointment found"}

    selected_doctor = new_doctor if new_doctor else old_slot["doctor"]
    
    doctor_slots = [
        s for s in appointments
        if s["doctor"].strip().lower() == selected_doctor.strip().lower()
        and s["status"] == "available"
        and is_future_slot(s["date"], s["time"])
    ]

    if not doctor_slots or slot_index >= len(doctor_slots):
        return {"success": False, "message": "Invalid slot selection"}

    chosen_slot = doctor_slots[slot_index]
    patient_data = next((p for p in patients if p["patient_id"] == pid), None)

    # Cancel old appointment
    old_slot["status"] = "available"
    old_slot["patient_id"] = None
    old_slot["patient_name"] = None

    # Book new slot
    chosen_slot["status"] = "booked"
    chosen_slot["patient_id"] = pid
    chosen_slot["patient_name"] = patient_data["name"] if patient_data else "Unknown"

    save_json("data/appointments.json", appointments)

    # Send notifications
    if patient_data and is_valid_email(patient_data["email"]):
        send_email_notification(
            to_email=patient_data["email"],
            patient_name=patient_data["name"],
            date=chosen_slot["date"],
            time=chosen_slot["time"],
            doctor=selected_doctor,
            subject_type="reschedule"
        )

    doctor_subject = "Appointment Rescheduled"
    doctor_body = (
        f"Dear Dr. {selected_doctor},\n\n"
        f"An appointment has been rescheduled.\n\n"
        f"New Appointment Details:\n"
        f"Patient ID: {pid}\n"
        f"Date: {chosen_slot['date']}\n"
        f"Time: {chosen_slot['time']}\n\n"
        f"Thank you."
    )
    send_doctor_notification(doctor_subject, doctor_body, selected_doctor)

    return {
        "success": True,
        "message": "Appointment rescheduled successfully",
        "new_appointment": {
            "patient_name": name,
            "patient_id": pid,
            "date": chosen_slot["date"],
            "time": chosen_slot["time"],
            "doctor": selected_doctor
        }
    }

# === FAQ Lookup ===
def answer_faq(user_input):
    for faq in faqs:
        if user_input.lower() in faq["question"].lower():
            return {"success": True, "answer": faq["answer"]}
    return {"success": False, "message": "No FAQ found for your query"}

# === AI Prompt Format ===
def format_prompt(user_input):
    return f"""<|system|>
    You are a polite, professional hospital receptionist. Answer short, helpful, and factual.
    <|user|>
    {user_input}
    <|assistant|>"""

def ask_ai_fallback(user_input):
    prompt = format_prompt(user_input)
    # response = pipe(prompt, max_new_tokens=80, do_sample=False, temperature=0.5)[0]["generated_text"]
    # # return response.split("<|assistant|>")[-1].strip()

    completion = client.chat.completions.create(
    extra_headers={
        "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
        "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
    },
    extra_body={},
    model="deepseek/deepseek-chat-v3-0324:free",
    messages=[
        {
        "role": "user",
        "content": prompt
        }
    ]
    )
    return completion.choices[0].message.content