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


class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    items = db.relationship('PlaylistItem', backref='playlist', cascade='all, delete-orphan', order_by='PlaylistItem.sequence')

    def __repr__(self):
        return f'<Playlist {self.id} name={self.name}>'


class PlaylistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    content_type = db.Column(db.String(128), nullable=True)
    sequence = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<PlaylistItem {self.id} playlist={self.playlist_id} seq={self.sequence}>'


class PlaylistPush(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    playlist = db.relationship('Playlist', backref='pushes')

    def __repr__(self):
        return f'<PlaylistPush {self.id} token={self.token}>'


class ScanRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    push_id = db.Column(db.Integer, db.ForeignKey('playlist_push.id'), nullable=False)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    remote_addr = db.Column(db.String(64), nullable=True)

    push = db.relationship('PlaylistPush', backref='scans')

    def __repr__(self):
        return f'<ScanRecord {self.id} push={self.push_id} at={self.scanned_at}>'
