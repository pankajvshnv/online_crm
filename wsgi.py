import os
from dotenv import load_dotenv

# Load environment configuration from absolute path
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

from app import app

# Standard WSGI entry point for aaPanel / Gunicorn / uWSGI
application = app

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5055))
    debug = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host=host, port=port, debug=debug)
