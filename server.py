import re
import requests
import json
from typing import Any, Dict, List, Optional
from flask import Flask, jsonify, render_template
from flask_cors import CORS

def run_datalens_query(page: int = 1) -> Optional[Dict[str, Any]]:
    url = "https://datalens.yandex/charts/api/run"
    headers = {"Content-Type": "application/json"}
    payload: Dict[str, Any] = {
        "id": "5jjsemsj8ssmr",
        "params": {},
        "responseOptions": {"includeConfig": True, "includeLogs": False}
    }
    if page > 1:
        payload["params"]["_page"] = str(page)
    try:
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"Ошибка запроса страницы {page}:", e)
        print("Код ответа:", resp.status_code)
        print("Тело ответа:", resp.text)
        return None
    return resp.json()

def extract_nodes_by_type(node: Dict[str, Any], types: List[str]) -> List[str]:
    res: List[str] = []
    t = node.get('type')
    content = node.get('content')
    if t == 'text' and 'text' in types and isinstance(content, str):
        res.append(content)
    elif t in ('bold', 'color') and t in types:
        if isinstance(content, str):
            res.append(content)
        elif isinstance(content, dict) and content.get('type') == 'text':
            res.append(content.get('content', ''))
    for child in node.get('children', []):
        res.extend(extract_nodes_by_type(child, types))
    return res

def process_datalens_response(resp: Dict[str, Any]) -> List[str]:
    head = resp['data']['head']
    rows = resp['data']['rows']
    idx_changes = next(i for i, h in enumerate(head) if h['name'] == 'Changes')
    idx_price = next(i for i, h in enumerate(head) if h['name'] == 'Market price')

    outputs: List[str] = []
    for row in rows:
        cells = row['cells']
        change_node = cells[idx_changes]['value']
        name = extract_nodes_by_type(change_node, ['bold'])[0] if extract_nodes_by_type(change_node, ['bold']) else ''
        texts = extract_nodes_by_type(change_node, ['text'])
        volume = next((v for v in reversed(texts) if v.isdigit()), '')
        price_node = cells[idx_price]['value']
        floors = extract_nodes_by_type(price_node, ['bold'])
        floor = floors[0].replace('💎', '') if floors else ''
        colors = extract_nodes_by_type(price_node, ['color'])
        def fmt(x: str) -> str:
            return x.replace('▲', '+').replace('▼', '-').strip()
        change_1d = fmt(colors[0]) if len(colors) > 0 else ''
        change_7d = fmt(colors[1]) if len(colors) > 1 else ''
        outputs.append(
            f"{name}: Volume: {volume} ton; "
            f"floorprice: {floor} ton; "
            f"1D: {change_1d}; "
            f"7D: {change_7d}."
        )
    return outputs

def parse_1d_changes(text: str):
    pattern = re.compile(r'([A-Za-z]+):\s*Volume:[^;]+;\s*floorprice:[^;]+;\s*1D:\s*([+-]\s*\d+(?:\.\d+)?)%;')
    data = {}
    for match in pattern.finditer(text):
        raw_name = match.group(1)
        raw_change = match.group(2).replace(' ', '')
        pretty_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', raw_name)
        data[pretty_name] = float(raw_change)
    return jsonify(data)

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    lines: List[str] = []
    for i in range(1, 8):
        data = run_datalens_query(page=i)
        if data:
            lines.extend(process_datalens_response(data))
    full_text = ' '.join(lines)
    return parse_1d_changes(full_text)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
