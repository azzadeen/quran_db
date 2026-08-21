import os
import sqlite3
import re
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "quran_corpus.db")

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

def get_custom_links_for_ayah(cursor, s, a):
    """Retrieves bi-directional custom links for a specific ayah and formats linked text."""
    query = '''
        SELECT id, source_surah, source_ayah, target_surah, target_ayah, link_comment
        FROM ayah_custom_links
        WHERE (source_surah = ? AND source_ayah = ?)
           OR (target_surah = ? AND target_ayah = ?)
    '''
    rows = cursor.execute(query, (s, a, s, a)).fetchall()
    links = []

    for r in rows:
        # Determine linked target/source relative to current ayah
        if r['source_surah'] == s and r['source_ayah'] == a:
            l_surah, l_ayah = r['target_surah'], r['target_ayah']
        else:
            l_surah, l_ayah = r['source_surah'], r['source_ayah']

        # Fetch text for the linked verse
        words = cursor.execute(
            "SELECT word_text FROM words WHERE surah = ? AND ayah = ? ORDER BY word_num ASC",
            (l_surah, l_ayah)
        ).fetchall()
        linked_text = " ".join([w['word_text'] for w in words]) if words else ""

        links.append({
            'link_id': r['id'],
            'linked_surah': l_surah,
            'linked_surah_name': SURAH_NAMES.get(l_surah, f"سورة {l_surah}"),
            'linked_ayah': l_ayah,
            'linked_text': linked_text,
            'link_comment': r['link_comment']
        })

    return links

def get_related_ayahs_chain(cursor, s, a):
    """Finds the entire contiguous chain of connected verses along with their assigned topic names."""
    linked_set = set()
    rows = cursor.execute("SELECT ayah FROM ayah_relations WHERE surah = ?", (s,)).fetchall()
    for r in rows:
        linked_set.add(r['ayah'])

    start_a = a
    while start_a in linked_set:
        start_a -= 1

    end_a = a
    while (end_a + 1) in linked_set:
        end_a += 1

    if start_a == end_a:
        return []

    related = []
    for cur_a in range(start_a, end_a + 1):
        clean_row = cursor.execute(
            "SELECT text_clean FROM verses_clean WHERE sura_id = ? AND aya_id = ?",
            (s, cur_a)
        ).fetchone()
        words = cursor.execute(
            "SELECT word_text FROM words WHERE surah = ? AND ayah = ? ORDER BY word_num ASC",
            (s, cur_a)
        ).fetchall()
        
        topics = cursor.execute(
            "SELECT t.name FROM topics t "
            "JOIN ayah_topics at ON t.id = at.topic_id "
            "WHERE at.surah = ? AND at.ayah = ? ORDER BY t.name ASC",
            (s, cur_a)
        ).fetchall()

        full_text = " ".join([w['word_text'] for w in words])
        clean_text = clean_row['text_clean'] if clean_row else full_text

        related.append({
            'ayah': cur_a,
            'full_text': full_text,
            'clean_text': clean_text,
            'topics': [t['name'] for t in topics]
        })

    return related

def get_ayah_details(cursor, s, a):
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

    rel_exists = cursor.execute(
        "SELECT 1 FROM ayah_relations WHERE surah = ? AND ayah = ?",
        (s, a)
    ).fetchone()

    related_chain = get_related_ayahs_chain(cursor, s, a)
    custom_links = get_custom_links_for_ayah(cursor, s, a)

    clean_text = clean_row['text_clean'] if clean_row else ""
    full_ayah = " ".join([w['word_text'] for w in words_in_ayah])

    return {
        'surah': s,
        'surah_name': SURAH_NAMES.get(s, f"سورة {s}"),
        'ayah': a,
        'full_text': full_ayah,
        'clean_text': clean_text,
        'is_related_to_prev': True if rel_exists else False,
        'related_ayahs': related_chain,
        'custom_links': custom_links,
        'assigned_topic_ids': [t['topic_id'] for t in assigned_topics],
        'notes': [dict(n) for n in notes],
        'words': [dict(w) for w in words_in_ayah]
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/topics')
def topics_page():
    return render_template('topics.html')

@app.route('/api/topics', methods=['GET'])
def get_topics():
    conn = get_db_connection()
    topics = conn.execute("SELECT id, name FROM topics ORDER BY name ASC").fetchall()
    conn.close()
    return jsonify([dict(t) for t in topics])

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

@app.route('/api/update_topic', methods=['POST'])
def update_topic():
    data = request.json
    topic_id = data.get('id')
    name = data.get('name', '').strip()

    if not topic_id or not name:
        return jsonify({"error": "Topic ID and new name are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE topics SET name = ? WHERE id = ?", (name, topic_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Topic name already exists"}), 400
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete_topic', methods=['POST'])
def delete_topic():
    data = request.json
    topic_id = data.get('id')

    if not topic_id:
        return jsonify({"error": "Topic ID is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ayah_topics WHERE topic_id = ?", (topic_id,))
    cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
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

@app.route('/api/add_custom_link', methods=['POST'])
def add_custom_link():
    data = request.json
    s_surah = data.get('source_surah')
    s_ayah = data.get('source_ayah')
    t_surah = data.get('target_surah')
    t_ayah = data.get('target_ayah')
    comment = data.get('link_comment', '').strip()

    if not all([s_surah, s_ayah, t_surah, t_ayah]):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure target verse exists in words DB
    target_exists = cursor.execute('SELECT 1 FROM words WHERE surah = ? AND ayah = ?', (t_surah, t_ayah)).fetchone()
    if not target_exists:
        conn.close()
        return jsonify({'error': 'Target ayah does not exist'}), 404

    cursor.execute('''
        INSERT INTO ayah_custom_links (source_surah, source_ayah, target_surah, target_ayah, link_comment)
        VALUES (?, ?, ?, ?, ?)
    ''', (s_surah, s_ayah, t_surah, t_ayah, comment))

    conn.commit()

    # Return updated current ayah details for instantaneous UI re-rendering
    updated_details = get_ayah_details(cursor, s_surah, s_ayah)
    conn.close()

    return jsonify({'status': 'success', 'data': updated_details})

@app.route('/api/delete_custom_link', methods=['POST'])
def delete_custom_link():
    data = request.json
    link_id = data.get('link_id')
    c_surah = data.get('current_surah')
    c_ayah = data.get('current_ayah')

    if not link_id:
        return jsonify({'error': 'Link ID is required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ayah_custom_links WHERE id = ?', (link_id,))
    conn.commit()

    # Return updated current ayah details for instantaneous UI re-rendering
    updated_details = get_ayah_details(cursor, c_surah, c_ayah) if c_surah and c_ayah else None
    conn.close()

    return jsonify({'status': 'success', 'data': updated_details})

@app.route('/api/toggle_ayah_relation', methods=['POST'])
def toggle_ayah_relation():
    data = request.json
    surah, ayah, is_related = data.get('surah'), data.get('ayah'), data.get('is_related', False)

    if not surah or not ayah:
        return jsonify({'error': 'Surah and ayah are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    if is_related:
        cursor.execute("INSERT OR IGNORE INTO ayah_relations (surah, ayah) VALUES (?, ?)", (surah, ayah))
    else:
        cursor.execute("DELETE FROM ayah_relations WHERE surah = ? AND ayah = ?", (surah, ayah))

    conn.commit()
    updated_details = get_ayah_details(cursor, surah, ayah)
    conn.close()

    return jsonify({'status': 'success', 'data': updated_details})

@app.route('/api/add_ayah_note', methods=['POST'])
def add_ayah_note():
    data = request.json
    surah, ayah, note_text = data.get('surah'), data.get('ayah'), data.get('note_text', '').strip()

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

    updated_details = get_ayah_details(cursor, surah, ayah)
    conn.close()

    return jsonify({'status': 'success', 'data': updated_details})

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

@app.route('/quran')
def quran_view():
    return render_template('quran.html')

import traceback

# Starting (surah, ayah) for Madani Mushaf pages 1 to 604
MADANI_PAGE_STARTS = [
    (1, 1), (2, 1), (2, 6), (2, 17), (2, 25), (2, 30), (2, 38), (2, 49), (2, 58), (2, 62),
    (2, 70), (2, 77), (2, 84), (2, 89), (2, 94), (2, 102), (2, 106), (2, 113), (2, 120), (2, 127),
    (2, 135), (2, 142), (2, 146), (2, 154), (2, 164), (2, 170), (2, 177), (2, 182), (2, 187), (2, 191),
    (2, 197), (2, 203), (2, 211), (2, 216), (2, 220), (2, 225), (2, 231), (2, 234), (2, 238), (2, 246),
    (2, 249), (2, 253), (2, 257), (2, 260), (2, 265), (2, 270), (2, 275), (2, 282), (2, 283), (3, 1),

    # Pages 51 - 100
    (3, 10), (3, 16), (3, 23), (3, 30), (3, 38), (3, 46), (3, 53), (3, 62), (3, 71), (3, 78),
    (3, 84), (3, 92), (3, 101), (3, 109), (3, 116), (3, 122), (3, 133), (3, 141), (3, 149), (3, 154),
    (3, 166), (3, 174), (3, 181), (3, 187), (3, 195), (4, 1), (4, 7), (4, 12), (4, 15), (4, 20),
    (4, 24), (4, 27), (4, 34), (4, 38), (4, 45), (4, 52), (4, 60), (4, 66), (4, 75), (4, 80),
    (4, 87), (4, 92), (4, 95), (4, 102), (4, 106), (4, 114), (4, 122), (4, 128), (4, 135), (4, 141),

    # Pages 101 - 150
    (4, 148), (4, 155), (4, 163), (4, 171), (5, 1), (5, 3), (5, 6), (5, 10), (5, 14), (5, 18),
    (5, 24), (5, 32), (5, 37), (5, 42), (5, 46), (5, 51), (5, 58), (5, 65), (5, 71), (5, 77),
    (5, 83), (5, 90), (5, 96), (5, 104), (5, 109), (6, 1), (6, 9), (6, 19), (6, 28), (6, 36),
    (6, 45), (6, 53), (6, 60), (6, 70), (6, 74), (6, 82), (6, 91), (6, 95), (6, 102), (6, 111),
    (6, 119), (6, 125), (6, 132), (6, 138), (6, 143), (6, 147), (6, 152), (6, 158), (7, 1), (7, 12),

    # Pages 151 - 200
    (7, 23), (7, 31), (7, 38), (7, 44), (7, 52), (7, 58), (7, 68), (7, 74), (7, 82), (7, 88),
    (7, 96), (7, 105), (7, 121), (7, 131), (7, 138), (7, 144), (7, 150), (7, 156), (7, 160), (7, 164),
    (7, 171), (7, 179), (7, 188), (7, 196), (8, 1), (8, 9), (8, 17), (8, 26), (8, 34), (8, 41),
    (8, 46), (8, 53), (8, 62), (8, 70), (9, 1), (9, 7), (9, 14), (9, 21), (9, 27), (9, 32),
    (9, 37), (9, 41), (9, 48), (9, 55), (9, 62), (9, 69), (9, 73), (9, 80), (9, 87), (9, 94),

    # Pages 201 - 250
    (9, 100), (9, 107), (9, 112), (9, 118), (9, 123), (10, 1), (10, 7), (10, 15), (10, 21), (10, 26),
    (10, 34), (10, 43), (10, 54), (10, 62), (10, 71), (10, 79), (10, 89), (10, 98), (10, 107), (11, 6),
    (11, 13), (11, 20), (11, 29), (11, 38), (11, 46), (11, 54), (11, 63), (11, 72), (11, 82), (11, 89),
    (11, 98), (11, 109), (12, 1), (12, 7), (12, 15), (12, 23), (12, 31), (12, 38), (12, 44), (12, 53),
    (12, 64), (12, 70), (12, 79), (12, 87), (12, 96), (12, 104), (13, 6), (13, 14), (13, 19), (13, 29),

    # Pages 251 - 300
    (13, 35), (13, 43), (14, 6), (14, 11), (14, 19), (14, 25), (14, 34), (14, 43), (15, 1), (15, 16),
    (15, 32), (15, 52), (15, 71), (15, 91), (16, 7), (16, 15), (16, 27), (16, 35), (16, 43), (16, 55),
    (16, 65), (16, 73), (16, 80), (16, 88), (16, 94), (16, 103), (16, 111), (16, 119), (17, 1), (17, 8),
    (17, 18), (17, 28), (17, 39), (17, 50), (17, 59), (17, 67), (17, 76), (17, 87), (17, 97), (17, 105),
    (18, 5), (18, 16), (18, 21), (18, 28), (18, 35), (18, 46), (18, 54), (18, 62), (18, 75), (18, 84),

    # Pages 301 - 350
    (18, 98), (19, 1), (19, 12), (19, 26), (19, 39), (19, 52), (19, 65), (19, 77), (19, 96), (20, 13),
    (20, 38), (20, 52), (20, 65), (20, 77), (20, 88), (20, 99), (20, 114), (20, 126), (21, 1), (21, 11),
    (21, 25), (21, 36), (21, 45), (21, 58), (21, 73), (21, 82), (21, 91), (21, 102), (22, 1), (22, 6),
    (22, 16), (22, 24), (22, 31), (22, 39), (22, 47), (22, 56), (22, 65), (22, 73), (23, 1), (23, 18),
    (23, 28), (23, 43), (23, 60), (23, 75), (23, 90), (23, 105), (24, 1), (24, 11), (24, 21), (24, 28),

    # Pages 351 - 400
    (24, 32), (24, 37), (24, 44), (24, 54), (24, 59), (25, 3), (25, 12), (25, 21), (25, 33), (25, 44),
    (25, 56), (25, 68), (26, 1), (26, 20), (26, 40), (26, 61), (26, 84), (26, 112), (26, 137), (26, 160),
    (26, 184), (26, 207), (27, 1), (27, 14), (27, 23), (27, 36), (27, 45), (27, 56), (27, 64), (27, 77),
    (27, 89), (28, 6), (28, 14), (28, 22), (28, 29), (28, 36), (28, 44), (28, 51), (28, 60), (28, 71),
    (28, 78), (28, 85), (29, 7), (29, 15), (29, 24), (29, 31), (29, 39), (29, 46), (29, 53), (29, 64),

    # Pages 401 - 450
    (30, 1), (30, 6), (30, 16), (30, 25), (30, 33), (30, 42), (30, 51), (31, 1), (31, 12), (31, 22),
    (31, 29), (32, 1), (32, 12), (32, 21), (33, 1), (33, 7), (33, 16), (33, 23), (33, 31), (33, 36),
    (33, 44), (33, 51), (33, 55), (33, 63), (34, 1), (34, 8), (34, 15), (34, 23), (34, 32), (34, 40),
    (34, 49), (35, 4), (35, 12), (35, 19), (35, 31), (35, 39), (35, 45), (36, 13), (36, 28), (36, 41),
    (36, 55), (36, 71), (37, 25), (37, 52), (37, 83), (37, 103), (37, 127), (37, 154), (38, 15), (38, 27),

    # Pages 451 - 500
    (38, 43), (38, 62), (38, 84), (39, 6), (39, 11), (39, 22), (39, 32), (39, 41), (39, 48), (39, 57),
    (39, 68), (40, 1), (40, 8), (40, 17), (40, 26), (40, 34), (40, 41), (40, 51), (40, 59), (40, 67),
    (40, 78), (41, 12), (41, 21), (41, 30), (41, 39), (41, 47), (42, 11), (42, 23), (42, 32), (42, 45),
    (42, 52), (43, 11), (43, 23), (43, 34), (43, 48), (43, 61), (43, 74), (44, 19), (44, 40), (45, 14),
    (45, 23), (45, 33), (46, 15), (46, 21), (46, 29), (47, 12), (47, 20), (47, 30), (48, 10), (48, 16),

    # Pages 501 - 550
    (48, 24), (49, 1), (49, 12), (50, 1), (50, 36), (51, 31), (52, 15), (53, 27), (54, 7), (54, 41),
    (55, 17), (55, 78), (56, 51), (57, 12), (57, 19), (57, 25), (58, 7), (58, 12), (58, 22), (59, 10),
    (59, 17), (60, 6), (61, 1), (62, 9), (63, 9), (64, 10), (65, 6), (66, 8), (67, 1), (67, 27),
    (68, 16), (68, 43), (69, 35), (70, 11), (70, 40), (71, 11), (72, 14), (73, 20), (74, 48), (75, 20),
    (76, 26), (77, 19), (78, 31), (79, 16), (80, 1), (81, 1), (82, 1), (83, 7), (84, 1), (85, 1),

    # Pages 551 - 600
    (86, 1), (87, 1), (88, 1), (89, 1), (90, 1), (91, 1), (92, 1), (93, 1), (94, 1), (95, 1),
    (96, 1), (97, 1), (98, 1), (99, 1), (100, 1), (101, 1), (102, 1), (103, 1), (104, 1), (105, 1),
    (106, 1), (107, 1), (108, 1), (109, 1), (110, 1), (111, 1), (112, 1), (113, 1), (114, 1), (114, 6),
    (86, 1), (87, 1), (88, 1), (89, 1), (90, 1), (91, 1), (92, 1), (93, 1), (94, 1), (95, 1),
    (96, 1), (97, 1), (98, 1), (99, 1), (100, 1), (101, 1), (102, 1), (103, 1), (104, 1), (105, 1),

    # Pages 601 - 604
    (107, 1), (109, 1), (111, 1), (112, 1)
]

def get_page_ayah_bounds(page_num):
    """Calculates start and end (surah, ayah) for a given Madani page number (1-604)."""
    if not 1 <= page_num <= 604:
        return None, None
        
    start_s, start_a = MADANI_PAGE_STARTS[page_num - 1]
    
    if page_num < 604:
        next_s, next_a = MADANI_PAGE_STARTS[page_num]
        if next_a == 1:
            end_s = next_s - 1
            end_a = 999  # Large upper bound to fetch all ayahs in previous surah
        else:
            end_s = next_s
            end_a = next_a - 1
    else:
        end_s, end_a = 114, 6  # Last verse of Surah An-Nas

    return (start_s, start_a), (end_s, end_a)


@app.route('/api/page')
def get_page_data():
    try:
        page_num = request.args.get('page', 1, type=int)
        (start_s, start_a), (end_s, end_a) = get_page_ayah_bounds(page_num)

        if not start_s:
            return jsonify({"error": f"Invalid page number: {page_num}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build SQL condition to span cross-surah page boundaries
        if start_s == end_s:
            sql = """
                SELECT surah, ayah, word_text 
                FROM words 
                WHERE surah = ? AND ayah >= ? AND ayah <= ? 
                ORDER BY surah ASC, ayah ASC, word_num ASC
            """
            params = (start_s, start_a, end_a)
        else:
            sql = """
                SELECT surah, ayah, word_text 
                FROM words 
                WHERE (surah = ? AND ayah >= ?)
                   OR (surah > ? AND surah < ?)
                   OR (surah = ? AND ayah <= ?)
                ORDER BY surah ASC, ayah ASC, word_num ASC
            """
            params = (start_s, start_a, start_s, end_s, end_s, end_a)

        rows = cursor.execute(sql, params).fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": f"No words found for page {page_num}"}), 404

        # Group individual word tokens into full verses
        ayahs_dict = {}
        for r in rows:
            key = (r['surah'], r['ayah'])
            if key not in ayahs_dict:
                ayahs_dict[key] = []
            ayahs_dict[key].append(r['word_text'])

        ayahs_list = []
        surah_names_list = []

        for (s, a), words in ayahs_dict.items():
            s_name = SURAH_NAMES.get(s, f"سورة {s}")
            if s_name not in surah_names_list:
                surah_names_list.append(s_name)

            ayahs_list.append({
                "surah": s,
                "ayah": a,
                "full_text": " ".join(words),
                "surah_name": s_name
            })

        return jsonify({
            "page": page_num,
            "surahs": surah_names_list,
            "ayahs": ayahs_list
        })

    except Exception as e:
        print("\n--- ERROR IN /api/page ---")
        traceback.print_exc()
        print("---------------------------\n")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
