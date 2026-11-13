import sqlite3
import os
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

def normalize_date_str(date_input: Optional[str]) -> str:
    """Safely normalizes any date input into ISO YYYY-MM-DD format."""
    if not date_input or not str(date_input).strip():
        return datetime.now().strftime("%Y-%m-%d")
    s = str(date_input).strip()
    if s.lower() in ("today", "tod"):
        return datetime.now().strftime("%Y-%m-%d")
    if s.lower() in ("yesterday", "yest"):
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%d-%m-%y", "%d/%m/%y", "%d %b %Y", "%d %b %y",
        "%d %B %Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10]
    return datetime.now().strftime("%Y-%m-%d")

def get_database_path() -> str:
    """Returns safe writable database file path for Android or Desktop."""
    try:
        from kivy.utils import platform
        if platform == 'android':
            from kivy.app import App
            app = App.get_running_app()
            if app and hasattr(app, 'user_data_dir') and app.user_data_dir:
                target_dir = app.user_data_dir
                os.makedirs(target_dir, exist_ok=True)
                return os.path.join(target_dir, "expenses.db")
            for env_var in ["ANDROID_PRIVATE", "ANDROID_ARGUMENT", "ANDROID_APP_PATH"]:
                val = os.environ.get(env_var)
                if val and os.path.exists(val):
                    return os.path.join(val, "expenses.db")
    except Exception:
        pass

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "expenses.db")


class DatabaseManager:
    """Manages SQLite database for transactions, categories, budgets, staff, and milk tracking."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path if db_path else get_database_path()
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        except Exception:
            pass
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Transactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL DEFAULT 'DEBIT',
                    amount REAL NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Others',
                    payment_mode TEXT NOT NULL DEFAULT 'UPI',
                    account_or_card TEXT,
                    merchant TEXT,
                    date TEXT NOT NULL,
                    notes TEXT,
                    raw_sms TEXT,
                    sms_hash TEXT UNIQUE,
                    is_manual INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Budgets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month_year TEXT UNIQUE NOT NULL, -- Format: YYYY-MM
                    total_budget REAL NOT NULL DEFAULT 0.0
                )
            """)

            # Category Budgets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS category_budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    monthly_limit REAL NOT NULL,
                    UNIQUE(category)
                )
            """)

            # Household Staff table (Cook, House Helper, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS household_staff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'Other', -- 'Cook', 'House Helper', etc.
                    monthly_salary REAL NOT NULL DEFAULT 0.0,
                    previous_dues REAL NOT NULL DEFAULT 0.0,
                    phone TEXT,
                    notes TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Staff Payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS staff_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    date TEXT NOT NULL,
                    month_for TEXT NOT NULL, -- YYYY-MM
                    payment_mode TEXT NOT NULL DEFAULT 'Cash',
                    payment_type TEXT NOT NULL DEFAULT 'Salary', -- 'Salary', 'Advance', 'Bonus'
                    notes TEXT,
                    transaction_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(staff_id) REFERENCES household_staff(id) ON DELETE CASCADE
                )
            """)

            # Milk Vendors table (Sundar, Jain Mandir)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS milk_vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    milk_type TEXT DEFAULT 'Cow Milk', -- 'Cow Milk', 'Buffalo Milk'
                    rate_per_liter REAL NOT NULL DEFAULT 60.0,
                    default_quantity REAL DEFAULT 1.0,
                    previous_dues REAL NOT NULL DEFAULT 0.0,
                    phone TEXT,
                    notes TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Milk Deliveries table (Daily log per milkman)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS milk_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_id INTEGER NOT NULL,
                    date TEXT NOT NULL, -- YYYY-MM-DD
                    quantity_liters REAL NOT NULL,
                    rate_at_delivery REAL NOT NULL,
                    shift TEXT DEFAULT 'Daily', -- 'Morning', 'Evening', 'Daily'
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(vendor_id, date, shift),
                    FOREIGN KEY(vendor_id) REFERENCES milk_vendors(id) ON DELETE CASCADE
                )
            """)

            # Milk Payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS milk_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    date TEXT NOT NULL,
                    month_for TEXT NOT NULL, -- YYYY-MM
                    payment_mode TEXT NOT NULL DEFAULT 'UPI',
                    notes TEXT,
                    transaction_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(vendor_id) REFERENCES milk_vendors(id) ON DELETE CASCADE
                )
            """)

            # Custom merchant-to-category learning rules
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS merchant_category_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant_pattern TEXT UNIQUE COLLATE NOCASE,
                    category TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indices for fast querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_mode ON transactions(payment_mode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_hash ON transactions(sms_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_milk_del_date ON milk_deliveries(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_pay_month ON staff_payments(month_for)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_merchant_rules ON merchant_category_rules(merchant_pattern)")

            # Seed default staff and milkmen if tables are newly created
            cursor.execute("SELECT COUNT(*) FROM household_staff")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO household_staff (name, role, monthly_salary, previous_dues, notes)
                    VALUES ('Cook', 'Cook', 4000.0, 0.0, 'Daily cooking (lunch/dinner)'),
                           ('House Helper', 'House Helper', 3500.0, 0.0, 'Cleaning, dusting & washing')
                """)

            cursor.execute("SELECT COUNT(*) FROM milk_vendors")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO milk_vendors (name, milk_type, rate_per_liter, default_quantity, previous_dues, notes)
                    VALUES ('Sundar', 'Cow Milk', 60.0, 1.5, 0.0, 'Morning delivery'),
                           ('Jain Mandir', 'Pure Milk', 70.0, 1.0, 0.0, 'Daily delivery')
                """)
            else:
                cursor.execute("UPDATE milk_vendors SET name = 'Sundar' WHERE name LIKE '%Milkman 1%'")
                cursor.execute("UPDATE milk_vendors SET name = 'Jain Mandir' WHERE name LIKE '%Milkman 2%'")

            # Migrations to ensure columns exist on older databases
            try:
                cursor.execute("ALTER TABLE household_staff ADD COLUMN previous_dues REAL NOT NULL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE milk_vendors ADD COLUMN previous_dues REAL NOT NULL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass

            conn.commit()

    @staticmethod
    def compute_sms_hash(body: str, timestamp_str: str = "") -> str:
        """Create a unique deterministic hash for an SMS to prevent duplicate imports."""
        normalized = f"{body.strip()}_{timestamp_str.strip()}".encode('utf-8')
        return hashlib.sha256(normalized).hexdigest()

    def add_transaction(
        self,
        amount: float,
        category: str = "Others",
        payment_mode: str = "UPI",
        account_or_card: Optional[str] = None,
        merchant: Optional[str] = None,
        date: Optional[str] = None,
        type: str = "DEBIT",
        txn_type: Optional[str] = None,
        notes: Optional[str] = None,
        raw_sms: Optional[str] = None,
        sms_hash: Optional[str] = None,
        is_manual: int = 1
    ) -> Optional[int]:
        """Add a transaction. Returns inserted ID or None if already exists (deduplicated)."""
        final_type = txn_type if txn_type else type
        if not date:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if raw_sms and not sms_hash:
            sms_hash = self.compute_sms_hash(raw_sms, date)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO transactions (
                        type, amount, category, payment_mode, account_or_card,
                        merchant, date, notes, raw_sms, sms_hash, is_manual
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    final_type, amount, category, payment_mode, account_or_card,
                    merchant, date, notes, raw_sms, sms_hash, is_manual
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    def add_transactions_batch(self, transactions: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Inserts multiple transactions in a SINGLE SQLite transaction.
        Returns (added_count, duplicate_count).
        100x faster than single-item inserts on Android flash storage.
        """
        if not transactions:
            return (0, 0)

        added = 0
        duplicates = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for txn in transactions:
                raw_sms = txn.get('raw_sms')
                date = txn.get('date') or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sms_hash = txn.get('sms_hash')
                if raw_sms and not sms_hash:
                    sms_hash = self.compute_sms_hash(raw_sms, date)

                txn_type = txn.get('txn_type') or txn.get('type') or 'DEBIT'
                try:
                    cursor.execute("""
                        INSERT INTO transactions (
                            type, amount, category, payment_mode, account_or_card,
                            merchant, date, notes, raw_sms, sms_hash, is_manual
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        txn_type,
                        txn.get('amount', 0.0),
                        txn.get('category', 'Others'),
                        txn.get('payment_mode', 'UPI'),
                        txn.get('account_or_card'),
                        txn.get('merchant'),
                        date,
                        txn.get('notes'),
                        raw_sms,
                        sms_hash,
                        txn.get('is_manual', 0)
                    ))
                    added += 1
                except sqlite3.IntegrityError:
                    duplicates += 1
            conn.commit()
        return (added, duplicates)

    def get_transactions(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        payment_mode: Optional[str] = None,
        search_query: Optional[str] = None,
        month_year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve filtered transactions."""
        query = "SELECT * FROM transactions WHERE 1=1"
        params: List[Any] = []

        if category and category != "All":
            query += " AND category = ?"
            params.append(category)

        if payment_mode and payment_mode != "All":
            query += " AND payment_mode = ?"
            params.append(payment_mode)

        if search_query:
            query += " AND (merchant LIKE ? OR notes LIKE ? OR account_or_card LIKE ?)"
            wildcard = f"%{search_query}%"
            params.extend([wildcard, wildcard, wildcard])

        if month_year:
            query += " AND strftime('%Y-%m', date) = ?"
            params.append(month_year)

        query += " ORDER BY date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_transaction(self, txn_id: int, **fields) -> bool:
        """Update specific fields of a transaction."""
        if not fields:
            return False

        keys = list(fields.keys())
        values = list(fields.values())
        set_clause = ", ".join([f"{k} = ?" for k in keys])
        values.append(txn_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE transactions SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_transaction(self, txn_id: int) -> bool:
        """Delete a transaction by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_summary_statistics(self, month_year: Optional[str] = None) -> Dict[str, Any]:
        """Calculates total spend, total credit, category breakdown, and payment mode breakdown."""
        if not month_year:
            month_year = datetime.now().strftime("%Y-%m")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN type = 'DEBIT' THEN amount ELSE 0 END) as total_debit,
                    SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END) as total_credit,
                    COUNT(*) as txn_count
                FROM transactions 
                WHERE strftime('%Y-%m', date) = ?
            """, (month_year,))
            totals = cursor.fetchone()
            total_debit = totals['total_debit'] or 0.0
            total_credit = totals['total_credit'] or 0.0
            txn_count = totals['txn_count'] or 0

            today_str = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT SUM(amount) as today_debit 
                FROM transactions 
                WHERE type = 'DEBIT' AND strftime('%Y-%m-%d', date) = ?
            """, (today_str,))
            today_res = cursor.fetchone()
            today_debit = today_res['today_debit'] or 0.0

            cursor.execute("""
                SELECT SUM(amount) as week_debit 
                FROM transactions 
                WHERE type = 'DEBIT' AND strftime('%Y-%W', date) = strftime('%Y-%W', 'now')
            """)
            week_res = cursor.fetchone()
            week_debit = week_res['week_debit'] or 0.0

            cursor.execute("""
                SELECT category, SUM(amount) as total, COUNT(*) as count 
                FROM transactions 
                WHERE type = 'DEBIT' AND strftime('%Y-%m', date) = ?
                GROUP BY category 
                ORDER BY total DESC
            """, (month_year,))
            category_breakdown = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT payment_mode, SUM(amount) as total, COUNT(*) as count 
                FROM transactions 
                WHERE type = 'DEBIT' AND strftime('%Y-%m', date) = ?
                GROUP BY payment_mode 
                ORDER BY total DESC
            """, (month_year,))
            mode_breakdown = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT total_budget FROM budgets WHERE month_year = ?", (month_year,))
            budget_row = cursor.fetchone()
            budget = budget_row['total_budget'] if budget_row else 0.0

            return {
                "month_year": month_year,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "today_debit": today_debit,
                "week_debit": week_debit,
                "txn_count": txn_count,
                "budget": budget,
                "budget_remaining": max(0.0, budget - total_debit) if budget > 0 else 0.0,
                "budget_percentage": (total_debit / budget * 100) if budget > 0 else 0.0,
                "categories": category_breakdown,
                "payment_modes": mode_breakdown
            }

    def get_all_available_months(self) -> List[Dict[str, str]]:
        """
        Returns list of all months with data in the database, ordered latest first.
        e.g. [{'month_year': '2026-11', 'display_name': 'November 2026'}, ...]
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT strftime('%Y-%m', date) as my
                FROM transactions
                WHERE date IS NOT NULL AND length(date) >= 7
                ORDER BY my DESC
            """)
            rows = cursor.fetchall()
            months_set = {r['my'] for r in rows if r['my']}

            cursor.execute("""
                SELECT DISTINCT strftime('%Y-%m', date) as my
                FROM milk_deliveries
                WHERE date IS NOT NULL AND length(date) >= 7
            """)
            for r in cursor.fetchall():
                if r['my']:
                    months_set.add(r['my'])

            curr_my = datetime.now().strftime("%Y-%m")
            months_set.add(curr_my)

            sorted_my = sorted(list(months_set), reverse=True)
            result = []
            for my in sorted_my:
                try:
                    dt = datetime.strptime(my, "%Y-%m")
                    display = dt.strftime("%B %Y")
                except Exception:
                    display = my
                result.append({"month_year": my, "display_name": display})
            return result

    def get_monthly_history_breakdown(self, limit_months: int = 24) -> List[Dict[str, Any]]:
        """
        Calculates per-month financial summaries across all months in the past 1-2 years.
        Returns detailed summary per month including total debit, credit, net savings,
        transaction count, top spending category, milk cost, and staff payments.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m', date) as month_year,
                    SUM(CASE WHEN type = 'DEBIT' THEN amount ELSE 0 END) as total_debit,
                    SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END) as total_credit,
                    COUNT(*) as txn_count
                FROM transactions
                WHERE date IS NOT NULL AND length(date) >= 7
                GROUP BY strftime('%Y-%m', date)
                ORDER BY month_year DESC
                LIMIT ?
            """, (limit_months,))
            rows = cursor.fetchall()
            months = [dict(r) for r in rows if r['month_year']]

            curr_my = datetime.now().strftime("%Y-%m")
            if not any(m['month_year'] == curr_my for m in months):
                months.insert(0, {
                    "month_year": curr_my,
                    "total_debit": 0.0,
                    "total_credit": 0.0,
                    "txn_count": 0
                })

            for m in months:
                my = m['month_year']
                try:
                    dt = datetime.strptime(my, "%Y-%m")
                    m['display_name'] = dt.strftime("%B %Y")
                    m['month_display'] = dt.strftime("%B %Y")
                    m['short_name'] = dt.strftime("%b %y")
                except Exception:
                    m['display_name'] = my
                    m['month_display'] = my
                    m['short_name'] = my

                m['total_debit'] = round(m.get('total_debit') or 0.0, 2)
                m['total_credit'] = round(m.get('total_credit') or 0.0, 2)
                m['net_savings'] = round(m['total_credit'] - m['total_debit'], 2)

                # Top spending category
                cursor.execute("""
                    SELECT category, SUM(amount) as cat_total
                    FROM transactions
                    WHERE type = 'DEBIT' AND strftime('%Y-%m', date) = ?
                    GROUP BY category
                    ORDER BY cat_total DESC LIMIT 1
                """, (my,))
                top_cat = cursor.fetchone()
                if top_cat:
                    m['top_category'] = top_cat['category']
                    m['top_category_amount'] = round(top_cat['cat_total'] or 0.0, 2)
                else:
                    m['top_category'] = "No Spends"
                    m['top_category_amount'] = 0.0

                # Milk delivery total
                cursor.execute("""
                    SELECT COALESCE(SUM(quantity_liters * rate_at_delivery), 0.0) as milk_total
                    FROM milk_deliveries
                    WHERE strftime('%Y-%m', date) = ?
                """, (my,))
                m['milk_total'] = round(cursor.fetchone()['milk_total'] or 0.0, 2)

                # Staff total
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0.0) as staff_total
                    FROM staff_payments
                    WHERE month_for = ?
                """, (my,))
                m['staff_total'] = round(cursor.fetchone()['staff_total'] or 0.0, 2)

            return months

    def set_budget(self, month_year: str, amount: float):
        """Set or update budget for a specific month (YYYY-MM)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO budgets (month_year, total_budget) VALUES (?, ?)
                ON CONFLICT(month_year) DO UPDATE SET total_budget = excluded.total_budget
            """, (month_year, amount))
            conn.commit()

    def get_recent_merchants(self, limit: int = 15) -> List[str]:
        """Fetch unique recent merchants for autocompletion."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT merchant FROM transactions 
                WHERE merchant IS NOT NULL AND merchant != '' 
                ORDER BY date DESC LIMIT ?
            """, (limit,))
            return [row['merchant'] for row in cursor.fetchall()]

    # -------------------------------------------------------------
    # CUSTOM CATEGORIES & MERCHANT LEARNING
    # -------------------------------------------------------------

    def set_merchant_category_rule(self, merchant: str, category: str, update_existing_others: bool = True) -> bool:
        """
        Saves a custom mapping from merchant to category so that future expenses
        or SMS from this merchant are automatically categorized into the user's custom category.
        Optionally retroactively updates past transactions from this merchant that were in 'Others'.
        """
        merchant_clean = merchant.strip()
        category_clean = category.strip()
        if not merchant_clean or not category_clean:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO merchant_category_rules (merchant_pattern, category)
                VALUES (?, ?)
                ON CONFLICT(merchant_pattern) DO UPDATE SET category = excluded.category
            """, (merchant_clean, category_clean))

            if update_existing_others:
                cursor.execute("""
                    UPDATE transactions 
                    SET category = ? 
                    WHERE merchant LIKE ? AND (category = 'Others' OR category = '' OR category IS NULL)
                """, (category_clean, f"%{merchant_clean}%"))

            conn.commit()
            return True

    def get_merchant_category_rule(self, merchant: str) -> Optional[str]:
        """Finds any saved custom category rule for a merchant."""
        if not merchant:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category FROM merchant_category_rules 
                WHERE ? LIKE '%' || merchant_pattern || '%' OR merchant_pattern LIKE '%' || ? || '%'
                ORDER BY LENGTH(merchant_pattern) DESC LIMIT 1
            """, (merchant, merchant))
            row = cursor.fetchone()
            return row['category'] if row else None

    def get_all_merchant_rules(self) -> Dict[str, str]:
        """Returns all custom merchant mappings as a lowercase dictionary."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT merchant_pattern, category FROM merchant_category_rules")
            return {r['merchant_pattern'].lower(): r['category'] for r in cursor.fetchall()}

    def get_all_categories(self) -> List[str]:
        """
        Returns a list of all distinct categories:
        Standard categories + any custom categories created by the user in transactions or rules.
        """
        standard = [
            "Food & Dining",
            "Groceries",
            "Shopping",
            "Travel & Commute",
            "Bills & Utilities",
            "Entertainment",
            "Health & Medical",
            "Investments & Savings",
            "Transfers & Rent",
            "Others"
        ]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT category FROM transactions 
                WHERE category IS NOT NULL AND TRIM(category) != ''
                UNION
                SELECT DISTINCT category FROM merchant_category_rules
                WHERE category IS NOT NULL AND TRIM(category) != ''
            """)
            db_cats = [r['category'].strip() for r in cursor.fetchall() if r['category'].strip()]

        # Combine standard + custom, keeping standard order and adding custom unique categories
        custom_cats = [c for c in db_cats if c not in standard]
        return standard[:-1] + sorted(custom_cats) + ["Others"]

    # -------------------------------------------------------------
    # HOUSEHOLD STAFF (Cook, House Helper, etc.)
    # -------------------------------------------------------------

    def get_staff_members(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Returns all registered household staff (Cook, Helper, etc.)."""
        query = "SELECT * FROM household_staff"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id ASC"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def add_staff_member(
        self,
        name: str,
        role: str,
        monthly_salary: float,
        previous_dues: float = 0.0,
        phone: str = "",
        notes: str = ""
    ) -> int:
        """Register a new staff member with salary and initial previous dues."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO household_staff (name, role, monthly_salary, previous_dues, phone, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, role, monthly_salary, previous_dues, phone, notes))
            conn.commit()
            return cursor.lastrowid

    def update_staff_member(self, staff_id: int, **fields) -> bool:
        """Update staff member details (e.g. salary, previous_dues, phone, name)."""
        if not fields:
            return False
        keys = list(fields.keys())
        values = list(fields.values())
        set_clause = ", ".join([f"{k} = ?" for k in keys])
        values.append(staff_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE household_staff SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def log_staff_payment(
        self,
        staff_id: int,
        amount: float,
        date: Optional[str] = None,
        month_for: Optional[str] = None,
        payment_mode: str = "Cash",
        payment_type: str = "Salary",
        notes: str = "",
        sync_to_main_expenses: bool = True
    ) -> int:
        """Record a salary or advance payment to Cook or House Helper."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not month_for:
            month_for = date[:7]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, role FROM household_staff WHERE id = ?", (staff_id,))
            staff = cursor.fetchone()
            staff_name = staff['name'] if staff else "Staff"

            txn_id = None
            if sync_to_main_expenses:
                cursor.execute("""
                    INSERT INTO transactions (
                        type, amount, category, payment_mode, merchant, date, notes, is_manual
                    ) VALUES ('DEBIT', ?, 'Transfers & Rent', ?, ?, ?, ?, 1)
                """, (
                    amount, payment_mode, f"{staff_name} ({payment_type})", date,
                    f"Staff payment for {month_for}: {notes}".strip()
                ))
                txn_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO staff_payments (
                    staff_id, amount, date, month_for, payment_mode, payment_type, notes, transaction_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (staff_id, amount, date, month_for, payment_mode, payment_type, notes, txn_id))
            conn.commit()
            return cursor.lastrowid

    def get_staff_monthly_summary(self, month_year: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns staff salary status:
        Agreed Monthly Salary, Previous Dues, Total Payable, Paid this month, and Remaining Balance Due.
        """
        if not month_year:
            month_year = datetime.now().strftime("%Y-%m")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    s.id, s.name, s.role, s.monthly_salary, s.previous_dues, s.phone, s.notes,
                    COALESCE(SUM(CASE WHEN p.payment_type = 'Salary' THEN p.amount ELSE 0 END), 0) as salary_paid,
                    COALESCE(SUM(CASE WHEN p.payment_type = 'Advance' THEN p.amount ELSE 0 END), 0) as advance_paid,
                    COALESCE(SUM(CASE WHEN p.payment_type = 'Bonus' THEN p.amount ELSE 0 END), 0) as bonus_paid,
                    COALESCE(SUM(p.amount), 0) as total_paid
                FROM household_staff s
                LEFT JOIN staff_payments p 
                    ON s.id = p.staff_id AND p.month_for = ?
                WHERE s.is_active = 1
                GROUP BY s.id
                ORDER BY s.id ASC
            """, (month_year,))
            rows = cursor.fetchall()

            summary = []
            for row in rows:
                item = dict(row)
                salary = item['monthly_salary'] or 0.0
                prev_dues = item.get('previous_dues', 0.0) or 0.0
                total_paid = item['total_paid'] or 0.0

                total_payable = salary + prev_dues
                balance_due = max(0.0, total_payable - total_paid)

                item['total_payable'] = round(total_payable, 2)
                item['balance_due'] = round(balance_due, 2)
                item['previous_dues'] = round(prev_dues, 2)
                item['month_for'] = month_year
                summary.append(item)
            return summary

    def get_staff_payment_history(self, staff_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get past payments made to staff."""
        query = """
            SELECT p.*, s.name as staff_name, s.role
            FROM staff_payments p
            JOIN household_staff s ON p.staff_id = s.id
        """
        params = []
        if staff_id:
            query += " WHERE p.staff_id = ?"
            params.append(staff_id)
        query += " ORDER BY p.date DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def delete_staff_payment(self, payment_id: int) -> bool:
        """Deletes a staff payment and its linked transaction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT transaction_id FROM staff_payments WHERE id = ?", (payment_id,))
            row = cursor.fetchone()
            if row and row['transaction_id']:
                cursor.execute("DELETE FROM transactions WHERE id = ?", (row['transaction_id'],))
            cursor.execute("DELETE FROM staff_payments WHERE id = ?", (payment_id,))
            conn.commit()
            return cursor.rowcount > 0

    # -------------------------------------------------------------
    # MILK TRACKER (Sundar & Jain Mandir)
    # -------------------------------------------------------------

    def get_milk_vendors(self) -> List[Dict[str, Any]]:
        """Fetch all milkmen / vendors with rates and previous dues."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM milk_vendors WHERE is_active = 1 ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def update_milk_vendor(self, vendor_id: int, **fields) -> bool:
        """Update milk vendor rate_per_liter, default_quantity, previous_dues, name, etc."""
        if not fields:
            return False
        keys = list(fields.keys())
        values = list(fields.values())
        set_clause = ", ".join([f"{k} = ?" for k in keys])
        values.append(vendor_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE milk_vendors SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def log_milk_delivery(
        self,
        vendor_id: int,
        date: Optional[str] = None,
        quantity_liters: Optional[float] = None,
        shift: str = "Daily",
        notes: str = ""
    ) -> int:
        """Log daily milk delivery for Sundar or Jain Mandir with safe date normalization."""
        date = normalize_date_str(date)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rate_per_liter, default_quantity FROM milk_vendors WHERE id = ?", (vendor_id,))
            vendor = cursor.fetchone()
            rate = vendor['rate_per_liter'] if vendor else 60.0
            if quantity_liters is None or quantity_liters <= 0:
                quantity_liters = vendor['default_quantity'] if vendor else 1.0

            cursor.execute("""
                INSERT INTO milk_deliveries (vendor_id, date, quantity_liters, rate_at_delivery, shift, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(vendor_id, date, shift) DO UPDATE SET
                    quantity_liters = excluded.quantity_liters,
                    rate_at_delivery = excluded.rate_at_delivery,
                    notes = excluded.notes
            """, (vendor_id, date, quantity_liters, rate, shift, notes))
            conn.commit()
            return cursor.lastrowid

    def log_milk_delivery_range(
        self,
        vendor_id: int,
        from_date: str,
        to_date: str,
        quantity_per_day: float,
        shift: str = "Daily",
        notes: str = ""
    ) -> int:
        """
        Logs milk delivery for a range of dates [from_date, to_date] inclusive.
        e.g. from 2026-11-01 to 2026-11-10 at 1.5L/day.
        Returns total number of days successfully logged.
        """
        d_start_str = normalize_date_str(from_date)
        d_end_str = normalize_date_str(to_date)

        dt_start = datetime.strptime(d_start_str, "%Y-%m-%d")
        dt_end = datetime.strptime(d_end_str, "%Y-%m-%d")
        if dt_start > dt_end:
            dt_start, dt_end = dt_end, dt_start

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rate_per_liter FROM milk_vendors WHERE id = ?", (vendor_id,))
            vendor = cursor.fetchone()
            rate = vendor['rate_per_liter'] if vendor else 60.0

            curr = dt_start
            count = 0
            while curr <= dt_end:
                day_str = curr.strftime("%Y-%m-%d")
                cursor.execute("""
                    INSERT INTO milk_deliveries (vendor_id, date, quantity_liters, rate_at_delivery, shift, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(vendor_id, date, shift) DO UPDATE SET
                        quantity_liters = excluded.quantity_liters,
                        rate_at_delivery = excluded.rate_at_delivery,
                        notes = excluded.notes
                """, (vendor_id, day_str, quantity_per_day, rate, shift, notes))
                curr += timedelta(days=1)
                count += 1
            conn.commit()
            return count

    def log_milk_payment(
        self,
        vendor_id: int,
        amount: float,
        date: Optional[str] = None,
        month_for: Optional[str] = None,
        payment_mode: str = "UPI",
        notes: str = "",
        sync_to_main_expenses: bool = True
    ) -> int:
        """Record payment made to a milkman."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not month_for:
            month_for = date[:7]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM milk_vendors WHERE id = ?", (vendor_id,))
            vendor = cursor.fetchone()
            vendor_name = vendor['name'] if vendor else "Milkman"

            txn_id = None
            if sync_to_main_expenses:
                cursor.execute("""
                    INSERT INTO transactions (
                        type, amount, category, payment_mode, merchant, date, notes, is_manual
                    ) VALUES ('DEBIT', ?, 'Groceries', ?, ?, ?, ?, 1)
                """, (
                    amount, payment_mode, f"{vendor_name} (Milk)", date,
                    f"Milk payment for {month_for}: {notes}".strip()
                ))
                txn_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO milk_payments (
                    vendor_id, amount, date, month_for, payment_mode, notes, transaction_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (vendor_id, amount, date, month_for, payment_mode, notes, txn_id))
            conn.commit()
            return cursor.lastrowid

    def get_milk_monthly_summary(self, month_year: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calculates monthly milk bill for Sundar & Jain Mandir:
        Rate/Liter, Previous Dues, Total Liters, Delivery Cost, Total Payable, Total Paid, and Balance Due.
        """
        if not month_year:
            month_year = datetime.now().strftime("%Y-%m")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            vendors = self.get_milk_vendors()
            summaries = []

            for v in vendors:
                vid = v['id']

                # Deliveries total
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(quantity_liters), 0.0) as total_liters,
                        COALESCE(SUM(quantity_liters * rate_at_delivery), 0.0) as total_bill,
                        COUNT(*) as delivery_days
                    FROM milk_deliveries
                    WHERE vendor_id = ? AND strftime('%Y-%m', date) = ?
                """, (vid, month_year))
                del_stats = cursor.fetchone()

                # Payments total
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0.0) as total_paid
                    FROM milk_payments
                    WHERE vendor_id = ? AND month_for = ?
                """, (vid, month_year))
                pay_stats = cursor.fetchone()

                total_liters = del_stats['total_liters'] or 0.0
                total_bill = del_stats['total_bill'] or 0.0
                delivery_days = del_stats['delivery_days'] or 0
                total_paid = pay_stats['total_paid'] or 0.0
                prev_dues = v.get('previous_dues', 0.0) or 0.0

                total_payable = total_bill + prev_dues
                balance_due = max(0.0, total_payable - total_paid)

                summaries.append({
                    "vendor_id": vid,
                    "name": v['name'],
                    "milk_type": v['milk_type'],
                    "rate_per_liter": v['rate_per_liter'],
                    "default_quantity": v['default_quantity'],
                    "previous_dues": round(prev_dues, 2),
                    "month_year": month_year,
                    "total_liters": round(total_liters, 2),
                    "total_bill": round(total_bill, 2),
                    "delivery_bill": round(total_bill, 2),
                    "total_payable": round(total_payable, 2),
                    "delivery_days": delivery_days,
                    "total_paid": round(total_paid, 2),
                    "balance_due": round(balance_due, 2)
                })

            return summaries

    def get_milk_deliveries(self, vendor_id: Optional[int] = None, month_year: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch deliveries for milkmen (optionally filtered by vendor or month, ordered latest first)."""
        query = """
            SELECT d.*, v.name as vendor_name 
            FROM milk_deliveries d
            LEFT JOIN milk_vendors v ON d.vendor_id = v.id
            WHERE 1=1
        """
        params = []
        if vendor_id:
            query += " AND d.vendor_id = ?"
            params.append(vendor_id)
        if month_year and month_year != "all":
            query += " AND strftime('%Y-%m', d.date) = ?"
            params.append(month_year)
        query += " ORDER BY d.date DESC, d.id DESC LIMIT ?"
        params.append(limit)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_milk_payment_history(self, vendor_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get past payments made to milkmen."""
        query = """
            SELECT p.*, v.name as vendor_name, v.milk_type
            FROM milk_payments p
            JOIN milk_vendors v ON p.vendor_id = v.id
        """
        params = []
        if vendor_id:
            query += " WHERE p.vendor_id = ?"
            params.append(vendor_id)
        query += " ORDER BY p.date DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def delete_milk_delivery(self, delivery_id: int) -> bool:
        """Deletes a milk delivery entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM milk_deliveries WHERE id = ?", (delivery_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_milk_payment(self, payment_id: int) -> bool:
        """Deletes a milk payment and linked transaction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT transaction_id FROM milk_payments WHERE id = ?", (payment_id,))
            row = cursor.fetchone()
            if row and row['transaction_id']:
                cursor.execute("DELETE FROM transactions WHERE id = ?", (row['transaction_id'],))
            cursor.execute("DELETE FROM milk_payments WHERE id = ?", (payment_id,))
            conn.commit()
            return cursor.rowcount > 0

    def export_all_data(self) -> Dict[str, Any]:
        """Exports all tables into a clean JSON-serializable dictionary for backup/transfer."""
        tables = [
            "transactions", "budgets", "category_budgets",
            "household_staff", "staff_payments",
            "milk_vendors", "milk_deliveries", "milk_payments",
            "merchant_category_rules"
        ]
        backup = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "data": {}
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for tbl in tables:
                try:
                    cursor.execute(f"SELECT * FROM {tbl}")
                    backup["data"][tbl] = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    backup["data"][tbl] = []
        return backup

    def import_all_data(self, backup: Dict[str, Any]) -> Dict[str, int]:
        """Restores data from a backup dictionary with smart deduplication."""
        counts = {"transactions": 0, "milk_deliveries": 0, "staff_payments": 0}
        if not isinstance(backup, dict):
            return counts
        data = backup.get("data") if "data" in backup and isinstance(backup["data"], dict) else backup
        if not data:
            return counts

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Import transactions
            for txn in data.get("transactions", []):
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO transactions 
                        (type, amount, category, payment_mode, account_or_card, merchant, date, notes, raw_sms, sms_hash, is_manual)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        txn.get("type", "DEBIT"),
                        float(txn.get("amount", 0)),
                        txn.get("category", "Others"),
                        txn.get("payment_mode", "UPI"),
                        txn.get("account_or_card"),
                        txn.get("merchant"),
                        txn.get("date"),
                        txn.get("notes"),
                        txn.get("raw_sms"),
                        txn.get("sms_hash"),
                        txn.get("is_manual", 0)
                    ))
                    if cursor.rowcount > 0:
                        counts["transactions"] += 1
                except Exception:
                    pass

            # Import milk deliveries
            for d in data.get("milk_deliveries", []):
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO milk_deliveries
                        (vendor_id, date, quantity_liters, rate_at_delivery, shift, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        int(d.get("vendor_id", 1)),
                        d.get("date"),
                        float(d.get("quantity_liters", 1.0)),
                        float(d.get("rate_at_delivery", 60.0)),
                        d.get("shift", "Daily"),
                        d.get("notes", "")
                    ))
                    if cursor.rowcount > 0:
                        counts["milk_deliveries"] += 1
                except Exception:
                    pass

            # Import milk payments
            for p in data.get("milk_payments", []):
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO milk_payments
                        (vendor_id, amount, date, month_for, payment_mode, notes, transaction_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        int(p.get("vendor_id", 1)),
                        float(p.get("amount", 0)),
                        p.get("date"),
                        p.get("month_for"),
                        p.get("payment_mode", "UPI"),
                        p.get("notes", ""),
                        p.get("transaction_id")
                    ))
                except Exception:
                    pass

            # Import budgets
            for b in data.get("budgets", []):
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO budgets (month_year, total_budget)
                        VALUES (?, ?)
                    """, (b.get("month_year"), float(b.get("total_budget", 0))))
                except Exception:
                    pass

            # Import merchant rules
            for r in data.get("merchant_category_rules", []):
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO merchant_category_rules (merchant_pattern, category)
                        VALUES (?, ?)
                    """, (r.get("merchant_pattern"), r.get("category")))
                except Exception:
                    pass

            # Import staff payments
            for sp in data.get("staff_payments", []):
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO staff_payments
                        (staff_id, amount, date, month_for, payment_mode, payment_type, notes, transaction_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        int(sp.get("staff_id", 1)),
                        float(sp.get("amount", 0)),
                        sp.get("date"),
                        sp.get("month_for"),
                        sp.get("payment_mode", "Cash"),
                        sp.get("payment_type", "Salary"),
                        sp.get("notes", ""),
                        sp.get("transaction_id")
                    ))
                    if cursor.rowcount > 0:
                        counts["staff_payments"] += 1
                except Exception:
                    pass

            conn.commit()
        return counts
