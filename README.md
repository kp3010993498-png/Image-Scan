# Admin QR Link Panel

A simple Flask app that allows a single admin to login, upload one image/video/audio file, verify and publish it, and generate a permanent QR code for scanning.

## Admin credentials
- Username: `admin`
- Password: `Admin@123`

## Features
- Admin login panel
- Dashboard to upload one media file at a time
- Verify upload before publishing
- Remove current content and replace it with a new upload
- Permanent QR code token stays the same even when content changes
- Local network scanning support for mobile access
- Inline preview of published media after scanning
- Support uploads up to 1GB

## Setup
1. Create a Python virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python run.py
```

4. Open the browser at `http://127.0.0.1:5000`.

5. For mobile access from another device on the same network, scan the QR code or use the network URL shown on the dashboard. Make sure the Windows firewall allows port `5000` and the app is running on `0.0.0.0`.

## Deploy to Render

1. Push your project to GitHub.
2. Go to https://render.com and sign in.
3. Create a new Web Service.
4. Connect your GitHub repository.
5. Set the Environment to `Python`.
6. Use the following build command:

```bash
pip install -r requirements.txt
```

7. Use the following start command:

```bash
gunicorn run:app
```

8. Set the environment variable `FLASK_ENV` to `production`.
9. Deploy the service.

Render will host the app and provide a public URL. The QR code will then point to the Render URL instead of your local machine.
