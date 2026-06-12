from app import create_app

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
    resp = client.get('/playlists')
    print('PLAYLISTS', resp.status_code)
    if resp.status_code != 200:
        print(resp.data.decode('utf-8'))
    resp = client.post('/playlists/create', data={'name': 'ScheduleTest'}, follow_redirects=True)
    print('CREATE', resp.status_code)
    print(resp.data.decode('utf-8')[:2000])
