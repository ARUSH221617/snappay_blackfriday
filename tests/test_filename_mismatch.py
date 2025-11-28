import pytest
from unittest.mock import MagicMock, patch
from main import SnappBot
import json
import os

class TestFileNameMismatch:
    def test_debug_filename_mismatch_fixed(self):
        # Setup
        bot = SnappBot()
        bot.target_product_name = "NonExistentProduct"

        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        # Mock AINavigator to return empty list or dummy products
        bot.ai.extract_campaign_products = MagicMock(return_value=[{"name": "Other", "selector": "sel"}])

        # Mock safe_goto
        bot.safe_goto = MagicMock(return_value=True)

        # Capture logs
        logs = []
        bot.log_handler = lambda msg: logs.append(msg)

        # Clean previous files
        if os.path.exists("debug_products.json"):
            os.remove("debug_products.json")
        if os.path.exists("debug_products_step3.json"):
            os.remove("debug_products_step3.json")

        # Run step 3
        bot.step_3_purchase(mock_page)

        # Check if the file created is "debug_products_step3.json"
        assert os.path.exists("debug_products_step3.json"), "Expected debug_products_step3.json to be created"
        assert not os.path.exists("debug_products.json"), "Did not expect debug_products.json to be created"

        # Check if the log message is consistent
        expected_msg = "Check 'debug_products_step3.json' to see what AI found."
        found_msg = any(expected_msg in log for log in logs)
        assert found_msg, f"Expected log message '{expected_msg}' not found in logs: {logs}"

        # Cleanup
        if os.path.exists("debug_products_step3.json"):
            os.remove("debug_products_step3.json")
