// 邮箱认证系统
class AuthSystem {
    constructor() {
        this.users = JSON.parse(localStorage.getItem('users')) || [];
        this.currentUser = JSON.parse(localStorage.getItem('currentUser')) || null;
        this.init();
    }

    init() {
        // 绑定事件监听器
        this.bindEvents();
        
        // 检查用户登录状态
        this.checkAuthStatus();
    }

    bindEvents() {
        // 获取DOM元素
        const loginBtn = document.getElementById('loginBtn');
        const registerBtn = document.getElementById('registerBtn');
        const loginModal = document.getElementById('loginModal');
        const registerModal = document.getElementById('registerModal');
        const showRegisterLink = document.getElementById('showRegister');
        const showLoginLink = document.getElementById('showLogin');
        const closeButtons = document.querySelectorAll('.close');
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const joinUsBtn = document.getElementById('joinUsBtn');

        // 绑定按钮点击事件
        if (loginBtn) loginBtn.addEventListener('click', () => this.openModal('login'));
        if (registerBtn) registerBtn.addEventListener('click', () => this.openModal('register'));
        if (joinUsBtn) joinUsBtn.addEventListener('click', () => this.openModal('register'));
        
        // 绑定模态框切换事件
        if (showRegisterLink) showRegisterLink.addEventListener('click', (e) => {
            e.preventDefault();
            this.closeModal('login');
            this.openModal('register');
        });
        
        if (showLoginLink) showLoginLink.addEventListener('click', (e) => {
            e.preventDefault();
            this.closeModal('register');
            this.openModal('login');
        });
        
        // 绑定关闭按钮事件
        closeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const modal = button.closest('.modal');
                if (modal) this.closeModal(modal.id === 'loginModal' ? 'login' : 'register');
            });
        });
        
        // 点击模态框外部关闭
        window.addEventListener('click', (e) => {
            if (e.target === loginModal) this.closeModal('login');
            if (e.target === registerModal) this.closeModal('register');
        });
        
        // 绑定表单提交事件
        if (loginForm) loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        if (registerForm) registerForm.addEventListener('submit', (e) => this.handleRegister(e));
    }

    openModal(type) {
        if (type === 'login') {
            document.getElementById('loginModal').style.display = 'block';
        } else if (type === 'register') {
            document.getElementById('registerModal').style.display = 'block';
        }
    }

    closeModal(type) {
        if (type === 'login') {
            document.getElementById('loginModal').style.display = 'none';
        } else if (type === 'register') {
            document.getElementById('registerModal').style.display = 'none';
        }
    }

    // 验证邮箱格式
    validateEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    // 验证密码强度
    validatePassword(password) {
        // 至少8位，包含字母和数字
        const passwordRegex = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{8,}$/;
        return passwordRegex.test(password);
    }

    // 用户注册
    handleRegister(e) {
        e.preventDefault();
        
        const name = document.getElementById('registerName').value;
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('registerConfirmPassword').value;
        
        // 验证输入
        if (!name || !email || !password || !confirmPassword) {
            alert('请填写所有字段');
            return;
        }
        
        if (!this.validateEmail(email)) {
            alert('请输入有效的邮箱地址');
            return;
        }
        
        if (!this.validatePassword(password)) {
            alert('密码至少8位，且包含字母和数字');
            return;
        }
        
        if (password !== confirmPassword) {
            alert('两次输入的密码不一致');
            return;
        }
        
        // 检查邮箱是否已存在
        if (this.users.some(user => user.email === email)) {
            alert('该邮箱已被注册');
            return;
        }
        
        // 创建新用户
        const newUser = {
            id: Date.now(),
            name: name,
            email: email,
            password: this.hashPassword(password), // 简单哈希处理
            createdAt: new Date().toISOString()
        };
        
        this.users.push(newUser);
        localStorage.setItem('users', JSON.stringify(this.users));
        
        alert('注册成功！');
        this.closeModal('register');
        
        // 自动登录
        this.login(email, password);
    }

    // 用户登录
    handleLogin(e) {
        e.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        
        if (!email || !password) {
            alert('请填写所有字段');
            return;
        }
        
        if (!this.validateEmail(email)) {
            alert('请输入有效的邮箱地址');
            return;
        }
        
        this.login(email, password);
    }

    // 执行登录逻辑
    login(email, password) {
        const user = this.users.find(u => u.email === email);
        
        if (!user) {
            alert('用户不存在');
            return;
        }
        
        if (user.password !== this.hashPassword(password)) {
            alert('密码错误');
            return;
        }
        
        // 登录成功
        this.currentUser = {
            id: user.id,
            name: user.name,
            email: user.email
        };
        
        localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
        this.closeModal('login');
        this.updateUIAfterLogin();
        alert(`欢迎回来，${user.name}！`);
    }

    // 简单密码哈希（实际项目中应使用更安全的方法）
    hashPassword(password) {
        // 这里只是一个简单的示例，实际应用中应该使用 bcrypt 等安全的哈希算法
        let hash = 0;
        for (let i = 0; i < password.length; i++) {
            const char = password.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // 转换为32位整数
        }
        return hash.toString();
    }

    // 检查用户登录状态
    checkAuthStatus() {
        if (this.currentUser) {
            this.updateUIAfterLogin();
        }
    }

    // 登出
    logout() {
        this.currentUser = null;
        localStorage.removeItem('currentUser');
        this.updateUIAfterLogout();
    }

    // 登录后更新UI
    updateUIAfterLogin() {
        const authButtons = document.querySelector('.auth-buttons');
        if (authButtons) {
            authButtons.innerHTML = `
                <span>欢迎，${this.currentUser.name}</span>
                <button id="logoutBtn">退出</button>
            `;
            
            document.getElementById('logoutBtn').addEventListener('click', () => {
                this.logout();
            });
        }
    }

    // 登出后更新UI
    updateUIAfterLogout() {
        const authButtons = document.querySelector('.auth-buttons');
        if (authButtons) {
            authButtons.innerHTML = `
                <button id="loginBtn">登录</button>
                <button id="registerBtn">注册</button>
            `;
            
            // 重新绑定事件
            document.getElementById('loginBtn').addEventListener('click', () => this.openModal('login'));
            document.getElementById('registerBtn').addEventListener('click', () => this.openModal('register'));
        }
    }
}

// 页面加载完成后初始化认证系统
document.addEventListener('DOMContentLoaded', () => {
    window.authSystem = new AuthSystem();
});