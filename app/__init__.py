import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from config import Config

db = SQLAlchemy()


def upgrade_database():
    if not db.engine.url.drivername.startswith('sqlite'):
        return

    with db.engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='drive_link'"))
        if result.first() is None:
            return

        columns = [row[1] for row in conn.execute(text("PRAGMA table_info('drive_link')"))]
        if 'filename' not in columns:
            conn.execute(text("ALTER TABLE drive_link ADD COLUMN filename VARCHAR(256)"))
        if 'content_type' not in columns:
            conn.execute(text("ALTER TABLE drive_link ADD COLUMN content_type VARCHAR(128)"))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'temp'), exist_ok=True)

    db.init_app(app)

    from app.routes import main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        upgrade_database()

    return app
