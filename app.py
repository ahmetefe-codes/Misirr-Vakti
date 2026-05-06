from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

VERI_DOSYASI = 'filmler.json'

def filmleri_oku():
    if not os.path.exists(VERI_DOSYASI):
        return []
    with open(VERI_DOSYASI, 'r', encoding='utf-8') as f:
        return json.load(f)

def filmleri_yaz(filmler):
    with open(VERI_DOSYASI, 'w', encoding='utf-8') as f:
        json.dump(filmler, f, ensure_ascii=False, indent=2from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)
DB_DOSYASI = 'filmler.db'

def db_baglanti():
    conn = sqlite3.connect(DB_DOSYASI)
    conn.row_factory = sqlite3.Row
    return conn

def db_olustur():
    conn = db_baglanti()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS filmler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT,
            afis TEXT,
            orijinal_link TEXT UNIQUE,
            video_linki TEXT,
            kategoriler TEXT,
            imdb TEXT,
            yil TEXT,
            aciklama TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/filmleri-getir')
def filmleri_getir():
    sayfa = int(request.args.get('sayfa', 1))
    kategori = request.args.get('kategori', '')
    arama = request.args.get('arama', '')
    limit = 27 
    offset = (sayfa - 1) * limit
    
    conn = db_baglanti()
    
    query = "SELECT * FROM filmler WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM filmler WHERE 1=1"
    params = []
    
    if kategori:
        query += " AND kategoriler LIKE ?"
        count_query += " AND kategoriler LIKE ?"
        params.append(f"%{kategori}%")
        
    if arama:
        query += " AND baslik LIKE ?"
        count_query += " AND baslik LIKE ?"
        params.append(f"%{arama}%")
        
    query += " ORDER BY yil DESC, id DESC LIMIT ? OFFSET ?"
    
    toplam_film = conn.execute(count_query, params).fetchone()[0]
    
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    filmler = []
    for row in rows:
        filmler.append({
            'baslik': row['baslik'],
            'afis': row['afis'],
            'orijinal_link': row['orijinal_link'],
            'video_linki': row['video_linki'],
            'kategoriler': row['kategoriler'].split(',') if row['kategoriler'] else [],
            'imdb': row['imdb'],
            'yil': row['yil'] if row['yil'] else '',
            'aciklama': row['aciklama'] if row['aciklama'] else ''
        })
        
    return jsonify({
        'filmler': filmler,
        'toplam': toplam_film,
        'toplam_sayfa': (toplam_film // limit) + (1 if toplam_film % limit > 0 else 0),
        'mevcut_sayfa': sayfa
    })

if __name__ == '__main__':
    db_olustur()
    # KANZİ YAMASI: host='0.0.0.0' ekleyerek evdeki tüm cihazlara yayını açtık!
    app.run(host='0.0.0.0', debug=True, port=5000)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/filmleri-getir')
def filmleri_getir():
    return jsonify(filmleri_oku())

@app.route('/film-sil', methods=['POST'])
def film_sil():
    link = request.get_json().get('link')
    liste = [f for f in filmleri_oku() if f['orijinal_link'] != link]
    filmleri_yaz(liste)
    return jsonify({"durum": "tamam"})

if __name__ == '__main__':
    # host='0.0.0.0' ayarı sunucuyu aynı ağdaki diğer cihazlara açar
    app.run(host='0.0.0.0', port=5000, debug=True)
