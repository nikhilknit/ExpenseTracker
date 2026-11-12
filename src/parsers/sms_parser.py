import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from .categorizer import categorize_transaction


class SMSParser:
    """
    Parses transaction SMS messages from Indian banks, credit cards, and UPI apps
    (HDFC, SBI, ICICI, Axis, Kotak, PNB, IndusInd, Paytm, PhonePe, CRED, etc.).
    """

    # OTP / Authentication verification requests to ignore (distinguished from debit alerts with security warnings)
    OTP_PROMPT_REGEX = re.compile(
        r'\b(?:is\s+your\s+(?:secret\s+)?otp|otp\s+(?:for\s+.*?\s+)?is\s+[0-9]{4,8}|use\s+otp\s+[0-9]{4,8}|your\s+otp\s+(?:for\s+.*?\s+)?is\s+[0-9]{4,8}|one\s*time\s*password\s+is\s+[0-9]{4,8}|verification\s*code\s+is\s+[0-9]{4,8})\b',
        re.IGNORECASE
    )

    # Amount extraction regex: matches Rs., INR, ₹, Re with optional commas and decimals
    AMOUNT_REGEX = re.compile(
        r'(?:rs\.?|inr|₹|re\.?)\s*([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)',
        re.IGNORECASE
    )
    AMOUNT_SUFFIX_REGEX = re.compile(
        r'\b([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)\s*(?:rs\.?|inr|₹|re\.?)\b',
        re.IGNORECASE
    )
    AMOUNT_VERB_REGEX = re.compile(
        r'(?:debited\s+(?:by|for|with)|credited\s+(?:with|by)|spent|paid)\s+([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)',
        re.IGNORECASE
    )
    ACTION_CUE_REGEX = re.compile(
        r'\b(?P<credit>credited|credit(?!\s+card)|received|refund(?:ed)?|deposited|cashback|salary|deposit)\b'
        r'|\b(?P<debit>debited|debit|spent|paid|purchase|deducted|withdrawn|sent|transferred|'
        r'transfer\s+(?:to|of)|txn\s+of|payment\s+(?:of|to|done)|autopay|swiped|charged)\b',
        re.IGNORECASE
    )
    BALANCE_CONTEXT_REGEX = re.compile(
        r'\b(?:available|avail|avl|closing|current|account|a/c)?\s*(?:balance|bal|limit|lmt|due)\b',
        re.IGNORECASE
    )

    # Account / Card number patterns
    ACCOUNT_REGEX = re.compile(
        r'(?:a\/c|acct|acc|account|card)\s*(?:no\.?)?\s*(?:ending\s*(?:with|in)?|xx+|\*+)?\s*([0-9xX*]{3,6})',
        re.IGNORECASE
    )

    # Merchant extraction patterns
    MERCHANT_PATTERNS = [
        # UPI/DR/123456/Merchant or UPI/CR/123456/Merchant or UPI:123456:Merchant or UPI/123456/Merchant
        re.compile(r'upi\s*[:\/\-]\s*(?:p2m\/|p2a\/|dr\/|cr\/)?(?:[0-9]+\s*[:\/\-]\s*)?([a-zA-Z0-9\s&\'-]+?)(?:[:\/\-.]|\s+bal|\s+avl|\s+ref|\s+on|\s+at|$)', re.IGNORECASE),
        # to VPA or to UPI ID: to swiggy@icici or to milkman@upi or vpa xyz@okhdfc
        re.compile(r'(?:to\s+vpa|vpa|to\s+upi|to)\s+([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)', re.IGNORECASE),
        # Paid Rs X to MERCHANT
        re.compile(r'paid\s+(?:rs\.?|inr|₹|re\.?)?\s*[0-9.,]+\s+to\s+([A-Za-z0-9\s&\'-]+?)(?:\.|\,|\s+(?:for|on|via|using|ref)|$)', re.IGNORECASE),
        # to MERCHANT on/via/ref/using/.
        re.compile(r'\bto\s+([A-Za-z0-9\s&\'-]+?)(?:\.|\,|\s+(?:on|via|using|avl|bal|ref|at)|$)', re.IGNORECASE),
        # at MERCHANT on/via/using
        re.compile(r'\bat\s+([A-Za-z0-9\s&\'-]+?)(?:\.|\,|\s+(?:on|via|using|avl|bal|ref|at)|$)', re.IGNORECASE),
        # towards MERCHANT
        re.compile(r'\btowards\s+([A-Za-z0-9\s&\'-]+?)(?:\.|\,|\s+(?:on|via|using|avl|bal|ref|at)|$)', re.IGNORECASE),
        # Info: BIL*NETFLIX or Info: SWIGGY
        re.compile(r'info\s*:\s*([A-Za-z0-9*_\-\s]+?)(?:\.|\,|$|\s+avl|\s+available)', re.IGNORECASE),
        # transfer to MERCHANT
        re.compile(r'transfer\s+to\s+([A-Za-z0-9\s&\'-]+?)(?:\.|\,|\s+(?:avl|ref|on)|$)', re.IGNORECASE),
        # spent on MERCHANT
        re.compile(r'spent\s+on\s+([A-Za-z0-9\s&\'-]+?)(?:\.|\,|\s+(?:on|via|using|avl|bal|ref|at)|$)', re.IGNORECASE)
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

        # If it's an explicit OTP authorization request, ignore
        if cls.OTP_PROMPT_REGEX.search(text):
            return False

        # Must have an amount
        if not cls.extract_amount(text):
            return False

        # Ignore mentions of "credit card" unless there is a transaction action.
        return bool(cls.ACTION_CUE_REGEX.search(text))

    @classmethod
    def _find_amount_candidate(cls, text: str) -> Optional[Tuple[int, int, float, int]]:
        candidates = []
        patterns = (
            (cls.AMOUNT_REGEX, 0),
            (cls.AMOUNT_SUFFIX_REGEX, 0),
            (cls.AMOUNT_VERB_REGEX, 1),
        )
        for pattern, priority in patterns:
            for match in pattern.finditer(text):
                try:
                    value = float(match.group(1).replace(',', '').strip())
                except ValueError:
                    continue
                if value > 0:
                    candidates.append((match.start(1), match.end(1), value, priority))

        cues = list(cls.ACTION_CUE_REGEX.finditer(text))

        def candidate_score(candidate):
            start, end, _, priority = candidate
            midpoint = (start + end) / 2
            cue_distance = min(
                (max(cue.start() - midpoint, midpoint - cue.end(), 0) for cue in cues),
                default=float("inf")
            )
            context_start = max(0, start - 36)
            balance_context = cls.BALANCE_CONTEXT_REGEX.search(text[context_start:start])
            return (cue_distance + (1000 if balance_context else 0), priority)

        return min(candidates, key=candidate_score) if candidates else None

    @classmethod
    def extract_amount(cls, text: str) -> Optional[float]:
        """Extracts the amount closest to a transaction action, not an account balance."""
        candidate = cls._find_amount_candidate(text)
        return round(candidate[2], 2) if candidate else None

    @classmethod
    def extract_type(cls, text: str) -> str:
        """Determines if transaction is DEBIT or CREDIT."""
        amount_candidate = cls._find_amount_candidate(text)
        reference_position = amount_candidate[0] if amount_candidate else 0
        cues = list(cls.ACTION_CUE_REGEX.finditer(text))
        if not cues:
            return "DEBIT"

        nearest_cue = min(
            cues,
            key=lambda cue: max(
                cue.start() - reference_position,
                reference_position - cue.end(),
                0
            )
        )
        return "CREDIT" if nearest_cue.group("credit") else "DEBIT"

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
                
                # Check for validity against common non-merchant stop words
                if cleaned and len(cleaned) >= 2 and not cleaned.lower() in [
                    "your", "account", "bank", "card", "vpa", "upi", "inr", "rs", "re", "avl", "bal", "ref", "dr", "cr", "sms", "block"
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
