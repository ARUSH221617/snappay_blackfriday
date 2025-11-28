import pytest
from main import SnappBot
from unittest.mock import MagicMock, patch

class TestSnappBot:
    def test_init(self):
        bot = SnappBot()
        assert bot.target_product_name == "iPhone" # Default

    def test_custom_handlers(self):
        logs = []
        def log_handler(msg):
            logs.append(msg)

        def input_handler(prompt):
            return "test_input"

        bot = SnappBot(input_handler=input_handler, log_handler=log_handler)

        bot.log("Hello")
        assert "Hello" in logs

        assert bot.input_handler("prompt") == "test_input"

    @patch('main.sync_playwright')
    def test_run_calls_playwright(self, mock_playwright):
        bot = SnappBot()
        # Mock everything to avoid real browser launch
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Prevent actual execution of logic steps
        with patch.object(bot, 'step_1_timetable'), \
             patch.object(bot, 'step_2_login'), \
             patch.object(bot, 'step_3_purchase'):
            bot.run()

        mock_p.chromium.launch.assert_called_once()
