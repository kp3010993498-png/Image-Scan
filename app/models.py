from datetime import datetime
from app import db


class DriveLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False)
    filename = db.Column(db.String(256), nullable=True)
    content_type = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<DriveLink {self.id} token={self.token}>'
