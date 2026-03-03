import importlib.util
import unittest

FLASK_AVAILABLE = (
    importlib.util.find_spec("flask") is not None
    and importlib.util.find_spec("flask_socketio") is not None
)

if FLASK_AVAILABLE:
    import dashboard


class StubTracker:
    def get_statistics(self):
        return {"total": 2, "completed": 1, "failed": 1, "processing": 0, "avg_duration": 1.0}

    def get_pending_jobs(self):
        return [{"customer_name": "A", "phone": "010", "status": "processing", "error_message": ""}]


class StubAnalyzer:
    def analyze_keywords(self):
        return {"keyword": 1}

    def analyze_customers(self):
        return [{"name": "A", "total_messages": 1, "my_messages": 1, "attachments": 0}]

    def analyze_timeline(self):
        return {f"{h:02d}:00": 0 for h in range(24)}

    def get_summary_statistics(self):
        return {"total_customers": 1, "total_messages": 1, "total_attachments": 0, "avg_messages_per_customer": 1}


@unittest.skipUnless(FLASK_AVAILABLE, "flask not installed")
class TestDashboard(unittest.TestCase):
    def setUp(self):
        dashboard.tracker = StubTracker()
        dashboard.analyzer = StubAnalyzer()
        self.client = dashboard.app.test_client()

    def test_index(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_stats_endpoint(self):
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total", resp.get_json())

    def test_jobs_endpoint(self):
        resp = self.client.get("/api/jobs")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data), 1)

    def test_analysis_endpoints(self):
        resp = self.client.get("/api/analysis/keywords")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/analysis/customers")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/analysis/timeline")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/analysis/summary")
        self.assertEqual(resp.status_code, 200)
