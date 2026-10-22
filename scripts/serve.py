"""Serve o site estático do códice (JSON + imagens)."""
import http.server
import os
import socketserver
import sys
import webbrowser

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
URL = f"http://127.0.0.1:{PORT}/"


class RootHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_ROOT, **kwargs)

    def log_message(self, format, *args):
        sys.stderr.write("%s\n" % (format % args))


def main() -> None:
    os.chdir(SITE_ROOT)
    with socketserver.TCPServer(("127.0.0.1", PORT), RootHandler) as httpd:
        print(f"Códice: {URL}")
        print("Ctrl+C para parar.")
        webbrowser.open(URL)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nParado.")


if __name__ == "__main__":
    main()
