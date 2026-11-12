import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from ..parsers.sms_parser import SMSParser

logger = logging.getLogger(__name__)


class SMSService:
    """
    Handles reading SMS messages from Android's Telephony ContentProvider
    via PyJNIus when running on Android, and provides mock/file fallback for Desktop.
    """

    def __init__(self, db_manager):
        self.db = db_manager
        self.is_android = self._check_is_android()

    @staticmethod
    def _check_is_android() -> bool:
        try:
            from kivy.utils import platform
            return platform == 'android'
        except ImportError:
            return False

    def request_permissions(self, callback: Optional[Callable[[bool], None]] = None):
        """Requests runtime SMS permissions on Android."""
        if not self.is_android:
            if callback:
                callback(True)
            return

        try:
            from android.permissions import request_permissions, Permission, check_permission
            
            def on_permission_result(permissions, grants):
                granted = bool(grants and all(grants))
                logger.info(f"SMS permission result: {granted}")
                if callback:
                    callback(granted)

            permissions = [Permission.READ_SMS, Permission.RECEIVE_SMS]
            request_permissions(permissions, on_permission_result)
        except Exception as e:
            logger.error(f"Error requesting Android permissions: {e}")
            if callback:
                callback(False)

    def read_sms_inbox(self, limit: Optional[int] = 200, full_scan: bool = False) -> List[Dict[str, Any]]:
        """
        Reads SMS messages from inbox.
        If full_scan is True or limit is None, reads all available historical messages.
        On Android: queries content://sms/inbox.
        On Desktop: loads realistic test samples from sample_sms.json.
        """
        effective_limit = None if full_scan else limit
        if self.is_android:
            return self._read_android_sms(limit=effective_limit)
        else:
            return self._read_mock_sms(limit=effective_limit or 100)

    def _read_android_sms(self, limit: Optional[int] = 200) -> List[Dict[str, Any]]:
        """Queries Android Telephony.Sms content provider safely across all Android OEM devices."""
        results = []
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            contentResolver = activity.getContentResolver()
            Uri = autoclass('android.net.Uri')
            sms_uri = Uri.parse("content://sms/inbox")

            # Safe sorting without appending raw SQL LIMIT to sortOrder
            sort_order = "date DESC"

            cursor = contentResolver.query(
                sms_uri,
                None,  # All columns
                None,  # Selection
                None,  # Selection args
                sort_order  # Sort order
            )

            if cursor is not None:
                body_idx = cursor.getColumnIndex("body")
                address_idx = cursor.getColumnIndex("address")
                date_idx = cursor.getColumnIndex("date")

                while cursor.moveToNext():
                    if limit and limit > 0 and len(results) >= limit:
                        break

                    body = cursor.getString(body_idx) if body_idx != -1 else ""
                    sender = cursor.getString(address_idx) if address_idx != -1 else ""
                    timestamp_epoch = cursor.getLong(date_idx) if date_idx != -1 else None

                    timestamp_str = None
                    if timestamp_epoch:
                        try:
                            timestamp_str = datetime.fromtimestamp(timestamp_epoch / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass

                    results.append({
                        "sender": sender,
                        "body": body,
                        "timestamp": timestamp_str
                    })
                cursor.close()
        except Exception as e:
            logger.error(f"Failed to read Android SMS via PyJNIus: {e}")

        return results

    def _read_mock_sms(self, limit: Optional[int] = 50) -> List[Dict[str, Any]]:
        """Loads sample SMS messages for desktop testing."""
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "tests",
            "sample_sms.json"
        )
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                samples = json.load(f)
                count = limit if limit else len(samples)
                return [
                    {
                        "sender": item.get("sender", "BANK"),
                        "body": item["body"],
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    for item in samples[:count]
                ]
        return []

    def sync_sms_transactions(self, limit: Optional[int] = 150, full_scan: bool = False) -> Dict[str, Any]:
        """
        Scans SMS inbox (recent or full history), parses transactions,
        and stores new ones in the database.
        Returns a summary of parsed, inserted, and duplicate transactions.
        """
        messages = self.read_sms_inbox(limit=limit, full_scan=full_scan)
        scanned_count = len(messages)
        parsed_count = 0
        added_count = 0
        duplicate_count = 0
        added_transactions = []
        custom_rules = self.db.get_all_merchant_rules()

        for msg in messages:
            body = msg.get("body", "")
            sender = msg.get("sender", "")
            timestamp = msg.get("timestamp")

            parsed = SMSParser.parse(
                body,
                sender=sender,
                timestamp_str=timestamp,
                custom_rules=custom_rules
            )
            if parsed:
                parsed_count += 1
                inserted_id = self.db.add_transaction(**parsed)
                if inserted_id:
                    added_count += 1
                    parsed["id"] = inserted_id
                    added_transactions.append(parsed)
                else:
                    duplicate_count += 1

        return {
            "scanned": scanned_count,
            "parsed": parsed_count,
            "added": added_count,
            "duplicates": duplicate_count,
            "transactions": added_transactions,
            "is_full_scan": full_scan
        }
