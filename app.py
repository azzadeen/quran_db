import sqlite3
import re
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_NAME = "quran_corpus.db"

SURAH_NAMES = {
    1: "الفاتحة", 2: "البقرة", 3: "آل عمران", 4: "النساء", 5: "المائدة", 6: "الأنعام", 7: "الأعراف", 8: "الأنفال", 9: "التوبة", 10: "يونس",
    11: "هود", 12: "يوسف", 13: "الرعد", 14: "إبراهيم", 15: "الحجر", 16: "النحل", 17: "الإسراء", 18: "الكهف", 19: "مريم", 20: "طه",
    21: "الأنبياء", 22: "الحج", 23: "المؤمنون", 24: "النور", 25: "الفرقان", 26: "الشعراء", 27: "النمل", 28: "القصص", 29: "العنكبوت", 30: "الروم",
    31: "لقمان", 32: "السجدة", 33: "الأحزاب", 34: "سبأ", 35: "فاطر", 36: "يس", 37: "الصافات", 38: "ص", 39: "الزمر", 40: "غافر",
    41: "فصلت", 42: "الشورى", 43: "الزخرف", 44: "الدخان", 45: "الجاثية", 46: "الأحقاف", 47: "محمد", 48: "الفتح", 49: "الحجرات", 50: "ق",
    51: "الذاريات", 52: "الطور", 53: "النجم", 54: "القمر", 55: "الرحمن", 56: "الواقعة", 57: "الحديد", 58: "المجادلة", 59: "الحشر", 60: "الممتحنة",
    61: "الصف", 62: "الجمعة", 63: "المنافقون", 64: "التغابن", 65: "الطلاق", 66: "التحريم", 67: "الملك", 68: "القلم", 69: "الحاقة", 70: "المعارج",
    71: "نوح", 72: "الجن", 73: "المزمل", 74: "المدثر", 75: "القيامة", 76: "الإنسان", 77: "المرسلات", 78: "النبأ", 79: "النازعات", 80: "عبس",
    81: "التكوير", 82: "الانفطار", 83: "المطففين", 84: "الانشقاق", 85: "البروج", 86: "الطارق", 87: "الأعلى", 88: "الغاشية", 89: "الفجر", 90: "البلد",
    91: "الشمس", 92: "الليل", 93: "الضحى", 94: "الشرح", 95: "التين", 96: "العلق", 97: "القدر", 98: "البينة", 99: "الزلزلة", 100: "العاديات",
    101: "القارعة", 102: "التكاثر", 103: "العصر", 104: "الهمزة", 105: "الفيل", 106: "قريش", 107: "الماعون", 108: "الكوثر", 109: "الكافرون", 110: "النصر",
    111: "المسد", 112: "الإخلاص", 113: "الفلق", 114: "الناس"
}

def remove_diacritics(text):
    """Normalizes Arabic text input by removing Tashkeel, Tatweel, and standardizing Alifs/Yaa/Taa Marbouta."""
    if not text:
        return ""
    text = re.sub(r'[\u064B-\u065F\u0670\u0640]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[^\u0621-\u064A0-9\s]', '', text)
    return text

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_ayah_details(cursor, s, a):
    """Helper to fetch full details of a specific surah and ayah."""
    words_in_ayah = cursor.execute(
        "SELECT id, surah, ayah, word_num, word_text, source_word, wazn, meaning "
        "FROM words WHERE surah = ? AND ayah = ? ORDER BY word_num ASC",
        (s, a)
    ).fetchall()

    if not words_in_ayah:
        return None

    assigned_topics = cursor.execute(
        "SELECT topic_id FROM ayah_topics WHERE surah = ? AND ayah = ?",
        (s, a)
    ).fetchall()

    clean_row = cursor.execute(
        "SELECT text_clean FROM verses_clean WHERE sura_id = ? AND aya_id = ?",
        (s, a)
    ).fetchone()

    notes = cursor.execute(
        "SELECT id, note_text, created_at FROM ayah_notes WHERE surah = ? AND ayah = ? ORDER BY id ASC",
        (s, a)
    ).fetchall()

    clean_text = clean_row['text_clean'] if clean_row else ""
    full_ayah = " ".join([w['word_text'] for w in words_in_ayah])

    return {
        'surah': s,
        'surah_name': SURAH_NAMES.get(s, f"سورة {s}"),
        'ayah': a,
        'full_text': full_ayah,
        'clean_text': clean_text,
        'assigned_topic_ids': [t['topic_id'] for t in assigned_topics],
        'notes': [dict(n) for n in notes],
        'words': [dict(w) for w in words_in_ayah]
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/topics', methods=['GET'])
def get_topics():
    conn = get_db_connection()
    topics = conn.execute("SELECT id, name FROM topics ORDER BY name ASC").fetchall()
    conn.close()
    return jsonify([dict(t) for t in topics])

@app.route('/topics')
def topics_page():
    return render_template('topics.html')

@app.route('/api/add_topic', methods=['POST'])
def add_topic():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({"error": "Topic name is required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO topics (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/ayah', methods=['GET'])
def get_single_ayah():
    try:
        s = int(request.args.get('surah'))
        a = int(request.args.get('ayah'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid surah or ayah parameter'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    ayah_data = get_ayah_details(cursor, s, a)
    conn.close()

    if not ayah_data:
        return jsonify({'error': 'Ayah not found'}), 404

    return jsonify(ayah_data)

@app.route('/api/search', methods=['GET'])
def search():
    column = request.args.get('column', 'source_word')
    query = request.args.get('query', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    matching_ayahs = []

    if column == 'full_text':
        clean_query = remove_diacritics(query).strip()
        if clean_query:
            sql = "SELECT sura_id AS surah, aya_id AS ayah FROM verses_clean WHERE text_clean LIKE ?"
            matching_ayahs = cursor.execute(sql, (f"%{clean_query}%",)).fetchall()
    elif column == 'topic':
        sql = '''
            SELECT DISTINCT at.surah, at.ayah 
            FROM ayah_topics at
            JOIN topics t ON at.topic_id = t.id
            WHERE t.name LIKE ?
        '''
        matching_ayahs = cursor.execute(sql, (f"%{query.strip()}%",)).fetchall()
    elif column in ['surah', 'ayah']:
        try:
            val = int(query)
            sql = f"SELECT DISTINCT surah, ayah FROM words WHERE {column} = ?"
            matching_ayahs = cursor.execute(sql, (val,)).fetchall()
        except ValueError:
            matching_ayahs = []
    elif column == 'word_text':
        clean_query = remove_diacritics(query)
        prefix = "" if clean_query.startswith(" ") else "%"
        suffix = "" if clean_query.endswith(" ") else "%"
        
        search_term = clean_query.strip()
        
        if search_term:
            pattern = f"{prefix}{search_term}{suffix}"
            sql = "SELECT DISTINCT surah, ayah FROM words WHERE word_simple_text LIKE ?"
            matching_ayahs = cursor.execute(sql, (pattern,)).fetchall()
        else:
            matching_ayahs = []
    else:
        valid_columns = ['source_word', 'wazn', 'meaning']
        if column in valid_columns:
            sql = f"SELECT DISTINCT surah, ayah FROM words WHERE {column} LIKE ?"
            matching_ayahs = cursor.execute(sql, (f"%{query.strip()}%",)).fetchall()

    if not matching_ayahs:
        conn.close()
        return jsonify({'total_found': 0, 'results': []})

    total_found = len(matching_ayahs)
    matching_ayahs = matching_ayahs[:500]
    results = []

    for row in matching_ayahs:
        ayah_data = get_ayah_details(cursor, row['surah'], row['ayah'])
        if ayah_data:
            results.append(ayah_data)

    conn.close()
    return jsonify({
        'total_found': total_found,
        'results': results
    })

@app.route('/api/add_ayah_note', methods=['POST'])
def add_ayah_note():
    data = request.json
    surah = data.get('surah')
    ayah = data.get('ayah')
    note_text = data.get('note_text', '').strip()

    if not surah or not ayah or not note_text:
        return jsonify({'error': 'Surah, ayah, and note_text are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ayah_notes (surah, ayah, note_text) VALUES (?, ?, ?)", (surah, ayah, note_text))
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'id': note_id, 'note_text': note_text})

@app.route('/api/delete_ayah_note', methods=['POST'])
def delete_ayah_note():
    data = request.json
    note_id = data.get('id')

    if not note_id:
        return jsonify({'error': 'Note ID is required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ayah_notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})

@app.route('/api/update_ayah_topics', methods=['POST'])
def update_ayah_topics():
    data = request.json
    surah, ayah, topic_ids = data.get('surah'), data.get('ayah'), data.get('topic_ids', [])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ayah_topics WHERE surah = ? AND ayah = ?", (surah, ayah))
    for t_id in topic_ids:
        cursor.execute("INSERT INTO ayah_topics (surah, ayah, topic_id) VALUES (?, ?, ?)", (surah, ayah, t_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/update_word', methods=['POST'])
def update_word():
    data = request.json
    word_id, field, value = data.get('id'), data.get('field'), data.get('value', '').strip()

    allowed_fields = ['source_word', 'wazn', 'meaning']
    if field not in allowed_fields:
        return jsonify({'status': 'error', 'message': 'Forbidden field'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE words SET {field} = ? WHERE id = ?", (value, word_id))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)