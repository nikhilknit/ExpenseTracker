import os
import sys
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.database.db_manager import DatabaseManager
from src.parsers.sms_parser import SMSParser
from src.parsers.categorizer import CATEGORY_METADATA, get_category_icon, get_category_color
from src.services.sms_service import SMSService

db = DatabaseManager()
sms_service = SMSService(db)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Smart Expense & Household Tracker</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: '#4f46e5',
            brandDark: '#3730a3',
          }
        }
      }
    }
  </script>
</head>
<body class="bg-slate-100 text-slate-800 font-sans pb-28">

  <!-- Top App Bar -->
  <header class="bg-indigo-600 text-white sticky top-0 z-30 shadow-md">
    <div class="max-w-md mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center space-x-2">
        <i class="fa-solid fa-wallet text-xl"></i>
        <h1 class="text-lg font-bold tracking-tight">Expense Tracker</h1>
      </div>
      <div class="flex items-center space-x-1.5">
        <button onclick="syncSMS(false)" title="Quick SMS Sync" class="bg-indigo-700 hover:bg-indigo-800 text-white text-xs px-2.5 py-1.5 rounded-lg flex items-center space-x-1 shadow transition">
          <i class="fa-solid fa-rotate text-[11px]"></i>
          <span>Sync</span>
        </button>
        <button onclick="syncSMS(true)" title="Scan All Existing SMS in Phone" class="bg-indigo-500 hover:bg-indigo-400 text-white text-xs px-2.5 py-1.5 rounded-lg flex items-center space-x-1 shadow transition">
          <i class="fa-solid fa-clock-rotate-left text-[11px]"></i>
          <span>Scan All SMS</span>
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-md mx-auto px-4 pt-3 space-y-4">

    <!-- Total Spend Hero Card -->
    <div class="bg-gradient-to-br from-indigo-600 to-violet-700 text-white rounded-2xl p-5 shadow-lg relative overflow-hidden">
      <div class="relative z-10">
        <div class="text-xs uppercase tracking-wider text-indigo-200 font-medium">Spent This Month</div>
        <div class="text-3xl font-extrabold mt-1 tracking-tight" id="lbl-total">₹ 0.00</div>
        
        <div class="mt-4 pt-3 border-t border-indigo-400/30 flex justify-between text-xs text-indigo-100">
          <div>Today: <span class="font-bold text-white" id="lbl-today">₹ 0.00</span></div>
          <div>This Week: <span class="font-bold text-white" id="lbl-week">₹ 0.00</span></div>
        </div>
      </div>
    </div>

    <!-- Monthly Budget Card -->
    <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200">
      <div class="flex items-center justify-between mb-2">
        <div class="text-xs font-semibold text-slate-500 uppercase tracking-wide">Monthly Budget</div>
        <button onclick="openBudgetModal()" class="text-indigo-600 hover:text-indigo-800 text-xs font-medium flex items-center space-x-1">
          <i class="fa-solid fa-pen text-[10px]"></i>
          <span>Edit</span>
        </button>
      </div>
      <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
        <div id="budget-progress" class="bg-indigo-600 h-2.5 rounded-full transition-all duration-500" style="width: 0%"></div>
      </div>
      <div class="flex justify-between text-xs mt-2 text-slate-600">
        <span id="lbl-budget-desc">No budget set</span>
        <span id="lbl-budget-rem" class="font-semibold text-slate-700"></span>
      </div>
    </div>

    <!-- Quick Tab Selector (5 Tabs) -->
    <div class="grid grid-cols-5 gap-1 bg-slate-200/90 p-1 rounded-xl text-[11px] font-semibold text-slate-600">
      <button onclick="switchView('recent')" id="tab-recent" class="py-2 rounded-lg bg-white text-indigo-600 shadow-sm text-center">Spends</button>
      <button onclick="switchView('staff')" id="tab-staff" class="py-2 rounded-lg text-center">Cook & Help</button>
      <button onclick="switchView('milk')" id="tab-milk" class="py-2 rounded-lg text-center">Milkmen</button>
      <button onclick="switchView('analytics')" id="tab-analytics" class="py-2 rounded-lg text-center">Analytics</button>
      <button onclick="switchView('sms')" id="tab-sms" class="py-2 rounded-lg text-center">SMS Scan</button>
    </div>

    <!-- ==================== VIEW 1: TRANSACTIONS LIST ==================== -->
    <div id="view-recent" class="space-y-3">
      <div class="flex space-x-2">
        <div class="relative flex-1">
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
          <input type="text" id="search-input" oninput="loadTransactions()" placeholder="Search merchant, notes, UPI..." class="w-full pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500">
        </div>
        <select id="filter-category" onchange="loadTransactions()" class="bg-white border border-slate-200 rounded-xl text-xs px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-600">
          <option value="All">All Spends</option>
          <option value="Food & Dining">Food & Dining</option>
          <option value="Groceries">Groceries</option>
          <option value="Shopping">Shopping</option>
          <option value="Travel & Commute">Travel & Commute</option>
          <option value="Bills & Utilities">Bills & Utilities</option>
          <option value="Entertainment">Entertainment</option>
          <option value="Health & Medical">Health & Medical</option>
          <option value="Transfers & Rent">Transfers & Rent</option>
          <option value="Others">Others</option>
        </select>
      </div>

      <div id="txn-list" class="space-y-2">
        <!-- Rendered via JS -->
      </div>
    </div>

    <!-- ==================== VIEW 2: COOK & HOUSE HELPER ==================== -->
    <div id="view-staff" class="hidden space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-sm font-bold text-slate-800">Cook & House Help Salaries</h2>
          <p class="text-xs text-slate-500">Manage salary, previous dues, advances & balance</p>
        </div>
        <button onclick="openStaffModal()" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-2.5 py-1 rounded-lg flex items-center space-x-1 shadow">
          <i class="fa-solid fa-plus text-[10px]"></i>
          <span>Add Staff</span>
        </button>
      </div>

      <!-- Staff Cards Container -->
      <div id="staff-cards" class="space-y-3">
        <!-- Rendered via JS -->
      </div>

      <!-- Staff Past Payments Log -->
      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200">
        <h3 class="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Staff Payment History</h3>
        <div id="staff-history-list" class="space-y-2 text-xs">
          <!-- Rendered via JS -->
        </div>
      </div>
    </div>

    <!-- ==================== VIEW 3: DUAL MILKMEN TRACKER ==================== -->
    <div id="view-milk" class="hidden space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-sm font-bold text-slate-800">Sundar & Jain Mandir Milk Tracker</h2>
          <p class="text-xs text-slate-500">Set price per liter, previous dues, daily milk & payments</p>
        </div>
        <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800" id="lbl-milk-month"></span>
      </div>

      <!-- 2 Milkmen Summary Cards -->
      <div id="milk-vendors-container" class="space-y-3">
        <!-- Rendered via JS -->
      </div>

      <!-- Milk Daily Delivery History -->
      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-xs font-bold text-slate-700 uppercase tracking-wider">Daily Milk Delivery Logs</h3>
          <select id="sel-milk-history-vendor" onchange="loadMilkDeliveries()" class="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white">
            <!-- Options populated dynamically -->
          </select>
        </div>
        <div id="milk-daily-list" class="space-y-2 text-xs max-h-60 overflow-y-auto">
          <!-- Rendered via JS -->
        </div>
      </div>
    </div>

    <!-- ==================== VIEW 4: ANALYTICS ==================== -->
    <div id="view-analytics" class="hidden space-y-4">
      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200">
        <h3 class="text-sm font-bold text-slate-800 mb-3 flex items-center space-x-2">
          <i class="fa-solid fa-chart-pie text-indigo-500"></i>
          <span>Category Breakdown</span>
        </h3>
        <div id="category-bars" class="space-y-3">
          <!-- Rendered via JS -->
        </div>
      </div>

      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200">
        <h3 class="text-sm font-bold text-slate-800 mb-3 flex items-center space-x-2">
          <i class="fa-solid fa-credit-card text-emerald-500"></i>
          <span>Payment Methods</span>
        </h3>
        <div id="mode-bars" class="space-y-2">
          <!-- Rendered via JS -->
        </div>
      </div>
    </div>

    <!-- ==================== VIEW 5: SMS SCANNER & HISTORICAL ==================== -->
    <div id="view-sms" class="hidden space-y-3">
      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200 space-y-3">
        <h3 class="text-sm font-bold text-slate-800 flex items-center space-x-2">
          <i class="fa-solid fa-mobile-screen text-indigo-500"></i>
          <span>Scan Existing Phone SMS</span>
        </h3>
        <p class="text-xs text-slate-500">
          Scan all bank, UPI (Google Pay, PhonePe, Paytm), and Credit Card SMS alerts stored in your phone. Old messages are parsed, categorized, and deduplicated automatically.
        </p>

        <div class="grid grid-cols-2 gap-2 pt-1">
          <button onclick="syncSMS(false)" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-2.5 rounded-xl shadow transition text-center">
            <i class="fa-solid fa-rotate mr-1"></i> Quick Sync (150 SMS)
          </button>
          <button onclick="syncSMS(true)" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold py-2.5 rounded-xl shadow transition text-center">
            <i class="fa-solid fa-clock-rotate-left mr-1"></i> Full Historical Scan
          </button>
        </div>

        <div id="sync-status-box" class="hidden p-3 rounded-xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-900 space-y-1">
          <!-- Status shown here -->
        </div>
      </div>

      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200 space-y-3">
        <h3 class="text-sm font-bold text-slate-800 flex items-center space-x-2">
          <i class="fa-solid fa-paste text-indigo-500"></i>
          <span>Test / Paste Custom Bank SMS</span>
        </h3>
        <textarea id="custom-sms-text" rows="3" class="w-full text-xs p-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="e.g. Alert: Rs. 450.00 debited from HDFC Bank A/C ending 1234 to VPA swiggy@icici on 11-Nov-26 via UPI."></textarea>
        <button onclick="parseCustomSMS()" class="w-full bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold py-2 rounded-xl transition shadow">
          Parse & Record Expense
        </button>
        <div id="sms-parse-result" class="text-xs p-3 rounded-xl bg-slate-50 text-slate-700 hidden"></div>
      </div>
    </div>

  </main>

  <!-- Floating Add Expense Button -->
  <button onclick="openAddModal()" title="Add Cash Expense" class="fixed bottom-6 right-6 w-14 h-14 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full shadow-2xl flex items-center justify-center text-xl transition transform active:scale-95 z-40">
    <i class="fa-solid fa-plus"></i>
  </button>

  <!-- ==================== MODALS ==================== -->

  <!-- Modal: Edit Staff (Salary & Previous Dues) -->
  <div id="staff-edit-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800" id="staff-edit-title">Edit Salary & Dues</h2>
        <button onclick="closeStaffEditModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <input type="hidden" id="edit-staff-id">
      <div>
        <label class="text-xs font-medium text-slate-600">Monthly Salary (₹) *</label>
        <input type="number" id="edit-staff-salary" step="100" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Previous Pending Dues (₹)</label>
        <input type="number" id="edit-staff-dues" step="50" placeholder="0.00" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
        <p class="text-[10px] text-slate-400 mt-0.5">Unpaid backlog from past months before using the app.</p>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Phone Number (Optional)</label>
        <input type="tel" id="edit-staff-phone" placeholder="e.g. 9876543210" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <button onclick="submitStaffUpdate()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Save Salary & Dues
      </button>
    </div>
  </div>

  <!-- Modal: Edit Milk Vendor (Price per Liter & Previous Dues) -->
  <div id="milk-edit-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800" id="milk-edit-title">Edit Price per Liter & Dues</h2>
        <button onclick="closeMilkEditModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <input type="hidden" id="edit-milk-vendor-id">
      <div>
        <label class="text-xs font-medium text-slate-600">Price per Liter (₹) *</label>
        <input type="number" step="1" id="edit-milk-rate" class="w-full text-lg font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Previous Pending Dues (₹)</label>
        <input type="number" step="50" id="edit-milk-dues" placeholder="0.00" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
        <p class="text-[10px] text-slate-400 mt-0.5">Unpaid milk bill from previous months.</p>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Default Daily Quantity (Liters)</label>
        <input type="number" step="0.25" id="edit-milk-default-qty" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <button onclick="submitMilkUpdate()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Save Price & Dues
      </button>
    </div>
  </div>

  <!-- Modal: Pay Staff (Cook / Helper) -->
  <div id="staff-pay-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800" id="staff-pay-title">Record Staff Payment</h2>
        <button onclick="closeStaffPayModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <input type="hidden" id="pay-staff-id">
      <div>
        <label class="text-xs font-medium text-slate-600">Amount (₹) *</label>
        <input type="number" id="pay-staff-amount" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="text-xs font-medium text-slate-600">Type</label>
          <select id="pay-staff-type" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white mt-1">
            <option value="Salary">Salary</option>
            <option value="Advance">Advance</option>
            <option value="Bonus">Bonus</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600">Payment Mode</label>
          <select id="pay-staff-mode" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white mt-1">
            <option value="Cash">Cash</option>
            <option value="UPI">UPI</option>
            <option value="Bank Transfer">Bank Transfer</option>
          </select>
        </div>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Notes</label>
        <input type="text" id="pay-staff-notes" placeholder="e.g. October Salary" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <button onclick="submitStaffPayment()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Record Payment
      </button>
    </div>
  </div>

  <!-- Modal: Log Daily Milk Delivery -->
  <div id="milk-delivery-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800" id="milk-modal-title">Record Milk Delivery</h2>
        <button onclick="closeMilkDeliveryModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <input type="hidden" id="milk-del-vendor-id">
      <div>
        <label class="text-xs font-medium text-slate-600">Date</label>
        <input type="date" id="milk-del-date" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Quantity (Liters) *</label>
        <input type="number" step="0.25" id="milk-del-qty" class="w-full text-lg font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Notes (Optional)</label>
        <input type="text" id="milk-del-notes" placeholder="e.g. Extra 0.5L for guests" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <button onclick="submitMilkDelivery()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Save Delivery Entry
      </button>
    </div>
  </div>

  <!-- Modal: Pay Milkman -->
  <div id="milk-pay-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800" id="milk-pay-title">Pay Milkman</h2>
        <button onclick="closeMilkPayModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <input type="hidden" id="pay-milk-vendor-id">
      <div>
        <label class="text-xs font-medium text-slate-600">Amount Paid (₹) *</label>
        <input type="number" id="pay-milk-amount" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Payment Mode</label>
        <select id="pay-milk-mode" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white mt-1">
          <option value="UPI">UPI (GPay / PhonePe / Paytm)</option>
          <option value="Cash">Cash</option>
        </select>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Notes</label>
        <input type="text" id="pay-milk-notes" placeholder="e.g. Full settlement" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <button onclick="submitMilkPayment()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Record Payment
      </button>
    </div>
  </div>

  <!-- Modal: Budget Modal -->
  <div id="budget-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800">Set Monthly Budget</h2>
        <button onclick="closeBudgetModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Monthly Budget (₹)</label>
        <input type="number" id="budget-input" placeholder="e.g. 25000" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <button onclick="saveBudget()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl transition">
        Update Budget
      </button>
    </div>
  </div>

  <!-- Modal: Add New Staff -->
  <div id="staff-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800">Register Staff Member</h2>
        <button onclick="closeStaffModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Name *</label>
        <input type="text" id="new-staff-name" placeholder="e.g. Driver Ramesh" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Role</label>
        <select id="new-staff-role" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white mt-1">
          <option>Cook</option>
          <option>House Helper</option>
          <option>Driver</option>
          <option>Gardener</option>
          <option>Other</option>
        </select>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Monthly Salary (₹)</label>
        <input type="number" id="new-staff-salary" placeholder="e.g. 5000" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Previous Pending Dues (₹)</label>
        <input type="number" id="new-staff-dues" placeholder="0.00" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <button onclick="saveNewStaff()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Add Staff Member
      </button>
    </div>
  </div>

  <!-- Modal: Add Manual Expense -->
  <div id="add-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <h2 class="text-base font-bold text-slate-800">Log New Expense</h2>
        <button onclick="closeAddModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Amount (₹) *</label>
        <input type="number" step="1" id="new-amount" placeholder="e.g. 250" class="w-full text-base font-bold p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Merchant / Paid To *</label>
        <input type="text" id="new-merchant" placeholder="e.g. CultFit, Chai, Stationery" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-xs font-medium text-slate-600">Category</label>
        <select id="new-category" onchange="toggleCustomCategoryInput()" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white mt-1">
          <option value="Food & Dining">Food & Dining</option>
          <option value="Groceries">Groceries</option>
          <option value="Shopping">Shopping</option>
          <option value="Travel & Commute">Travel & Commute</option>
          <option value="Bills & Utilities">Bills & Utilities</option>
          <option value="Entertainment">Entertainment</option>
          <option value="Health & Medical">Health & Medical</option>
          <option value="Transfers & Rent">Transfers & Rent</option>
          <option value="__custom__">✨ Enter Custom Category...</option>
          <option value="Others">Others</option>
        </select>
        <div id="new-custom-category-box" class="hidden mt-2">
          <input type="text" id="new-custom-category" placeholder="Type custom category (e.g. Gym, Pet Care, Books)..." class="w-full text-xs p-2.5 border border-indigo-300 bg-indigo-50/50 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-medium text-indigo-900">
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="text-xs font-medium text-slate-600">Mode</label>
          <select id="new-mode" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white mt-1">
            <option value="Cash">Cash</option>
            <option value="UPI">UPI</option>
            <option value="Credit Card">Credit Card</option>
            <option value="Debit Card">Debit Card</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-600">Notes (Optional)</label>
          <input type="text" id="new-notes" placeholder="Notes" class="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
        </div>
      </div>
      <button onclick="saveExpense()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Record Expense
      </button>
    </div>
  </div>

  <!-- Modal: Set Custom Category for Transaction -->
  <div id="category-edit-modal" class="fixed inset-0 bg-black/50 z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-sm rounded-2xl p-5 space-y-4 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b">
        <div>
          <h2 class="text-base font-bold text-slate-800" id="cat-edit-title">Assign Category</h2>
          <p class="text-[11px] text-slate-500" id="cat-edit-subtitle"></p>
        </div>
        <button onclick="closeCategoryEditModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <input type="hidden" id="cat-edit-txn-id">
      <input type="hidden" id="cat-edit-merchant">
      <div>
        <label class="text-xs font-medium text-slate-600">Category Name *</label>
        <input type="text" id="cat-edit-input" placeholder="Type custom category (e.g. Gym, Pet Care, Books, Car)..." class="w-full text-sm font-semibold p-2.5 border border-indigo-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none mt-1">
      </div>
      <div>
        <label class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Quick Suggestions</label>
        <div class="flex flex-wrap gap-1.5 mt-1.5" id="cat-quick-pills"></div>
      </div>
      <div class="bg-indigo-50 p-2.5 rounded-xl border border-indigo-100 flex items-start space-x-2">
        <input type="checkbox" id="cat-remember-rule" checked class="mt-0.5 rounded text-indigo-600 focus:ring-indigo-500">
        <label for="cat-remember-rule" class="text-[11px] text-indigo-900 leading-tight">
          <strong>Auto-categorize future SMS:</strong> Remember this category whenever an SMS is detected from this merchant.
        </label>
      </div>
      <button onclick="submitCategoryUpdate()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow transition">
        Save & Apply Category
      </button>
    </div>
  </div>

  <!-- Notification Toast -->
  <div id="toast" class="fixed top-4 left-1/2 transform -translate-x-1/2 bg-slate-900 text-white px-4 py-2 rounded-xl text-xs font-medium shadow-2xl hidden z-50"></div>

  <script>
    const categoryIcons = {
      "Food & Dining": "fa-utensils text-orange-500",
      "Groceries": "fa-basket-shopping text-emerald-500",
      "Shopping": "fa-bag-shopping text-purple-500",
      "Travel & Commute": "fa-car text-blue-500",
      "Bills & Utilities": "fa-bolt text-amber-500",
      "Entertainment": "fa-film text-pink-500",
      "Health & Medical": "fa-heart-pulse text-teal-500",
      "Transfers & Rent": "fa-people-roof text-indigo-500",
      "Others": "fa-receipt text-slate-400"
    };

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.remove('hidden');
      setTimeout(() => t.classList.add('hidden'), 2500);
    }

    function switchView(view) {
      const views = ['recent', 'staff', 'milk', 'analytics', 'sms'];
      views.forEach(v => {
        document.getElementById(`view-${v}`).classList.add('hidden');
        document.getElementById(`tab-${v}`).className = "py-2 rounded-lg text-center transition";
      });

      document.getElementById(`view-${view}`).classList.remove('hidden');
      document.getElementById(`tab-${view}`).className = "py-2 rounded-lg bg-white text-indigo-600 shadow-sm text-center font-bold";

      if (view === 'staff') loadStaffData();
      if (view === 'milk') loadMilkData();
      if (view === 'analytics') loadAnalytics();
    }

    // ----------------- EXPENSES & STATS -----------------
    async function loadStats() {
      const res = await fetch('/api/stats');
      const data = await res.json();
      
      document.getElementById('lbl-total').textContent = `₹ ${data.total_debit.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      document.getElementById('lbl-today').textContent = `₹ ${data.today_debit.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      document.getElementById('lbl-week').textContent = `₹ ${data.week_debit.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;

      const prog = document.getElementById('budget-progress');
      const budgetDesc = document.getElementById('lbl-budget-desc');
      const budgetRem = document.getElementById('lbl-budget-rem');

      if (data.budget > 0) {
        prog.style.width = `${Math.min(100, data.budget_percentage)}%`;
        prog.className = data.budget_percentage > 90 ? "bg-rose-500 h-2.5 rounded-full" : "bg-indigo-600 h-2.5 rounded-full";
        budgetDesc.textContent = `₹${data.total_debit.toFixed(0)} of ₹${data.budget.toFixed(0)} (${data.budget_percentage.toFixed(0)}%)`;
        budgetRem.textContent = `₹${data.budget_remaining.toFixed(0)} left`;
      } else {
        prog.style.width = '0%';
        budgetDesc.textContent = 'No budget configured';
        budgetRem.textContent = '';
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function escapeJs(str) {
      if (!str) return '';
      return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    async function loadTransactions() {
      const query = document.getElementById('search-input').value;
      const category = document.getElementById('filter-category').value;
      const res = await fetch(`/api/transactions?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`);
      const txns = await res.json();

      const container = document.getElementById('txn-list');
      if (txns.length === 0) {
        container.innerHTML = `
          <div class="text-center py-8 text-slate-400 text-xs">
            <i class="fa-solid fa-receipt text-2xl mb-1"></i>
            <div>No transactions found</div>
          </div>
        `;
        return;
      }

      container.innerHTML = txns.map(t => {
        const isDebit = t.type === 'DEBIT';
        const sign = isDebit ? '-' : '+';
        const amtColor = isDebit ? 'text-slate-800' : 'text-emerald-600';
        const iconClass = categoryIcons[t.category] || "fa-tag text-indigo-500";
        const isOthers = (t.category === 'Others' || !t.category);
        const catBadge = isOthers 
          ? `<span onclick="event.stopPropagation(); openEditCategoryModal(${t.id}, '${escapeJs(t.merchant)}', '${escapeJs(t.category)}')" class="bg-amber-100 hover:bg-amber-200 text-amber-800 font-bold px-1.5 py-0.5 rounded text-[10px] cursor-pointer inline-flex items-center space-x-1" title="Click to assign custom category"><span>Others</span> <i class="fa-solid fa-pen text-[9px]"></i></span>`
          : `<span onclick="event.stopPropagation(); openEditCategoryModal(${t.id}, '${escapeJs(t.merchant)}', '${escapeJs(t.category)}')" class="cursor-pointer hover:underline text-slate-600" title="Click to change category">${escapeHtml(t.category)}</span>`;

        return `
          <div onclick="openEditCategoryModal(${t.id}, '${escapeJs(t.merchant)}', '${escapeJs(t.category)}')" class="bg-white rounded-xl p-3 shadow-sm border border-slate-100 flex items-center justify-between hover:border-indigo-300 hover:shadow-md transition cursor-pointer">
            <div class="flex items-center space-x-3">
              <div class="w-9 h-9 rounded-full bg-slate-50 flex items-center justify-center text-sm border border-slate-100">
                <i class="fa-solid ${iconClass}"></i>
              </div>
              <div>
                <div class="text-xs font-bold text-slate-800">${escapeHtml(t.merchant || 'Expense')}</div>
                <div class="text-[11px] text-slate-400 flex items-center space-x-1.5 mt-0.5">
                  <span class="bg-slate-100 px-1.5 py-0.2 rounded text-slate-600 font-medium">${t.payment_mode}</span>
                  <span>•</span>
                  ${catBadge}
                  <span>•</span>
                  <span>${t.date.slice(0, 10)}</span>
                </div>
              </div>
            </div>
            <div class="text-right">
              <div class="text-xs font-extrabold ${amtColor}">${sign} ₹${t.amount.toFixed(2)}</div>
              <button onclick="event.stopPropagation(); deleteTransaction(${t.id})" class="text-[10px] text-slate-300 hover:text-rose-500 mt-1 transition">
                <i class="fa-solid fa-trash"></i>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    // ----------------- COOK & HOUSE HELPER -----------------
    async function loadStaffData() {
      const res = await fetch('/api/staff/summary');
      const staffList = await res.json();
      const container = document.getElementById('staff-cards');

      container.innerHTML = staffList.map(s => {
        const roleIcon = s.role === 'Cook' ? 'fa-kitchen-set text-amber-500' : 'fa-broom text-blue-500';
        const isPaidFull = s.balance_due <= 0;
        const statusBadge = isPaidFull 
          ? '<span class="bg-emerald-100 text-emerald-800 text-[10px] px-2 py-0.5 rounded-full font-bold">Cleared</span>'
          : `<span class="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded-full font-bold">₹${s.balance_due.toFixed(0)} Pending</span>`;

        return `
          <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200 space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2.5">
                <div class="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-lg">
                  <i class="fa-solid ${roleIcon}"></i>
                </div>
                <div>
                  <div class="text-sm font-bold text-slate-800 flex items-center space-x-1.5">
                    <span>${s.name}</span>
                    <span class="text-xs font-normal text-slate-500">(${s.role})</span>
                    <button onclick="openEditStaffModal(${s.id}, '${s.name}', ${s.monthly_salary}, ${s.previous_dues}, '${s.phone || ''}')" class="text-slate-400 hover:text-indigo-600 text-xs ml-1" title="Edit Salary & Previous Dues">
                      <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                  </div>
                  <div class="text-[11px] text-slate-500 mt-0.5">
                    Salary: <span class="font-bold text-slate-700">₹${s.monthly_salary.toLocaleString('en-IN')}</span> 
                    ${s.previous_dues > 0 ? `• Prev Dues: <span class="font-bold text-rose-600">₹${s.previous_dues.toLocaleString('en-IN')}</span>` : ''}
                  </div>
                </div>
              </div>
              <div>${statusBadge}</div>
            </div>

            <div class="grid grid-cols-4 gap-1.5 bg-slate-50 p-2.5 rounded-xl text-center text-xs">
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Total Bill</div>
                <div class="font-bold text-slate-700 mt-0.5">₹${s.total_payable.toFixed(0)}</div>
              </div>
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Salary Paid</div>
                <div class="font-bold text-emerald-600 mt-0.5">₹${s.salary_paid.toFixed(0)}</div>
              </div>
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Advance</div>
                <div class="font-bold text-indigo-600 mt-0.5">₹${s.advance_paid.toFixed(0)}</div>
              </div>
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Remaining</div>
                <div class="font-bold ${s.balance_due > 0 ? 'text-rose-600' : 'text-slate-600'} mt-0.5">₹${s.balance_due.toFixed(0)}</div>
              </div>
            </div>

            <div class="flex space-x-2 pt-1">
              <button onclick="openStaffPayModal(${s.id}, '${s.name}', 'Salary', ${s.balance_due})" class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-2 rounded-xl transition shadow">
                <i class="fa-solid fa-money-check mr-1"></i> Pay Salary
              </button>
              <button onclick="openStaffPayModal(${s.id}, '${s.name}', 'Advance', 500)" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold py-2 rounded-xl transition">
                <i class="fa-solid fa-hand-holding-dollar mr-1"></i> Give Advance
              </button>
              <button onclick="openEditStaffModal(${s.id}, '${s.name}', ${s.monthly_salary}, ${s.previous_dues}, '${s.phone || ''}')" class="px-3 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold py-2 rounded-xl transition" title="Edit Salary & Dues">
                <i class="fa-solid fa-pen"></i>
              </button>
            </div>
          </div>
        `;
      }).join('');

      loadStaffHistory();
    }

    function openEditStaffModal(id, name, salary, dues, phone) {
      document.getElementById('edit-staff-id').value = id;
      document.getElementById('staff-edit-title').textContent = `Edit ${name} (Salary & Dues)`;
      document.getElementById('edit-staff-salary').value = salary;
      document.getElementById('edit-staff-dues').value = dues || 0;
      document.getElementById('edit-staff-phone').value = phone || '';
      document.getElementById('staff-edit-modal').classList.remove('hidden');
    }
    function closeStaffEditModal() { document.getElementById('staff-edit-modal').classList.add('hidden'); }

    async function submitStaffUpdate() {
      const staff_id = parseInt(document.getElementById('edit-staff-id').value);
      const monthly_salary = parseFloat(document.getElementById('edit-staff-salary').value);
      const previous_dues = parseFloat(document.getElementById('edit-staff-dues').value) || 0.0;
      const phone = document.getElementById('edit-staff-phone').value.trim();

      await fetch('/api/staff/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({staff_id, monthly_salary, previous_dues, phone})
      });

      closeStaffEditModal();
      showToast("Salary & Previous Dues updated!");
      loadStaffData();
    }

    async function loadStaffHistory() {
      const res = await fetch('/api/staff/history');
      const history = await res.json();
      const container = document.getElementById('staff-history-list');

      if (!history.length) {
        container.innerHTML = '<div class="text-slate-400 text-center py-2">No staff payments recorded yet.</div>';
        return;
      }

      container.innerHTML = history.slice(0, 8).map(h => `
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
          <div>
            <div class="font-bold text-slate-700">${h.staff_name} <span class="font-normal text-slate-400 text-[10px]">(${h.payment_type})</span></div>
            <div class="text-[10px] text-slate-400">${h.date} via ${h.payment_mode} ${h.notes ? '• ' + h.notes : ''}</div>
          </div>
          <div class="text-right">
            <div class="font-bold text-slate-800">₹${h.amount.toFixed(2)}</div>
            <button onclick="deleteStaffPayment(${h.id})" class="text-[10px] text-slate-300 hover:text-rose-500 transition">
              <i class="fa-solid fa-trash"></i>
            </button>
          </div>
        </div>
      `).join('');
    }

    function openStaffPayModal(staffId, staffName, defaultType, defaultAmt) {
      document.getElementById('pay-staff-id').value = staffId;
      document.getElementById('staff-pay-title').textContent = `Pay ${staffName}`;
      document.getElementById('pay-staff-type').value = defaultType;
      document.getElementById('pay-staff-amount').value = defaultAmt > 0 ? defaultAmt : '';
      document.getElementById('staff-pay-modal').classList.remove('hidden');
    }
    function closeStaffPayModal() { document.getElementById('staff-pay-modal').classList.add('hidden'); }

    async function submitStaffPayment() {
      const staff_id = parseInt(document.getElementById('pay-staff-id').value);
      const amount = parseFloat(document.getElementById('pay-staff-amount').value);
      const payment_type = document.getElementById('pay-staff-type').value;
      const payment_mode = document.getElementById('pay-staff-mode').value;
      const notes = document.getElementById('pay-staff-notes').value.trim();

      if (!amount || amount <= 0) {
        alert("Please enter a valid payment amount!");
        return;
      }

      await fetch('/api/staff/pay', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({staff_id, amount, payment_type, payment_mode, notes})
      });

      closeStaffPayModal();
      showToast("Payment recorded & synced to expenses!");
      loadStaffData();
      loadStats();
      loadTransactions();
    }

    async function deleteStaffPayment(id) {
      if (!confirm("Delete this payment record?")) return;
      await fetch(`/api/staff/delete-payment?id=${id}`, {method: 'POST'});
      showToast("Payment deleted");
      loadStaffData();
      loadStats();
    }

    // ----------------- DUAL MILKMEN TRACKER (SUNDAR & JAIN MANDIR) -----------------
    let cachedVendors = [];

    async function loadMilkData() {
      const res = await fetch('/api/milk/summary');
      cachedVendors = await res.json();
      const container = document.getElementById('milk-vendors-container');
      const monthLabel = document.getElementById('lbl-milk-month');

      if (cachedVendors.length > 0) {
        monthLabel.textContent = cachedVendors[0].month_year;
      }

      container.innerHTML = cachedVendors.map(v => {
        return `
          <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200 space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2.5">
                <div class="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center text-lg text-amber-600">
                  <i class="fa-solid fa-bottle-water"></i>
                </div>
                <div>
                  <div class="text-sm font-bold text-slate-800 flex items-center space-x-1.5">
                    <span>${v.name}</span>
                    <button onclick="openEditMilkVendorModal(${v.vendor_id}, '${v.name}', ${v.rate_per_liter}, ${v.previous_dues}, ${v.default_quantity})" class="text-slate-400 hover:text-indigo-600 text-xs ml-1" title="Edit Price per Liter & Dues">
                      <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                  </div>
                  <div class="text-[11px] text-slate-500 mt-0.5">
                    Rate: <span class="font-bold text-slate-800">₹${v.rate_per_liter}/L</span> • Default: ${v.default_quantity}L 
                    ${v.previous_dues > 0 ? `• Prev Dues: <span class="font-bold text-rose-600">₹${v.previous_dues}</span>` : ''}
                  </div>
                </div>
              </div>
              <div class="text-right">
                <span class="text-[11px] font-bold ${v.balance_due > 0 ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800'} px-2 py-0.5 rounded-full">
                  ₹${v.balance_due.toFixed(0)} Due
                </span>
              </div>
            </div>

            <div class="grid grid-cols-4 gap-1.5 bg-slate-50 p-2.5 rounded-xl text-center text-xs">
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Delivered</div>
                <div class="font-bold text-indigo-600 mt-0.5">${v.total_liters} L</div>
              </div>
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Delivery Cost</div>
                <div class="font-bold text-slate-700 mt-0.5">₹${v.total_bill.toFixed(0)}</div>
              </div>
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Total Bill</div>
                <div class="font-bold text-slate-800 mt-0.5">₹${v.total_payable.toFixed(0)}</div>
              </div>
              <div>
                <div class="text-[10px] text-slate-400 font-medium">Paid</div>
                <div class="font-bold text-emerald-600 mt-0.5">₹${v.total_paid.toFixed(0)}</div>
              </div>
            </div>

            <!-- Quick Action Buttons -->
            <div class="flex space-x-2 pt-1">
              <button onclick="quickLogMilk(${v.vendor_id}, ${v.default_quantity})" class="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold py-2 rounded-xl transition shadow">
                <i class="fa-solid fa-plus mr-1"></i> +${v.default_quantity}L Today
              </button>
              <button onclick="openMilkDeliveryModal(${v.vendor_id}, '${v.name}')" class="px-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold py-2 rounded-xl transition">
                <i class="fa-solid fa-calendar-day mr-1"></i> Custom L
              </button>
              <button onclick="openMilkPayModal(${v.vendor_id}, '${v.name}', ${v.balance_due})" class="px-3 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-2 rounded-xl transition shadow">
                <i class="fa-solid fa-receipt mr-1"></i> Pay
              </button>
              <button onclick="openEditMilkVendorModal(${v.vendor_id}, '${v.name}', ${v.rate_per_liter}, ${v.previous_dues}, ${v.default_quantity})" class="px-2.5 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold py-2 rounded-xl transition" title="Edit Price/L & Dues">
                <i class="fa-solid fa-pen"></i>
              </button>
            </div>
          </div>
        `;
      }).join('');

      const sel = document.getElementById('sel-milk-history-vendor');
      sel.innerHTML = cachedVendors.map(v => `<option value="${v.vendor_id}">${v.name}</option>`).join('');
      loadMilkDeliveries();
    }

    function openEditMilkVendorModal(vendorId, name, rate, dues, defaultQty) {
      document.getElementById('edit-milk-vendor-id').value = vendorId;
      document.getElementById('milk-edit-title').textContent = `Edit ${name} (Price & Dues)`;
      document.getElementById('edit-milk-rate').value = rate;
      document.getElementById('edit-milk-dues').value = dues || 0;
      document.getElementById('edit-milk-default-qty').value = defaultQty || 1.0;
      document.getElementById('milk-edit-modal').classList.remove('hidden');
    }
    function closeMilkEditModal() { document.getElementById('milk-edit-modal').classList.add('hidden'); }

    async function submitMilkUpdate() {
      const vendor_id = parseInt(document.getElementById('edit-milk-vendor-id').value);
      const rate_per_liter = parseFloat(document.getElementById('edit-milk-rate').value);
      const previous_dues = parseFloat(document.getElementById('edit-milk-dues').value) || 0.0;
      const default_quantity = parseFloat(document.getElementById('edit-milk-default-qty').value) || 1.0;

      if (!rate_per_liter || rate_per_liter <= 0) {
        alert("Please enter a valid price per liter!");
        return;
      }

      await fetch('/api/milk/update-vendor', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({vendor_id, rate_per_liter, previous_dues, default_quantity})
      });

      closeMilkEditModal();
      showToast("Milk price per liter & dues updated!");
      loadMilkData();
    }

    async function quickLogMilk(vendorId, qty) {
      await fetch('/api/milk/delivery', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({vendor_id: vendorId, quantity_liters: qty})
      });
      showToast(`Recorded ${qty} Liters for today!`);
      loadMilkData();
    }

    function openMilkDeliveryModal(vendorId, name) {
      document.getElementById('milk-del-vendor-id').value = vendorId;
      document.getElementById('milk-modal-title').textContent = `Log Delivery - ${name}`;
      document.getElementById('milk-del-date').value = new Date().toISOString().slice(0, 10);
      document.getElementById('milk-del-qty').value = '';
      document.getElementById('milk-delivery-modal').classList.remove('hidden');
    }
    function closeMilkDeliveryModal() { document.getElementById('milk-delivery-modal').classList.add('hidden'); }

    async function submitMilkDelivery() {
      const vendor_id = parseInt(document.getElementById('milk-del-vendor-id').value);
      const date = document.getElementById('milk-del-date').value;
      const quantity_liters = parseFloat(document.getElementById('milk-del-qty').value);
      const notes = document.getElementById('milk-del-notes').value.trim();

      if (!quantity_liters || quantity_liters <= 0) {
        alert("Please enter a valid milk quantity in liters!");
        return;
      }

      await fetch('/api/milk/delivery', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({vendor_id, date, quantity_liters, notes})
      });

      closeMilkDeliveryModal();
      showToast("Milk delivery entry saved!");
      loadMilkData();
    }

    function openMilkPayModal(vendorId, name, balanceDue) {
      document.getElementById('pay-milk-vendor-id').value = vendorId;
      document.getElementById('milk-pay-title').textContent = `Pay ${name}`;
      document.getElementById('pay-milk-amount').value = balanceDue > 0 ? balanceDue : '';
      document.getElementById('milk-pay-modal').classList.remove('hidden');
    }
    function closeMilkPayModal() { document.getElementById('milk-pay-modal').classList.add('hidden'); }

    async function submitMilkPayment() {
      const vendor_id = parseInt(document.getElementById('pay-milk-vendor-id').value);
      const amount = parseFloat(document.getElementById('pay-milk-amount').value);
      const payment_mode = document.getElementById('pay-milk-mode').value;
      const notes = document.getElementById('pay-milk-notes').value.trim();

      if (!amount || amount <= 0) {
        alert("Please enter a valid amount!");
        return;
      }

      await fetch('/api/milk/pay', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({vendor_id, amount, payment_mode, notes})
      });

      closeMilkPayModal();
      showToast("Milk payment recorded & added to expenses!");
      loadMilkData();
      loadStats();
      loadTransactions();
    }

    async function loadMilkDeliveries() {
      const vendorId = document.getElementById('sel-milk-history-vendor').value;
      if (!vendorId) return;

      const res = await fetch(`/api/milk/deliveries?vendor_id=${vendorId}`);
      const deliveries = await res.json();
      const container = document.getElementById('milk-daily-list');

      if (!deliveries.length) {
        container.innerHTML = '<div class="text-slate-400 text-center py-2">No deliveries recorded this month.</div>';
        return;
      }

      container.innerHTML = deliveries.map(d => `
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
          <div>
            <span class="font-bold text-slate-700">${d.date}</span>
            <span class="text-slate-400 text-[10px]">(${d.shift})</span>
            ${d.notes ? `<div class="text-[10px] text-slate-400">${d.notes}</div>` : ''}
          </div>
          <div class="flex items-center space-x-3">
            <span class="font-bold text-indigo-600">${d.quantity_liters} Liters</span>
            <span class="text-slate-500 text-xs">₹${(d.quantity_liters * d.rate_at_delivery).toFixed(0)}</span>
            <button onclick="deleteMilkDelivery(${d.id})" class="text-slate-300 hover:text-rose-500 transition">
              <i class="fa-solid fa-trash text-[11px]"></i>
            </button>
          </div>
        </div>
      `).join('');
    }

    async function deleteMilkDelivery(id) {
      if (!confirm("Delete this delivery entry?")) return;
      await fetch(`/api/milk/delete-delivery?id=${id}`, {method: 'POST'});
      showToast("Delivery deleted");
      loadMilkData();
    }

    // ----------------- ANALYTICS -----------------
    async function loadAnalytics() {
      const res = await fetch('/api/stats');
      const data = await res.json();
      const total = data.total_debit || 1;

      const catContainer = document.getElementById('category-bars');
      catContainer.innerHTML = data.categories.map(c => {
        const pct = (c.total / total * 100).toFixed(1);
        const iconClass = categoryIcons[c.category] || categoryIcons["Others"];
        return `
          <div class="space-y-1">
            <div class="flex justify-between text-xs">
              <span class="font-medium flex items-center space-x-1.5">
                <i class="fa-solid ${iconClass}"></i>
                <span>${c.category}</span>
              </span>
              <span class="font-bold text-slate-700">₹ ${c.total.toFixed(2)} (${pct}%)</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2">
              <div class="bg-indigo-600 h-2 rounded-full" style="width: ${pct}%"></div>
            </div>
          </div>
        `;
      }).join('') || '<div class="text-xs text-slate-400">No data available</div>';

      const modeContainer = document.getElementById('mode-bars');
      modeContainer.innerHTML = data.payment_modes.map(m => {
        const pct = (m.total / total * 100).toFixed(1);
        return `
          <div class="flex justify-between items-center text-xs py-1.5 border-b border-slate-50">
            <span class="font-medium text-slate-700">${m.payment_mode}</span>
            <span class="font-bold text-slate-800">₹ ${m.total.toFixed(2)} (${pct}%)</span>
          </div>
        `;
      }).join('') || '<div class="text-xs text-slate-400">No data available</div>';
    }

    // ----------------- SMS SYNC & HISTORICAL SCAN -----------------
    async function syncSMS(isFullScan = false) {
      showToast(isFullScan ? "Scanning all past SMS in phone inbox..." : "Scanning recent SMS alerts...");
      
      const statusBox = document.getElementById('sync-status-box');
      if (statusBox) {
        statusBox.classList.remove('hidden');
        statusBox.innerHTML = `<strong>Scanning in progress...</strong> Analyzing ${isFullScan ? 'entire SMS inbox' : 'recent messages'} for UPI and bank debits.`;
      }

      const res = await fetch('/api/sync-sms', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({full_scan: isFullScan})
      });
      const data = await res.json();

      const msg = `Scan Complete: Scanned ${data.scanned} SMS. Added ${data.added} new transactions (${data.duplicates} duplicates skipped).`;
      showToast(msg);

      if (statusBox) {
        statusBox.innerHTML = `
          <div class="font-bold text-emerald-800"><i class="fa-solid fa-circle-check mr-1"></i> Scan Finished Successfully</div>
          <div>Total SMS Checked: <strong>${data.scanned}</strong></div>
          <div>Transaction Alerts Detected: <strong>${data.parsed}</strong></div>
          <div>New Expenses Added to Database: <strong class="text-emerald-700">+${data.added}</strong></div>
          <div>Previously Saved (Deduplicated): <strong>${data.duplicates}</strong></div>
        `;
      }

      loadStats();
      loadTransactions();
    }

    async function parseCustomSMS() {
      const text = document.getElementById('custom-sms-text').value.trim();
      if (!text) return;
      const res = await fetch('/api/parse-sms', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      const data = await res.json();
      const resultDiv = document.getElementById('sms-parse-result');
      resultDiv.classList.remove('hidden');
      if (data.success) {
        resultDiv.className = "text-xs p-3 rounded-xl bg-emerald-50 text-emerald-800 border border-emerald-200";
        resultDiv.innerHTML = `<strong>Success!</strong> Auto-detected: ₹${data.parsed.amount} debited at ${data.parsed.merchant} (${data.parsed.category} via ${data.parsed.payment_mode}). Added to database!`;
        document.getElementById('custom-sms-text').value = '';
        loadStats();
        loadTransactions();
      } else {
        resultDiv.className = "text-xs p-3 rounded-xl bg-rose-50 text-rose-800 border border-rose-200";
        resultDiv.innerHTML = `<strong>Failed:</strong> ${data.error || 'Could not parse transaction from this SMS text.'}`;
      }
    }

    // ----------------- GENERAL EXPENSE & CUSTOM CATEGORIES -----------------
    function openAddModal() { 
      document.getElementById('add-modal').classList.remove('hidden'); 
      document.getElementById('new-amount').focus();
    }
    function closeAddModal() { document.getElementById('add-modal').classList.add('hidden'); }
    function openBudgetModal() { document.getElementById('budget-modal').classList.remove('hidden'); }
    function closeBudgetModal() { document.getElementById('budget-modal').classList.add('hidden'); }
    function openStaffModal() { document.getElementById('staff-modal').classList.remove('hidden'); }
    function closeStaffModal() { document.getElementById('staff-modal').classList.add('hidden'); }

    function toggleCustomCategoryInput() {
      const sel = document.getElementById('new-category');
      const box = document.getElementById('new-custom-category-box');
      if (sel.value === '__custom__') {
        box.classList.remove('hidden');
        document.getElementById('new-custom-category').focus();
      } else {
        box.classList.add('hidden');
      }
    }

    function openEditCategoryModal(txnId, merchant, currentCategory) {
      document.getElementById('cat-edit-txn-id').value = txnId;
      document.getElementById('cat-edit-merchant').value = merchant || '';
      document.getElementById('cat-edit-title').textContent = `Set Category: ${merchant || 'Expense'}`;
      document.getElementById('cat-edit-subtitle').textContent = `Currently: ${currentCategory || 'Others'}`;
      document.getElementById('cat-edit-input').value = (currentCategory === 'Others' || !currentCategory) ? '' : currentCategory;
      document.getElementById('category-edit-modal').classList.remove('hidden');
      document.getElementById('cat-edit-input').focus();
    }

    function closeCategoryEditModal() {
      document.getElementById('category-edit-modal').classList.add('hidden');
    }

    function pickCategoryPill(name) {
      document.getElementById('cat-edit-input').value = name;
    }

    async function submitCategoryUpdate() {
      const id = parseInt(document.getElementById('cat-edit-txn-id').value);
      const merchant = document.getElementById('cat-edit-merchant').value;
      const category = document.getElementById('cat-edit-input').value.trim() || 'Others';
      const remember = document.getElementById('cat-remember-rule').checked;

      await fetch('/api/update-category', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id, merchant, category, remember})
      });

      closeCategoryEditModal();
      showToast(`Category updated to "${category}"!`);
      loadStats();
      loadTransactions();
      loadCategories();
    }

    async function loadCategories() {
      try {
        const res = await fetch('/api/categories');
        const cats = await res.json();
        
        // Update filter dropdown
        const filterSel = document.getElementById('filter-category');
        const currentFilter = filterSel.value;
        filterSel.innerHTML = `<option value="All">All Spends</option>` + 
          cats.map(c => `<option value="${escapeHtml(c)}" ${c === currentFilter ? 'selected' : ''}>${escapeHtml(c)}</option>`).join('');

        // Update pills in category modal
        const pillsContainer = document.getElementById('cat-quick-pills');
        if (pillsContainer) {
          pillsContainer.innerHTML = cats.filter(c => c !== 'Others').slice(0, 10).map(c => 
            `<button type="button" onclick="pickCategoryPill('${escapeJs(c)}')" class="px-2 py-1 bg-slate-100 hover:bg-indigo-100 text-slate-700 hover:text-indigo-700 text-[11px] rounded-lg transition font-medium">${escapeHtml(c)}</button>`
          ).join('');
        }
      } catch (e) {
        console.error("Failed to load categories:", e);
      }
    }

    async function saveNewStaff() {
      const name = document.getElementById('new-staff-name').value.trim();
      const role = document.getElementById('new-staff-role').value;
      const salary = parseFloat(document.getElementById('new-staff-salary').value) || 0;
      const dues = parseFloat(document.getElementById('new-staff-dues').value) || 0;

      if (!name) {
        alert("Please enter staff name!");
        return;
      }

      await fetch('/api/staff/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, role, monthly_salary: salary, previous_dues: dues})
      });

      closeStaffModal();
      showToast("Staff member registered!");
      loadStaffData();
    }

    async function saveExpense() {
      const amount = parseFloat(document.getElementById('new-amount').value);
      const merchant = document.getElementById('new-merchant').value.trim();
      let category = document.getElementById('new-category').value;
      if (category === '__custom__') {
        const customCat = document.getElementById('new-custom-category').value.trim();
        category = customCat || "Others";
      }
      const payment_mode = document.getElementById('new-mode').value;
      const notes = document.getElementById('new-notes').value.trim();

      if (!amount || amount <= 0 || !merchant) {
        alert("Please enter amount and description!");
        return;
      }

      await fetch('/api/add-transaction', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({amount, merchant, category, payment_mode, notes})
      });

      closeAddModal();
      showToast("Expense logged successfully!");
      document.getElementById('new-amount').value = '';
      document.getElementById('new-merchant').value = '';
      document.getElementById('new-notes').value = '';
      document.getElementById('new-custom-category').value = '';
      document.getElementById('new-custom-category-box').classList.add('hidden');
      document.getElementById('new-category').value = 'Food & Dining';
      loadStats();
      loadTransactions();
      loadCategories();
    }

    async function deleteTransaction(id) {
      if (!confirm("Delete this transaction?")) return;
      await fetch(`/api/delete-transaction?id=${id}`, {method: 'POST'});
      showToast("Transaction deleted");
      loadStats();
      loadTransactions();
    }

    async function saveBudget() {
      const budget = parseFloat(document.getElementById('budget-input').value);
      if (!budget || budget <= 0) return;
      await fetch('/api/set-budget', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({budget})
      });
      closeBudgetModal();
      showToast("Budget updated!");
      loadStats();
    }

    // Initial load
    loadStats();
    loadTransactions();
    loadCategories();
  </script>
</body>
</html>"""


class RequestHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif path == "/api/stats":
            stats = db.get_summary_statistics()
            self._send_json(stats)
        elif path == "/api/transactions":
            q = query.get('q', [''])[0]
            cat = query.get('category', ['All'])[0]
            txns = db.get_transactions(limit=100, search_query=q if q else None, category=cat if cat != "All" else None)
            self._send_json(txns)
        elif path == "/api/categories":
            self._send_json(db.get_all_categories())
        # Staff endpoints
        elif path == "/api/staff/summary":
            m = query.get('month', [None])[0]
            self._send_json(db.get_staff_monthly_summary(month_year=m))
        elif path == "/api/staff/history":
            sid = int(query.get('staff_id', [0])[0]) if query.get('staff_id') else None
            self._send_json(db.get_staff_payment_history(staff_id=sid))
        # Milk endpoints
        elif path == "/api/milk/summary":
            m = query.get('month', [None])[0]
            self._send_json(db.get_milk_monthly_summary(month_year=m))
        elif path == "/api/milk/deliveries":
            vid = int(query.get('vendor_id', [1])[0])
            m = query.get('month', [None])[0]
            self._send_json(db.get_milk_deliveries(vendor_id=vid, month_year=m))
        elif path == "/api/milk/history":
            vid = int(query.get('vendor_id', [0])[0]) if query.get('vendor_id') else None
            self._send_json(db.get_milk_payment_history(vendor_id=vid))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        data = json.loads(post_data.decode('utf-8')) if post_data else {}

        if path == "/api/sync-sms":
            full_scan = data.get("full_scan", False)
            result = sms_service.sync_sms_transactions(full_scan=full_scan)
            self._send_json(result)
        elif path == "/api/parse-sms":
            text = data.get("text", "")
            parsed = SMSParser.parse(text, sender="Web Tester")
            if parsed:
                inserted_id = db.add_transaction(**parsed)
                if inserted_id:
                    parsed["id"] = inserted_id
                    self._send_json({"success": True, "parsed": parsed})
                else:
                    self._send_json({"success": False, "error": "This transaction already exists in the database (duplicate)."})
            else:
                self._send_json({"success": False, "error": "Could not extract valid transaction amount or debit pattern from SMS."})
        elif path == "/api/add-transaction":
            merchant = data.get("merchant", "Cash Expense").strip() or "Cash Expense"
            category = data.get("category", "Others").strip() or "Others"
            txn_id = db.add_transaction(
                amount=float(data.get("amount", 0)),
                merchant=merchant,
                category=category,
                payment_mode=data.get("payment_mode", "Cash"),
                notes=data.get("notes", ""),
                is_manual=1
            )
            if merchant and merchant != "Cash Expense" and category != "Others":
                db.set_merchant_category_rule(merchant, category, update_existing_others=False)
            self._send_json({"success": True, "id": txn_id})
        elif path == "/api/update-category":
            txn_id = int(data.get("id", 0))
            category = data.get("category", "Others").strip() or "Others"
            merchant = data.get("merchant", "").strip()
            remember = data.get("remember", True)
            success = db.update_transaction(txn_id, category=category)
            if remember and merchant and merchant != "Cash Expense":
                db.set_merchant_category_rule(merchant, category, update_existing_others=True)
            self._send_json({"success": success})
        elif path == "/api/delete-transaction":
            query = parse_qs(parsed_url.query)
            txn_id = int(query.get('id', [0])[0])
            success = db.delete_transaction(txn_id)
            self._send_json({"success": success})
        elif path == "/api/set-budget":
            month_year = datetime.now().strftime("%Y-%m")
            db.set_budget(month_year, float(data.get("budget", 0)))
            self._send_json({"success": True})
        # Staff POST actions
        elif path == "/api/staff/pay":
            pay_id = db.log_staff_payment(
                staff_id=int(data.get("staff_id", 1)),
                amount=float(data.get("amount", 0)),
                date=data.get("date"),
                month_for=data.get("month_for"),
                payment_mode=data.get("payment_mode", "Cash"),
                payment_type=data.get("payment_type", "Salary"),
                notes=data.get("notes", "")
            )
            self._send_json({"success": True, "id": pay_id})
        elif path == "/api/staff/update":
            sid = int(data.get("staff_id", 0))
            fields = {}
            if "monthly_salary" in data:
                fields["monthly_salary"] = float(data["monthly_salary"])
            if "previous_dues" in data:
                fields["previous_dues"] = float(data["previous_dues"])
            if "phone" in data:
                fields["phone"] = data["phone"]
            if "notes" in data:
                fields["notes"] = data["notes"]
            if "name" in data and data["name"]:
                fields["name"] = data["name"]
            success = db.update_staff_member(sid, **fields)
            self._send_json({"success": success})
        elif path == "/api/staff/add":
            sid = db.add_staff_member(
                name=data.get("name", "Staff"),
                role=data.get("role", "Other"),
                monthly_salary=float(data.get("monthly_salary", 0)),
                previous_dues=float(data.get("previous_dues", 0)),
                phone=data.get("phone", "")
            )
            self._send_json({"success": True, "id": sid})
        elif path == "/api/staff/delete-payment":
            query = parse_qs(parsed_url.query)
            pid = int(query.get('id', [0])[0])
            success = db.delete_staff_payment(pid)
            self._send_json({"success": success})
        # Milk POST actions
        elif path == "/api/milk/delivery":
            del_id = db.log_milk_delivery(
                vendor_id=int(data.get("vendor_id", 1)),
                date=data.get("date"),
                quantity_liters=float(data.get("quantity_liters")) if data.get("quantity_liters") is not None else None,
                shift=data.get("shift", "Daily"),
                notes=data.get("notes", "")
            )
            self._send_json({"success": True, "id": del_id})
        elif path == "/api/milk/pay":
            pay_id = db.log_milk_payment(
                vendor_id=int(data.get("vendor_id", 1)),
                amount=float(data.get("amount", 0)),
                date=data.get("date"),
                month_for=data.get("month_for"),
                payment_mode=data.get("payment_mode", "UPI"),
                notes=data.get("notes", "")
            )
            self._send_json({"success": True, "id": pay_id})
        elif path == "/api/milk/update-vendor":
            vid = int(data.get("vendor_id", 0))
            fields = {}
            if "rate_per_liter" in data:
                fields["rate_per_liter"] = float(data["rate_per_liter"])
            if "previous_dues" in data:
                fields["previous_dues"] = float(data["previous_dues"])
            if "default_quantity" in data:
                fields["default_quantity"] = float(data["default_quantity"])
            if "name" in data and data["name"]:
                fields["name"] = data["name"]
            success = db.update_milk_vendor(vid, **fields)
            self._send_json({"success": success})
        elif path == "/api/milk/delete-delivery":
            query = parse_qs(parsed_url.query)
            did = int(query.get('id', [0])[0])
            success = db.delete_milk_delivery(did)
            self._send_json({"success": success})
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port=5000):
    server = HTTPServer(('0.0.0.0', port), RequestHandler)
    print(f"\n[+] Smart Expense & Household Tracker running at: http://localhost:{port}")
    print(f"[+] To view on your phone on the same Wi-Fi, open: http://<YOUR_COMPUTER_IP>:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == '__main__':
    run_server()
