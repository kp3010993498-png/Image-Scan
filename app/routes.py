import io
import os
import re
import secrets
import base64
import shutil
import socket
from datetime import datetime, date, time as dt_time
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_from_directory,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
import qrcode

from app import db
from app.models import DriveLink, Playlist, PlaylistItem, PlaylistPush, ScanRecord, PlaylistSchedule

main_bp = Blueprint('main', __name__)

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'Admin@123'
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg',
    'mp4', 'webm', 'ogg', 'mov', 'mkv',
    'mp3', 'wav', 'm4a', 'aac', 'flac'
}


def login_required(view):
    def wrapped_view(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('main.login'))
        return view(*args, **kwargs)

    wrapped_view.__name__ = view.__name__
    return wrapped_view


def allowed_file(filename: str) -> bool:
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def get_local_network_ip():
    sock = None
        if not (window_start <= now <= window_end):
            return render_template(
                'view.html',
                error=f'This playlist is scheduled for {schedule.scheduled_date} at {schedule.scheduled_time.strftime("%H:%M")}. It will automatically play at that time.',
                is_scheduling=True,
                server_now=now.isoformat(),
                scheduled_dt=scheduled_dt.isoformat(),
                window_start=window_start.isoformat(),
                window_end=window_end.isoformat(),
                auto_refresh=True,
            )
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = None
    finally:
        if sock:
            sock.close()
    return ip


def get_current_link():
    return DriveLink.query.first()


def get_playlist(push_token: str):
    push = PlaylistPush.query.filter_by(token=push_token, active=True).first()
    if not push:
        return None
    return push.playlist


def get_storage_filename(token: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f'{token}{ext}'


def get_preview_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}:
        return 'image'
    if ext in {'.mp4', '.webm', '.ogg', '.mov', '.mkv'}:
        return 'video'
    if ext in {'.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'}:
        return 'audio'
    return 'link'


def generate_qr_data(text: str) -> str:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


def get_local_network_ip():
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = None
    finally:
        if sock:
            sock.close()
    return ip


def extract_drive_file_id(url: str):
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'[\?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return None


def get_preview_url_and_type(url: str):
    preview_url = url
    preview_type = 'link'
    base_path = url.split('?', 1)[0].lower()
    ext = os.path.splitext(base_path)[1]

    image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
    video_exts = {'.mp4', '.webm', '.ogg', '.mov', '.mkv'}
    audio_exts = {'.mp3', '.wav', '.ogg', '.m4a', '.aac'}

    if ext in image_exts:
        preview_type = 'image'
    elif ext in video_exts:
        preview_type = 'video'
    elif ext in audio_exts:
        preview_type = 'audio'
    else:
        file_id = extract_drive_file_id(url)
        if file_id:
            preview_url = f'https://drive.google.com/uc?export=view&id={file_id}'
            preview_type = 'iframe'

    return preview_url, preview_type


@main_bp.route('/')
def index():
    if session.get('admin_logged_in'):
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Login successful.', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Invalid login credentials.', 'danger')

    return render_template('login.html')


@main_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('main.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    current_link = get_current_link()
    current_file = None
    scan_url = None
    network_scan_url = None
    qr_base64 = None

    if current_link and current_link.filename:
        current_file = current_link
        scan_url = url_for('main.view_link', token=current_link.token, _external=True)
        local_ip = get_local_network_ip()
        if local_ip:
            port = request.environ.get('SERVER_PORT', '5000')
            network_scan_url = f'http://{local_ip}:{port}{url_for("main.view_link", token=current_link.token)}'
        qr_target = scan_url
        qr_base64 = generate_qr_data(qr_target)

    # playlist metrics
    playlist_count = Playlist.query.count()
    active_push_count = PlaylistPush.query.filter_by(active=True).count()
    total_scans = db.session.query(db.func.count(ScanRecord.id)).scalar() or 0

    return render_template(
        'dashboard.html',
        current_file=current_file,
        scan_url=scan_url,
        network_scan_url=network_scan_url,
        qr_base64=qr_base64,
        playlist_count=playlist_count,
        active_push_count=active_push_count,
        total_scans=total_scans,
    )


@main_bp.route('/verify', methods=['POST'])
@login_required
def verify():
    file = request.files.get('media_file')
    if not file or file.filename == '':
        flash('Please choose a file to upload.', 'warning')
        return redirect(url_for('main.dashboard'))

    if not allowed_file(file.filename):
        flash('Invalid file type. Upload image, video, or audio.', 'danger')
        return redirect(url_for('main.dashboard'))

    filename = secure_filename(file.filename)
    temp_name = f'{secrets.token_hex(8)}_{filename}'
    temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp', temp_name)
    file.save(temp_path)

    preview_type = get_preview_type(filename)
    preview_url = url_for('main.temporary_file', filename=temp_name)

    return render_template(
        'verify.html',
        file_name=filename,
        preview_url=preview_url,
        preview_type=preview_type,
        temp_filename=temp_name,
        content_type=file.mimetype,
    )


@main_bp.route('/temp/<filename>')
@login_required
def temporary_file(filename):
    temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp')
    return send_from_directory(temp_dir, filename, as_attachment=False)


@main_bp.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    flash('Upload failed: file is too large. Maximum upload size is 1GB.', 'danger')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/publish', methods=['POST'])
@login_required
def publish():
    temp_filename = request.form.get('temp_filename', '')
    content_type = request.form.get('content_type', 'application/octet-stream')
    if not temp_filename:
        flash('No file available to publish.', 'warning')
        return redirect(url_for('main.dashboard'))

    temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp', temp_filename)
    if not os.path.exists(temp_path):
        flash('Temporary file not found. Please upload again.', 'danger')
        return redirect(url_for('main.dashboard'))

    current_link = get_current_link()
    token = current_link.token if current_link else secrets.token_urlsafe(16)
    final_filename = get_storage_filename(token, temp_filename)
    final_path = os.path.join(current_app.config['UPLOAD_FOLDER'], final_filename)

    if current_link and current_link.filename:
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_link.filename)
        if os.path.exists(old_path) and old_path != final_path:
            os.remove(old_path)

    try:
        shutil.copy2(temp_path, final_path)
    except PermissionError:
        flash('Publish failed: cannot copy file while it is in use. Close any preview or media player and try again.', 'danger')
        return redirect(url_for('main.dashboard'))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    if current_link:
        current_link.filename = final_filename
        current_link.content_type = content_type
        current_link.created_at = datetime.utcnow()
    else:
        current_link = DriveLink(
            token=token,
            filename=final_filename,
            content_type=content_type,
        )
        db.session.add(current_link)

    db.session.commit()
    flash('File published successfully.', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/remove', methods=['POST'])
@login_required
def remove():
    current_link = get_current_link()
    if current_link and current_link.filename:
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_link.filename)
        if os.path.exists(old_path):
            os.remove(old_path)
        current_link.filename = None
        current_link.content_type = None
        db.session.commit()
        flash('Current upload removed.', 'info')
    else:
        flash('No upload exists to remove.', 'warning')

    return redirect(url_for('main.dashboard'))


@main_bp.route('/media/<filename>')
def serve_media(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=False)


@main_bp.route('/view/<token>')
def view_link(token):
    link = DriveLink.query.filter_by(token=token).first()
    if not link or not link.filename:
        return render_template('view.html', error='No content is currently published for this QR code.')

    media_url = url_for('main.serve_media', filename=link.filename, _external=True)
    preview_type = get_preview_type(link.filename)
    return render_template('view.html', media_url=media_url, preview_type=preview_type)


@main_bp.route('/playlists')
@login_required
def playlists():
    all_playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    return render_template('playlists.html', playlists=all_playlists)


@main_bp.route('/playlists/create', methods=['POST'])
@login_required
def create_playlist():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Please provide a playlist name.', 'warning')
        return redirect(url_for('main.playlists'))
    pl = Playlist(name=name)
    db.session.add(pl)
    db.session.commit()
    flash('Playlist created.', 'success')
    return redirect(url_for('main.playlist_detail', playlist_id=pl.id))


@main_bp.route('/playlists/<int:playlist_id>')
@login_required
def playlist_detail(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    return render_template('playlist_detail.html', playlist=pl)


@main_bp.route('/playlists/<int:playlist_id>/upload', methods=['POST'])
@login_required
def playlist_upload(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    file = request.files.get('media_file')
    if not file or file.filename == '':
        flash('Please choose a file to upload.', 'warning')
        return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))
    if not allowed_file(file.filename):
        flash('Invalid file type.', 'danger')
        return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))

    filename = secure_filename(file.filename)
    stored_name = f'{secrets.token_urlsafe(12)}{os.path.splitext(filename)[1]}'
    final_path = os.path.join(current_app.config['UPLOAD_FOLDER'], stored_name)
    try:
        file.save(final_path)
    except Exception:
        flash('Failed to save uploaded file.', 'danger')
        return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))

    # determine next sequence
    max_seq = db.session.query(db.func.max(PlaylistItem.sequence)).filter(PlaylistItem.playlist_id == pl.id).scalar() or 0
    item = PlaylistItem(playlist_id=pl.id, filename=stored_name, content_type=file.mimetype, sequence=(max_seq or 0) + 1)
    db.session.add(item)
    db.session.commit()
    flash('File added to playlist.', 'success')
    return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))


@main_bp.route('/playlists/<int:playlist_id>/item/<int:item_id>/delete', methods=['POST'])
@login_required
def playlist_item_delete(playlist_id, item_id):
    item = PlaylistItem.query.filter_by(id=item_id, playlist_id=playlist_id).first_or_404()
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], item.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    db.session.delete(item)
    db.session.commit()
    flash('Item removed from playlist.', 'info')
    return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))


@main_bp.route('/playlists/<int:playlist_id>/reorder', methods=['POST'])
@login_required
def playlist_reorder(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    # Accept JSON order (AJAX) or form order (legacy)
    if request.is_json:
        data = request.get_json()
        order = data.get('order', [])
    else:
        order = request.form.getlist('order')

    try:
        for idx, item_id in enumerate(order, start=1):
            it = PlaylistItem.query.filter_by(id=int(item_id), playlist_id=pl.id).first()
            if it:
                it.sequence = idx
        db.session.commit()
        if request.is_json:
            return {'status': 'ok'}
        flash('Playlist reordered.', 'success')
    except Exception:
        db.session.rollback()
        if request.is_json:
            return {'status': 'error'}, 500
        flash('Failed to reorder playlist.', 'danger')
    return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))


@main_bp.route('/playlists/<int:playlist_id>/push', methods=['POST'])
@login_required
def playlist_push(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    token = secrets.token_urlsafe(12)
    push = PlaylistPush(playlist_id=pl.id, token=token, active=True)
    db.session.add(push)
    db.session.commit()
    push_url = url_for('main.playlist_view_current', _external=True)
    qr_base64 = generate_qr_data(push_url)
    flash('Playlist pushed. Share the stable QR code with users.', 'success')
    return render_template('playlist_pushed.html', playlist=pl, push=push, push_url=push_url, qr_base64=qr_base64)


@main_bp.route('/playlist/current')
def playlist_view_current():
    push = PlaylistPush.query.filter_by(active=True).order_by(PlaylistPush.created_at.desc()).first()
    if not push:
        return render_template('view.html', error='No playlist has been pushed yet.', is_scheduling=False)
    
    # Check if playlist has an active schedule
    schedule = PlaylistSchedule.query.filter_by(playlist_id=push.playlist_id, is_active=True).first()
    is_scheduled_time = False
    if schedule:
        now = datetime.now()
        current_date = now.date()
        current_time = now.time()
        # Check if we're within the scheduled window (allow 5 min before and after)
        from datetime import timedelta
        scheduled_dt = datetime.combine(schedule.scheduled_date, schedule.scheduled_time)
        window_start = scheduled_dt - timedelta(minutes=5)
        window_end = scheduled_dt + timedelta(minutes=5)
        if not (window_start <= now <= window_end):
            return render_template(
                'view.html',
                error=f'This playlist is scheduled for {schedule.scheduled_date} at {schedule.scheduled_time.strftime("%H:%M")}. It will automatically play at that time.',
                is_scheduling=True,
                server_now=now.isoformat(),
                scheduled_dt=scheduled_dt.isoformat(),
                window_start=window_start.isoformat(),
                window_end=window_end.isoformat(),
                auto_refresh=True,
            )
        is_scheduled_time = True
    
    # record scan
    try:
        rec = ScanRecord(push_id=push.id, remote_addr=request.remote_addr)
        db.session.add(rec)
        db.session.commit()
    except Exception:
        db.session.rollback()

    items = PlaylistItem.query.filter_by(playlist_id=push.playlist_id).order_by(PlaylistItem.sequence).all()
    media = []
    for it in items:
        media.append({'url': url_for('main.serve_media', filename=it.filename, _external=True), 'type': get_preview_type(it.filename)})

    return render_template('playlist_view.html', media=media, playlist=push.playlist, is_scheduled_time=is_scheduled_time)


@main_bp.route('/playlist/view/<token>')
def playlist_view(token):
    push = PlaylistPush.query.filter_by(token=token, active=True).first()
    if not push:
        return render_template('view.html', error='This playlist QR code is not active or does not exist.', is_scheduling=False)
    
    # Check if playlist has an active schedule
    schedule = PlaylistSchedule.query.filter_by(playlist_id=push.playlist_id, is_active=True).first()
    is_scheduled_time = False
    if schedule:
        now = datetime.now()
        from datetime import timedelta
        scheduled_dt = datetime.combine(schedule.scheduled_date, schedule.scheduled_time)
        window_start = scheduled_dt - timedelta(minutes=5)
        window_end = scheduled_dt + timedelta(minutes=5)
        if not (window_start <= now <= window_end):
            return render_template('view.html', error=f'This playlist is scheduled for {schedule.scheduled_date} at {schedule.scheduled_time.strftime("%H:%M")}. It will automatically play at that time.', is_scheduling=True)
        is_scheduled_time = True
    
    # record scan
    try:
        rec = ScanRecord(push_id=push.id, remote_addr=request.remote_addr)
        db.session.add(rec)
        db.session.commit()
    except Exception:
        db.session.rollback()

    items = PlaylistItem.query.filter_by(playlist_id=push.playlist_id).order_by(PlaylistItem.sequence).all()
    media = []
    for it in items:
        media.append({'url': url_for('main.serve_media', filename=it.filename, _external=True), 'type': get_preview_type(it.filename)})

    return render_template('playlist_view.html', media=media, playlist=push.playlist, is_scheduled_time=is_scheduled_time)


@main_bp.route('/playlists/<int:playlist_id>/pushes')
@login_required
def playlist_pushes(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    # get pushes with scan counts
    rows = (
        db.session.query(PlaylistPush, db.func.count(ScanRecord.id).label('scan_count'))
        .outerjoin(ScanRecord, PlaylistPush.id == ScanRecord.push_id)
        .filter(PlaylistPush.playlist_id == pl.id)
        .group_by(PlaylistPush.id)
        .order_by(PlaylistPush.created_at.desc())
        .all()
    )
    return render_template('playlist_pushes.html', playlist=pl, rows=rows)


@main_bp.route('/push/<int:push_id>/deactivate', methods=['POST'])
@login_required
def deactivate_push(push_id):
    push = PlaylistPush.query.get_or_404(push_id)
    push.active = False
    db.session.commit()
    flash('Push deactivated.', 'info')
    return redirect(url_for('main.playlist_pushes', playlist_id=push.playlist_id))


@main_bp.route('/playlists/<int:playlist_id>/schedule', methods=['POST'])
@login_required
def set_playlist_schedule(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    scheduled_date_str = request.form.get('scheduled_date', '')
    scheduled_time_str = request.form.get('scheduled_time', '')
    
    if not scheduled_date_str or not scheduled_time_str:
        flash('Please provide both date and time.', 'warning')
        return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))
    
    try:
        from datetime import datetime as dt
        scheduled_date = dt.strptime(scheduled_date_str, '%Y-%m-%d').date()
        scheduled_time = dt.strptime(scheduled_time_str, '%H:%M').time()
        
        # Delete existing schedules for this playlist
        PlaylistSchedule.query.filter_by(playlist_id=pl.id).delete()
        
        # Create new schedule
        schedule = PlaylistSchedule(playlist_id=pl.id, scheduled_date=scheduled_date, scheduled_time=scheduled_time, is_active=True)
        db.session.add(schedule)
        db.session.commit()
        flash(f'Playlist scheduled for {scheduled_date} at {scheduled_time.strftime("%H:%M")}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to set schedule: {str(e)}', 'danger')
    
    return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))


@main_bp.route('/playlists/<int:playlist_id>/schedule/remove', methods=['POST'])
@login_required
def remove_playlist_schedule(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    PlaylistSchedule.query.filter_by(playlist_id=pl.id).delete()
    db.session.commit()
    flash('Schedule removed. Playlist will play immediately when scanned.', 'info')
    return redirect(url_for('main.playlist_detail', playlist_id=playlist_id))
