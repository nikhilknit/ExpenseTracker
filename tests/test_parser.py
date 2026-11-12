import os
import sys
import json
import unittest

# Ensure src is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.parsers.sms_parser import SMSParser
from src.database.db_manager import DatabaseManager


class TestSMSParser(unittest.TestCase):

    def setUp(self):
        self.sample_file = os.path.join(os.path.dirname(__file__), "sample_sms.json")
        with open(self.sample_file, "r") as f:
            self.samples = json.load(f)

    def test_sample_parsing(self):
        for item in self.samples:
            body = item["body"]
            sender = item.get("sender", "")

            if item.get("is_otp"):
                self.assertFalse(
                    SMSParser.is_transaction_sms(body),
                    f"OTP message should not be treated as a completed transaction: {body}"
                )
                continue

            parsed = SMSParser.parse(body, sender=sender)
            self.assertIsNotNone(parsed, f"Failed to parse SMS: {body}")

            if "expected_amount" in item:
                self.assertEqual(parsed["amount"], item["expected_amount"], f"Amount mismatch in: {body}")

            if "expected_mode" in item:
                self.assertEqual(parsed["payment_mode"], item["expected_mode"], f"Mode mismatch in: {body}")

            if "expected_category" in item:
                self.assertEqual(parsed["category"], item["expected_category"], f"Category mismatch in: {body}")

            if "expected_type" in item:
                self.assertEqual(parsed["type"], item["expected_type"], f"Type mismatch in: {body}")

    def test_indian_bank_real_sms_patterns(self):
        """Tests real-world Indian bank transaction alerts that include OTP security warnings."""
        sms_samples = [
            ("Dear Customer, INR 350.00 debited from A/c **1234 on 12-Nov-26 towards SWIGGY. Do not share your OTP with anyone.", 350.0, "DEBIT", "Swiggy"),
            ("Update: An amount of INR 1,250.00 has been debited from your A/c **4321 on 12-Nov-26 towards ZOMATO. Avl bal: INR 15,200.00. Do not share OTP.", 1250.0, "DEBIT", "Zomato"),
            ("Sent Rs.320.00 from Kotak Bank AC X1234 to milkman@upi on 12-Nov-26. Ref 123456789. Never share your password/OTP.", 320.0, "DEBIT", "Milkman"),
            ("ALERT: INR 450.00 debited from Axis Bank A/c no. XX1234 on 12-11-26 14:30:10 via UPI: 123456789:PhonePe. Bal: INR 12,000.00", 450.0, "DEBIT", "Phonepe"),
            ("Dear SBI User, your A/C 1234 is debited by Rs.500.00 on 12Nov26 transfer to UPI/DR/123456/Swiggy. If not done by you, SMS BLOCK", 500.0, "DEBIT", "Swiggy"),
            ("Rs.150 paid to Sundar Milk via UPI transaction ID 987654321.", 150.0, "DEBIT", "Sundar Milk"),
        ]

        for body, exp_amt, exp_type, exp_merchant in sms_samples:
            self.assertTrue(SMSParser.is_transaction_sms(body), f"Should recognize as valid transaction: {body}")
            parsed = SMSParser.parse(body, sender="BANK")
            self.assertIsNotNone(parsed, f"Failed to parse: {body}")
            self.assertEqual(parsed["amount"], exp_amt, f"Amount failed for {body}")
            self.assertEqual(parsed["type"], exp_type, f"Type failed for {body}")
            if exp_merchant:
                self.assertEqual(parsed["merchant"], exp_merchant, f"Merchant failed for {body}")

        # Verification that pure OTP authentication prompts are still strictly rejected
        otp_samples = [
            "123456 is your secret OTP for transaction of Rs 1500.00 at Amazon. Do not share this OTP with anyone.",
            "OTP for transaction of Rs 200.00 is 987654. Valid for 10 mins.",
            "Use OTP 432109 to complete payment of Rs 150.",
            "Your one time password is 332211 for purchase of Rs 200. Do not disclose."
        ]
        for otp in otp_samples:
            self.assertFalse(SMSParser.is_transaction_sms(otp), f"Should reject pure OTP auth prompt: {otp}")

    def test_database_integration(self):
        test_db_path = os.path.join(BASE_DIR, "test_expenses.db")
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        db = DatabaseManager(db_path=test_db_path)

        # Insert manual transaction
        txn_id = db.add_transaction(
            amount=50.0,
            category="Food & Dining",
            payment_mode="Cash",
            merchant="Chai Tapri",
            notes="Morning Tea"
        )
        self.assertIsNotNone(txn_id)

        # Insert SMS parsed transaction
        parsed = SMSParser.parse(
            "Alert: Rs. 450.00 debited from HDFC Bank A/C ending 1234 to VPA swiggy@icici on 11-Nov-26 via UPI.",
            sender="AD-HDFCBK"
        )
        self.assertIsNotNone(parsed)
        sms_txn_id = db.add_transaction(**parsed)
        self.assertIsNotNone(sms_txn_id)

        # Deduplication check: re-inserting exact same SMS should return None
        duplicate_id = db.add_transaction(**parsed)
        self.assertIsNone(duplicate_id, "Duplicate SMS should be ignored by hash")

        # Check summary
        stats = db.get_summary_statistics()
        self.assertEqual(stats["total_debit"], 500.0)
        self.assertEqual(stats["txn_count"], 2)

        # Clean up test db
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    def test_custom_category_and_merchant_learning(self):
        test_db_path = os.path.join(BASE_DIR, "test_custom_cats.db")
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        db = DatabaseManager(db_path=test_db_path)

        # 1. Unclassified SMS defaults to 'Others'
        sms_text = "Alert: Rs. 1200.00 debited from SBI A/C ending 5678 to VPA cultfit@upi on 10-Nov-26 via UPI."
        parsed = SMSParser.parse(sms_text, sender="SBI")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["category"], "Others")
        txn_id = db.add_transaction(**parsed)
        self.assertIsNotNone(txn_id)

        # 2. User customizes category to 'Fitness & Gym' and saves rule
        db.update_transaction(txn_id, category="Fitness & Gym")
        db.set_merchant_category_rule("cultfit", "Fitness & Gym", update_existing_others=True)

        updated_txn = db.get_transactions(limit=1)[0]
        self.assertEqual(updated_txn["category"], "Fitness & Gym")

        # 3. New SMS from 'cultfit' should now auto-categorize to 'Fitness & Gym'
        new_sms = "Alert: Rs. 2500.00 debited from SBI A/C ending 5678 to VPA cultfit@upi on 12-Nov-26 via UPI."
        learned_rules = db.get_all_merchant_rules()
        self.assertIn("cultfit", learned_rules)
        parsed_new = SMSParser.parse(new_sms, sender="SBI", custom_rules=learned_rules)
        self.assertIsNotNone(parsed_new)
        self.assertEqual(parsed_new["category"], "Fitness & Gym")

        # 4. User adds manual expense with a brand new custom category 'Pet Care'
        manual_id = db.add_transaction(
            amount=400.0,
            merchant="Dr. Dog Clinic",
            category="Pet Care",
            payment_mode="Cash"
        )
        self.assertIsNotNone(manual_id)

        # 5. get_all_categories() includes standard + custom categories
        all_cats = db.get_all_categories()
        self.assertIn("Fitness & Gym", all_cats)
        self.assertIn("Pet Care", all_cats)

        # 6. get_summary_statistics() groups by the custom categories
        stats = db.get_summary_statistics()
        cat_names = [c["category"] for c in stats["categories"]]
        self.assertIn("Fitness & Gym", cat_names)
        self.assertIn("Pet Care", cat_names)

        if os.path.exists(test_db_path):
            os.remove(test_db_path)


if __name__ == "__main__":
    unittest.main()
