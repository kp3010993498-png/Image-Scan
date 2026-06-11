import io
import os
import re
import secrets
import shutil
import socket
from datetime import datetime
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
    send_file,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
import qrcode
from PIL import Image

from app import db
from app.models import DriveLink

main_bp = Blueprint('main', __name__)

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'Admin@123'
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg',
    'mp4', 'webm', 'ogg', 'mov', 'mkv',
    'mp3', 'wav', 'm4a', 'aac', 'flac'
}
FIXED_QR_FILENAME = 'QR Code.png'


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


def get_current_link():
    return DriveLink.query.first()


def get_network_scan_url():
    local_ip = get_local_network_ip()
    if not local_ip:
        return None

    port = request.environ.get('SERVER_PORT', '5000')
    return f'http://{local_ip}:{port}{url_for("main.scan_current")}'


def get_qr_scan_url():
    host = request.host.split(':', 1)[0].lower()
    if host in {'127.0.0.1', 'localhost'}:
        return get_network_scan_url() or url_for('main.scan_current', _external=True)

    return url_for('main.scan_current', _external=True)


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


def generate_qr_image(target_url: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=16,
        border=4,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color='black', back_color='white').convert('RGBA')

    template_path = os.path.abspath(os.path.join(current_app.root_path, '..', FIXED_QR_FILENAME))
    if os.path.exists(template_path):
        template = Image.open(template_path).convert('RGBA')
        crop_size = int(min(template.size) * 0.52)
        left = (template.width - crop_size) // 2
        top = (template.height - crop_size) // 2
        portrait = template.crop((left, top, left + crop_size, top + crop_size))

        logo_size = int(qr_image.width * 0.42)
        portrait = portrait.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        padding = int(qr_image.width * 0.025)
        holder_size = logo_size + (padding * 2)
        holder = Image.new('RGBA', (holder_size, holder_size), 'white')
        holder.paste(portrait, (padding, padding), portrait)

        x = (qr_image.width - holder.width) // 2
        y = (qr_image.height - holder.height) // 2
        qr_image.paste(holder, (x, y), holder)

    buffer = io.BytesIO()
    qr_image.convert('RGB').save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


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
    qr_image_url = None

    if current_link and current_link.filename:
        current_file = current_link
        scan_url = get_qr_scan_url()
        qr_image_url = url_for('main.fixed_qr_code')
        network_scan_url = get_network_scan_url()

    return render_template(
        'dashboard.html',
        current_file=current_file,
        scan_url=scan_url,
        network_scan_url=network_scan_url,
        qr_image_url=qr_image_url,
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


@main_bp.route('/fixed-qr-code')
def fixed_qr_code():
    target_url = get_qr_scan_url()
    return send_file(generate_qr_image(target_url), mimetype='image/png')


@main_bp.route('/scan')
def scan_current():
    link = get_current_link()
    if not link or not link.filename:
        return render_template('view.html', error='No content is currently published for this QR code.')

    return redirect(url_for('main.view_link', token=link.token))


@main_bp.route('/view/<token>')
def view_link(token):
    link = DriveLink.query.filter_by(token=token).first()
    if not link or not link.filename:
        return render_template('view.html', error='No content is currently published for this QR code.')

    media_url = url_for('main.serve_media', filename=link.filename, _external=True)
    preview_type = get_preview_type(link.filename)
    return render_template('view.html', media_url=media_url, preview_type=preview_type)
