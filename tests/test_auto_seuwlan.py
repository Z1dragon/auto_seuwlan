import tempfile
import unittest
from pathlib import Path

import auto_seuwlan as app


class AutoSeuwlanTests(unittest.TestCase):
    def test_infer_seu_eportal_from_a79_url(self):
        url = "https://w.seu.edu.cn/a79.htm?UserIP=10.1.2.3&wlanacname=AP01"
        self.assertEqual(app.infer_portal_type(url), "seu_eportal")

    def test_infer_srun_from_ac_id(self):
        url = "https://example.edu/srun_portal_pc?ac_id=1"
        self.assertEqual(app.infer_portal_type(url), "srun")

    def test_apply_isp_suffix(self):
        self.assertEqual(app.apply_isp_suffix("123456", "cmcc"), "123456@cmcc")
        self.assertEqual(app.apply_isp_suffix("123456@telecom", "cmcc"), "123456@telecom")
        self.assertEqual(app.apply_isp_suffix("123456", ""), "123456")

    def test_parse_jsonp(self):
        self.assertEqual(app.parse_jsonp('dr1003({"result":"1","ret_code":"0"})')["result"], "1")

    def test_summarize_ret_code_already_online(self):
        ok, message = app.summarize_portal_response('dr1003({"result":"0","ret_code":"2"})')
        self.assertTrue(ok)
        self.assertIn("already online", message)

    def test_split_urls(self):
        self.assertEqual(app.split_urls("http://a,http://b; http://c"), ("http://a", "http://b", "http://c"))

    def test_redact_url(self):
        url = "https://w.seu.edu.cn/a79.htm?UserIP=10.1.2.3&user_password=secret&wlanacname=AP01"
        redacted = app.redact_url(url)
        self.assertIn("UserIP=10.1.%2A.%2A", redacted)
        self.assertIn("user_password=%2A%2A%2A", redacted)
        self.assertNotIn("secret", redacted)

    def test_extract_url_ignores_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seuwlan.md"
            path.write_text("https://w.seu.edu.cn/a79.htm?UserIP=10.x.x.x&wlanacname=...", encoding="utf-8")
            self.assertIsNone(app.extract_first_url_from_markdown(path))

    def test_extract_url_reads_real_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seuwlan.md"
            path.write_text("login: https://w.seu.edu.cn/a79.htm?UserIP=10.1.2.3&wlanacname=AP01", encoding="utf-8")
            self.assertEqual(
                app.extract_first_url_from_markdown(path),
                "https://w.seu.edu.cn/a79.htm?UserIP=10.1.2.3&wlanacname=AP01",
            )

    def test_decode_command_output_tolerates_invalid_bytes(self):
        decoded = app.decode_command_output(b"\xaf\xffnetsh output")
        self.assertIn("netsh output", decoded)

    def test_looks_like_portal_body(self):
        self.assertTrue(app.looks_like_portal_body("<html>wlanacname=AP01</html>"))
        self.assertFalse(app.looks_like_portal_body("<html>plain page</html>"))


if __name__ == "__main__":
    unittest.main()
