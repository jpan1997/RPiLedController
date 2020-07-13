import json
import SimpleHTTPServer
import SocketServer
import sys

# https://stackoverflow.com/questions/21631799/how-can-i-pass-parameters-to-a-requesthandler
# https://stackoverflow.com/questions/9698614/super-raises-typeerror-must-be-type-not-classobj-for-new-style-class
def make_handler(strip):
    class CustomHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self.strip = strip
            SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, *args, **kwargs)
            
        def do_GET(self):
            # print(self)
            if self.path == '/':
                self.path = '/home/pi/Projects/RPiLedController/frontend/index.html'
                # SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                with open(self.path) as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            # print(self)
            length = int(self.headers.getheader("content-length"))
            payload = self.rfile.read(length)
            print("POST: " + payload)
            sys.stdout.flush()
            data = json.loads(payload)
            
            self.strip.update_settings(data)

            # non-settings requests
            if "reset_settings" in data:
                self.strip.reset_settings()
            
            if "get_settings" in data:
                settings = self.strip.get_settings()
                self.wfile.write(json.dumps(settings))

            
    return CustomHandler

    
class Server:
    def __init__(self, port, strip):
        self.httpd = SocketServer.TCPServer(("", port), make_handler(strip))

    def run(self):
        print("Serving on port: " + str(self.httpd.server_address[1]))
        sys.stdout.flush()
        
        try:
            self.httpd.serve_forever()
        except:
            pass
    
    def kill(self):
        self.httpd.server_close()