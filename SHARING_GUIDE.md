# 🏢 Sharing EDI Validator with Office Colleagues

## Quick Setup Guide for Colleagues

### **Method 1: Share on Office Network** (Recommended for Live Demo)

#### **You (Host):**

1. **Start network server**: Double-click `START_SERVER_NETWORK.bat`
2. **Share your IP**: Tell colleagues to use `http://192.168.1.4:8000`

#### **Your Colleagues:**

1. **Get the HTML file** from:
   - Download from: https://github.com/prajaktawanjari/EDI-Validator
   - Or you can email them the `index.html` file directly

2. **Open** `index.html` in any browser (Chrome, Edge, Firefox)

3. **Configure API URL**:
   - Click ⚙️ **"API Settings"** at the top
   - Change URL from `http://127.0.0.1:8000` to `http://192.168.1.4:8000`
   - Close the settings

4. **Start validating!**
   - Paste EDI message
   - Click **Validate**
   - See errors highlighted with suggestions

---

### **Method 2: GitHub Repository** (Best for Developers)

**Share this link**: https://github.com/prajaktawanjari/EDI-Validator

#### **They need to:**

1. **Download the code**:
   ```bash
   git clone https://github.com/prajaktawanjari/EDI-Validator.git
   cd EDI-Validator
   ```

2. **Install Python dependencies**:
   ```bash
   pip install fastapi uvicorn[standard]
   ```

3. **Start server**:
   ```bash
   # Windows:
   START_SERVER.bat
   
   # Or manually:
   python -m uvicorn api:app --reload --port 8000
   ```

4. **Open validator**:
   - Double-click `index.html`
   - Or visit: `file:///path/to/index.html`

---

### **Method 3: Send ZIP File** (No Git Required)

1. **Create a shareable package**:
   - Go to: https://github.com/prajaktawanjari/EDI-Validator
   - Click green **"Code"** button
   - Click **"Download ZIP"**

2. **Share the ZIP** via:
   - Email
   - Shared network drive
   - Teams/Slack
   - USB drive

3. **Recipients unzip and follow Method 2 steps**

---

## 📋 Requirements for Others

### **To just use the HTML interface:**
- Any modern web browser (Chrome, Edge, Firefox)
- Internet connection to view live on your network

### **To run their own server:**
- Python 3.8+ installed
- `pip install fastapi uvicorn[standard]`
- Clone or download the repository

---

## 🎯 Quick Demo Script

When showing to colleagues:

1. **Open the validator** (already configured to your network IP)

2. **Show a failing example**:
   ```
   UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+999+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'
   ```
   - Click **Validate**
   - Show red-bordered error segments
   - Point out the 💡 suggestion boxes

3. **Fix the errors** and show it passing:
   ```
   UNB+UNOC:3+SENDER:ZZZ+RECEIVER:ZZZ+260408:1200+REF123'UNH+1+IFTMIN:D:04A:UN:BIG14'BGM+610+ORD001+9'DTM+137:20260408:102'NAD+CZ+9SENDER:::91'NAD+CN+9CONSIGNEE:::91'GID+1+7:PK'CNT+7:10:KGM'UNT+8+1'UNZ+1+REF123'
   ```
   - Click **Validate**
   - Show ✅ "Validation passed"

4. **Demonstrate Format button** (splits segments into lines)

---

## 🌐 Network Access Setup

### **Your Computer (Server):**

1. Run: `START_SERVER_NETWORK.bat`
2. Your IP: `192.168.1.4`
3. API accessible at: `http://192.168.1.4:8000`

### **Firewall Settings** (if colleagues can't connect):

**Windows Firewall:**
```powershell
# Run in PowerShell as Administrator:
New-NetFirewallRule -DisplayName "EDI Validator API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**Or manually:**
1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Click "Inbound Rules" → "New Rule"
4. Choose "Port" → Next
5. Enter port `8000` → Next
6. Allow the connection → Finish

---

## 📊 Features to Highlight

✅ **11 Business Rules** - UNH, UNT, UNZ, BGM, DTM, NAD, TOD→FP, GDS→DGS, DGS validation  
✅ **Error Highlighting** - Red borders around segments with errors  
✅ **Smart Suggestions** - 💡 boxes with fix recommendations  
✅ **Syntax Coloring** - Color-coded segment tags  
✅ **Format Helper** - One-click segment formatting  
✅ **Strict Interchange Validation** - UNB/UNZ reference matching  

---

## 🆘 Troubleshooting

### **"Failed to connect to API"**

1. Check server is running (`START_SERVER_NETWORK.bat`)
2. Verify API URL in ⚙️ settings matches server IP
3. Check firewall allows port 8000
4. Make sure you're on the same network

### **"No response from server"**

- Check Windows Firewall settings
- Confirm your IP hasn't changed: `ipconfig`
- Try `http://localhost:8000` if testing on same computer

### **"CORS error"**

- Already handled! CORS is enabled in `api.py`
- If issues persist, restart the server

---

## 📧 Sharing Quick Links

**Email template:**

```
Subject: EDI Validator - IFTMIN Validation Tool

Hi Team,

I've built an EDI Validator for UN/EDIFACT IFTMIN messages.

🌐 Live Demo (on my computer):
   - Download: https://github.com/prajaktawanjari/EDI-Validator/archive/refs/heads/main.zip
   - Open index.html in browser
   - Set API URL to: http://192.168.1.4:8000

📦 Full Code:
   GitHub: https://github.com/prajaktawanjari/EDI-Validator

✨ Features:
   - Real-time validation with error highlighting
   - Smart suggestions for fixes
   - 11 business rules enforced
   - Syntax highlighting and auto-formatting

Let me know if you have questions!
```

---

## 🚀 For Presentations

1. **Keep server running** during demo
2. **Pre-load test messages** in separate browser tabs
3. **Show both failing and passing examples**
4. **Highlight the error visualization** (red borders)
5. **Demo the Format button** for readability

---

## 💾 Backup Options

If network fails, you can:
- Run demo on your laptop (localhost)
- Share screen via Teams/Zoom
- Record a video walkthrough
- Email the ZIP with instructions

