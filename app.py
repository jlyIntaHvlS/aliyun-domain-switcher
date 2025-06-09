from flask import Flask, render_template, request, jsonify
import requests
import json
from alibabacloud_alidns20150109.client import Client as Alidns20150109Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_alidns20150109 import models as alidns_20150109_models
from alibabacloud_tea_util import models as util_models
import logging
import webbrowser
import threading
import os

app = Flask(__name__)

# 域名与record_id映射
domains_grouped = {
    "uat": [
        {"name": "c-live-uat.itaiping.com", "record_id": "750504892456594432"},
        {"name": "live-pull-uat.itaiping.com", "record_id": "750355900240312320"},
        {"name": "live-push-uat.itaiping.com", "record_id": "750355800824879104"},
    ],
    "sit": [
        {"name": "c-live-sit.itaiping.com", "record_id": "750504812829774848"},
        {"name": "live-pull-sit.itaiping.com", "record_id": "750355686825761792"},
        {"name": "live-push-sit.itaiping.com", "record_id": "750355501208909824"},
#       {"name": "live-push-sit.ectaiping.com", "record_id": "899131973240838144"},
    ]
}

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=32c5dbdc-fa8f-48e3-b47f-3b340b4cd749"

# 全局变量，保存启动时的域名状态
startup_domain_status = []

def create_client():
    config = open_api_models.Config(
        access_key_id = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'),
        access_key_secret = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    )
    config.endpoint = 'alidns.cn-shanghai.aliyuncs.com'
    return Alidns20150109Client(config)

def get_domain_status(record_id):
    client = create_client()
    describe_domain_record_info_request = alidns_20150109_models.DescribeDomainRecordInfoRequest(
        record_id=record_id
    )
    runtime = util_models.RuntimeOptions()
    try:
        response = client.describe_domain_record_info_with_options(describe_domain_record_info_request, runtime)
        if hasattr(response.body, 'status') and response.body.status:
            return response.body.status.lower()
        else:
            return None
    except Exception as error:
        return None

def query_all_domain_status():
    result = []
    for group in domains_grouped.values():
        for d in group:
            try:
                status = get_domain_status(d['record_id'])
                if status is None:
                    status = 'disable'
                else:
                    status = status.lower()
            except Exception:
                status = 'disable'
            result.append({
                "name": d["name"],
                "record_id": d["record_id"],
                "status": status
            })
    return result

# 启动时查询一次
startup_domain_status = query_all_domain_status()

@app.route('/')
def index():
    grouped_status = {}
    for group, ds in domains_grouped.items():
        grouped_status[group] = []
        for d in ds:
            try:
                status = get_domain_status(d['record_id'])
                if status is None:
                    status = 'disable'
                else:
                    status = status.lower()
            except Exception:
                status = 'disable'
            grouped_status[group].append({
                "name": d["name"],
                "record_id": d["record_id"],
                "status": status
            })
    return render_template('index.html', domains_grouped=grouped_status)

@app.route('/toggle_domain', methods=['POST'])
def toggle_domain():
    record_id = request.json.get('record_id')
    action = request.json.get('action')
    status = 'enable' if action == 'start' else 'disable'

    # 根据 record_id 查找域名
    domain_name = next((d['name'] for group in domains_grouped.values() for d in group if d['record_id'] == record_id), record_id)

    try:
        client = create_client()
        request_obj = alidns_20150109_models.SetDomainRecordStatusRequest(
            record_id=record_id,
            status=status.upper()  # 阿里云API需要大写
        )
        client.set_domain_record_status(request_obj)
        send_wechat_message(f"域名：{domain_name} 已{'启动' if status == 'enable' else '停止'}")
        return jsonify({'status': 'success'})
    except Exception:
        return jsonify({'status': 'fail', 'error': '切换域名状态失败'})

@app.route('/refresh_status', methods=['GET'])
def refresh_status():
    grouped_status = {}
    for group, ds in domains_grouped.items():
        grouped_status[group] = []
        for d in ds:
            try:
                status = get_domain_status(d['record_id'])
                if status is None:
                    status = 'disable'
                else:
                    status = status.lower()
            except Exception:
                status = 'disable'
            grouped_status[group].append({
                "name": d["name"],
                "record_id": d["record_id"],
                "status": status
            })
    return jsonify(grouped_status)

def send_wechat_message(message):
    headers = {'Content-Type': 'application/json'}
    data = {
        "msgtype": "text",
        "text": {
            "content": message
        }
    }
    response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        pass  # 不再打印日志

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

if __name__ == '__main__':
    while True:
        try:
            threading.Timer(1.0, lambda: webbrowser.open('http://localhost:4999')).start()
            app.run(debug=False, port=4999)
        except Exception as e:
            import time
            print(f"程序崩溃，5秒后重启。错误信息：{e}")
            time.sleep(5)
