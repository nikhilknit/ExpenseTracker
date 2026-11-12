import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.database.db_manager import DatabaseManager


class TestHouseholdAndMilkTracking(unittest.TestCase):

    def setUp(self):
        self.test_db_path = os.path.join(BASE_DIR, "test_household.db")
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.db = DatabaseManager(db_path=self.test_db_path)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_default_staff_and_milkmen_seeded(self):
        staff = self.db.get_staff_members()
        self.assertGreaterEqual(len(staff), 2)
        roles = [s['role'] for s in staff]
        self.assertIn('Cook', roles)
        self.assertIn('House Helper', roles)

        vendors = self.db.get_milk_vendors()
        self.assertEqual(len(vendors), 2)
        names = [v['name'] for v in vendors]
        self.assertTrue(any('Sundar' in n for n in names))
        self.assertTrue(any('Jain Mandir' in n for n in names))

    def test_staff_payment_logging(self):
        staff = self.db.get_staff_members()
        cook = [s for s in staff if s['role'] == 'Cook'][0]

        # Log an advance payment of 1000
        pay_id1 = self.db.log_staff_payment(
            staff_id=cook['id'],
            amount=1000.0,
            date="2026-11-05",
            month_for="2026-11",
            payment_mode="Cash",
            payment_type="Advance",
            notes="Diwali festival advance"
        )
        self.assertIsNotNone(pay_id1)

        # Log salary payment of 3000
        pay_id2 = self.db.log_staff_payment(
            staff_id=cook['id'],
            amount=3000.0,
            date="2026-11-10",
            month_for="2026-11",
            payment_mode="UPI",
            payment_type="Salary",
            notes="Remaining salary"
        )
        self.assertIsNotNone(pay_id2)

        # Verify monthly summary
        summary = self.db.get_staff_monthly_summary(month_year="2026-11")
        cook_summary = [s for s in summary if s['id'] == cook['id']][0]
        self.assertEqual(cook_summary['salary_paid'], 3000.0)
        self.assertEqual(cook_summary['advance_paid'], 1000.0)
        self.assertEqual(cook_summary['total_paid'], 4000.0)
        self.assertEqual(cook_summary['balance_due'], 0.0)

        # Verify synced to main transactions
        txns = self.db.get_transactions(category="Transfers & Rent")
        self.assertEqual(len(txns), 2)

    def test_dual_milkmen_tracking(self):
        vendors = self.db.get_milk_vendors()
        m1 = vendors[0]
        m2 = vendors[1]

        # Log 3 days of delivery for Milkman 1 (1.5L @ 60 = 90/day)
        self.db.log_milk_delivery(vendor_id=m1['id'], date="2026-11-01", quantity_liters=1.5)
        self.db.log_milk_delivery(vendor_id=m1['id'], date="2026-11-02", quantity_liters=1.5)
        self.db.log_milk_delivery(vendor_id=m1['id'], date="2026-11-03", quantity_liters=2.0) # extra on 3rd

        # Log 2 days of delivery for Milkman 2 (1.0L @ 70 = 70/day)
        self.db.log_milk_delivery(vendor_id=m2['id'], date="2026-11-01", quantity_liters=1.0)
        self.db.log_milk_delivery(vendor_id=m2['id'], date="2026-11-02", quantity_liters=1.0)

        # Record partial payment for Milkman 1 (Rs 200 via UPI)
        self.db.log_milk_payment(
            vendor_id=m1['id'],
            amount=200.0,
            date="2026-11-03",
            month_for="2026-11",
            payment_mode="UPI",
            notes="Weekly partial payment"
        )

        summaries = self.db.get_milk_monthly_summary(month_year="2026-11")
        m1_sum = [s for s in summaries if s['vendor_id'] == m1['id']][0]
        m2_sum = [s for s in summaries if s['vendor_id'] == m2['id']][0]

        # M1: 1.5 + 1.5 + 2.0 = 5.0 Liters. 5.0 * 60 = 300. Paid: 200. Balance: 100
        self.assertEqual(m1_sum['total_liters'], 5.0)
        self.assertEqual(m1_sum['total_bill'], 300.0)
        self.assertEqual(m1_sum['total_paid'], 200.0)
        self.assertEqual(m1_sum['balance_due'], 100.0)

        # M2: 1.0 + 1.0 = 2.0 Liters. 2.0 * 70 = 140. Paid: 0. Balance: 140
        self.assertEqual(m2_sum['total_liters'], 2.0)
        self.assertEqual(m2_sum['total_bill'], 140.0)
        self.assertEqual(m2_sum['total_paid'], 0.0)
        self.assertEqual(m2_sum['balance_due'], 140.0)

    def test_edit_rates_and_previous_dues(self):
        # Test editing staff salary and previous dues
        staff = self.db.get_staff_members()
        cook = [s for s in staff if s['role'] == 'Cook'][0]
        self.db.update_staff_member(cook['id'], monthly_salary=4500.0, previous_dues=500.0)

        summary = self.db.get_staff_monthly_summary(month_year="2026-11")
        cook_sum = [s for s in summary if s['id'] == cook['id']][0]
        self.assertEqual(cook_sum['monthly_salary'], 4500.0)
        self.assertEqual(cook_sum['previous_dues'], 500.0)
        self.assertEqual(cook_sum['total_payable'], 5000.0)
        self.assertEqual(cook_sum['balance_due'], 5000.0)

        # Test editing milk vendor price per liter and previous dues
        vendors = self.db.get_milk_vendors()
        sundar = [v for v in vendors if 'Sundar' in v['name']][0]
        self.db.update_milk_vendor(sundar['id'], rate_per_liter=65.0, previous_dues=300.0, default_quantity=2.0)

        self.db.log_milk_delivery(vendor_id=sundar['id'], date="2026-11-01", quantity_liters=2.0)
        m_summaries = self.db.get_milk_monthly_summary(month_year="2026-11")
        sundar_sum = [s for s in m_summaries if s['vendor_id'] == sundar['id']][0]
        self.assertEqual(sundar_sum['rate_per_liter'], 65.0)
        self.assertEqual(sundar_sum['previous_dues'], 300.0)
        # 2.0L * 65 = 130 + 300 prev dues = 430 total payable
        self.assertEqual(sundar_sum['delivery_bill'], 130.0)
        self.assertEqual(sundar_sum['total_payable'], 430.0)
        self.assertEqual(sundar_sum['balance_due'], 430.0)

    def test_yesterday_custom_milk_and_expense_logging(self):
        from datetime import datetime, timedelta
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        month_str = yesterday_str[:7]

        vendors = self.db.get_milk_vendors()
        sundar = [v for v in vendors if 'Sundar' in v['name']][0]

        # Log 1 liter milk yesterday
        del_id = self.db.log_milk_delivery(
            vendor_id=sundar['id'],
            date=yesterday_str,
            quantity_liters=1.0,
            notes="1 litre milk yesterday"
        )
        self.assertIsNotNone(del_id)

        # Check delivery history
        delivs = self.db.get_milk_deliveries(vendor_id=sundar['id'], month_year=month_str)
        yest_deliv = [d for d in delivs if d['date'] == yesterday_str][0]
        self.assertEqual(yest_deliv['quantity_liters'], 1.0)
        self.assertEqual(yest_deliv['notes'], "1 litre milk yesterday")

        # Check balance due
        m_sums = self.db.get_milk_monthly_summary(month_year=month_str)
        s_sum = [s for s in m_sums if s['vendor_id'] == sundar['id']][0]
        expected_bill = 1.0 * sundar['rate_per_liter']
        self.assertGreaterEqual(s_sum['balance_due'], expected_bill)

        # Log custom expense for yesterday
        txn_id = self.db.add_transaction(
            amount=250.0,
            merchant="Local Kirana",
            category="Groceries",
            payment_mode="Cash",
            date=f"{yesterday_str} 14:30:00",
            notes="Vegetables bought yesterday",
            is_manual=1
        )
        self.assertIsNotNone(txn_id)

        txns = self.db.get_transactions(limit=10, search_query="Local Kirana")
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0]['amount'], 250.0)
        self.assertTrue(txns[0]['date'].startswith(yesterday_str))


if __name__ == "__main__":
    unittest.main()
