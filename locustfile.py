from locust import HttpUser, task, between

class MetricsUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def get_metrics(self):
        self.client.get("/metrics")

    @task(weight=5)
    @task(weight=5)
    def health_check(self):
        # FastAPI health check
        self.client.get("/health")
