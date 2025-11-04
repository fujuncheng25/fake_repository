#!/usr/bin/env python3
import http.server
import socketserver
import os
import mimetypes
from urllib.parse import unquote

PORT = 44817
HOST = "0.0.0.0"

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # 添加CORS头部
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_GET(self):
        # 解码URL路径
        path = unquote(self.path)
        
        # 如果请求根路径，返回index.html
        if path == '/' or path == '/index.html':
            self.path = '/index.html'
        elif path == '/':
            self.path = '/index.html'
        
        # 尝试提供静态文件
        try:
            super().do_GET()
        except FileNotFoundError:
            # 如果文件未找到，返回404页面
            self.path = '/404.html'
            try:
                super().do_GET()
            except:
                # 如果连404页面都没有，返回简单404响应
                self.send_response(404)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>404 Not Found</h1>")
    
    def guess_type(self, path):
        # 使用mimetypes模块猜测MIME类型
        mimetype, _ = mimetypes.guess_type(path)
        if mimetype is None:
            mimetype = 'application/octet-stream'
        return mimetype

# 设置当前工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 启动服务器
with socketserver.TCPServer((HOST, PORT), CustomHTTPRequestHandler) as httpd:
    print(f"流浪猫公益项目服务器运行在 http://{HOST}:{PORT}/")
    print("按 Ctrl+C 停止服务器")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")