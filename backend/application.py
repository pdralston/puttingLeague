#!/usr/bin/env python3
"""
Elastic Beanstalk entry point for DG Putt application
"""

from app import app

# EB expects the application object to be called 'application'
application = app

if __name__ == "__main__":
    application.run(debug=False)
