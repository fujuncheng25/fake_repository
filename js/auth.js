// 邮箱认证系统
class AuthSystem {
    constructor() {
        this.init();
    }

    init() {
        // 绑定事件监听器
        this.bindEvents();
        // Check current user status
        this.checkCurrentUser();
    }

    checkCurrentUser() {
        fetch('/api/current_user')
            .then(response => response.json())
            .then(user => {
                if (user.id) {
                    // User is logged in
                    this.updateUIAfterLogin(user);
                } else {
                    // User is not logged in, make sure buttons are in correct state
                    const uploadBtn = document.getElementById('uploadCatBtn');
                    const adminBtn = document.getElementById('adminBtn');
                    if (uploadBtn) uploadBtn.style.display = 'none';
                    if (adminBtn) adminBtn.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error checking current user:', error);
            });
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
        
        // 调用API注册用户
        fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                email: email,
                password: password,
                confirmPassword: confirmPassword
            })
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                return response.json().then(err => Promise.reject(err));
            }
        })
        .then(data => {
            alert('注册成功！');
            this.closeModal('register');
            // 自动登录
            this.login(email, password);
        })
        .catch(error => {
            alert(error.error || '注册失败');
        });
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
        fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                return response.json().then(err => Promise.reject(err));
            }
        })
        .then(user => {
            // 登录成功，更新UI
            this.closeModal('login');
            // Update the UI to show the user is logged in
            this.updateUIAfterLogin(user);
        })
        .catch(error => {
            alert(error.error || '登录失败');
        });
    }

    // 更新UI显示登录状态
    updateUIAfterLogin(user) {
        // Hide login/register buttons
        const loginBtn = document.getElementById('loginBtn');
        const registerBtn = document.getElementById('registerBtn');
        const joinUsBtn = document.getElementById('joinUsBtn');
        
        if (loginBtn) loginBtn.style.display = 'none';
        if (registerBtn) registerBtn.style.display = 'none';
        if (joinUsBtn) joinUsBtn.style.display = 'none';
        
        // Show upload button
        const uploadBtn = document.getElementById('uploadCatBtn');
        if (uploadBtn) uploadBtn.style.display = 'inline-block';
        
        // Show messages button
        const messagesBtn = document.createElement('button');
        messagesBtn.id = 'messagesBtn';
        messagesBtn.textContent = '消息中心';
        messagesBtn.style.marginLeft = '10px';
        messagesBtn.addEventListener('click', () => {
            window.location.href = '/messages';
        });
        uploadBtn.parentNode.insertBefore(messagesBtn, uploadBtn.nextSibling);
        
        // If admin, show admin button
        if (user.is_admin) {
            const adminBtn = document.getElementById('adminBtn');
            if (adminBtn) adminBtn.style.display = 'inline-block';
        }
        
        // Show user info and logout button
        const headerContainer = document.querySelector('header .container');
        // Remove existing user info if present
        const existingUserInfo = document.querySelector('.user-info');
        if (existingUserInfo) {
            existingUserInfo.remove();
        }
        
        const userInfo = document.createElement('div');
        userInfo.className = 'user-info';
        userInfo.innerHTML = `
            <span>欢迎, ${user.name}</span>
            <button id="logoutBtn">退出</button>
        `;
        headerContainer.appendChild(userInfo);
        
        // Add logout event
        document.getElementById('logoutBtn').addEventListener('click', () => this.logout());
    }

    // 用户退出
    logout() {
        fetch('/api/logout', {
            method: 'POST'
        })
        .then(() => {
            // Reset UI to show login/register buttons
            const loginBtn = document.getElementById('loginBtn');
            const registerBtn = document.getElementById('registerBtn');
            
            if (loginBtn) loginBtn.style.display = 'inline-block';
            if (registerBtn) registerBtn.style.display = 'inline-block';
            
            // Hide upload and admin buttons
            const uploadBtn = document.getElementById('uploadCatBtn');
            const adminBtn = document.getElementById('adminBtn');
            const messagesBtn = document.getElementById('messagesBtn');
            if (uploadBtn) uploadBtn.style.display = 'none';
            if (adminBtn) adminBtn.style.display = 'none';
            if (messagesBtn) messagesBtn.remove();
            
            // Remove user info
            const userInfo = document.querySelector('.user-info');
            if (userInfo) userInfo.remove();
        });
    }
}

// 页面加载完成后初始化认证系统
document.addEventListener('DOMContentLoaded', () => {
    window.authSystem = new AuthSystem();
});