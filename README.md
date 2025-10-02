# Smart Link — Waste Management Alert System

## 📌 Overview
**Smart Link** is an intelligent waste management and civic monitoring system that empowers **citizens** to report garbage issues and helps **municipal officers** resolve them faster and more reliably.  

The system integrates **Flask**, **YOLOv8**, and multiple **AWS services** to provide a seamless workflow:
- Citizens report issues with images + auto-location detection.
- YOLOv8 verifies trash presence in uploaded photos.
- Officers receive complaints on a dashboard, can navigate to sites, and validate cleanup.
- Notifications (SMS & Email) keep citizens updated at each stage.

---

## 💡 Motivation
India’s rapidly urbanizing cities face challenges in civic cleanliness. Traditional reporting systems are inefficient and lack verification. Citizens often report, but:
- Officers cannot validate on-site visits.
- No real feedback loop exists for citizens.
- Complaints are unstructured and prone to delays.

**Smart Link** solves these by introducing:
- **AI-powered trash detection (YOLOv8)**.
- **Location verification (AWS Location Service + GPS)**.
- **Automated notifications (AWS SNS)**.
- **Gamified officer dashboard** for accountability.

---

## ✨ Key Features
### 🔹 Citizen Complaint System
- Submit complaints with photo evidence.  
- System automatically detects **area, city, pincode, latitude, longitude**.  
- YOLOv8 verifies presence of garbage before registering complaint.  

### 🔹 Officer Dashboard
- Officers view complaints with ID, location, and images.  
- Google Maps integration for directions.  
- Verify post-cleanup images → YOLOv8 double-checks cleanliness.  
- Officer’s **GPS location** verified to ensure they were physically present at the site.  

### 🔹 Automatic Garbage Detection
- CCTV cameras feed directly into YOLOv8.  
- If garbage is detected, auto-complaints are filed to authorities.  

### 🔹 Notifications
- Citizens receive SMS + Email when complaints are **submitted** and **resolved**.  
- Powered by **AWS SNS** for scalable notifications.  

### 🔹 AWS Cloud Integration
- **Elastic Beanstalk** → Backend deployment.  
- **S3** → Complaint image storage.  
- **SageMaker** → YOLOv8 hosting (optional for scalability).  
- **RDS** → Complaint database.  
- **Location Service** → GPS-based officer validation.  

---

## 📜 License
MIT License © 2025 Team Smart Link


## 📜 License
This project is licensed under the [MIT License](LICENSE).

