import os
import json
from dotenv import load_dotenv
from flask import Flask
from db import DB
from daemon import Daemon
from transport.http import HttpTransport
from transport.http import http_transport, init_http_transport
from envelope import Envelope
import copy

load_dotenv()

app = Flask(__name__)

node_id = os.getenv('F42BBS_NODE_ID')
shared_key = os.getenv('F42BBS_KEY')
db_path = os.getenv('F42BBS_DB', 'f42bbs.db')
port = int(os.getenv('STEP_PORT', '8766'))

with open('nodes.json', 'r') as f:
    nodes_data = json.load(f)
    nodes = nodes_data['nodes']

if not node_id:
    raise ValueError('F42BBS_NODE_ID not set')
if not shared_key:
    raise ValueError('F42BBS_KEY not set')

db = DB(db_path)
transport = HttpTransport()
daemon = Daemon(node_id, db, transport, shared_key)

https_peers = []
for node in nodes:
    if node['node_id'] == node_id:
        continue
    for transport_addr in node['transports']:
        if transport_addr.startswith('https:'):
            url = transport_addr[6:]
            https_peers.append({
                'node_id': node['node_id'],
                'name': node['name'],
                'url': url,
                'trust': node['trust']
            })

original_fanout = daemon._fanout

def http_fanout(env: Envelope) -> None:
    subscribers = daemon.db.get_subscribers(env.topic)
    
    for peer in https_peers:
        if peer['node_id'] == env.origin:
            continue
        if peer['node_id'] == daemon.node_id:
            continue
        if peer['trust'] == 'blocked':
            continue
        
        env_copy = copy.deepcopy(env)
        env_copy.hops = env.hops + [daemon.node_id]
        transport.send(env_copy, to_address=peer['url'])

daemon._fanout = http_fanout

app.register_blueprint(http_transport)
init_http_transport(daemon, shared_key)

if __name__ == '__main__':
    print(f'F42BBS HTTP Node')
    print(f'Node ID: {node_id}')
    print(f'Port: {port}')
    print(f'Database: {db_path}')
    print(f'HTTPS Peers: {len(https_peers)}')
    for peer in https_peers:
        print(f'  - {peer["node_id"]} ({peer["name"]}): {peer["url"]}')
    print()
    app.run(host='0.0.0.0', port=port, debug=False)
