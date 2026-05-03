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
        json.dump(filmler, f, ensure_ascii=False, indent=2)

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