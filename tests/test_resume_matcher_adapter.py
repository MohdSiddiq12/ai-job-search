import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from integrations.resume_matcher import IntegrationUnavailable, get_adapter


class ResumeMatcherBoundaryTests(unittest.TestCase):
    def test_unconfigured_state_is_explicit(self):
        state = get_adapter().availability()
        self.assertEqual(state["status"], "not_configured")
        self.assertFalse(state["available"])

    def test_unconfigured_adapter_never_claims_or_attempts_remote_work(self):
        adapter = get_adapter()
        with self.assertRaisesRegex(IntegrationUnavailable, "no request was sent"):
            adapter.submit({"job": {"id": "test"}}, "idempotency_123")
        with self.assertRaisesRegex(IntegrationUnavailable, "no operation can be queried"):
            adapter.get_operation("external-op")


if __name__ == "__main__":
    unittest.main()
