# Smart Expense Tracker (Android & Desktop)

A 100% Python-powered personal finance and expense tracking Android application. Designed specifically for Indian payment ecosystems (UPI, Credit Cards, Debit Cards, Net Banking) as well as cash transactions.

---

## 🌟 Key Features

1. **Automatic SMS Expense Extraction & Full Historical Scan**:
   - Auto-scans incoming bank alerts and transaction SMS messages.
   - **Scan All Existing SMS**: A single button scans your phone's entire historical SMS inbox to import months of past UPI, card, and bank expenses.
   - Supports **HDFC, SBI, ICICI, Axis, Kotak, PNB, Paytm, PhonePe, Google Pay, CRED, Amazon Pay**, and more.
   - Parses the transaction amount near debit/credit action text (rather than a later balance), plus **Merchant / Payee**, **Payment Mode** (UPI vs Card), **Account / Card Number**, and **Timestamp**.
   - Runs inbox scans in the background so importing older SMS history does not freeze the interface.
   - Filters out non-transactional messages (OTPs, promo alerts, security notices).
   - **Smart Deduplication**: Uses deterministic SHA-256 hashes to ensure identical SMS alerts are never added twice.

2. **Domestic Staff & Salary Tracker (Cook, House Helper, etc.)**:
   - Track monthly agreed salary, advance payments, and remaining dues for:
     - 👩‍🍳 **Cook**
     - 🧹 **House Helper / Maid**
     - 🚗 Any additional staff (Driver, Gardener)
   - Record salary or advance payments via **Cash, UPI, or Bank Transfer**.
   - Automatically syncs staff payments to your main monthly expense overview.

3. **Dual Milkmen Tracker (Daily Quantity & Bill Calculator)**:
   - Dedicated tracking for **Sundar** and **Jain Mandir** (with configurable rates e.g. ₹60/L and ₹70/L).
   - **1-Click Daily Entry**: Quick buttons to log today's delivery (e.g. `+1.5 L Today` for Sundar, `+1.0 L Today` for Jain Mandir, or custom quantity).
   - **Auto Bill Calculation**: Automatically calculates `Total Liters * Rate = Monthly Bill`.
   - **Payment & Balance Tracking**: Log payments made to Sundar or Jain Mandir and track pending dues.

4. **Intelligent Auto-Categorization**:
   - Automatically classifies expenses into:
     - 🍔 **Food & Dining** (Swiggy, Zomato, McDonald's, Starbucks, Cafes)
     - 🛒 **Groceries & Milk** (Milkmen, Blinkit, Zepto, BigBasket, Instamart, DMart, Kirana)
     - 🛍️ **Shopping** (Amazon, Flipkart, Myntra, Zara, Croma)
     - 🚗 **Travel & Commute** (Uber, Ola, Rapido, Metro, Petrol/Fuel, Shell, IRCTC)
     - ⚡ **Bills & Utilities** (Electricity, Jio, Airtel, Gas, Water, Broadband)
     - 🎬 **Entertainment & OTT** (Netflix, Spotify, BookMyShow, Prime Video)
     - 💊 **Health & Medical** (Apollo, 1mg, Pharmacies, Clinics)
     - 👥 **Transfers & Household Help** (Cook, House Helper, Rent, Maid)
     - 📈 **Investments** (Zerodha, Groww, AngelOne, Mutual Funds, SIP)
     - 💵 **Cash / Others**

5. **Hybrid Logging (Cash & Manual Payments)**:
   - Quick **`+` (Floating Action Button)** to record cash expenses (chai, local vendors, tips, personal loans).
   - Full control to edit, delete, or re-categorize any transaction.

6. **Monthly Budgets & Analytics**:
   - Set monthly spending budgets with real-time visual progress bars.
   - Category-wise spending breakdown with percentages.
   - Payment method distribution (UPI vs Credit Card vs Cash).

7. **100% Private & Offline**:
   - Stores all financial data locally on your device in `expenses.db` (SQLite).
   - Zero telemetry, no third-party cloud data selling.

---

## 📁 Project Structure

```
ExpenseTracker/
├── main.py                     # Main KivyMD Android application
├── web_preview.py              # Instant mobile-friendly web dashboard (zero-dependency)
├── buildozer.spec              # Buildozer configuration to build Android APK
├── requirements.txt            # Python dependencies (Kivy, KivyMD, PyJNIus)
├── expenses.db                 # Local SQLite database (auto-created)
├── .github/
│   └── workflows/
│       └── build-apk.yml       # 1-Click automated GitHub Actions APK builder
├── src/
│   ├── database/
│   │   └── db_manager.py       # SQLite transactions, budgets & analytics
│   ├── parsers/
│   │   ├── sms_parser.py       # Bank & UPI SMS regex extraction engine
│   │   └── categorizer.py      # Keyword and merchant category mapper
│   ├── services/
│   │   └── sms_service.py      # Android PyJNIus SMS reader + Desktop fallback
│   └── ui/
│       └── kv_layout.py        # KivyMD Material Design interface
└── tests/
    ├── test_parser.py          # Unit tests verifying bank SMS parsing
    └── sample_sms.json         # Dataset of realistic bank SMS messages
```

---

## 🚀 How to Run & Test

### Option 1: Mobile Web App (PWA) & Free Cloud Hosting (Recommended)

The app comes with a zero-dependency, responsive Web App and Progressive Web App (PWA) that you can access from your phone or laptop browser and even **install to your home screen** as an app:

#### A. Free Cloud Hosting on Render.com (100% Free Forever):
1. Create a free account at [Render.com](https://render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository (`ExpenseTracker`).
4. Set:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements-web.txt` (Instant build)
   - **Start Command**: `python web_preview.py`
   - **Instance Type**: `Free`
5. Click **Create Web Service**. Within 60 seconds, you get a live public HTTPS link (e.g. `https://my-expenses.onrender.com`).
6. **Install on Phone**: Open the link on your phone in Chrome or Safari, tap the three dots (or Share button) -> tap **"Add to Home screen"** / **"Install app"**. It will appear on your phone like a native app!
7. **Backup & Restore**: Use the **Backup** button in the top bar to download a 1-click `.json` backup of your data anytime, or restore it onto another device.

#### B. Run Locally or on Home Wi-Fi:
```bash
python web_preview.py
```
- Open **`http://localhost:5000`** on your computer.
- To open it on your phone: connect your phone to the same Wi-Fi network and open `http://<YOUR_PC_IP>:5000`.

---

### Option 2: Desktop KivyMD GUI

If you want to run the native desktop Kivy interface:

```bash
pip install -r requirements.txt
python main.py
```

---

### Option 3: Run Unit Tests

Verify that all bank SMS formats and OTP exclusions work properly:

```bash
python tests/test_parser.py
```

---

## 📱 How to Build the Android APK

### Method A: 1-Click Automated Cloud Build (Recommended for Windows)

Since Android NDK builds require a Linux environment, you can use the included GitHub Actions workflow to build the APK completely free without installing anything on your PC:

1. Push this folder to a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Expense Tracker"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
2. Open your repository on GitHub and click the **Actions** tab.
3. The **"Build Android APK with Buildozer"** workflow will automatically run.
4. When finished (usually 5–8 minutes), download the **`SmartExpenseTracker-Debug-APK`** artifact, transfer it to your Android phone, and install!

---

### Method B: Local Build via WSL / Ubuntu Linux

If you have WSL2 (Ubuntu) or a Linux machine:

```bash
# 1. Install prerequisites
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev cython3

# 2. Install Buildozer
pip install --upgrade buildozer

# 3. Build debug APK
buildozer android debug

# 4. The resulting APK will be saved in bin/
```

Transfer the `.apk` file from `bin/` to your Android phone via USB or Google Drive and install.

---

## 🔒 Android Permissions

When running on your phone, the app requests:
- **`READ_SMS` / `RECEIVE_SMS`**: To read bank transaction alerts and extract amount, merchant, and payment mode automatically.
- **`INTERNET`**: Used only for loading Material Design icon fonts (all expense data remains strictly offline in local SQLite).
