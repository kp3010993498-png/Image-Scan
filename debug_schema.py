from app import create_app, db
from app.models import PlaylistSchedule
app = create_app()
with app.app_context():
    print('tables=', db.engine.table_names())
    print('PlaylistSchedule exists?', PlaylistSchedule.__table__.name)
