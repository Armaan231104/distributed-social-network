import os
import threading
import time
from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "posts"

    def ready(self):
        # Prevent double start from Django autoreloader
        if os.environ.get("RUN_MAIN") != "true":
            return

        from .github_sync import sync_github_activity

        def github_loop():
            while True:
                print("Running GitHub sync...")
                try:
                    sync_github_activity()
                except Exception as e:
                    print("GitHub sync error:", e)

                time.sleep(20)  # check every 20 seconds

        thread = threading.Thread(target=github_loop, daemon=True)
        thread.start()