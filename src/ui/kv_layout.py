import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

KV_STRING = '''
#:import get_color_from_hex kivy.utils.get_color_from_hex

<TransactionItem@TwoLineAvatarIconListItem>:
    merchant: ""
    category: ""
    amount: ""
    date_str: ""
    mode: ""
    icon_name: "currency-inr"
    icon_color: "#607D8B"
    amount_color: [0.85, 0.1, 0.1, 1]

    text: root.merchant
    secondary_text: f"{root.category} • {root.mode} • {root.date_str}"
    
    IconLeftWidget:
        icon: root.icon_name
        theme_text_color: "Custom"
        text_color: get_color_from_hex(root.icon_color)

    RightLabel:
        text: root.amount
        font_style: "Subtitle1"
        theme_text_color: "Custom"
        text_color: root.amount_color
        size_hint_x: None
        width: "110dp"
        halign: "right"

<RightLabel@MDLabel>:

MDScreen:
    md_bg_color: app.theme_cls.bg_normal

    MDBottomNavigation:
        id: bottom_nav
        panel_color: app.theme_cls.bg_dark
        selected_color_background: 0, 0, 0, 0
        text_color_active: app.theme_cls.primary_color

        # ---------------- 1. DASHBOARD TAB ----------------
        MDBottomNavigationItem:
            name: 'screen_dashboard'
            text: 'Overview'
            icon: 'view-dashboard'

            MDBoxLayout:
                orientation: 'vertical'

                MDTopAppBar:
                    title: "Expense Tracker"
                    elevation: 2
                    right_action_items: [["sync", lambda x: app.sync_sms(False)], ["clock-rotate-left", lambda x: app.sync_sms(True)]]

                ScrollView:
                    MDBoxLayout:
                        orientation: 'vertical'
                        padding: ["16dp", "16dp", "16dp", "80dp"]
                        spacing: "16dp"
                        adaptive_height: True

                        # Total Spend Card
                        MDCard:
                            orientation: "vertical"
                            padding: "16dp"
                            spacing: "8dp"
                            radius: [16, 16, 16, 16]
                            elevation: 3
                            size_hint_y: None
                            height: "140dp"
                            md_bg_color: app.theme_cls.primary_color

                            MDLabel:
                                text: "Total Spent This Month"
                                font_style: "Subtitle2"
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 0.8

                            MDLabel:
                                id: lbl_total_spent
                                text: "₹ 0.00"
                                font_style: "H4"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1

                            MDBoxLayout:
                                orientation: "horizontal"
                                MDLabel:
                                    id: lbl_today_spent
                                    text: "Today: ₹ 0.00"
                                    font_style: "Caption"
                                    theme_text_color: "Custom"
                                    text_color: 1, 1, 1, 0.9
                                MDLabel:
                                    id: lbl_week_spent
                                    text: "This Week: ₹ 0.00"
                                    font_style: "Caption"
                                    theme_text_color: "Custom"
                                    text_color: 1, 1, 1, 0.9

                        # Budget Card
                        MDCard:
                            orientation: "vertical"
                            padding: "16dp"
                            spacing: "6dp"
                            radius: [12, 12, 12, 12]
                            elevation: 1
                            size_hint_y: None
                            height: "105dp"
                            line_color: 0.8, 0.8, 0.8, 0.3

                            MDBoxLayout:
                                orientation: "horizontal"
                                MDLabel:
                                    text: "Monthly Budget"
                                    font_style: "Subtitle1"
                                    bold: True
                                MDIconButton:
                                    icon: "pencil-outline"
                                    font_size: "18sp"
                                    on_release: app.open_set_budget_dialog()

                            MDProgressBar:
                                id: progress_budget
                                value: 0
                                max: 100
                                color: app.theme_cls.primary_color

                            MDLabel:
                                id: lbl_budget_status
                                text: "No budget set (Tap pencil to set)"
                                font_style: "Caption"
                                theme_text_color: "Secondary"

                        # Quick Action Banner
                        MDCard:
                            orientation: "horizontal"
                            padding: "12dp"
                            spacing: "12dp"
                            radius: [12, 12, 12, 12]
                            size_hint_y: None
                            height: "70dp"
                            md_bg_color: 0.15, 0.65, 0.45, 0.12
                            line_color: 0.15, 0.65, 0.45, 0.3

                            MDIcon:
                                icon: "message-processing-outline"
                                theme_text_color: "Custom"
                                text_color: 0.15, 0.65, 0.45, 1
                                size_hint_x: None
                                width: "32dp"
                                pos_hint: {"center_y": 0.5}

                            MDBoxLayout:
                                orientation: "vertical"
                                MDLabel:
                                    text: "Auto SMS Tracker"
                                    bold: True
                                    font_style: "Subtitle2"
                                MDLabel:
                                    id: lbl_sms_sync_status
                                    text: "Scan all past & new UPI/Bank alerts"
                                    font_style: "Caption"
                                    theme_text_color: "Secondary"

                            MDRaisedButton:
                                text: "Scan All"
                                md_bg_color: 0.15, 0.65, 0.45, 1
                                size_hint_x: None
                                width: "80dp"
                                pos_hint: {"center_y": 0.5}
                                on_release: app.sync_sms(True)

                        # Recent Transactions Header
                        MDBoxLayout:
                            orientation: "horizontal"
                            size_hint_y: None
                            height: "30dp"
                            MDLabel:
                                text: "Recent Transactions"
                                font_style: "H6"
                                bold: True
                            MDTextButton:
                                text: "See all"
                                theme_text_color: "Primary"
                                on_release: bottom_nav.switch_tab('screen_transactions')

                        # List of recent transactions
                        MDList:
                            id: list_recent_transactions

        # ---------------- 2. TRANSACTIONS TAB ----------------
        MDBottomNavigationItem:
            name: 'screen_transactions'
            text: 'History'
            icon: 'format-list-bulleted'

            MDBoxLayout:
                orientation: 'vertical'

                MDTopAppBar:
                    title: "Transaction History"
                    elevation: 2

                MDBoxLayout:
                    orientation: 'horizontal'
                    padding: ["12dp", "8dp", "12dp", "4dp"]
                    spacing: "8dp"
                    size_hint_y: None
                    height: "56dp"

                    MDTextField:
                        id: search_field
                        hint_text: "Search merchant, note, or card..."
                        icon_right: "magnify"
                        mode: "round"
                        size_hint_x: 0.8
                        on_text: app.filter_transactions(self.text)

                    MDIconButton:
                        icon: "filter-variant"
                        pos_hint: {"center_y": 0.5}
                        on_release: app.open_category_filter_dialog()

                ScrollView:
                    MDList:
                        id: list_all_transactions
                        padding: ["0dp", "0dp", "0dp", "80dp"]

        # ---------------- 3. COOK & HOUSE HELPER TAB ----------------
        MDBottomNavigationItem:
            name: 'screen_staff'
            text: 'Cook & Help'
            icon: 'account-group'

            MDBoxLayout:
                orientation: 'vertical'

                MDTopAppBar:
                    title: "Cook & House Helper"
                    elevation: 2
                    right_action_items: [["plus", lambda x: app.open_add_staff_dialog()]]

                ScrollView:
                    MDBoxLayout:
                        orientation: 'vertical'
                        padding: ["16dp", "16dp", "16dp", "80dp"]
                        spacing: "16dp"
                        adaptive_height: True

                        MDLabel:
                            text: "Monthly Salary & Dues"
                            font_style: "H6"
                            bold: True

                        MDList:
                            id: list_staff_cards

                        MDSeparator:

                        MDLabel:
                            text: "Staff Payment History"
                            font_style: "Subtitle1"
                            bold: True

                        MDList:
                            id: list_staff_history

        # ---------------- 4. DUAL MILKMEN TAB ----------------
        MDBottomNavigationItem:
            name: 'screen_milk'
            text: 'Milkmen'
            icon: 'cup-water'

            MDBoxLayout:
                orientation: 'vertical'

                MDTopAppBar:
                    title: "Dual Milkmen Tracker"
                    elevation: 2

                ScrollView:
                    MDBoxLayout:
                        orientation: 'vertical'
                        padding: ["16dp", "16dp", "16dp", "80dp"]
                        spacing: "16dp"
                        adaptive_height: True

                        MDLabel:
                            text: "Milk Vendors (Monthly Bill & Dues)"
                            font_style: "H6"
                            bold: True

                        MDList:
                            id: list_milk_vendors

                        MDSeparator:

                        MDLabel:
                            text: "Recent Daily Deliveries"
                            font_style: "Subtitle1"
                            bold: True

                        MDList:
                            id: list_milk_deliveries

        # ---------------- 5. ANALYTICS & SMS TAB ----------------
        MDBottomNavigationItem:
            name: 'screen_analytics'
            text: 'Analytics'
            icon: 'chart-pie'

            MDBoxLayout:
                orientation: 'vertical'

                MDTopAppBar:
                    title: "Analytics & SMS Scanner"
                    elevation: 2

                ScrollView:
                    MDBoxLayout:
                        orientation: 'vertical'
                        padding: ["16dp", "16dp", "16dp", "80dp"]
                        spacing: "16dp"
                        adaptive_height: True

                        # Category Spending
                        MDLabel:
                            text: "Category Breakdown"
                            font_style: "H6"
                            bold: True

                        MDList:
                            id: list_category_analytics

                        MDSeparator:

                        # Payment Modes
                        MDLabel:
                            text: "Payment Modes"
                            font_style: "H6"
                            bold: True

                        MDList:
                            id: list_payment_modes

                        MDSeparator:

                        # SMS Scan Card
                        MDCard:
                            orientation: "vertical"
                            padding: "16dp"
                            spacing: "10dp"
                            radius: [12, 12, 12, 12]
                            adaptive_height: True
                            line_color: 0.8, 0.8, 0.8, 0.3

                            MDLabel:
                                text: "Scan Existing Phone SMS"
                                font_style: "Subtitle1"
                                bold: True

                            MDLabel:
                                text: "Reads all existing bank & UPI transaction SMS alerts on your phone. Duplicate messages are automatically filtered."
                                font_style: "Body2"
                                theme_text_color: "Secondary"

                            MDBoxLayout:
                                orientation: "horizontal"
                                spacing: "10dp"
                                size_hint_y: None
                                height: "40dp"

                                MDRaisedButton:
                                    text: "Quick Sync"
                                    icon: "sync"
                                    on_release: app.sync_sms(False)

                                MDRaisedButton:
                                    text: "Scan All Past SMS"
                                    icon: "clock-rotate-left"
                                    md_bg_color: 0.15, 0.65, 0.45, 1
                                    on_release: app.sync_sms(True)

                            MDLabel:
                                id: lbl_sync_log
                                text: "Ready to scan."
                                font_style: "Caption"
                                theme_text_color: "Secondary"

    # Floating Action Button for Manual Entry (Cash / Other)
    MDFloatingActionButton:
        icon: "plus"
        elevation: 4
        pos_hint: {"right": 0.95, "y": 0.10}
        md_bg_color: app.theme_cls.primary_color
        on_release: app.open_add_expense_dialog()
'''

class ExpenseTrackerApp:
    """Wrapper class so the app logic can run in KivyMD or fallback seamlessly."""
    pass
