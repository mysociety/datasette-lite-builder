from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from multiprocessing import Process
from http.server import HTTPServer, SimpleHTTPRequestHandler
import time
from pathlib import Path

from .build import build_all


def get_server_func(port: int, serve_path: Path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_path), **kwargs)

    def create_server():
        print(f"Serving {serve_path} on port {port}, access at: http://0.0.0.0:{port}")
        httpd = HTTPServer(("0.0.0.0", port), Handler)
        httpd.serve_forever()

    return create_server


class Rebuilder(FileSystemEventHandler):
    def __init__(
        self,
        serve_path: Path,
        customization_path: Path,
        port: int,
        watch_folders: list[Path],
    ):
        super().__init__()
        self.p = None
        self.serve_path = serve_path
        self.customisation_path = customization_path
        self.port = port
        self.watch_folders = watch_folders
        self.create_server = get_server_func(port, serve_path)

    def stop_server(self):
        if self.p:
            print("Stopping server")
            self.p.terminate()

    def rebuild(self):
        build_all(self.serve_path, self.customisation_path)
        print("Rebuild complete")

    def start_server(self):
        if self.p:
            self.stop_server()
        print("Starting Server")
        self.p = Process(target=self.create_server)
        self.p.start()

    def on_modified(self, event):
        if self.should_rebuild(event):
            print("Rebuilding")
            self.rebuild()

    def should_rebuild(self, event):
        """Include code to make sure you only rebuild on events you care about. Or
        you could implement watchdog's RegexMatchingEventHandler"""
        return True

    def run(self):
        self.rebuild()
        self.start_server()

        observer = Observer()
        for folder in self.watch_folders:
            observer.schedule(self, folder, recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
