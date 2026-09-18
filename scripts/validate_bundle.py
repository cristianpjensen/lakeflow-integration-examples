import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class WorkspaceStubHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/api/2.0/preview/scim/v2/Me"):
            self.send_json(200, {"id": "ci", "userName": "ci@example.com", "active": True})
            return

        if self.path.startswith("/api/2.0/workspace/get-status"):
            self.send_json(200, {"path": "/Workspace/.bundle-ci", "object_type": "DIRECTORY", "object_id": 1})
            return

        self.send_error(404)

    def send_json(self, status: int, value: dict[str, object]) -> None:
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        pass


def main() -> None:
    # Bundle validation resolves the current user even when no deployment occurs.
    server = ThreadingHTTPServer(("127.0.0.1", 0), WorkspaceStubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    environment = os.environ.copy()
    environment.update(
        {
            "DATABRICKS_AUTH_TYPE": "pat",
            "DATABRICKS_CONFIG_FILE": "/dev/null",
            "DATABRICKS_HOST": f"http://127.0.0.1:{server.server_port}",
            "DATABRICKS_TOKEN": "unused",
        }
    )

    try:
        result = subprocess.run(
            ["databricks", "bundle", "validate", "--target", "ci"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
