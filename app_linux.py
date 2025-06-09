import hashlib
import hmac
import base64
import urllib.parse
import datetime
import uuid
import requests
from flask import Flask, render_template, request, jsonify
import logging
import os
import time
import json

app = Flask(__name__)

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dns_manager.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    ]
}

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=32c5dbdc-fa8f-48e3-b47f-3b340b4cd749"

# 阿里云API配置
ALIYUN_API_ENDPOINT = "https://alidns.cn-shanghai.aliyuncs.com"
ALIYUN_ACCESS_KEY_ID = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
ALIYUN_ACCESS_KEY_SECRET = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')

def sign_request(parameters):
    """生成阿里云API签名"""
    # 添加公共参数
    parameters['Format'] = 'JSON'
    parameters['Version'] = '2015-01-09'
    parameters['AccessKeyId'] = ALIYUN_ACCESS_KEY_ID
    parameters['SignatureMethod'] = 'HMAC-SHA1'
    parameters['Timestamp'] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    parameters['SignatureVersion'] = '1.0'
    parameters['SignatureNonce'] = str(uuid.uuid4())
    
    # 排序参数
    sorted_params = sorted(parameters.items())
    
    # 构建规范化的查询字符串
    canonicalized_query_string = urllib.parse.urlencode(sorted_params)
    
    # 构建待签名字符串
    string_to_sign = "GET&%2F&" + urllib.parse.quote(canonicalized_query_string, safe='')
    
    # 计算签名
    key = ALIYUN_ACCESS_KEY_SECRET + "&"
    signature = hmac.new(key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    signature = base64.b64encode(signature).decode('utf-8')
    
    # 添加签名到参数
    parameters['Signature'] = signature
    return parameters

def get_domain_status(record_id):
    """使用原生HTTP请求获取域名状态"""
    try:
        logger.info(f"获取域名状态, record_id: {record_id}")
        
        # 构建请求参数
        params = {
            'Action': 'DescribeDomainRecordInfo',
            'RecordId': record_id
        }
        
        # 签名请求
        signed_params = sign_request(params)
        
        # 发送请求
        response = requests.get(ALIYUN_API_ENDPOINT, params=signed_params)
        
        if response.status_code == 200:
            data = response.json()
            if 'Status' in data:
                status = data['Status'].lower()
                logger.info(f"域名状态获取成功, record_id: {record_id}, 状态: {status}")
                return status
        
        logger.warning(f"未获取到域名状态, record_id: {record_id}, 响应: {response.text}")
        return 'disable'
    except Exception as e:
        logger.error(f"获取域名状态异常, record_id: {record_id}")
        logger.error(str(e))
        return 'disable'

def set_domain_record_status(record_id, status):
    """使用原生HTTP请求设置域名状态"""
    try:
        logger.info(f"设置域名状态, record_id: {record_id}, status: {status}")
        
        # 构建请求参数
        params = {
            'Action': 'SetDomainRecordStatus',
            'RecordId': record_id,
            'Status': status.upper()
        }
        
        # 签名请求
        signed_params = sign_request(params)
        
        # 发送请求
        response = requests.get(ALIYUN_API_ENDPOINT, params=signed_params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('RecordId') == record_id:
                return True
        
        logger.warning(f"设置域名状态失败, record_id: {record_id}, 响应: {response.text}")
        return False
    except Exception as e:
        logger.error(f"设置域名状态异常, record_id: {record_id}")
        logger.error(str(e))
        return False

def query_all_domain_status():
    logger.info("开始查询所有域名状态")
    result = []
    for group_name, group in domains_grouped.items():
        for d in group:
            try:
                status = get_domain_status(d['record_id'])
                result.append({
                    "name": d["name"],
                    "record_id": d["record_id"],
                    "status": status
                })
            except Exception as e:
                logger.error(f"查询域名状态失败: {d['name']}({d['record_id']})")
                logger.error(str(e))
                result.append({
                    "name": d["name"],
                    "record_id": d["record_id"],
                    "status": 'error'
                })
    logger.info(f"完成域名状态查询, 共{len(result)}条记录")
    return result

# 启动时查询一次
try:
    startup_domain_status = query_all_domain_status()
    logger.info("启动时域名状态查询完成")
except Exception as e:
    logger.error("启动时域名状态查询失败")
    logger.error(str(e))
    startup_domain_status = []

@app.route('/')
def index():
    logger.info("访问首页")
    try:
        grouped_status = {}
        for group, ds in domains_grouped.items():
            grouped_status[group] = []
            for d in ds:
                try:
                    status = get_domain_status(d['record_id'])
                    grouped_status[group].append({
                        "name": d["name"],
                        "record_id": d["record_id"],
                        "status": status
                    })
                except Exception as e:
                    logger.error(f"首页查询域名状态失败: {d['name']}")
                    logger.error(str(e))
                    grouped_status[group].append({
                        "name": d["name"],
                        "record_id": d["record_id"],
                        "status": 'error'
                    })
        return render_template('index.html', domains_grouped=grouped_status)
    except Exception as e:
        logger.error("首页渲染异常")
        logger.error(str(e))
        return "服务器内部错误", 500

@app.route('/toggle_domain', methods=['POST'])
def toggle_domain():
    logger.info("收到域名切换请求")
    try:
        record_id = request.json.get('record_id')
        action = request.json.get('action')
        status = 'enable' if action == 'start' else 'disable'
        logger.info(f"切换域名状态: record_id={record_id}, action={action}, target_status={status}")

        # 查找域名名称
        domain_name = "未知域名"
        for group in domains_grouped.values():
            for d in group:
                if d['record_id'] == record_id:
                    domain_name = d['name']
                    break
        
        # 使用原生HTTP请求设置域名状态
        success = set_domain_record_status(record_id, status.upper())
        
        if success:
            logger.info(f"域名状态切换成功: {domain_name} -> {status}")
            send_wechat_message(f"域名：{domain_name} 已{'启动' if status == 'enable' else '停止'}")
            
            # 等待状态更新
            time.sleep(1)
            
            # 立即查询新状态确认
            new_status = get_domain_status(record_id)
            return jsonify({'status': 'success', 'new_status': new_status})
        else:
            logger.error(f"域名状态切换失败: {domain_name}")
            return jsonify({'status': 'fail', 'error': 'API调用失败'}), 500
    
    except Exception as e:
        logger.error("域名状态切换失败")
        logger.error(str(e))
        return jsonify({'status': 'fail', 'error': str(e)}), 500

@app.route('/refresh_status', methods=['GET'])
def refresh_status():
    logger.info("收到状态刷新请求")
    try:
        grouped_status = {}
        for group, ds in domains_grouped.items():
            grouped_status[group] = []
            for d in ds:
                try:
                    status = get_domain_status(d['record_id'])
                    grouped_status[group].append({
                        "name": d["name"],
                        "record_id": d["record_id"],
                        "status": status
                    })
                except Exception as e:
                    logger.error(f"刷新状态失败: {d['name']}")
                    logger.error(str(e))
                    grouped_status[group].append({
                        "name": d["name"],
                        "record_id": d["record_id"],
                        "status": 'error'
                    })
        return jsonify(grouped_status)
    except Exception as e:
        logger.error("状态刷新全局异常")
        logger.error(str(e))
        return jsonify({'status': 'error', 'message': '刷新失败'}), 500

def send_wechat_message(message):
    try:
        headers = {'Content-Type': 'application/json'}
        data = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(data))
        if response.status_code != 200:
            logger.warning(f"企业微信消息发送失败: HTTP {response.status_code}, 响应: {response.text}")
        else:
            logger.info("企业微信消息发送成功")
    except Exception as e:
        logger.error("发送企业微信消息异常")
        logger.error(str(e))

if __name__ == '__main__':
    logger.info("=== 应用程序启动 ===")
    
    # 禁用Flask的默认日志处理器
    flask_log = logging.getLogger('werkzeug')
    flask_log.setLevel(logging.WARNING)
    
    port = 4999
    restart_count = 0
    max_restarts = 10
    
    while restart_count < max_restarts:
        try:
            logger.info(f"启动Flask服务 (端口: {port}), 重启次数: {restart_count}")
            app.run(debug=False, port=port, host="0.0.0.0")
        except Exception as e:
            restart_count += 1
            logger.critical(f"应用程序崩溃! 重启次数: {restart_count}/{max_restarts}")
            logger.critical(f"错误类型: {type(e).__name__}")
            logger.critical(f"错误信息: {str(e)}")
            
            if restart_count >= max_restarts:
                logger.critical("达到最大重启次数，程序终止")
                break
            
            logger.info("5秒后重新启动...")
            time.sleep(5)
    
    logger.critical("=== 应用程序终止 ===")
