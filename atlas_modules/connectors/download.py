from . import setup as connector_setup

def connector_package_response(self, payload, app):
    (filename, data) = connector_setup.package(payload)
    self.send_response(200)
    self.send_header('Content-Type', 'application/zip')
    self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
    self.send_header('Content-Length', str(len(data)))
    self.send_header('Cache-Control', 'no-store')
    self.send_header('Referrer-Policy', 'no-referrer')
    self.end_headers()
    self.wfile.write(data)
