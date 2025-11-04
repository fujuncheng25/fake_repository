# 流浪猫公益项目 - CATalist Web Application

一个基于邮箱认证的流浪猫公益网站，致力于帮助流浪猫找到温暖的家。

## 项目特点

- 邮箱认证系统（注册/登录/登出）
- 响应式设计，适配移动端和桌面端
- 猫咪信息展示
- 领养申请功能

## 技术栈

- HTML5
- CSS3
- JavaScript (ES6+)
- 本地存储 (LocalStorage)

## 安装和运行

1. 克隆项目:
   ```
   git clone <repository-url>
   ```

2. 进入项目目录:
   ```
   cd CATalist_webapplication_CTB_project_with_OPENHANDS
   ```

3. 运行服务器:
   ```
   node server.js
   ```

4. 在浏览器中访问: http://localhost:44817

## 功能说明

### 用户认证
- 用户可以通过邮箱注册账户
- 注册时需要验证邮箱格式和密码强度
- 用户登录后可以申请领养猫咪

### 猫咪信息
- 展示待领养的猫咪信息
- 包括猫咪名称、年龄、性别和描述

## 开发说明

所有代码均使用纯JavaScript实现，无需额外依赖。

## 项目结构

```
.
├── index.html          # 主页面
├── css/
│   └── style.css       # 样式文件
├── js/
│   ├── auth.js         # 认证系统
│   └── main.js         # 主应用逻辑
├── assets/             # 静态资源
├── server.js           # 简单HTTP服务器
└── package.json        # 项目配置
```