from flask import Flask, request, jsonify
from flask_cors import CORS
from receptionist_core import (
    register_patient, get_patient_id, suggest_doctor_by_disease,
    book_appointment, cancel_appointment, get_reschedule_slots,
    reschedule_appointment, get_available_slots, answer_faq,
    ask_ai_fallback, patients, doctors, appointments
)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "Hospital Receptionist API is running"})

@app.route('/api/register', methods=['POST'])
def register_patient_api():
    try:
        data = request.json
        required_fields = ['name', 'dob', 'address', 'phone', 'email']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
        
        patient_id = register_patient(
            data['name'], data['dob'], data['address'], 
            data['phone'], data['email']
        )
        
        return jsonify({
            "success": True,
            "message": "Patient registered successfully",
            "patient_id": patient_id
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/patient/<name>', methods=['GET'])
def get_patient_info(name):
    try:
        patient_id = get_patient_id(name)
        if not patient_id:
            return jsonify({"success": False, "message": "Patient not found"}), 404
        
        patient_data = next((p for p in patients if p["patient_id"] == patient_id), None)
        return jsonify({
            "success": True,
            "patient": patient_data
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/doctor-suggestion', methods=['POST'])
def doctor_suggestion():
    try:
        data = request.json
        if 'symptom' not in data:
            return jsonify({"success": False, "message": "Missing symptom description"}), 400
        
        suggestion = suggest_doctor_by_disease(data['symptom'])
        return jsonify(suggestion)
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/doctors', methods=['GET'])
def get_all_doctors():
    try:
        return jsonify({
            "success": True,
            "doctors": doctors
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/available-slots', methods=['GET'])
def available_slots():
    try:
        slots = get_available_slots()
        return jsonify({
            "success": True,
            "available_slots": slots
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/book-appointment', methods=['POST'])
def book_appointment_api():
    try:
        data = request.json
        required_fields = ['patient_id', 'doctor_name']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
        
        payment_confirmed = data.get('payment_confirmed', False)
        result = book_appointment(data['patient_id'], data['doctor_name'], payment_confirmed)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/cancel-appointment', methods=['POST'])
def cancel_appointment_api():
    try:
        data = request.json
        if 'name' not in data:
            return jsonify({"success": False, "message": "Missing patient name"}), 400
        
        result = cancel_appointment(data['name'])
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/reschedule-slots', methods=['POST'])
def get_reschedule_slots_api():
    try:
        data = request.json
        if 'name' not in data:
            return jsonify({"success": False, "message": "Missing patient name"}), 400
        if 'doctor_name' not in data:
            return jsonify({"success": False, "message": "Missing doctor name"}), 400
        
        same_doctor = data.get('same_doctor', True)
        result = get_reschedule_slots(data['name'], data['doctor_name'], same_doctor)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/reschedule-appointment', methods=['POST'])
def reschedule_appointment_api():
    try:
        data = request.json
        required_fields = ['name', 'slot_index']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
        
        new_doctor = data.get('new_doctor', None)
        result = reschedule_appointment(data['name'], data['slot_index'], new_doctor)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/faq', methods=['POST'])
def faq_api():
    try:
        data = request.json
        if 'question' not in data:
            return jsonify({"success": False, "message": "Missing question"}), 400
        
        result = answer_faq(data['question'])
        
        if result['success']:
            return jsonify(result)
        else:
            # If no FAQ found, try AI fallback
            ai_response = ask_ai_fallback(data['question'])
            return jsonify({
                "success": True,
                "answer": ai_response,
                "source": "ai"
            })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/ai-query', methods=['POST'])
def ai_query():
    try:
        data = request.json
        if 'query' not in data:
            return jsonify({"success": False, "message": "Missing query"}), 400
        
        response = ask_ai_fallback(data['query'])
        return jsonify({
            "success": True,
            "response": response
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/appointments/<patient_name>', methods=['GET'])
def get_patient_appointments(patient_name):
    try:
        patient_id = get_patient_id(patient_name)
        if not patient_id:
            return jsonify({"success": False, "message": "Patient not found"}), 404
        
        patient_appointments = [
            appt for appt in appointments 
            if appt.get("patient_id") == patient_id and appt["status"] == "booked"
        ]
        
        return jsonify({
            "success": True,
            "appointments": patient_appointments
        })
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)