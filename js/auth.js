// 閭璁よ瘉绯荤粺
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
        const showForgotPasswordLink = document.getElementById('showForgotPassword');
        const showLoginFromForgotLink = document.getElementById('showLoginFromForgot');
        const showForgotFromResetLink = document.getElementById('showForgotFromReset');
        const closeButtons = document.querySelectorAll('.close');
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const forgotPasswordForm = document.getElementById('forgotPasswordForm');
        const resetPasswordForm = document.getElementById('resetPasswordForm');
        const joinUsBtn = document.getElementById('joinUsBtn');

        // 绑定按钮点击事件
        if (loginBtn) loginBtn.addEventListener('click', () => this.openModal('login'));
        if (registerBtn) registerBtn.addEventListener('click', () => this.openModal('register'));
        if (joinUsBtn) joinUsBtn.addEventListener('click', () => this.openModal('register'));
        
        // 缁戝畾妯℃€佹鍒囨崲浜嬩欢
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
        
        if (showForgotPasswordLink) showForgotPasswordLink.addEventListener('click', (e) => {
            e.preventDefault();
            this.closeModal('login');
            this.openModal('forgotPassword');
        });
        
        if (showLoginFromForgotLink) showLoginFromForgotLink.addEventListener('click', (e) => {
            e.preventDefault();
            this.closeModal('forgotPassword');
            this.openModal('login');
        });
        
        if (showForgotFromResetLink) showForgotFromResetLink.addEventListener('click', (e) => {
            e.preventDefault();
            const email = document.getElementById('resetPasswordEmail').value;
            if (email) {
                document.getElementById('forgotPasswordEmail').value = email;
            }
            this.closeModal('resetPassword');
            this.openModal('forgotPassword');
        });
        
        // 绑定关闭按钮事件
        closeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const modal = button.closest('.modal');
                if (modal) {
                    if (modal.id === 'loginModal') this.closeModal('login');
                    else if (modal.id === 'registerModal') this.closeModal('register');
                    else if (modal.id === 'forgotPasswordModal') this.closeModal('forgotPassword');
                    else if (modal.id === 'resetPasswordModal') this.closeModal('resetPassword');
                }
            });
        });
        
        // 鐐瑰嚮妯℃€佹澶栭儴鍏抽棴
        const forgotPasswordModal = document.getElementById('forgotPasswordModal');
        const resetPasswordModal = document.getElementById('resetPasswordModal');
        window.addEventListener('click', (e) => {
            if (e.target === loginModal) this.closeModal('login');
            if (e.target === registerModal) this.closeModal('register');
            if (e.target === forgotPasswordModal) this.closeModal('forgotPassword');
            if (e.target === resetPasswordModal) this.closeModal('resetPassword');
        });
        
        // 绑定表单提交事件
        if (loginForm) loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        if (registerForm) registerForm.addEventListener('submit', (e) => this.handleRegister(e));
        if (forgotPasswordForm) forgotPasswordForm.addEventListener('submit', (e) => this.handleForgotPassword(e));
        if (resetPasswordForm) resetPasswordForm.addEventListener('submit', (e) => this.handleResetPassword(e));
    }

    openModal(type) {
        if (type === 'login') {
            document.getElementById('loginModal').style.display = 'block';
        } else if (type === 'register') {
            document.getElementById('registerModal').style.display = 'block';
        } else if (type === 'forgotPassword') {
            document.getElementById('forgotPasswordModal').style.display = 'block';
        } else if (type === 'resetPassword') {
            document.getElementById('resetPasswordModal').style.display = 'block';
        }
    }

    closeModal(type) {
        if (type === 'login') {
            document.getElementById('loginModal').style.display = 'none';
        } else if (type === 'register') {
            document.getElementById('registerModal').style.display = 'none';
        } else if (type === 'forgotPassword') {
            document.getElementById('forgotPasswordModal').style.display = 'none';
        } else if (type === 'resetPassword') {
            document.getElementById('resetPasswordModal').style.display = 'none';
        }
    }

    // 楠岃瘉閭鏍煎紡
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
        
        // 楠岃瘉杈撳叆
        if (!name || !email || !password || !confirmPassword) {
            alert('请填写所有字段');
            return;
        }
        
        if (!this.validateEmail(email)) {
            alert('请输入有效的邮箱名或密码');
            return;
        }
        
        if (!this.validatePassword(password)) {
            alert('请输入有效的邮箱名或密码');
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
            if (data.email_sent) {
                alert('注册成功！\n\n我们已向您的邮箱发送了一封验证邮件。\n请检查您的邮箱并点击验证链接来激活您的账户。\n\n验证后您才能登录。');
            } else {
                alert('注册成功！\n\n注意：验证邮件发送失败。\n请联系管理员或稍后重试。');
            }
            this.closeModal('register');
            // Clear form
            document.getElementById('registerForm').reset();
            // Don't auto-login - user needs to verify email first

        })
        .catch(error => {
            alert(error.error || '娉ㄥ唽澶辫触');
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
            alert('请输入有效的邮箱名或密码');
            return;
        }
        
        this.login(email, password);
    }

    // 鎵ц鐧诲綍閫昏緫
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
            if (!user.is_verified && !user.is_admin) {
                alert('您已登录，但邮箱尚未验证。\n\n您暂时不能上传猫咪信息或进行某些操作。\n请前往邮箱完成验证，或联系管理员。');
            }

        })
        .catch(error => {
            alert(error.error || '鐧诲綍澶辫触');
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
if (uploadBtn) {
            if (user.is_verified || user.is_admin) {
                uploadBtn.style.display = 'inline-block';
            } else {
                uploadBtn.style.display = 'none';
            }
        }

        
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
            <a href="/profile" style="margin: 0 10px; color: #4CAF50; text-decoration: none;">个人资料</a>
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

    // 忘记密码
    handleForgotPassword(e) {
        e.preventDefault();
        
        const email = document.getElementById('forgotPasswordEmail').value.trim();
        const statusDiv = document.getElementById('forgotPasswordStatus');
        
        if (!email) {
            statusDiv.style.display = 'block';
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '请输入邮箱地址';
            return;
        }
        
        if (!this.validateEmail(email)) {
            statusDiv.style.display = 'block';
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '请输入有效的邮箱地址';
            return;
        }
        
        statusDiv.style.display = 'block';
        statusDiv.style.backgroundColor = '#d1ecf1';
        statusDiv.style.color = '#0c5460';
        statusDiv.textContent = '正在发送验证码...';
        
        fetch('/api/user/forgot-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email: email })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message && data.email_sent) {
                statusDiv.style.backgroundColor = '#d4edda';
                statusDiv.style.color = '#155724';
                statusDiv.textContent = '验证码已发送到您的邮箱，请查收。';
                // Store email and show reset password modal
                document.getElementById('resetPasswordEmail').value = email;
                setTimeout(() => {
                    this.closeModal('forgotPassword');
                    this.openModal('resetPassword');
                }, 1500);
            } else {
                statusDiv.style.backgroundColor = '#f8d7da';
                statusDiv.style.color = '#721c24';
                statusDiv.textContent = data.error || '发送失败，请稍后重试';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '发送失败，请稍后重试';
        });
    }

    // 重置密码
    handleResetPassword(e) {
        e.preventDefault();
        
        const email = document.getElementById('resetPasswordEmail').value;
        const code = document.getElementById('resetPasswordCode').value.trim();
        const newPassword = document.getElementById('resetPasswordNew').value;
        const confirmPassword = document.getElementById('resetPasswordConfirm').value;
        const statusDiv = document.getElementById('resetPasswordStatus');
        
        statusDiv.style.display = 'none';
        
        if (!code || code.length !== 6) {
            statusDiv.style.display = 'block';
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '请输入6位验证码';
            return;
        }
        
        if (!newPassword || !confirmPassword) {
            statusDiv.style.display = 'block';
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '请填写所有字段';
            return;
        }
        
        if (newPassword !== confirmPassword) {
            statusDiv.style.display = 'block';
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '两次输入的密码不一致';
            return;
        }
        
        if (!this.validatePassword(newPassword)) {
            statusDiv.style.display = 'block';
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '密码至少8位，且包含字母和数字';
            return;
        }
        
        statusDiv.style.display = 'block';
        statusDiv.style.backgroundColor = '#d1ecf1';
        statusDiv.style.color = '#0c5460';
        statusDiv.textContent = '正在重置密码...';
        
        fetch('/api/user/reset-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                code: code,
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                statusDiv.style.backgroundColor = '#d4edda';
                statusDiv.style.color = '#155724';
                statusDiv.textContent = data.message;
                // Clear form and redirect to login
                setTimeout(() => {
                    document.getElementById('resetPasswordForm').reset();
                    this.closeModal('resetPassword');
                    this.openModal('login');
                    alert('密码重置成功！请使用新密码登录。');
                }, 1500);
            } else {
                statusDiv.style.backgroundColor = '#f8d7da';
                statusDiv.style.color = '#721c24';
                statusDiv.textContent = data.error || '密码重置失败';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            statusDiv.style.backgroundColor = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.textContent = '密码重置失败，请稍后重试';
        });
    }
}

// 页面加载完成后初始化认证系统
document.addEventListener('DOMContentLoaded', () => {
    window.authSystem = new AuthSystem();
});
