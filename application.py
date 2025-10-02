from flask import Flask, render_template, redirect, request, session, flash, jsonify, g, current_app
from flask_session import Session
from helpers import login_required,officer_login_required, upload_image, haversine, get_cursor, get_db, keep_api_warm, process_complaints, process_completed_complaints, send_sms_and_emails
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import numpy as np
from mysql.connector import connect, Error
import boto3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import requests
import threading
import os

application = Flask(__name__)
app = application

threading.Thread(target=keep_api_warm, daemon=True).start()

# Google SMTP credentials
SENDER_EMAIL = os.getenv('SENDER_EMAIL')  # Your Gmail address
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')  # Generated from App Passwords

# AWS credentials 
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = 'eu-north-1' 
BUCKET_NAME = 'smartlink1'

url = "https://yolov8-api-qe9y.onrender.com/predict"

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    cursor = g.pop('cursor', None)
    if cursor:
        cursor.close()
    if db:
        db.close()

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.after_request
def after_request(response):
    # Set the cache control headers to prevent caching
    response.headers['Cache-Control'] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers['Pragma'] = "no-cache"
    return response

@app.route('/')
def index():
    """Home page"""

    if session.get("officer_id") is not None:
        return redirect("/officer-dash")

    cursor = get_cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM complaints;")
        complaints = cursor.fetchone()["COUNT(*)"]
    except:
        complaints = 0
    
    try:
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'new'") 
        pending = cursor.fetchone()["COUNT(*)"]
    except:
        pending = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'completed'")
        completed = cursor.fetchone()["COUNT(*)"]
    except:
        completed = 0

    query = """SELECT users.username, users.email, COUNT(complaints.complaint_id) AS complaints, 
                COUNT(CASE WHEN complaints.status = 'completed' THEN 1 END) AS completed, 
                CASE 
                    WHEN SUM(CASE WHEN complaints.status IN ('new', 'pending') THEN 1 ELSE 0 END) > 0 
                    THEN 'Active'
                    ELSE 'Inactive'
                    END AS user_status
               FROM complaints JOIN users ON complaints.user_id = users.id GROUP BY users.id ORDER BY complaints DESC LIMIT 5"""
    
    cursor.execute(query)
    top_users = cursor.fetchall()

    return render_template("index.html", username=session.get("username"), complaints=complaints, pending=pending, completed=completed, top_users=top_users)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            flash('Must provide username', 'error')
            return render_template("login.html")
        
        # Ensure password was submitted
        if not request.form.get("password"):
            flash('Must provide password', 'error')
            return render_template("login.html")
        
        # Query database for username
        username = request.form.get("username")
        password = request.form.get("password")

        cursor = get_cursor()
        try:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            usernames = cursor.fetchone()
        except:
            flash('Invalid username', 'error')
            return render_template("login.html")
        
        if usernames is None:
            flash('Invalid username', 'error')
            return render_template("login.html")
        
        if not check_password_hash(usernames["password"], password):
            flash('Incorrect password', 'error')
            return render_template("login.html")
        
        session["user_id"] = str(usernames["id"])
        session["username"] = usernames["username"]
        session["email"] = usernames["email"]
        flash('Logged in successfully', 'success')

        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("login.html")
    
@app.route("/logout")
@login_required
def logout():
    """Log user out"""
    # Forget any user_id
    session.clear()

    flash('Logged out successfully', 'info')
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            flash('Must provide username', 'error')
            return render_template("register.html") 
        
        # Ensure phone number was submitted
        if not request.form.get("mobile_no"):
            flash('Must provide mobile number', 'error')
            return render_template("register.html")
        
        if not re.fullmatch(r'^\+91\d{10}$', request.form.get("mobile_no")):
            flash("Enter a valid number in +91XXXXXXXXXX format.", "error")
            return redirect("/register")
        
        # Ensure email was submitted
        if not request.form.get("email"):
            flash('Must provide email', 'error')
            return render_template("register.html")
        
        # Ensure password was submitted
        if not request.form.get("password"):
            flash('Must provide password', 'error')
            return render_template("register.html")
        
        # Ensure password confirmation was submitted
        if not request.form.get("confirm_password"):
            flash('Must provide password confirmation', 'error')
            return render_template("register.html")
        
        # Ensure password and confirmation match
        if request.form.get("password") != request.form.get("confirm_password"):
            flash('Passwords do not match', 'error')
            return render_template("register.html")
         
        # Check if username already exists
        cursor = get_cursor()
        db = get_db()

        username = request.form.get("username")
        email_id = request.form.get("email")


        # Hash the password
        hashed_password = generate_password_hash(request.form.get("password"))

        # Store the user in the database
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email_id, hashed_password))
            db.commit()
            return render_template("login.html")
        except Error as e:
            flash("Username or email already exists", 'error')
            return render_template("register.html")        

    else:
        return render_template("register.html")
    
@app.route("/profile")
def profile():
    """User profile page"""
    if session.get("user_id") is None and session.get("officer_id") is None:
        flash('You must be logged in to view this page', 'error')
        return redirect("/")
    
    cursor = get_cursor()
    if session.get("officer_id") is not None:
        try:
            cursor.execute("SELECT o.username, o.mobile_no, o.email, o.id, COUNT(c.complaint_id) AS total_complaints, COUNT(CASE WHEN c.status = 'Completed' THEN 1 END) AS completed_complaints FROM officers o JOIN complaints c ON c.assigned_officer = o.id WHERE o.id = %s", (session["officer_id"],))
            user = cursor.fetchone()
            if user is None:
                flash('Officer not found', 'error')
                return redirect("/officer-login")
        except:
            flash('Error fetching officer data', 'error')
            return redirect("/officer-login")
        
    elif session.get("user_id") is not None:
        try:
            cursor.execute("SELECT u.username, u.mobile_no, u.email, u.id, COUNT(c.complaint_id) AS total_complaints, COUNT(CASE WHEN c.status = 'Completed' THEN 1 END) AS completed_complaints FROM users u JOIN complaints c ON c.user_id = u.id  WHERE u.id = %s", (session["user_id"],))
            user = cursor.fetchone()
            if user is None:
                flash('User not found', 'error')
                return redirect("/")
            
        except:
            flash('Error fetching user data', 'error')
            return redirect("/")    
    return render_template("profile.html", user=user)
        
@app.route("/get-location", methods=["POST"])
def get_location():
        data = request.get_json()
        latitude = data["latitude"]
        longitude = data["longitude"]

        # Connect to AWS Location Service
        client = boto3.client(
            'location',
            region_name= AWS_REGION,
            aws_access_key_id= AWS_ACCESS_KEY,
            aws_secret_access_key= AWS_SECRET_KEY
        )

        try:
            response = client.search_place_index_for_position(
                IndexName='SmartLink',
                Position=[longitude, latitude]
            )

            if response['Results']:
                place = response['Results'][0]['Place']
                return jsonify({
                    'neighborhood': place.get('Neighborhood', 'Not found'),
                    'municipality': place.get('Municipality', 'Not found'),
                    'postal_code': place.get('PostalCode', 'Not found')
                })
            else:
                return jsonify({
                    'neighborhood': 'Not found',
                    'municipality': 'Not found',
                    'postal_code': 'Not found'
                })

        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
@app.route("/auto-complaint", methods=["POST"])
def auto_complaint():
    """Auto complaint submission endpoint for garbage detection from camera feed"""
    file = request.files.get('image')
    if not file:
        return jsonify({"error": "No image provided"}), 400
    area = request.form.get("area")
    city = request.form.get("city")
    pincode = request.form.get("pincode")
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    description = "Auto-generated complaint from CCTV feed. Please check the image for details."
    user_id = request.form.get("user_id")
    email = request.form.get("email")

    if not all([area, city, pincode, latitude, longitude]):
        return jsonify({"error": "All fields are required"}), 400
    
    cursor = get_cursor()
    db = get_db()
    try:
        cursor.execute("SELECT id, email FROM officers WHERE assigned_area = %s", (area,))
        officer = cursor.fetchone()
        if officer:
            assigned_officer_id = officer["id"]
        else:
            assigned_officer_id = 2  # Default officer ID if no officer is found for the area
    except Error as e:
        return jsonify({"error": f"Error fetching officer: {str(e)}"}), 500
    
    s3_url = upload_image(file.stream, secure_filename(file.filename))
    if not s3_url or "Error" in s3_url:
        return jsonify({"error": "Error uploading image to S3"}), 500
    
    try:
        cursor.execute("INSERT INTO complaints (user_id, image_file_id, area, city, pincode, latitude, longitude, description, assigned_officer) VALUES(%s, %s, %s, %s, %s, %s, %s, %s,%s)",
                       (user_id, s3_url, area, city, pincode, latitude, longitude, description, assigned_officer_id))
        db.commit()
    except Error as e:
        return jsonify({"error": f"Error inserting complaint: {str(e)}"}), 500

    # SMS notification setup
    o_msg = "🚨 New garbage complaint raised in your area. Please check the dashboard."
    u_msg = "Your complaint has been submitted successfully."
    o_mail = f"A new garbage complaint has been raised in your area.\n\nDetails:\nArea: {area}\nCity: {city}\nPincode: {pincode}\nLatitude: {latitude}\nLongitude: {longitude}\nDescription: {description}\n\nPlease check the dashboard for more details."
    u_mail = f"Your complaint has been submitted successfully.\n\nDetails:\nArea: {area}\nCity: {city}\nPincode: {pincode}\nLatitude: {latitude}\nLongitude: {longitude}\nDescription: {description}\n\nThank you for helping us keep the environment clean!"

    send_sms_and_emails(email, officer["email"], o_msg, u_msg, o_mail, u_mail)
    return jsonify({"message": "Complaint submitted successfully"}), 200
        
@app.route("/complaint", methods=["GET", "POST"])
@login_required
def complaint():
    """Complaint page"""
    
    if request.method == "POST":
        # Ensure complaint was submitted
        if 'image' not in request.files:
            flash('No image in the form', 'error')
            return render_template("complaint.html")
    
        file = request.files['image']
    
        if file.filename == '':
            flash('No image selected for uploading', 'error')
            return render_template("complaint.html", message="No image selected for uploading")

        # Database related coding
        area = request.form.get("area").strip()
    
        city = request.form.get("city")
    
        pincode= request.form.get("pincode")
    
        latitude = request.form.get("latitude")
    
        longitude = request.form.get("longitude")
    
        description = request.form.get("description")

        if not all([area, city, pincode, latitude, longitude]):
            flash('All fields are required', 'error')
            return render_template("complaint.html")
        
        if not description:
            description = "Trash detected in the area. Please check the image for details."

        cursor = get_cursor()
        db = get_db()
        try:
            cursor.execute("SELECT id, email FROM officers WHERE assigned_area = %s", (area,))
            officer = cursor.fetchone()
            if officer:
                assigned_officer_id = officer["id"]
            else:
                assigned_officer_id = 2  # Default officer ID if no officer is found for the area
        except Error as e:
            flash(f"Error fetching officer: {str(e)}", 'error')
            return render_template("complaint.html",)
        
        # Read file as bytes
        file_bytes = file.read()
        file.seek(0)

        # Get session and form data
        session_data = dict(session)
        form_data = {
            "area": area,
            "city": city,
            "pincode": pincode,
            "latitude": latitude,
            "longitude": longitude,
            "description": description
        }

        # Launch background thread
        # Launch thread with app context
        threading.Thread(
            target=process_complaints,
            args=(current_app._get_current_object(), file_bytes, file.filename, file.mimetype, session_data, form_data, officer, assigned_officer_id),
            daemon=True
        ).start()

        flash("Complaint is being analyzed. You will be notified if garbage is detected.", "info")
        return redirect("/")


        
        
        # file_bytes = file.read()
        # file.seek(0) 

        # files_api = {"file": (file.filename, BytesIO(file_bytes), file.mimetype)}
        # try:
        #     response = requests.post(url, files=files_api, timeout=200)
        #     if response.status_code != 200:
        #         flash("Garbage detection API error", 'error')
        #         return render_template("complaint.html")
        #     response_data = response.json()
        #     if response_data["message"] == "No objects detected.":
        #         flash("No garbage detected in the image", 'error')
        #         return redirect("/")
        #     flash(f"Garbage detected in the image: {response_data['message']}", 'info')
        # except Exception as e:
        #     flash(f"API error: {str(e)}", 'error')
        #     return render_template("complaint.html")
        
        # # --- S3 Upload ---
        # filename = secure_filename(file.filename)
        # s3_url = upload_image(BytesIO(file_bytes), filename)

        # if not s3_url or "Error" in s3_url:
        #     flash("Error uploading to S3", 'error')
        #     return render_template("complaint.html")
        
        # try:
        #     cursor.execute("INSERT INTO complaints (user_id, image_file_id, area, city, pincode, latitude, longitude, description, assigned_officer) VALUES(%s, %s, %s, %s, %s, %s, %s, %s,%s)",(session["user_id"], s3_url, area, city, pincode, latitude, longitude, description, assigned_officer_id))
        #     db.commit()
        # except Error as e:
        #     flash(f"Error inserting complaint: {str(e)}", 'error')
        #     return render_template("complaint.html")

        # # SMS notification setup
        # sms = boto3.client("sns", 
        #                    region_name = AWS_REGION, 
        #                    aws_access_key_id = AWS_ACCESS_KEY, 
        #                    aws_secret_access_key = AWS_SECRET_KEY)
        
        # # Send SMS notification to user
        # sms.publish(
        # PhoneNumber="+919866510983",  # Replace with actual number
        # Message="Your complaint has been submitted successfully.",
        # )

        # # Notify the assigned officer
        # sms.publish(
        # PhoneNumber="+919676394804",
        # Message="🚨 New garbage complaint raised in your area. Please check the dashboard for details.",
        # )
        
        # # Send email notification
        # try:
        #     msg = MIMEMultipart()
        #     msg['From'] = SENDER_EMAIL
        #     msg['To'] = session.get("email")  # Assuming username is the email
        #     msg['Subject'] = 'New Garbage Complaint Submitted'
        #     body = f"Your complaint has been submitted successfully.\n\nDetails:\nArea: {area}\nCity: {city}\nPincode: {pincode}\nLatitude: {latitude}\nLongitude: {longitude}\nDescription: {description}\n\nThank you for helping us keep the environment clean!"
        #     msg.attach(MIMEText(body, 'plain'))

        #     with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        #         server.login(SENDER_EMAIL, SENDER_PASSWORD)
        #         server.sendmail(SENDER_EMAIL, session.get("email"), msg.as_string())

        # except Exception as e:
        #     flash(f"Error sending email: {str(e)}", 'error')

        # try:
        #     msg_officer = MIMEMultipart()
        #     msg_officer['From'] = SENDER_EMAIL
        #     msg_officer['To'] = officer["email"]  # Assuming officer has an email field
        #     msg_officer['Subject'] = 'New Garbage Complaint Assigned'
        #     body_officer = f"A new garbage complaint has been assigned to you.\n\nDetails:\nArea: {area}\nCity: {city}\nPincode: {pincode}\nLatitude: {latitude}\nLongitude: {longitude}\nDescription: {description}\n\nPlease check the dashboard for more details."
        #     msg_officer.attach(MIMEText(body_officer, 'plain'))

        #     with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        #         server.login(SENDER_EMAIL, SENDER_PASSWORD)
        #         server.sendmail(SENDER_EMAIL, officer["email"], msg_officer.as_string())
        
        # except Exception as e:
        #     flash(f"Error sending email to officer: {str(e)}", 'error')
        
        # # Flash success message
        # flash('Complaint submitted successfully', 'success')
        # return redirect("/")
    else:
        try:
            requests.get("https://yolov8-api-qe9y.onrender.com/ping", timeout=3)
            flash('Garbage detection API is online', 'info')
        except Exception:
            pass
        return render_template("complaint.html")
    
@app.route("/faq")
def faq():
    """FAQ page"""
    return render_template("faq.html")

@app.route("/about")
def about():
    """About page"""
    return render_template("about.html")

@app.route("/officer-login", methods=["GET", "POST"])
def officer_login():
    """Officer login page"""
    # Forget any user_id
    session.clear()

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("officer-username"):
            flash('Must provide username', 'error')
            return render_template("officer-login.html")
        
        # Ensure password was submitted
        if not request.form.get("officer-password"):
            flash('Must provide password', 'error')
            return render_template("officer-login.html")
        
        #Database
        # Query database for username
        username = request.form.get("officer-username")
        password = request.form.get("officer-password")

        cursor = get_cursor()
        try:
            cursor.execute("SELECT * FROM officers WHERE username = %s", (username,))
            officer = cursor.fetchone()
        except:
            flash('Invalid username', 'error')
            return render_template("officer-login.html")
        
        if officer is None:
            flash('Invalid username', 'error')
            return render_template("officer-login.html")

        # Check password
        if not check_password_hash(officer["password"], password):
            flash('Incorrect password', 'error')
            return render_template("officer-login.html")
        
        session["officer_id"] =  str(officer["id"])
        session["username"] = officer["username"]
        session["email"] = officer["email"]

        flash('Logged in successfully', 'success')
        return redirect("/officer-dash")
    
    else:
        return render_template("officer-login.html")
    
@app.route("/officer-dash")
@officer_login_required
def officer_dash():
    """Officer dashboard page"""

    cursor = get_cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE assigned_officer = %s", (session["officer_id"],))
        total_complaints = cursor.fetchone()["COUNT(*)"]
    except:
        total_complaints = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE assigned_officer = %s AND status = 'new'", (session["officer_id"],))
        pending_complaints = cursor.fetchone()["COUNT(*)"]
    except:
        pending_complaints = 0
    
    try:
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE assigned_officer = %s AND status = 'completed'", (session["officer_id"],))
        completed_complaints = cursor.fetchone()["COUNT(*)"]
    except:
        completed_complaints = 0


    # image_data = None
            # if "image_file_id" in complaint:
            #     image_file = user_images_collection.find_one(
            #         {"_id": ObjectId(complaint["image_file_id"])}
            #     )
                
            #     if image_file and "file_id" in image_file:
            #         image_data = base64.b64encode(
            #             fs.get(image_file["file_id"]).read()
            #         ).decode('utf-8')

    try:
        cursor.execute("SELECT u.username, c.complaint_id, c.area, c.city, c.pincode, c.latitude, c.longitude, c.status, c.description, c.assigned_officer, c.timestamp, c.image_file_id, c.cleanup_image_id FROM complaints c JOIN users u ON c.user_id = u.id WHERE assigned_officer = %s ORDER BY timestamp DESC", (session["officer_id"],))
        complaints = cursor.fetchall()
    except:
        flash('Error fetching complaints data', 'error')

        return render_template("officer-dash.html", complaints=[], error="Error fetching complaints data", username=session.get("username"))
    
    if complaints is None:
        flash('No complaints assigned to you', 'info')

        return render_template("officer-dash.html", complaints=[], username=session.get("username"))
    
    return render_template("officer-dash.html", complaints=complaints, username=session.get("username"), total_complaints=total_complaints, pending_complaints=pending_complaints, completed_complaints=completed_complaints)

@app.route("/complete", methods=["GET", "POST"])
@officer_login_required
def complete():
    """Complete complaint"""

    if request.method == "POST":
        # Ensure complaint was submitted
        if 'image' not in request.files:
            flash('No image in the form', 'error')
            return render_template("complete.html")
        
        file = request.files['image']
        
        if file.filename == '':
            flash('No image selected for uploading', 'error')
            return render_template("complete.html")
        
        # Database related coding
        area = request.form.get("area").strip()
    
        city = request.form.get("city")
    
        pincode= request.form.get("pincode")
    
        latitude = request.form.get("latitude")
    
        longitude = request.form.get("longitude")

        complaint_id = request.form.get("complaint_id")

        if not all([area, city, pincode, latitude, longitude, complaint_id]):
            flash('All fields are required', 'error')
            return redirect("/officer-dash")
        
        cursor = get_cursor()
        db = get_db()
        try:
            cursor.execute("SELECT latitude, longitude FROM complaints WHERE complaint_id = %s", (complaint_id,))
            complaint = cursor.fetchone()
        except:
            flash('Error fetching complaint data', 'error')
            return redirect("/officer-dash")
        
        if complaint is None:
            flash('Complaint not found', 'error')
            return redirect("/officer-dash")
        
        distance = haversine(float(complaint["latitude"]), float(complaint["longitude"]), float(latitude), float(longitude))

        if distance > 25:
            flash('You are too far from the complaint location', 'error')
            return redirect("/officer-dash")
        
        # Read file as bytes
        file_bytes = file.read()
        file.seek(0)

        # Get session data and form data
        session_data = dict(session)
        try:
            cursor.execute("SELECT email FROM users WHERE id = (SELECT user_id FROM complaints WHERE complaint_id = %s)", (complaint_id,))
            user = cursor.fetchone()
            if user:
                complaints = {
                    "email": user["email"]
                }
        except:
            complaints = None


        complaints["id"] = complaint_id

        
        # cursor.execute("UPDATE complaints SET status = 'completed' WHERE complaint_id = %s", (complaint_id,))
        # db.commit()
        # if file:
        #     filename = secure_filename(file.filename)

        #     s3_url = upload_image(file.stream, filename)
        
        # if s3_url and "Error" not in s3_url and "File not found" not in s3_url:
        #     s3_url = s3_url
        # else:
        #     flash('Error uploading image to S3', 'error')
        #     return redirect("/officer-dash")
        
        # Insert resolved complaint into the database
        # try:
        #     cursor.execute("UPDATE complaints SET cleanup_image_id = %s WHERE complaint_id = %s", (s3_url, complaint_id))
        #     db.commit() 
        # except Error as e:
        #     flash(f"Error inserting resolved complaint: {str(e)}", 'error')
        #     return redirect("/officer-dash")
        
        
        

        threading.Thread(
            target=process_completed_complaints,
            args=(current_app._get_current_object(), file_bytes, file.filename, file.mimetype, session_data, complaints),
            daemon=True
        ).start()

        flash("Complaint is being processed. You will be notified once it is completed.", "info")
        return redirect("/officer-dash")





        # # Send SMS notification to user
        # sms = boto3.client("sns",
        #                    region_name = AWS_REGION, 
        #                    aws_access_key_id = AWS_ACCESS_KEY, 
        #                    aws_secret_access_key = AWS_SECRET_KEY)
        # sms.publish(
        # PhoneNumber="+919866510983",  # Replace with actual number
        # Message="Your complaint has been completed successfully.\nDescription: {description}",
        # )

        # sms.publish(
        # PhoneNumber="+919676394804",  # Replace with actual officer number
        # Message="🚨 Complaint has been completed successfully. Please check the dashboard for details.\nDescription: {description}",
        # )

        # # Send email notification 
        # try:
        #     msg = MIMEMultipart()
        #     msg['From'] = SENDER_EMAIL
        #     msg['To'] = complaints["email"]  # Assuming username is the email
        #     msg['Subject'] = 'Garbage Complaint Completed'
        #     body = f"Your complaint has been completed successfully.\n\nDetails:\nArea: {area}\nCity: {city}\nPincode: {pincode}\nLatitude: {latitude}\nLongitude: {longitude}\n\nThank you for helping us keep the environment clean!"
        #     msg.attach(MIMEText(body, 'plain'))

        #     with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        #         server.login(SENDER_EMAIL, SENDER_PASSWORD)
        #         server.sendmail(SENDER_EMAIL, complaints["email"], msg.as_string())
            
        # except Exception as e:
        #     flash(f"Error sending email: {str(e)}", 'error')

        # try:
        #     msg_officer = MIMEMultipart()
        #     msg_officer['From'] = SENDER_EMAIL
        #     msg_officer['To'] = session.get("email")  # Assuming officer has an email field
        #     msg_officer['Subject'] = 'Garbage Complaint Completed'
        #     body_officer = f"A garbage complaint has been completed successfully.\n\nDetails:\nArea: {area}\nCity: {city}\nPincode: {pincode}\nLatitude: {latitude}\nLongitude: {longitude}\n\nPlease check the dashboard for more details."
        #     msg_officer.attach(MIMEText(body_officer, 'plain'))

        #     with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        #         server.login(SENDER_EMAIL, SENDER_PASSWORD)
        #         server.sendmail(SENDER_EMAIL, session.get("email"), msg_officer.as_string())

        # except Exception as e:
        #     flash(f"Error sending email to officer: {str(e)}", 'error')
        
        # flash('Complaint completed successfully', 'success')

    else:
        complaint_id = request.args.get("id")  # Get complaint_id from URL
        if complaint_id:
            return render_template("complete.html", complaint_id=complaint_id)
        else:
            return render_template("complete.html")
    

if __name__ == "__main__":
    # Run the application
    app.run(debug=True, use_reloader=False)