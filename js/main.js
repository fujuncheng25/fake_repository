// 主应用程序逻辑
document.addEventListener('DOMContentLoaded', function() {
    // 初始化应用
    initializeApp();
    
    // 检查用户认证状态
    checkAuthStatus();
    
    // 加载猫咪信息
    loadCatData();
});

function initializeApp() {
    console.log('流浪猫公益项目应用已启动');
    
    // 绑定页面滚动事件
    window.addEventListener('scroll', handleScroll);
    
    // 绑定导航链接点击事件
    bindNavigationEvents();
    
    // 绑定认证相关按钮事件
    bindAuthEvents();
}

function handleScroll() {
    // 可以在这里添加滚动相关的功能
}

function bindNavigationEvents() {
    const navLinks = document.querySelectorAll('nav a');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            scrollToSection(targetId);
        });
    });
}

function bindAuthEvents() {
    // 绑定新按钮事件
    document.getElementById('uploadCatBtn').addEventListener('click', function() {
        window.location.href = '/upload';
    });
    
    document.getElementById('adminBtn').addEventListener('click', function() {
        window.location.href = '/admin';
    });
    
    // 绑定原来的登录/注册按钮事件
    if (window.authSystem) {
        document.getElementById('loginBtn').addEventListener('click', () => window.authSystem.openModal('login'));
        document.getElementById('registerBtn').addEventListener('click', () => window.authSystem.openModal('register'));
    }
}

function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

// 检查用户认证状态
function checkAuthStatus() {
    fetch('/api/current_user')
        .then(response => response.json())
        .then(user => {
            if (user.id) {
                // 用户已登录
                updateUIAfterLogin(user);
                
                // 显示上传按钮
                document.getElementById('uploadCatBtn').style.display = 'inline-block';
                
                // 如果是管理员，显示管理按钮
                if (user.is_admin) {
                    document.getElementById('adminBtn').style.display = 'inline-block';
                }
            } else {
                // 用户未登录
                updateUIAfterLogout();
            }
        })
        .catch(error => {
            console.error('Error checking auth status:', error);
            updateUIAfterLogout();
        });
}

// 登录后更新UI
function updateUIAfterLogin(user) {
    console.log('updateUIAfterLogin called with user:', user);
    const authButtons = document.querySelector('.auth-buttons');
    console.log('authButtons:', authButtons);
    if (authButtons) {
        // Hide login/register buttons
        const loginBtn = document.getElementById('loginBtn');
        const registerBtn = document.getElementById('registerBtn');
        if (loginBtn) {
            loginBtn.style.display = 'none';
            console.log('Hid login button');
        }
        if (registerBtn) {
            registerBtn.style.display = 'none';
            console.log('Hid register button');
        }
        
        // Show upload button
        const uploadBtn = document.getElementById('uploadCatBtn');
        if (uploadBtn) {
            uploadBtn.style.display = 'inline-block';
            console.log('Showed upload button');
        } else {
            console.log('Upload button not found');
        }
        
        // If admin, show admin button
        if (user.is_admin) {
            const adminBtn = document.getElementById('adminBtn');
            if (adminBtn) {
                adminBtn.style.display = 'inline-block';
                console.log('Showed admin button');
            } else {
                console.log('Admin button not found');
            }
        }
        
        // Add user welcome message and logout button if not already present
        let userInfo = document.querySelector('.user-info');
        if (!userInfo) {
            userInfo = document.createElement('div');
            userInfo.className = 'user-info';
            userInfo.innerHTML = `
                <span>欢迎，${user.name}</span>
                <button id="logoutBtn">退出</button>
            `;
            authButtons.appendChild(userInfo);
            
            // Bind logout event
            document.getElementById('logoutBtn').addEventListener('click', function() {
                logout();
            });
            console.log('Added user info and logout button');
        }
    } else {
        console.log('authButtons not found');
    }
}

// 登出后更新UI
function updateUIAfterLogout() {
    const authButtons = document.querySelector('.auth-buttons');
    if (authButtons) {
        // Hide upload and admin buttons
        const uploadBtn = document.getElementById('uploadCatBtn');
        const adminBtn = document.getElementById('adminBtn');
        if (uploadBtn) uploadBtn.style.display = 'none';
        if (adminBtn) adminBtn.style.display = 'none';
        
        // Show login/register buttons
        const loginBtn = document.getElementById('loginBtn');
        const registerBtn = document.getElementById('registerBtn');
        if (loginBtn) loginBtn.style.display = 'inline-block';
        if (registerBtn) registerBtn.style.display = 'inline-block';
        
        // Remove user info if present
        const userInfo = document.querySelector('.user-info');
        if (userInfo) userInfo.remove();
        
        // Re-bind events
        bindAuthEvents();
    }
}

// 登出功能
function logout() {
    fetch('/api/logout', {
        method: 'POST'
    })
    .then(() => {
        updateUIAfterLogout();
        // 重新加载页面以刷新状态
        window.location.reload();
    })
    .catch(error => console.error('Error:', error));
}

// 模拟猫咪数据
const catData = [
    {
        id: 1,
        name: "小花",
        age: "2岁",
        gender: "雌性",
        description: "性格温顺，喜欢与人亲近",
        image: "assets/cat1.jpg"
    },
    {
        id: 2,
        name: "小黑",
        age: "1.5岁",
        gender: "雄性",
        description: "活泼好动，好奇心强",
        image: "assets/cat2.jpg"
    },
    {
        id: 3,
        name: "小白",
        age: "3岁",
        gender: "雌性",
        description: "优雅安静，适合家庭饲养",
        image: "assets/cat3.jpg"
    },
    {
        id: 4,
        name: "小橘",
        age: "1岁",
        gender: "雄性",
        description: "贪吃可爱，非常亲人",
        image: "assets/cat4.jpg"
    }
];

// 加载猫咪信息
function loadCatData() {
    fetch('/api/cats')
        .then(response => response.json())
        .then(cats => {
            const catList = document.querySelector('.cat-list');
            if (!catList) return;
            
            catList.innerHTML = '';
            
            cats.forEach(cat => {
                const catCard = createCatCard(cat);
                catList.appendChild(catCard);
            });
        })
        .catch(error => {
            console.error('Error loading cats:', error);
            // Fallback to hardcoded data if API fails
            fallbackToHardcodedData();
        });
}

// Fallback to hardcoded data if API fails
function fallbackToHardcodedData() {
    const catList = document.querySelector('.cat-list');
    if (!catList) return;
    
    catList.innerHTML = '';
    
    const hardcodedCats = [
        {
            id: 1,
            name: "小花",
            age: "2岁",
            gender: "雌性",
            description: "性格温顺，喜欢与人亲近",
            image: "assets/cat1.jpg"
        },
        {
            id: 2,
            name: "小黑",
            age: "1.5岁",
            gender: "雄性",
            description: "活泼好动，好奇心强",
            image: "assets/cat2.jpg"
        },
        {
            id: 3,
            name: "小白",
            age: "3岁",
            gender: "雌性",
            description: "优雅安静，适合家庭饲养",
            image: "assets/cat3.jpg"
        },
        {
            id: 4,
            name: "小橘",
            age: "1岁",
            gender: "雄性",
            description: "贪吃可爱，非常亲人",
            image: "assets/cat4.jpg"
        }
    ];
    
    hardcodedCats.forEach(cat => {
        const catCard = createCatCard(cat);
        catList.appendChild(catCard);
    });
}

// 创建猫咪卡片
function createCatCard(cat) {
    const card = document.createElement('div');
    card.className = 'cat-card';
    card.innerHTML = `
        <div class="image-placeholder" style="background-color: #f0f0f0; height: 200px; display: flex; align-items: center; justify-content: center;">
            <span>猫咪图片</span>
        </div>
        <div class="info">
            <h3>${cat.name}</h3>
            <p><strong>年龄:</strong> ${cat.age}</p>
            <p><strong>性别:</strong> ${cat.gender}</p>
            <p>${cat.description}</p>
            <button class="adopt-btn" data-cat-id="${cat.id}">我要领养</button>
        </div>
    `;
    
    // 绑定领养按钮事件
    const adoptBtn = card.querySelector('.adopt-btn');
    adoptBtn.addEventListener('click', function() {
        handleAdoptClick(cat.id);
    });
    
    return card;
}

// 处理领养点击事件
function handleAdoptClick(catId) {
    // Check if user is logged in
    fetch('/api/current_user')
        .then(response => response.json())
        .then(user => {
            if (!user.id) {
                alert('请先登录后再申请领养！');
                // Show login modal
                if (window.authSystem) {
                    window.authSystem.openModal('login');
                }
                return;
            }
            
            alert(`感谢您的爱心！您已申请领养猫咪（ID: ${catId}）。我们的工作人员会尽快与您联系。`);
        })
        .catch(error => {
            console.error('Error:', error);
            alert('请先登录后再申请领养！');
        });
}

// 模拟加载更多功能
function loadMoreCats() {
    console.log('加载更多猫咪信息...');
    // 在实际应用中，这里会从服务器获取更多数据
}