import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from .categorizer import categorize_transaction


class SMSParser:
    """
    Parses transaction SMS messages from Indian banks, credit cards, and UPI apps
    (HDFC, SBI, ICICI, Axis, Kotak, PNB, IndusInd, Paytm, PhonePe, CRED, etc.).
    """

    # Common OTP / Promotional non-transactional patterns to ignore
    OTP_PATTERNS = [
        r'\botp\b',
        r'one\s*time\s*password',
        r'verification\s*code',
        r'security\s*code',
        r'do\s*not\s*share',
        r'is\s*your\s*secret\s*otp',
        r'mandate\s*created'
    ]

    # Amount extraction regex: matches Rs., INR, ₹ with optional commas and decimals
    AMOUNT_REGEX = re.compile(
        r'(?:rs\.?|inr|₹)\s*([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)',
        re.IGNORECASE
    )

    # Debit vs Credit keywords
    DEBIT_REGEX = re.compile(
        r'\b(?:debited|debit|spent|paid|purchase|deducted|withdrawn|sent|transferred|txn\s+of)\b',
        re.IGNORECASE
    )
    CREDIT_REGEX = re.compile(
        r'\b(?:credited|credit|received|refund|refunded|deposited|cashback|salary)\b',
        re.IGNORECASE
    )

    # Account / Card number patterns
    ACCOUNT_REGEX = re.compile(
        r'(?:a\/c|acct|acc|account|card)\s*(?:no\.?)?\s*(?:ending\s*(?:with|in)?|xx+|\*+)?\s*([0-9xX*]{3,6})',
        re.IGNORECASE
    )

    # Merchant extraction patterns
    MERCHANT_PATTERNS = [
        # to VPA swiggy@icici or to VPA xyz
        re.compile(r'(?:to\s+vpa|vpa)\s+([a-zA-Z0-9.\-_@]+)', re.IGNORECASE),
        # at MERCHANT on/Bal/.
        re.compile(r'\bat\s+([A-Za-z0-9\s&.\'-]+?)(?:\s+(?:on|via|using|avl|bal|ref|at|\.|\,)|$)', re.IGNORECASE),
        # to MERCHANT on/via/ref/.
        re.compile(r'\bto\s+([A-Za-z0-9\s&.\'-]+?)(?:\s+(?:on|via|using|avl|bal|ref|at|\.|\,)|$)', re.IGNORECASE),
        # UPI/431298765432/Blinkit/
        re.compile(r'upi\/(?:[0-9]+\/)?([a-zA-Z0-9\s&.\'-]+?)(?:\/|\.|\,|$|\s+bal)', re.IGNORECASE),
        # Info: BIL*NETFLIX or Info: SWIGGY
        re.compile(r'info\s*:\s*([A-Za-z0-9*_\-\s]+?)(?:\.|\,|$|\s+avl|\s+available)', re.IGNORECASE),
        # transfer to MERCHANT
        re.compile(r'transfer\s+to\s+([A-Za-z0-9\s&.\'-]+?)(?:\.|\,|$|\s+avl|\s+ref)', re.IGNORECASE),
        # Paid Rs X to MERCHANT
        re.compile(r'paid\s+(?:rs\.?|inr|₹)?\s*[0-9.,]+\s+to\s+([A-Za-z0-9\s&.\'-]+?)(?:\s+for|\s+on|\.|\,|$)', re.IGNORECASE)
    ]

    # Date pattern matchers
    DATE_PATTERNS = [
        # 11-Nov-26 or 11-Nov-2026 or 11/11/2026
        (r'(\d{1,2})[-/]([A-Za-z]{3})[-/](\d{2,4})', '%d-%b-%Y'),
        (r'(\d{1,2})([A-Za-z]{3})(\d{2,4})', '%d%b%Y'),
        (r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', '%d-%m-%Y'),
    ]

    @classmethod
    def is_transaction_sms(cls, text: str) -> bool:
        """Determines if the text is an actual transaction SMS and not an OTP or promo."""
        if not text or not isinstance(text, str):
            return False

        lower_text = text.lower()

        # If it's strictly an OTP message without transaction confirmation, ignore
        for otp_pat in cls.OTP_PATTERNS:
            if re.search(otp_pat, lower_text):
                # Only ignore if it does not contain explicit "debited" or "spent"
                if not (cls.DEBIT_REGEX.search(lower_text) or cls.CREDIT_REGEX.search(lower_text)):
                    return False
                # If it has "OTP for transaction of Rs...", that's still an unconfirmed auth OTP
                if "is your otp" in lower_text or "do not share" in lower_text or "secret otp" in lower_text:
                    return False

        # Must have an amount
        if not cls.AMOUNT_REGEX.search(text):
            return False

        # Must have debit or credit keyword
        has_debit = bool(cls.DEBIT_REGEX.search(text))
        has_credit = bool(cls.CREDIT_REGEX.search(text))

        return has_debit or has_credit

    @classmethod
    def extract_amount(cls, text: str) -> Optional[float]:
        """Extracts transaction monetary amount."""
        matches = cls.AMOUNT_REGEX.findall(text)
        if not matches:
            return None

        # Clean commas and parse first valid amount
        for match in matches:
            try:
                cleaned = match.replace(',', '').strip()
                val = float(cleaned)
                # Ignore amounts like 0.00 or unrealistic amounts
                if val > 0:
                    return round(val, 2)
            except ValueError:
                continue
        return None

    @classmethod
    def extract_type(cls, text: str) -> str:
        """Determines if transaction is DEBIT or CREDIT."""
        lower_text = text.lower()
        if cls.CREDIT_REGEX.search(lower_text) and not ("debited" in lower_text and "refund" not in lower_text):
            return "CREDIT"
        return "DEBIT"

    @classmethod
    def extract_payment_mode(cls, text: str) -> str:
        """Identifies payment mode (UPI, Credit Card, Debit Card, Net Banking)."""
        lower = text.lower()
        if "upi" in lower or "vpa" in lower or "gpay" in lower or "phonepe" in lower or "paytm qr" in lower:
            return "UPI"
        if "credit card" in lower or "credit card ending" in lower or "spent on card" in lower or "avl lmt" in lower:
            return "Credit Card"
        if "debit card" in lower or "atm" in lower:
            return "Debit Card"
        if "card ending" in lower or "card no" in lower:
            return "Credit Card"  # Default assumption for generic card spent
        if "netbanking" in lower or "inb" in lower or "neft" in lower or "rtgs" in lower or "imps" in lower:
            return "Net Banking"
        return "UPI"  # Most common everyday transaction mode

    @classmethod
    def extract_account_info(cls, text: str) -> str:
        """Extracts masked account or card ending digits."""
        match = cls.ACCOUNT_REGEX.search(text)
        if match:
            raw_digits = match.group(1).replace('x', '').replace('X', '').replace('*', '')
            if raw_digits:
                return f"**{raw_digits}"

        # Check for card ending
        card_match = re.search(r'card\s+(?:ending\s*)?([0-9]{4})', text, re.IGNORECASE)
        if card_match:
            return f"Card **{card_match.group(1)}"

        return "Main Account"

    @classmethod
    def extract_merchant(cls, text: str) -> str:
        """Extracts merchant or payee name."""
        for pattern in cls.MERCHANT_PATTERNS:
            match = pattern.search(text)
            if match:
                raw_merchant = match.group(1).strip()
                # Clean up common garbage
                raw_merchant = re.sub(r'^(bil\*|pg\*|paytm\*|razorpay\*|ccavenue\*)', '', raw_merchant, flags=re.IGNORECASE)
                raw_merchant = re.sub(r'[@\-_].*$', '', raw_merchant)  # Clean UPI handles e.g. swiggy@icici -> swiggy
                cleaned = raw_merchant.strip().strip('.').strip('-')
                
                # Check for validity
                if cleaned and len(cleaned) >= 2 and not cleaned.lower() in [
                    "your", "account", "bank", "card", "vpa", "upi", "inr", "rs", "avl", "bal", "ref"
                ]:
                    # Capitalize nicely
                    return cleaned.title()

        return "UPI / General Merchant"

    @classmethod
    def extract_date(cls, text: str, fallback_timestamp: Optional[str] = None) -> str:
        """Extracts date from text or returns fallback/current datetime."""
        for pattern, date_fmt in cls.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    d, m, y = match.groups()
                    if len(y) == 2:
                        y = f"20{y}"
                    date_str = f"{int(d):02d}-{m.title()}-{y}"
                    dt = datetime.strptime(date_str, "%d-%b-%Y" if not m.isdigit() else "%d-%m-%Y")
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

        if fallback_timestamp:
            return fallback_timestamp
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def parse(
        cls,
        body: str,
        sender: str = "",
        timestamp_str: Optional[str] = None,
        custom_rules: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parses an SMS into a structured transaction dictionary.
        Returns None if message is not an expense or transaction SMS.
        """
        if not cls.is_transaction_sms(body):
            return None

        amount = cls.extract_amount(body)
        if not amount:
            return None

        txn_type = cls.extract_type(body)
        payment_mode = cls.extract_payment_mode(body)
        account = cls.extract_account_info(body)
        merchant = cls.extract_merchant(body)
        date = cls.extract_date(body, fallback_timestamp=timestamp_str)
        category = categorize_transaction(
            merchant=merchant,
            notes="",
            raw_text=body,
            custom_rules=custom_rules
        )

        return {
            "type": txn_type,
            "amount": amount,
            "category": category,
            "payment_mode": payment_mode,
            "account_or_card": account,
            "merchant": merchant,
            "date": date,
            "notes": f"Auto-detected from {sender}" if sender else "Auto-detected from SMS",
            "raw_sms": body,
            "is_manual": 0
        }
