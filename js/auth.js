// 閭璁よ瘉绯荤粺
class AuthSystem {
    constructor() {
        this.init();
    }

    init() {
        // 缁戝畾浜嬩欢鐩戝惉鍣?
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
        // 鑾峰彇DOM鍏冪礌
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

        // 缁戝畾鎸夐挳鐐瑰嚮浜嬩欢
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
        
        // 缁戝畾鍏抽棴鎸夐挳浜嬩欢
        closeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const modal = button.closest('.modal');
                if (modal) this.closeModal(modal.id === 'loginModal' ? 'login' : 'register');
            });
        });
        
        // 鐐瑰嚮妯℃€佹澶栭儴鍏抽棴
        window.addEventListener('click', (e) => {
            if (e.target === loginModal) this.closeModal('login');
            if (e.target === registerModal) this.closeModal('register');
        });
        
        // 缁戝畾琛ㄥ崟鎻愪氦浜嬩欢
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

    // 楠岃瘉閭鏍煎紡
    validateEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    // 楠岃瘉瀵嗙爜寮哄害
    validatePassword(password) {
        // 鑷冲皯8浣嶏紝鍖呭惈瀛楁瘝鍜屾暟瀛?
        const passwordRegex = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{8,}$/;
        return passwordRegex.test(password);
    }

    // 鐢ㄦ埛娉ㄥ唽
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
            alert('璇疯緭鍏ユ湁鏁堢殑閭鍦板潃');
            return;
        }
        
        if (!this.validatePassword(password)) {
            alert('瀵嗙爜鑷冲皯8浣嶏紝涓斿寘鍚瓧姣嶅拰鏁板瓧');
            return;
        }
        
        if (password !== confirmPassword) {
            alert('两次输入的密码不一致');
            return;
        }
        
        // 璋冪敤API娉ㄥ唽鐢ㄦ埛
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

    // 鐢ㄦ埛鐧诲綍
    handleLogin(e) {
        e.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        
        if (!email || !password) {
            alert('请填写所有字段');
            return;
        }
        
        if (!this.validateEmail(email)) {
            alert('璇疯緭鍏ユ湁鏁堢殑閭鍦板潃');
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
            // 鐧诲綍鎴愬姛锛屾洿鏂癠I
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

    // 鏇存柊UI鏄剧ず鐧诲綍鐘舵€?
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
        messagesBtn.textContent = '娑堟伅涓績';
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
            <span>娆㈣繋, ${user.name}</span>
            <button id="logoutBtn">閫€鍑?/button>
        `;
        headerContainer.appendChild(userInfo);
        
        // Add logout event
        document.getElementById('logoutBtn').addEventListener('click', () => this.logout());
    }

    // 鐢ㄦ埛閫€鍑?
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

// 椤甸潰鍔犺浇瀹屾垚鍚庡垵濮嬪寲璁よ瘉绯荤粺
document.addEventListener('DOMContentLoaded', () => {
    window.authSystem = new AuthSystem();
});
