import math
from functools import wraps
from flask import session, redirect, g, flash
import mysql.connector
import boto3
import requests
import time
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from werkzeug.utils import secure_filename
import os

# Google SMTP credentials
SENDER_EMAIL = os.getenv('SENDER_EMAIL')  # Your Gmail address
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')  # Generated from App Passwords

# AWS credentials
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')  # Your AWS Access Key
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')  # Your AWS Secret Key
AWS_REGION = 'eu-north-1' 
BUCKET_NAME = 'smartlink1'

# Deployed API endpoint
url = "https://yolov8-api-qe9y.onrender.com/predict"

def login_required(f):
    """
    Decorator to check if the user is logged in.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    
    return decorated_function

def user_or_officer_login_required(f):
    """
    Decorator to check if the user or officer is logged in.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None or session.get("officer_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    
    return decorated_function

def officer_login_required(f):
    """
    Decorator to check if the user is logged in.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("officer_id") is None:
            return redirect("/officer-login")
        return f(*args, **kwargs)
    
    return decorated_function

def upload_image(file_stream, file_name):
    try:
        s3 = boto3.client('s3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION)
        
        s3_key = f"user_uploads/{file_name}"
        
        s3.upload_fileobj(
            Fileobj=file_stream,
            Bucket=BUCKET_NAME,
            Key=s3_key
        )

        # s3.upload_file(file_path, BUCKET_NAME, s3_key)
        file_url = f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

        return file_url

    except FileNotFoundError:
        return "File not found."
    
    except Exception as e:
        return f"An error occurred: {str(e)}"
    
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0)**2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance  # in meters

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            port=os.getenv('DB_PORT')
        )
    return g.db

def get_cursor():
    if 'cursor' not in g:
        g.cursor = get_db().cursor(dictionary=True)
    return g.cursor

def keep_api_warm():
    while True:
        try:
            requests.get("https://yolov8-api-qe9y.onrender.com/ping", timeout=5)
        except:
            pass
        time.sleep(600)  # Ping every 10 minutes

import threading

def process_complaints(app, file_bytes, file_name, file_mime, session_data, form_data, officer, assigned_officer_id):
    with app.app_context():
        try:
            # Detection API call
            files_api = {"file": (file_name, BytesIO(file_bytes), file_mime)}
            response = requests.post(url, files=files_api, timeout=200)

            if response.status_code != 200:
                print("Garbage detection API error")
                return

            response_data = response.json()
            if response_data["message"] == "No objects detected.":
                print("No garbage detected, skipping DB insert.")
                return

            # Upload to S3
            s3_url = upload_image(BytesIO(file_bytes), secure_filename(file_name))
            if not s3_url or "Error" in s3_url:
                print("Error uploading to S3")
                return

            # Insert into DB
            db = get_db()
            cursor = get_cursor()
            cursor.execute(
                "INSERT INTO complaints (user_id, image_file_id, area, city, pincode, latitude, longitude, description, assigned_officer) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (session_data["user_id"], s3_url, form_data["area"], form_data["city"], form_data["pincode"],
                 form_data["latitude"], form_data["longitude"], form_data["description"], assigned_officer_id)
            )
            db.commit()

            # Notify
            o_msg = "🚨 New garbage complaint raised in your area. Please check the dashboard."
            u_msg = "Your complaint has been submitted successfully."
            o_mail = f"A new garbage complaint has been raised in your area.\n\nDetails:\nArea: {form_data['area']}\nCity: {form_data['city']}\nPincode: {form_data['pincode']}\nLatitude: {form_data['latitude']}\nLongitude: {form_data['longitude']}\nDescription: {form_data['description']}"
            u_mail = f"Your complaint has been submitted successfully.\n\nDetails:\nArea: {form_data['area']}\nCity: {form_data['city']}\nPincode: {form_data['pincode']}\nLatitude: {form_data['latitude']}\nLongitude: {form_data['longitude']}\nDescription: {form_data['description']}"
            send_sms_and_emails(session_data["email"], officer["email"], o_msg, u_msg, o_mail, u_mail)

        except Exception as e:
            print(f"Error in background processing: {str(e)}")

def send_sms_and_emails(user_email_id, officer_email_id, o_msg, u_msg, o_mail, u_mail):
    # --- SMS
    sms = boto3.client("sns", 
                       region_name="eu-north-1", 
                       aws_access_key_id=AWS_ACCESS_KEY, 
                       aws_secret_access_key=AWS_SECRET_KEY)

    sms.publish(
        PhoneNumber=os.getenv('PH_NUMBER_USER'),
        Message= u_msg,
    )

    sms.publish(
        PhoneNumber=os.getenv('PH_NUMBER_OFFICER'),
        Message= o_msg,
    )

    # --- Email to user
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = user_email_id
        msg['Subject'] = 'SmartLink: Complaint Information'
        body = u_mail
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, user_email_id, msg.as_string())
    except Exception as e:
        print(f"User email failed: {str(e)}")

    # --- Email to officer
    try:
        msg_officer = MIMEMultipart()
        msg_officer['From'] = SENDER_EMAIL
        msg_officer['To'] = officer_email_id
        msg_officer['Subject'] = 'SmartLink: Information'
        body_officer = o_mail
        msg_officer.attach(MIMEText(body_officer, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, officer_email_id, msg_officer.as_string())
    except Exception as e:
        print(f"Officer email failed: {str(e)}")

def process_completed_complaints(app, file_bytes, file_name, file_mime, session_data, complaints):
    with app.app_context():
        try:
            # Detection API call
            files_api = {"file": (file_name, BytesIO(file_bytes), file_mime)}
            response = requests.post(url, files=files_api, timeout=200)

            if response.status_code != 200:
                print("Garbage detection API error")
                return
            
            response_data = response.json()
            if response_data["message"] == "Trash detected.":
                print("Trash detected, skipping DB update.")
                return
            
            # Upload to S3
            s3_url = upload_image(BytesIO(file_bytes), secure_filename(file_name))
            if not s3_url or "Error" in s3_url:
                print("Error uploading to S3")
                return
            
            # Update DB
            db = get_db()
            cursor = get_cursor()
            
            try:
                cursor.execute("UPDATE complaints SET cleanup_image_id = %s WHERE complaint_id = %s",
                            (s3_url, complaints["id"]))
                db.commit()
            except Exception as e:
                print(f"DB update error: {str(e)}")
                return
            
            # Update complaint status
            try:
                cursor.execute("UPDATE complaints SET status = 'completed' WHERE complaint_id = %s", (complaints["id"],))
                db.commit()
            except Exception as e:
                print(f"DB status update error: {str(e)}")
                return
            # Notify
            o_msg = "🚨 Complaint has been completed successfully. Please check the dashboard for details."
            u_msg = "Your complaint has been completed successfully. Thank you for using our service."
            o_mail = f"A garbage complaint has been completed successfully for the complaint id {complaints['id']}\nPlease check the dashboard for more details."
            u_mail = f"Your complaint with id {complaints['id']} has been completed successfully.\n\nThank you for helping us keep the environment clean!"
            try:
                send_sms_and_emails(complaints["email"],session_data["email"], o_msg, u_msg, o_mail, u_mail)
            except Exception as e:
                print(f"Error sending SMS or email: {str(e)}")

        except Exception as e:
            print(f"Error in background processing: {str(e)}")
            
