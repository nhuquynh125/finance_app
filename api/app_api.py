from flask import Flask, jsonify, request
from app.core.transaction_manager import TransactionManager
from app.data.models import get_connection

app = Flask(__name__)
tm = TransactionManager()

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    month = request.args.get('month')
    txs = tm.get_transactions(month=month)
    return jsonify(txs)

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    data = request.json
    # account_id, amount, type, description, date, category_id, note
    alert = tm.add_transaction(
        account_id=data.get('account_id', 1),
        amount=data.get('amount'),
        type_=data.get('type'),
        description=data.get('description'),
        date=data.get('date'),
        category_id=data.get('category_id'),
        note=data.get('note', '')
    )
    return jsonify({"status": "success", "alert": alert})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_connection()
    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    return jsonify([dict(c) for c in cats])

if __name__ == '__main__':
    # Chạy server nội bộ để Mobile App có thể kết nối (thường dùng port 5000)
    app.run(host='0.0.0.0', port=5000, debug=True)
