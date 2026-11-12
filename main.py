import os
import sys
from datetime import datetime

# Path setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.database.db_manager import DatabaseManager
from src.parsers.sms_parser import SMSParser
from src.parsers.categorizer import CATEGORY_METADATA, get_category_icon, get_category_color
from src.services.sms_service import SMSService

KIVY_IMPORT_ERROR = None
try:
    from kivy.lang import Builder
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivymd.app import MDApp
    from kivymd.uix.card import MDCard
    from kivymd.uix.label import MDLabel
    from kivymd.uix.list import (
        TwoLineAvatarIconListItem,
        ThreeLineAvatarIconListItem,
        IconLeftWidget,
        OneLineAvatarIconListItem,
        TwoLineListItem,
    )
    from kivymd.uix.dialog import MDDialog
    from kivymd.uix.button import MDFlatButton, MDRaisedButton
    from kivymd.uix.textfield import MDTextField
    from kivymd.uix.progressbar import MDProgressBar
    from src.ui.kv_layout import KV_STRING
    HAS_KIVY = True
except Exception as e:
    import traceback
    KIVY_IMPORT_ERROR = traceback.format_exc()
    HAS_KIVY = False


class ExpenseTrackerApp(MDApp if HAS_KIVY else object):

    def __init__(self, **kwargs):
        if HAS_KIVY:
            super().__init__(**kwargs)
        self.db = None
        self.sms_service = None
        self.dialog = None
        self.budget_dialog = None
        self.staff_dialog = None
        self.milk_dialog = None
        self.filter_category = "All"
        try:
            self.db = DatabaseManager()
            self.sms_service = SMSService(self.db)
        except Exception as e:
            import traceback
            print("INITIAL DB INIT ERROR:", traceback.format_exc())

    def build(self):
        try:
            # Guarantee database is initialized in case __init__ was early
            if self.db is None:
                db_path = None
                if hasattr(self, 'user_data_dir') and self.user_data_dir:
                    try:
                        os.makedirs(self.user_data_dir, exist_ok=True)
                        db_path = os.path.join(self.user_data_dir, "expenses.db")
                    except Exception:
                        pass
                self.db = DatabaseManager(db_path=db_path)
                self.sms_service = SMSService(self.db)

            self.theme_cls.primary_palette = "Indigo"
            self.theme_cls.accent_palette = "Amber"
            self.theme_cls.theme_style = "Light"
            self.title = "Smart Expense Tracker"
            screen = Builder.load_string(KV_STRING)
            return screen
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("FATAL BUILD ERROR:\n", err)
            from kivy.uix.scrollview import ScrollView
            from kivy.uix.label import Label
            sv = ScrollView()
            lbl = Label(text=f"App Load Error:\n\n{err}", size_hint_y=None, color=(1, 0.2, 0.2, 1), font_size="13sp")
            lbl.bind(texture_size=lbl.setter('size'))
            sv.add_widget(lbl)
            return sv

    def on_start(self):
        """Called when Kivy application starts - ultra-lightweight initial load."""
        try:
            self.update_dashboard_summary()
            self.populate_recent_transactions()
            self.populate_milk_cards()
            self.populate_staff_cards()
        except Exception as e:
            import traceback
            print("Error in initial load:", traceback.format_exc())

        # Load heavy history list and request permissions safely after UI is visible
        if HAS_KIVY:
            Clock.schedule_once(lambda dt: self._safe_post_start(), 1.0)

    def _safe_post_start(self):
        try:
            self.populate_all_transactions()
        except Exception as e:
            print("Error populating history:", e)
        try:
            self.sms_service.request_permissions(callback=self._on_permission_granted)
        except Exception as e:
            print("Error requesting permissions:", e)

    def _on_permission_granted(self, granted: bool):
        if granted and HAS_KIVY:
            # Safe sync on main thread via Clock
            Clock.schedule_once(lambda dt: self.sync_sms(full_scan=False), 0.8)

    def update_dashboard_summary(self):
        """Updates only the numeric dashboard spend cards & budget without recreating widgets (<5ms)."""
        if not hasattr(self, 'root') or not self.root or not hasattr(self.root, 'ids'):
            return
        try:
            stats = self.db.get_summary_statistics()
            ids = self.root.ids
            if 'lbl_total_spent' in ids:
                ids.lbl_total_spent.text = f"₹ {stats['total_debit']:,.2f}"
            if 'lbl_today_spent' in ids:
                ids.lbl_today_spent.text = f"Today: ₹ {stats['today_debit']:,.2f}"
            if 'lbl_week_spent' in ids:
                ids.lbl_week_spent.text = f"This Week: ₹ {stats['week_debit']:,.2f}"

            budget = stats.get("budget", 0.0)
            if 'progress_budget' in ids and 'lbl_budget_status' in ids:
                if budget > 0:
                    ids.progress_budget.value = min(100, stats["budget_percentage"])
                    ids.lbl_budget_status.text = f"Spent ₹ {stats['total_debit']:,.2f} of ₹ {budget:,.2f} ({stats['budget_percentage']:.1f}%)"
                    if stats["total_debit"] > budget:
                        ids.lbl_budget_status.theme_text_color = "Error"
                    else:
                        ids.lbl_budget_status.theme_text_color = "Secondary"
                else:
                    ids.progress_budget.value = 0
                    ids.lbl_budget_status.text = "No budget set (Tap pencil to set)"
        except Exception as e:
            print("Error updating dashboard:", e)

    def refresh_all_screens(self):
        """Full refresh across all views."""
        self.update_dashboard_summary()
        self.populate_recent_transactions()
        self.populate_all_transactions()
        self.populate_staff_cards()
        self.populate_milk_cards()
        if hasattr(self.root, 'ids') and 'list_category_analytics' in self.root.ids:
            stats = self.db.get_summary_statistics()
            self.populate_analytics(stats)

    def populate_recent_transactions(self):
        if not hasattr(self.root, 'ids') or 'list_recent_transactions' not in self.root.ids:
            return
        recent_list = self.root.ids.list_recent_transactions
        recent_list.clear_widgets()

        txns = self.db.get_transactions(limit=6)
        if not txns:
            item = TwoLineListItem(
                text="No transactions yet",
                secondary_text="Tap + to add cash expense or Sync to scan SMS"
            )
            recent_list.add_widget(item)
            return

        for txn in txns:
            is_debit = (txn["type"] == "DEBIT")
            sign = "-" if is_debit else "+"
            cat_icon = get_category_icon(txn["category"])
            cat_color = get_category_color(txn["category"])
            cat_display = txn["category"] if txn["category"] != "Others" else "Others (Tap to categorize)"

            item = TwoLineAvatarIconListItem(
                text=txn["merchant"] or "Expense",
                secondary_text=f"{sign}₹{txn['amount']:,.2f} | {cat_display} | {txn['date'][:10]}",
                on_release=lambda x, t=txn: self.show_transaction_detail(t)
            )

            icon = IconLeftWidget(
                icon=cat_icon,
                theme_text_color="Custom",
                text_color=cat_color
            )
            item.add_widget(icon)
            recent_list.add_widget(item)

    def populate_all_transactions(self, query: str = ""):
        if not hasattr(self.root, 'ids') or 'list_all_transactions' not in self.root.ids:
            return
        txns_list = self.root.ids.list_all_transactions
        txns_list.clear_widgets()

        # Fast limit: 35 items loads instantly in 50ms rather than freezing on 200 items
        txns = self.db.get_transactions(
            limit=35,
            search_query=query if query else None,
            category=self.filter_category if self.filter_category != "All" else None
        )

        if not txns:
            txns_list.add_widget(
                TwoLineListItem(
                    text="No transactions found",
                    secondary_text="Try changing search or filter"
                )
            )
            return

        for txn in txns:
            is_debit = (txn["type"] == "DEBIT")
            sign = "-" if is_debit else "+"
            cat_icon = get_category_icon(txn["category"])
            cat_color = get_category_color(txn["category"])
            cat_display = txn["category"] if txn["category"] != "Others" else "Others (Tap to categorize)"

            item = TwoLineAvatarIconListItem(
                text=f"{txn['merchant'] or 'Expense'} ({sign}₹{txn['amount']:,.2f})",
                secondary_text=f"{cat_display} • {txn['payment_mode']} • {txn['date'][:10]}",
                on_release=lambda x, t=txn: self.show_transaction_detail(t)
            )

            icon = IconLeftWidget(
                icon=cat_icon,
                theme_text_color="Custom",
                text_color=cat_color
            )
            item.add_widget(icon)
            txns_list.add_widget(item)

    # ----------------- COOK & HOUSE HELPER -----------------
    def populate_staff_cards(self):
        if not hasattr(self, 'root') or not self.root or not hasattr(self.root, 'ids'):
            return
        if 'list_staff_cards' not in self.root.ids:
            return
        staff_list = self.root.ids.list_staff_cards
        staff_list.clear_widgets()

        try:
            month_summary = self.db.get_staff_monthly_summary()
        except Exception as e:
            print("Error loading staff summary:", e)
            month_summary = []

        for s in month_summary:
            due = s.get('balance_due', 0.0)
            status = "Cleared" if due <= 0 else f"₹{due:,.0f} Due"
            role = s.get('role', 'Help')
            role_icon = "chef-hat" if role == "Cook" else "broom"
            name = s.get('name', 'Staff')
            salary = s.get('monthly_salary', 0.0)
            dues = s.get('previous_dues', 0.0)
            payable = s.get('total_payable', 0.0)
            paid = s.get('total_paid', 0.0)
            adv = s.get('advance_paid', 0.0)

            item = ThreeLineAvatarIconListItem(
                text=f"{name} ({role}) - {status}",
                secondary_text=f"Salary: ₹{salary:,.0f} + Dues: ₹{dues:,.0f} = ₹{payable:,.0f}",
                tertiary_text=f"Paid: ₹{paid:,.0f} (Adv: ₹{adv:,.0f}) • Tap to pay/edit",
                on_release=lambda x, st=s: self.open_staff_actions_dialog(st)
            )
            icon = IconLeftWidget(icon=role_icon)
            item.add_widget(icon)
            staff_list.add_widget(item)

        # Payment history
        if 'list_staff_history' in self.root.ids:
            history_list = self.root.ids.list_staff_history
            history_list.clear_widgets()
            try:
                payments = self.db.get_staff_payment_history(limit=10)
            except Exception as e:
                print("Error loading staff payments:", e)
                payments = []

            if not payments:
                history_list.add_widget(TwoLineListItem(text="No staff payments yet", secondary_text="Tap on a staff member above to pay"))
            else:
                for p in payments:
                    sname = p.get('staff_name', 'Staff')
                    pamt = p.get('amount', 0.0)
                    ptype = p.get('payment_type', 'Salary')
                    pdate = (p.get('date') or '')[:10]
                    pmode = p.get('payment_mode', 'Cash')
                    pnotes = p.get('notes') or ''
                    item = TwoLineListItem(
                        text=f"{sname} - ₹{pamt:,.2f} ({ptype})",
                        secondary_text=f"{pdate} via {pmode} {('• ' + pnotes) if pnotes else ''}"
                    )
                    history_list.add_widget(item)

    def open_staff_actions_dialog(self, staff_data):
        """Action options for Cook / House Helper."""
        box = BoxLayout(orientation="vertical", spacing="12dp", size_hint_y=None, height="140dp")

        btn_pay = MDRaisedButton(
            text=f"Record Payment (₹{staff_data['balance_due']:,.0f} Due)",
            md_bg_color=[0.15, 0.65, 0.45, 1],
            size_hint_x=1,
            on_release=lambda x: (self.staff_dialog.dismiss(), self.open_staff_payment_dialog(staff_data))
        )
        btn_edit = MDRaisedButton(
            text="Edit Salary & Previous Dues",
            size_hint_x=1,
            on_release=lambda x: (self.staff_dialog.dismiss(), self.open_edit_staff_dialog(staff_data))
        )

        box.add_widget(btn_pay)
        box.add_widget(btn_edit)

        self.staff_dialog = MDDialog(
            title=f"Manage: {staff_data['name']} ({staff_data['role']})",
            type="custom",
            content_cls=box,
            buttons=[MDFlatButton(text="CLOSE", on_release=lambda x: self.staff_dialog.dismiss())]
        )
        self.staff_dialog.open()

    def open_edit_staff_dialog(self, staff_data):
        """Dialog to update salary, previous dues, and phone for staff."""
        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="210dp")
        txt_salary = MDTextField(hint_text="Monthly Salary (₹)", text=str(staff_data['monthly_salary']), input_filter="float")
        txt_dues = MDTextField(hint_text="Previous Dues (₹)", text=str(staff_data.get('previous_dues', 0)), input_filter="float")
        txt_phone = MDTextField(hint_text="Phone Number (Optional)", text=str(staff_data.get('phone') or ""))

        box.add_widget(txt_salary)
        box.add_widget(txt_dues)
        box.add_widget(txt_phone)

        def save_staff_edit(btn):
            try:
                salary = float(txt_salary.text.strip() or 0)
                dues = float(txt_dues.text.strip() or 0)
                phone = txt_phone.text.strip()
                self.db.update_staff_member(
                    staff_id=staff_data['id'],
                    monthly_salary=salary,
                    previous_dues=dues,
                    phone=phone
                )
                self.dialog.dismiss()
                self.populate_staff_cards()
                self.update_dashboard_summary()
            except ValueError:
                pass

        self.dialog = MDDialog(
            title=f"Edit {staff_data['name']}'s Salary & Dues",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE CHANGES", on_release=save_staff_edit)
            ]
        )
        self.dialog.open()

    def open_staff_payment_dialog(self, staff_data):
        """Dialog to pay Cook or House Helper."""
        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="200dp")
        txt_amt = MDTextField(hint_text="Amount (₹)", text=str(staff_data['balance_due']) if staff_data['balance_due'] > 0 else "500", input_filter="float")
        txt_type = MDTextField(hint_text="Type: Salary / Advance", text="Salary" if staff_data['balance_due'] > 0 else "Advance")
        txt_notes = MDTextField(hint_text="Notes (Optional)")

        box.add_widget(txt_amt)
        box.add_widget(txt_type)
        box.add_widget(txt_notes)

        def save_pay(btn):
            try:
                amt = float(txt_amt.text.strip())
                ptype = txt_type.text.strip() or "Salary"
                notes = txt_notes.text.strip()
                self.db.log_staff_payment(
                    staff_id=staff_data['id'],
                    amount=amt,
                    payment_type=ptype,
                    notes=notes
                )
                self.staff_dialog.dismiss()
                self.populate_staff_cards()
                self.update_dashboard_summary()
            except ValueError:
                pass

        self.staff_dialog = MDDialog(
            title=f"Pay {staff_data['name']} ({staff_data['role']})",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.staff_dialog.dismiss()),
                MDRaisedButton(text="RECORD PAYMENT", on_release=save_pay)
            ]
        )
        self.staff_dialog.open()

    def open_add_staff_dialog(self):
        """Add new staff (e.g. Driver, Maid, Cook)."""
        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="250dp")
        txt_name = MDTextField(hint_text="Name (e.g. Ramesh)")
        txt_role = MDTextField(hint_text="Role: Cook / House Helper / Driver")
        txt_salary = MDTextField(hint_text="Monthly Salary (₹)", input_filter="float")
        txt_dues = MDTextField(hint_text="Previous Dues (₹, Optional)", text="0", input_filter="float")

        box.add_widget(txt_name)
        box.add_widget(txt_role)
        box.add_widget(txt_salary)
        box.add_widget(txt_dues)

        def save_new_staff(btn):
            try:
                name = txt_name.text.strip()
                role = txt_role.text.strip() or "Other"
                salary = float(txt_salary.text.strip() or 0)
                dues = float(txt_dues.text.strip() or 0)
                if name:
                    self.db.add_staff_member(name=name, role=role, monthly_salary=salary, previous_dues=dues)
                    self.dialog.dismiss()
                    self.populate_staff_cards()
                    self.update_dashboard_summary()
            except ValueError:
                pass

        self.dialog = MDDialog(
            title="Register Household Staff",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="ADD", on_release=save_new_staff)
            ]
        )
        self.dialog.open()

    # ----------------- DUAL MILKMEN TRACKER -----------------
    def populate_milk_cards(self):
        if not hasattr(self, 'root') or not self.root or not hasattr(self.root, 'ids'):
            return
        if 'list_milk_vendors' not in self.root.ids:
            return
        vendors_list = self.root.ids.list_milk_vendors
        vendors_list.clear_widgets()

        try:
            summaries = self.db.get_milk_monthly_summary()
        except Exception as e:
            print("Error loading milk summaries:", e)
            summaries = []

        for v in summaries:
            v_due = v.get('balance_due', 0.0)
            v_name = v.get('name', 'Milkman')
            v_rate = v.get('rate_per_liter', 0.0)
            v_liters = v.get('total_liters', 0.0)
            v_bill = v.get('delivery_bill', 0.0)
            v_dues = v.get('previous_dues', 0.0)
            v_payable = v.get('total_payable', 0.0)
            v_paid = v.get('total_paid', 0.0)

            item = ThreeLineAvatarIconListItem(
                text=f"{v_name} (₹{v_due:,.0f} Due)",
                secondary_text=f"Rate: ₹{v_rate:.0f}/L | {v_liters:.1f}L = ₹{v_bill:,.0f} + Dues: ₹{v_dues:,.0f}",
                tertiary_text=f"Total: ₹{v_payable:,.0f} | Paid: ₹{v_paid:,.0f} • Tap to manage",
                on_release=lambda x, ven=v: self.open_milk_actions_dialog(ven)
            )
            icon = IconLeftWidget(icon="bottle-wine-outline")
            item.add_widget(icon)
            vendors_list.add_widget(item)

        # Recent Deliveries (across both milkmen)
        if 'list_milk_deliveries' in self.root.ids:
            deliv_list = self.root.ids.list_milk_deliveries
            deliv_list.clear_widgets()
            all_delivs = []
            for v in summaries:
                try:
                    all_delivs.extend(self.db.get_milk_deliveries(vendor_id=v['vendor_id']))
                except Exception:
                    pass
            all_delivs.sort(key=lambda x: str(x.get('date', '')), reverse=True)

            if not all_delivs:
                deliv_list.add_widget(TwoLineListItem(text="No milk deliveries recorded yet", secondary_text="Tap a milkman above to log daily delivery"))
            else:
                for d in all_delivs[:8]:
                    d_qty = float(d.get('quantity_liters') or 0.0)
                    d_rate = float(d.get('rate_at_delivery') or 0.0)
                    d_date = (d.get('date') or '')[:10]
                    d_vname = d.get('vendor_name', 'Milkman')
                    d_notes = d.get('notes') or ''
                    deliv_list.add_widget(TwoLineListItem(
                        text=f"{d_date} - {d_qty:.1f} L ({d_vname})",
                        secondary_text=f"Cost: ₹{d_qty * d_rate:,.0f} {('• ' + d_notes) if d_notes else ''}"
                    ))

    def open_milk_actions_dialog(self, vendor_data):
        """Dialog to quickly log milk delivery, record payment, or edit price per liter and dues."""
        box = BoxLayout(orientation="vertical", spacing="12dp", size_hint_y=None, height="240dp")
        
        btn_quick_add = MDRaisedButton(
            text=f"+{vendor_data['default_quantity']} Liters Today",
            size_hint_x=1,
            on_release=lambda x: self.quick_log_milk(vendor_data['vendor_id'], vendor_data['default_quantity'])
        )
        btn_custom_add = MDFlatButton(
            text="Log Custom Liters / Date",
            size_hint_x=1,
            on_release=lambda x: self.open_custom_milk_delivery(vendor_data)
        )
        btn_pay = MDRaisedButton(
            text=f"Pay Milkman (₹{vendor_data['balance_due']:,.0f} Due)",
            md_bg_color=[0.15, 0.65, 0.45, 1],
            size_hint_x=1,
            on_release=lambda x: self.open_milk_payment_dialog(vendor_data)
        )
        btn_edit = MDRaisedButton(
            text=f"Edit Price/Liter & Dues (₹{vendor_data['rate_per_liter']}/L)",
            size_hint_x=1,
            on_release=lambda x: (self.milk_dialog.dismiss(), self.open_edit_milk_dialog(vendor_data))
        )

        box.add_widget(btn_quick_add)
        box.add_widget(btn_custom_add)
        box.add_widget(btn_pay)
        box.add_widget(btn_edit)

        self.milk_dialog = MDDialog(
            title=f"Manage: {vendor_data['name']}",
            type="custom",
            content_cls=box,
            buttons=[MDFlatButton(text="CLOSE", on_release=lambda x: self.milk_dialog.dismiss())]
        )
        self.milk_dialog.open()

    def open_edit_milk_dialog(self, vendor_data):
        """Dialog to update rate per liter, default quantity, and previous dues for milkman."""
        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="210dp")
        txt_rate = MDTextField(hint_text="Price per Liter (₹)", text=str(vendor_data['rate_per_liter']), input_filter="float")
        txt_dues = MDTextField(hint_text="Previous Dues (₹)", text=str(vendor_data.get('previous_dues', 0)), input_filter="float")
        txt_qty = MDTextField(hint_text="Daily Default Liters (e.g. 1.5)", text=str(vendor_data['default_quantity']), input_filter="float")

        box.add_widget(txt_rate)
        box.add_widget(txt_dues)
        box.add_widget(txt_qty)

        def save_milk_edit(btn):
            try:
                rate = float(txt_rate.text.strip() or 0)
                dues = float(txt_dues.text.strip() or 0)
                qty = float(txt_qty.text.strip() or 1.0)
                self.db.update_milk_vendor(
                    vendor_id=vendor_data['vendor_id'],
                    rate_per_liter=rate,
                    previous_dues=dues,
                    default_quantity=qty
                )
                self.dialog.dismiss()
                self.populate_milk_cards()
                self.update_dashboard_summary()
            except ValueError:
                pass

        self.dialog = MDDialog(
            title=f"Edit Rates - {vendor_data['name']}",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE CHANGES", on_release=save_milk_edit)
            ]
        )
        self.dialog.open()

    def quick_log_milk(self, vendor_id, qty):
        self.db.log_milk_delivery(vendor_id=vendor_id, quantity_liters=qty)
        if self.milk_dialog:
            self.milk_dialog.dismiss()
        self.populate_milk_cards()
        self.update_dashboard_summary()

    def open_custom_milk_delivery(self, vendor_data):
        if self.milk_dialog:
            self.milk_dialog.dismiss()

        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="120dp")
        txt_qty = MDTextField(hint_text="Quantity in Liters (e.g. 1.5)", text=str(vendor_data['default_quantity']), input_filter="float")
        box.add_widget(txt_qty)

        def save_deliv(btn):
            try:
                qty = float(txt_qty.text.strip())
                self.db.log_milk_delivery(vendor_id=vendor_data['vendor_id'], quantity_liters=qty)
                self.dialog.dismiss()
                self.populate_milk_cards()
                self.update_dashboard_summary()
            except ValueError:
                pass

        self.dialog = MDDialog(
            title=f"Log Milk - {vendor_data['name']}",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE", on_release=save_deliv)
            ]
        )
        self.dialog.open()

    def open_milk_payment_dialog(self, vendor_data):
        if self.milk_dialog:
            self.milk_dialog.dismiss()

        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="150dp")
        txt_amt = MDTextField(hint_text="Amount Paid (₹)", text=str(vendor_data['balance_due']) if vendor_data['balance_due'] > 0 else "", input_filter="float")
        txt_notes = MDTextField(hint_text="Notes (Optional)")
        box.add_widget(txt_amt)
        box.add_widget(txt_notes)

        def save_milk_pay(btn):
            try:
                amt = float(txt_amt.text.strip())
                notes = txt_notes.text.strip()
                self.db.log_milk_payment(vendor_id=vendor_data['vendor_id'], amount=amt, notes=notes)
                self.dialog.dismiss()
                self.populate_milk_cards()
                self.update_dashboard_summary()
            except ValueError:
                pass

        self.dialog = MDDialog(
            title=f"Pay {vendor_data['name']}",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="RECORD PAYMENT", on_release=save_milk_pay)
            ]
        )
        self.dialog.open()

    # ----------------- ANALYTICS -----------------
    def populate_analytics(self, stats: Optional[dict] = None):
        if not hasattr(self, 'root') or not self.root or not hasattr(self.root, 'ids'):
            return
        if 'list_category_analytics' not in self.root.ids:
            return

        if stats is None:
            stats = self.db.get_summary_statistics()

        cat_list = self.root.ids.list_category_analytics
        cat_list.clear_widgets()
        total_debit = stats.get("total_debit", 0.0)

        for item in stats.get("categories", []):
            pct = (item["total"] / total_debit * 100) if total_debit > 0 else 0
            list_item = TwoLineAvatarIconListItem(
                text=f"{item['category']} ({pct:.1f}%)",
                secondary_text=f"Total: ₹ {item['total']:,.2f}  •  {item['count']} transactions"
            )
            icon = IconLeftWidget(
                icon=get_category_icon(item["category"]),
                theme_text_color="Custom",
                text_color=get_category_color(item["category"])
            )
            list_item.add_widget(icon)
            cat_list.add_widget(list_item)

        mode_list = self.root.ids.list_payment_modes
        mode_list.clear_widgets()
        for item in stats.get("payment_modes", []):
            pct = (item["total"] / total_debit * 100) if total_debit > 0 else 0
            list_item = TwoLineAvatarIconListItem(
                text=f"{item['payment_mode']} ({pct:.1f}%)",
                secondary_text=f"Total: ₹ {item['total']:,.2f}  •  {item['count']} transactions"
            )
            mode_icon = "contactless-payment" if item["payment_mode"] == "UPI" else (
                "credit-card" if "Card" in item["payment_mode"] else "cash"
            )
            icon = IconLeftWidget(icon=mode_icon)
            list_item.add_widget(icon)
            mode_list.add_widget(list_item)

    def filter_transactions(self, query: str):
        self.populate_all_transactions(query=query)

    def sync_sms(self, full_scan: bool = False):
        """Executes SMS inbox scan safely on main thread via Clock without threading JNI crash."""
        if hasattr(self, '_sync_active') and self._sync_active:
            return
        self._sync_active = True

        scan_type = "Historical Scan" if full_scan else "Quick Sync"
        if hasattr(self, 'root') and self.root and hasattr(self.root, 'ids'):
            if 'lbl_sms_sync_status' in self.root.ids:
                self.root.ids.lbl_sms_sync_status.text = f"{scan_type} in progress..."
            if 'lbl_sync_log' in self.root.ids:
                self.root.ids.lbl_sync_log.text = f"[{datetime.now().strftime('%H:%M:%S')}] Scanning SMS..."

        def do_sync(dt=None):
            try:
                limit = None if full_scan else 100
                result = self.sms_service.sync_sms_transactions(limit=limit, full_scan=full_scan)
                self._on_sync_finished(result, scan_type)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._on_sync_error(str(e))

        if HAS_KIVY:
            Clock.schedule_once(do_sync, 0.1)
        else:
            do_sync()

    def _on_sync_finished(self, result: dict, scan_type: str):
        self._sync_active = False
        if hasattr(self, 'root') and self.root and hasattr(self.root, 'ids'):
            status_msg = f"{scan_type}: Scanned {result['scanned']} SMS. Added {result['added']} new transactions ({result['duplicates']} duplicates skipped)."
            if 'lbl_sms_sync_status' in self.root.ids:
                self.root.ids.lbl_sms_sync_status.text = f"{result['added']} new transactions added"
            if 'lbl_sync_log' in self.root.ids:
                self.root.ids.lbl_sync_log.text = f"[{datetime.now().strftime('%H:%M:%S')}] {status_msg}"
        self.update_dashboard_summary()
        self.populate_recent_transactions()

    def _on_sync_error(self, error_str: str):
        self._sync_active = False
        if hasattr(self, 'root') and self.root and hasattr(self.root, 'ids'):
            if 'lbl_sms_sync_status' in self.root.ids:
                self.root.ids.lbl_sms_sync_status.text = "Sync error"
            if 'lbl_sync_log' in self.root.ids:
                self.root.ids.lbl_sync_log.text = f"[{datetime.now().strftime('%H:%M:%S')}] Error reading SMS: {error_str}"

    def parse_custom_sms(self):
        """Parses manually pasted SMS in the SMS Scanner tab."""
        text = self.root.ids.txt_custom_sms.text.strip()
        if not text:
            return

        parsed = SMSParser.parse(text, sender="Custom Input")
        if parsed:
            txn_id = self.db.add_transaction(**parsed)
            if txn_id:
                self.root.ids.lbl_sync_log.text = (
                    f"Successfully parsed & added ₹{parsed['amount']} to {parsed['category']} ({parsed['merchant']})!"
                )
                self.root.ids.txt_custom_sms.text = ""
                self.populate_recent_transactions()
                self.update_dashboard_summary()
            else:
                self.root.ids.lbl_sync_log.text = "This transaction is already saved in your database (duplicate)."
        else:
            self.root.ids.lbl_sync_log.text = "Could not parse monetary transaction from this text. Ensure it has amount and debit/credit alert."

    def open_add_expense_dialog(self):
        """Opens modal dialog to log cash or manual expenses with custom or standard categories."""
        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="300dp")

        txt_amount = MDTextField(hint_text="Amount (e.g. 150)", input_filter="float")
        txt_merchant = MDTextField(hint_text="Merchant / Paid To (e.g. Gym, Grocery, Chai)")
        txt_category = MDTextField(
            hint_text="Category (Type custom or pick standard)",
            text="Food & Dining",
            helper_text="Enter any custom category (e.g. Gym, Books, Car, Pet Care)",
            helper_text_mode="on_focus"
        )
        txt_mode = MDTextField(hint_text="Mode: Cash / UPI / Card", text="Cash")
        txt_notes = MDTextField(hint_text="Notes (Optional)")

        box.add_widget(txt_amount)
        box.add_widget(txt_merchant)
        box.add_widget(txt_category)
        box.add_widget(txt_mode)
        box.add_widget(txt_notes)

        def save_expense(btn):
            try:
                amt = float(txt_amount.text.strip())
                if amt <= 0:
                    return
            except ValueError:
                return

            merchant = txt_merchant.text.strip() or "Cash Expense"
            mode = txt_mode.text.strip() or "Cash"
            category = txt_category.text.strip() or "Others"
            notes = txt_notes.text.strip()

            self.db.add_transaction(
                amount=amt,
                category=category,
                payment_mode=mode,
                merchant=merchant,
                notes=notes,
                is_manual=1
            )
            if merchant and merchant != "Cash Expense" and category != "Others":
                self.db.set_merchant_category_rule(merchant, category, update_existing_others=False)

            self.dialog.dismiss()
            self.populate_recent_transactions()
            self.update_dashboard_summary()

        self.dialog = MDDialog(
            title="Log New Expense",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE", on_release=save_expense)
            ]
        )
        self.dialog.open()

    def open_set_budget_dialog(self):
        """Dialog to set monthly budget."""
        stats = self.db.get_summary_statistics()
        current_budget = str(stats.get("budget", ""))

        txt_budget = MDTextField(
            hint_text="Monthly Budget (₹)",
            text=current_budget if current_budget != "0.0" else "",
            input_filter="float"
        )

        def save_budget(btn):
            try:
                amt = float(txt_budget.text.strip())
                month_year = datetime.now().strftime("%Y-%m")
                self.db.set_budget(month_year, amt)
                self.budget_dialog.dismiss()
                self.update_dashboard_summary()
            except ValueError:
                pass

        self.budget_dialog = MDDialog(
            title="Set Monthly Budget",
            type="custom",
            content_cls=txt_budget,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.budget_dialog.dismiss()),
                MDRaisedButton(text="SAVE", on_release=save_budget)
            ]
        )
        self.budget_dialog.open()

    def open_category_filter_dialog(self):
        """Filter transactions by standard or user-defined custom categories."""
        categories = ["All"] + self.db.get_all_categories()
        box = BoxLayout(orientation="vertical", spacing="6dp", size_hint_y=None, height="320dp")

        filter_dialog = None

        def set_cat(cat_name):
            self.filter_category = cat_name
            filter_dialog.dismiss()
            self.populate_all_transactions()

        for cat in categories[:12]:
            btn = MDFlatButton(text=cat, size_hint_x=1, on_release=lambda x, c=cat: set_cat(c))
            box.add_widget(btn)

        filter_dialog = MDDialog(
            title="Filter by Category",
            type="custom",
            content_cls=box,
            buttons=[MDFlatButton(text="CLOSE", on_release=lambda x: filter_dialog.dismiss())]
        )
        filter_dialog.open()

    def show_transaction_detail(self, txn: dict):
        """Shows full details of a transaction with options to delete or change/assign custom category."""
        body = (
            f"Merchant: {txn.get('merchant', 'N/A')}\n"
            f"Amount: ₹ {txn.get('amount', 0):,.2f}\n"
            f"Category: {txn.get('category', 'Others')}\n"
            f"Mode: {txn.get('payment_mode', 'UPI')}\n"
            f"Account/Card: {txn.get('account_or_card', 'N/A')}\n"
            f"Date: {txn.get('date', 'N/A')}\n"
            f"Notes: {txn.get('notes', 'None')}\n"
        )
        if txn.get('raw_sms'):
            body += f"\nOriginal SMS:\n{txn['raw_sms']}"

        detail_dialog = None

        def delete_txn(btn):
            self.db.delete_transaction(txn["id"])
            detail_dialog.dismiss()
            self.populate_all_transactions()
            self.populate_recent_transactions()
            self.update_dashboard_summary()

        def edit_cat(btn):
            detail_dialog.dismiss()
            self.open_edit_category_dialog(txn)

        detail_dialog = MDDialog(
            title="Transaction Details",
            text=body,
            buttons=[
                MDFlatButton(text="DELETE", theme_text_color="Error", on_release=delete_txn),
                MDFlatButton(text="CHANGE CATEGORY", theme_text_color="Custom", text_color=[0.25, 0.45, 0.9, 1], on_release=edit_cat),
                MDRaisedButton(text="CLOSE", on_release=lambda x: detail_dialog.dismiss())
            ]
        )
        detail_dialog.open()

    def open_edit_category_dialog(self, txn: dict):
        """Assign any custom or standard category to a transaction and remember it for future SMS."""
        box = BoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="170dp")
        curr_cat = txn.get('category', 'Others')
        txt_cat = MDTextField(
            hint_text="Category (e.g. Gym, Pet Care, Books, Car)",
            text="" if curr_cat == "Others" else curr_cat,
            helper_text="Future SMS from this merchant will also auto-use this category",
            helper_text_mode="persistent"
        )
        box.add_widget(txt_cat)

        def save_cat(btn):
            new_cat = txt_cat.text.strip() or "Others"
            self.db.update_transaction(txn["id"], category=new_cat)
            merchant = txn.get("merchant")
            if merchant and merchant != "Cash Expense":
                self.db.set_merchant_category_rule(merchant, new_cat, update_existing_others=True)
            self.dialog.dismiss()
            self.populate_all_transactions()
            self.populate_recent_transactions()
            self.update_dashboard_summary()

        self.dialog = MDDialog(
            title=f"Set Category ({txn.get('merchant', 'Expense')})",
            type="custom",
            content_cls=box,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE CATEGORY", on_release=save_cat)
            ]
        )
        self.dialog.open()


if __name__ == '__main__':
    if HAS_KIVY:
        try:
            ExpenseTrackerApp().run()
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("FATAL CRASH IN RUN():\n", err)
            try:
                from kivy.app import App
                from kivy.uix.scrollview import ScrollView
                from kivy.uix.label import Label
                class CrashReporterApp(App):
                    def build(self):
                        sv = ScrollView()
                        lbl = Label(
                            text=f"Startup Error:\n\n{err}\n\nPlease take a screenshot of this error.",
                            size_hint_y=None,
                            color=(1, 0.2, 0.2, 1),
                            font_size="13sp"
                        )
                        lbl.bind(texture_size=lbl.setter('size'))
                        sv.add_widget(lbl)
                        return sv
                CrashReporterApp().run()
            except Exception:
                pass
    else:
        is_android = ('ANDROID_ARGUMENT' in os.environ or 'PYTHON_SERVICE_ARGUMENT' in os.environ)
        if is_android:
            print("KIVY LOAD ERROR:\n", KIVY_IMPORT_ERROR)
            try:
                from kivy.app import App
                from kivy.uix.scrollview import ScrollView
                from kivy.uix.label import Label
                class FallbackApp(App):
                    def build(self):
                        sv = ScrollView()
                        lbl = Label(
                            text=f"Android Startup Failed:\n\n{KIVY_IMPORT_ERROR}",
                            size_hint_y=None,
                            color=(1, 0.2, 0.2, 1),
                            font_size="13sp"
                        )
                        lbl.bind(texture_size=lbl.setter('size'))
                        sv.add_widget(lbl)
                        return sv
                FallbackApp().run()
            except Exception:
                pass
        else:
            print("="*60)
            print("Kivy / KivyMD is not yet installed in this Python environment.")
            print("To run the desktop Kivy app:")
            print("   pip install -r requirements.txt")
            print("   python main.py")
            print("="*60)
            print("\nStarting the built-in Instant Web / Mobile Preview Dashboard instead...")
            print("This allows you to test the exact same SQLite database, SMS parser,")
            print("and expense tracking interface immediately from your PC or phone browser!")
            print("="*60)
            from web_preview import run_server
            run_server()
